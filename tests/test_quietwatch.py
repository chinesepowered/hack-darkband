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
