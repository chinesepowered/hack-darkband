from onsen.quietwatch import late_handoff


def msg(content, at):
    return {"content": content, "inserted_at": at}


def test_a_claimed_commit_left_unhanded_is_late():
    t = 1_800_000_000.0
    texts = [msg("@a @b [task] stage=1 part=1/1 build it", "2027-01-15T08:00:00Z")]
    claimed = [(1, "abc1234", t)]
    assert late_handoff(texts, claimed, t + 200, set(), 300) is None          # not late yet
    assert late_handoff(texts, claimed, t + 301, set(), 300) == (1, "abc1234", t)
    assert late_handoff(texts, claimed, t + 301, {(1, "abc1234")}, 300) is None  # once per commit


def test_a_handoff_of_that_commit_or_a_later_one_counts():
    t = 1_800_000_000.0
    claimed = [(1, "abc1234", t)]
    done = [msg("@e @r [ready] stage=1 commit=abc1234ffff ok", "2027-01-15T08:00:00Z")]
    assert late_handoff(done, claimed, t + 999, set(), 300) is None
    later = [msg("@e @r [ready] stage=1 commit=def5678 newer", "2027-01-15T08:00:00Z")]
    later[0]["inserted_at"] = "2030-01-01T00:00:00Z"  # after the claim
    assert late_handoff(later, claimed, t + 999, set(), 300) is None


def test_an_accepted_stage_needs_no_handoff():
    t = 1_800_000_000.0
    gate = [msg("@a @e [gate] stage=1 ACCEPTED commit=abc1234", "2027-01-15T08:00:00Z")]
    assert late_handoff(gate, [(1, "fff0000", t)], t + 999, set(), 300) is None


def test_a_restarted_watcher_knows_which_commits_it_already_nudged():
    from onsen.quietwatch import already_nudged
    texts = [msg("@b [nudge] stage=1 handoff=late commit=90357c2\n⏰ ...", "2027-01-15T08:00:00Z")]
    assert already_nudged(texts) == {(1, "90357c2")}


def test_a_nudge_quoting_a_ready_is_not_a_handoff():
    t = 1_800_000_000.0
    nudge = [msg("@b [nudge] stage=1 handoff=late commit=aaa0001\npost `[ready] stage=1 commit=aaa0001` now",
                 "2030-01-01T00:00:00Z")]
    assert late_handoff(nudge, [(1, "bbb0002", t)], t + 999, set(), 300) == (1, "bbb0002", t)


def test_an_accepted_stage_is_closed_once():
    from onsen.quietwatch import newly_accepted
    gate = msg("@a @e [gate] stage=1 ACCEPTED commit=6feba80 exam=81% review=carried", "2027-01-15T08:00:00Z")
    assert newly_accepted([gate]) == [1]
    closed = msg("@b [nudge] stage=1 closed\n🔒 Stage 1 is accepted", "2027-01-15T08:01:00Z")
    assert newly_accepted([gate, closed]) == []
    quoting = msg("@b [nudge] stage=2 handoff=late ... after [gate] stage=1 ACCEPTED", "2027-01-15T08:02:00Z")
    assert newly_accepted([quoting]) == []  # only Nap Guard's own gate message counts


def test_a_seat_mid_turn_is_busy_and_a_finished_turn_is_idle():
    """Run R: the room 'went quiet' while the Builder ran a seven-minute check and streamed a long patch, and the
    watcher nudged the Architect for nothing. A seat whose turn has started and not completed is working."""
    from onsen.quietwatch import turn_state

    def ev(t, who, kind, content):
        return {"inserted_at": f"2026-11-27T14:{t}Z", "sender_name": who, "sender_type": "Agent",
                "message_type": kind, "content": content}
    msgs = [
        ev("00:01", "Builder", "task", '{"event":"turn_started"}'),
        ev("00:02", "Builder", "tool_call", '{"name":"bash"}'),
        ev("00:03", "Architect", "task", '{"event":"turn_started"}'),
        ev("00:04", "Architect", "text", "[plan] stage=2"),
        ev("00:05", "Architect", "task", "context 100197/400000 tokens"),
        ev("00:06", "Architect", "task", '{"event":"turn_complete","outcome":"complete"}'),
        ev("00:07", "Nap Guard", "text", "[nudge] quiet=6m"),
        ev("00:08", "Reviewer", "tool_result", '{"name":"git diff"}'),  # its turn_started is older than the window
    ]
    assert turn_state(msgs) == {"Builder": "busy", "Architect": "idle", "Reviewer": "busy"}
    assert turn_state(list(reversed(msgs))) == turn_state(msgs)  # pages come newest first


def test_each_seat_is_last_seen_at_its_own_newest_event():
    from onsen.quietwatch import last_seen
    msgs = [{"inserted_at": "2026-11-27T13:54:31Z", "sender_name": "Builder", "sender_type": "Agent"},
            {"inserted_at": "2026-11-27T14:08:08Z", "sender_name": "Architect", "sender_type": "Agent"},
            {"inserted_at": "2026-11-27T13:50:00Z", "sender_name": "Builder", "sender_type": "Agent"},
            {"inserted_at": "2026-11-27T14:09:00Z", "sender_name": "the human", "sender_type": "User"}]
    seen = last_seen(msgs)
    assert set(seen) == {"Builder", "Architect"} and seen["Architect"] - seen["Builder"] == 13 * 60 + 37



def test_a_handoff_that_quotes_the_gate_accepts_nothing():
    """Run S: the Architect's handoff explained that 'a stage is accepted only when Nap Guard posts `[gate] stage=1
    ACCEPTED`', and the watcher read that as stage 1 being accepted, so a commit the checker claimed went unhanded
    for eleven minutes without a nudge. Only a message that *is* a [gate] (or [nudge]) counts."""
    from onsen.quietwatch import late_handoff, newly_accepted, already_nudged
    task = {"inserted_at": "2026-11-27T14:16:54Z", "content": "@[[0a1b2c3d-0000-4000-8000-00000000000a]] [task] "
            "stage=1 part=4/4 Check with onsen-check; a stage is accepted only when Nap Guard posts `[gate] stage=1 "
            "ACCEPTED`. A late handoff gets `[nudge] stage=1 handoff=late commit=fdf07f5` and a closed stage "
            "`[nudge] stage=1 closed`."}
    claimed = [(1, "fdf07f5", 1000.0)]
    assert late_handoff([task], claimed, 1000.0 + 301, set(), 300) == (1, "fdf07f5", 1000.0)
    assert newly_accepted([task]) == [] and already_nudged([task]) == set()


def test_only_the_receipt_ends_the_watch():
    """A premature [report] is answered by Nap Guard, not receipted, so the watch must keep going (Run T)."""
    from onsen.quietwatch import ends_run
    assert ends_run("@[[0a1b2c3d-0000-4000-8000-00000000000a]] [receipt] 🛁 Onsen dark run complete")
    assert not ends_run("@[[0a1b2c3d-0000-4000-8000-00000000000a]] [report] stage 1 not accepted")
    assert not ends_run("[task] stage=1 part=4/4 finish with your `[report]`; Nap Guard posts its `[receipt]`")
