from __future__ import annotations

from band.testing.fake_tools import FakeAgentTools
from conftest import CREW, deliver

from onsen.napguard import NapGuardAdapter


def last(tools):
    return tools.messages_sent[-1]["content"] if tools.messages_sent else ""


async def test_full_run_one_wakeup_then_receipt():
    ng, tools = NapGuardAdapter(), FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [seal] run=r1 spec=capyfinder stages=2 scenarios=16 sha256=" + "a" * 64, "Examiner", tools)
    assert not tools.messages_sent  # silent bookkeeping

    # stage 1: fail, then pass + approval -> gate to Architect
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=FAIL passed=5/8 satisfaction=62% by=Builder", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=8/8 satisfaction=100% by=Builder", "Examiner", tools)
    assert not tools.messages_sent
    await deliver(ng, "@b @nap-guard [review] stage=1 APPROVED clean diff", "Reviewer", tools)
    assert last(tools).startswith("[gate] stage=1 ACCEPTED")
    assert "62%→100%" in last(tools)

    # a low-confidence answer gets batched, not escalated
    await deliver(ng, "@b @nap-guard [answer] for=Builder confidence=low claims=1\nIs Ueno zoo open on Mondays?", "Scout", tools)
    n_before = len(tools.messages_sent)
    assert n_before == 1

    # stage 2 accepted -> the single wake-up, which mentions the human and lists the batched question
    await deliver(ng, "@b @nap-guard [review] stage=2 APPROVED", "Reviewer", tools)
    await deliver(ng, "@b @nap-guard [exam] stage=2 verdict=PASS passed=8/8 satisfaction=100% by=Builder", "Examiner", tools)
    wake = tools.messages_sent[-1]
    assert wake["content"].startswith("[wake] #1 reason=ready-to-ship")
    assert "Ueno" in wake["content"]
    assert "id-human" in str(wake["mentions"])

    # human ships -> tally request -> tallies -> receipt + reveal notice
    await deliver(ng, "@nap-guard ship", "Capy Human", tools, kind="User")
    assert last(tools).startswith("[tally-request]")
    await deliver(ng, "@nap-guard [tally] agent=scout answered=7 escalated=1 docs=3 data=1 failed=0", "Scout", tools)
    await deliver(ng, "@nap-guard [tally] agent=examiner run=r1 rounds=3 curves=1:62%→100%;2:100%", "Examiner", tools)
    receipt = [m["content"] for m in tools.messages_sent if m["content"].startswith("[receipt]")]
    assert receipt, tools.messages_sent
    assert "wake-ups: 1" in receipt[0] and "answered: 7" in receipt[0]
    assert any(m["content"].startswith("reveal") for m in tools.messages_sent)


async def test_thrash_triggers_chill_break_and_removes_looping_agent():
    ng, tools = NapGuardAdapter(), FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [seal] run=r2 stages=3 sha256=x", "Examiner", tools)
    for sat in ("50%", "50%", "40%"):
        await deliver(ng, f"@b @nap-guard [exam] stage=1 verdict=FAIL satisfaction={sat} by=Builder", "Examiner", tools)
    chill = last(tools)
    assert chill.startswith("[chill]") and "reason=thrash" in chill
    assert "Builder out of the room" in chill
    assert tools.participants_removed, "the looping builder should be removed"

    await deliver(ng, "@nap-guard resume", "Capy Human", tools, kind="User")
    assert "resume=true" in last(tools)


async def test_improving_failures_are_not_thrash():
    ng, tools = NapGuardAdapter(), FakeAgentTools(participants=CREW)
    for sat in ("40%", "60%", "80%"):
        await deliver(ng, f"@nap-guard [exam] stage=1 verdict=FAIL satisfaction={sat} by=Builder", "Examiner", tools)
    assert not any(m["content"].startswith("[chill]") for m in tools.messages_sent)


async def test_approval_must_be_for_the_commit_that_passed():
    ng, tools = NapGuardAdapter(), FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [seal] run=r3 stages=2 sha256=x", "Examiner", tools)
    await deliver(ng, "@nap-guard [review] stage=1 commit=aaaa111 APPROVED", "Reviewer", tools)
    await deliver(ng, "@nap-guard [exam] stage=1 verdict=PASS satisfaction=100% by=Builder commit=bbbb222", "Examiner", tools)
    assert "WAITING" in last(tools) and "bbbb222" in last(tools)
    await deliver(ng, "@nap-guard [review] stage=1 commit=bbbb222 APPROVED", "Reviewer", tools)
    assert last(tools).startswith("[gate] stage=1 ACCEPTED")


async def test_block_after_acceptance_reopens_the_stage():
    ng, tools = NapGuardAdapter(), FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [seal] run=r4 stages=2 sha256=x", "Examiner", tools)
    await deliver(ng, "@nap-guard [exam] stage=1 verdict=PASS satisfaction=100% by=Builder", "Examiner", tools)
    await deliver(ng, "@nap-guard [review] stage=1 APPROVED", "Reviewer", tools)
    assert last(tools).startswith("[gate] stage=1 ACCEPTED")
    await deliver(ng, "@nap-guard [review] stage=1 commit=ccc3333 BLOCKED: data mutated to match a test", "Reviewer", tools)
    assert last(tools).startswith("[gate] stage=1 REOPENED")
    await deliver(ng, "@nap-guard [review] stage=1 commit=ddd4444 APPROVED", "Reviewer", tools)
    await deliver(ng, "@nap-guard [exam] stage=1 verdict=PASS satisfaction=100% by=Builder commit=ddd4444", "Examiner", tools)
    assert last(tools).startswith("[gate] stage=1 ACCEPTED")


def dark_guard(claims: dict[str, int | None], unclaimed: set[str] = frozenset()):
    """A Nap Guard whose acceptance checker and REST poster are fakes: `claims` maps commit -> claimed stage when Nap
    Guard runs the checker; the Builder's own checker runs claim every commit's stage except those in `unclaimed`."""
    posted: list[dict] = []
    runs: list[tuple[int, str]] = []

    async def checker(n, commit):
        runs.append((n, commit))
        return {"claimed": claims.get(commit), "passed": 120, "total": 122, "summary": "FAILED test_x"}

    async def poster(room, content, roles):
        posted.append({"content": content, "roles": roles})

    return (NapGuardAdapter(checker=checker, poster=poster, claimed=lambda n, c: c not in unclaimed), posted,
            runs)


async def test_dark_run_never_wakes_the_human(monkeypatch):
    """ONSEN_DARK=1: the dispatched task is the only human input, so Nap Guard gates, answers and reports
    without ever mentioning the human."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({"abc1234": 1})
    tools = FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [seal] stage=1 sha256=" + "c" * 64, "Examiner", tools)

    # exam PASS + approval on the same commit: Nap Guard runs the checker itself, and it claims the stage
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=9/9 satisfaction=100% commit=abc1234", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=abc1234 APPROVED", "Reviewer", tools)
    await ng.settle()
    assert runs == [(1, "abc1234")]
    gate = posted[-1]
    assert gate["content"].startswith("[gate] stage=1 ACCEPTED") and "Examiner: publish" in gate["content"]
    assert "checker=claimed:1" in gate["content"] and gate["roles"] == ["architect", "examiner"]

    # a question for the human is answered by Nap Guard, not escalated
    await deliver(ng, "@nap-guard [blocking-question] which time zone should timestamps use?", "Builder", tools)
    assert last(tools).startswith("[decide]")

    # a stall is a notice to the Architect; nobody is removed or woken
    for i, sat in enumerate(("5/10", "5/10", "4/10")):
        await deliver(ng, f"@b @nap-guard [exam] stage=2 verdict=FAIL passed={sat} commit=def567{i}", "Examiner", tools)
    assert last(tools).startswith("[chill] stage=2 break=1")
    assert not tools.participants_removed

    # the Architect's final report ends the run with a receipt
    await deliver(ng, "@nap-guard [report] stages accepted: 1; stage 2 blocked on history ordering", "Architect", tools)
    receipt = last(tools)
    assert receipt.startswith("[receipt]") and "wake-ups: 0" in receipt and "checker claims it at abc1234" in receipt
    assert all("id-human" not in str(m["mentions"]) for m in tools.messages_sent)


async def test_dark_verdict_comes_from_the_counts_not_the_word(monkeypatch):
    """An Examiner that says FAIL at 25/26 still passes (at least 90%); one that says PASS at 8/10 doesn't."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({"aaa1111": 1, "bbb2222": 1})
    tools = FakeAgentTools(participants=CREW)
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=8/10 satisfaction=80% commit=bbb2222", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=bbb2222 APPROVED", "Reviewer", tools)
    await ng.settle()
    assert not runs and not posted
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=FAIL passed=25/26 satisfaction=96% commit=aaa1111", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=aaa1111 APPROVED", "Reviewer", tools)
    await ng.settle()
    assert runs == [(1, "aaa1111")] and posted[-1]["content"].startswith("[gate] stage=1 ACCEPTED")


async def test_dark_gate_needs_the_checker_to_claim_the_stage(monkeypatch):
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({"ccc3333": None, "ddd4444": 1})
    tools = FakeAgentTools(participants=CREW)
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=10/10 commit=ccc3333", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=ccc3333 APPROVED", "Reviewer", tools)
    await ng.settle()
    assert posted[-1]["content"].startswith("[gate] stage=1 WAITING") and posted[-1]["roles"][0] == "builder"
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=10/10 commit=ddd4444", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=ddd4444 APPROVED", "Reviewer", tools)
    await ng.settle()
    assert posted[-1]["content"].startswith("[gate] stage=1 ACCEPTED commit=ddd4444")


async def test_dark_second_chill_makes_the_exam_advisory_and_third_falls_back_to_the_checker(monkeypatch):
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({"eee5555": 1})
    tools = FakeAgentTools(participants=CREW)
    for c in ("eee1111", "eee2222", "eee3333"):
        await deliver(ng, f"@b @nap-guard [exam] stage=1 verdict=FAIL passed=5/10 commit={c}", "Examiner", tools)
    assert "break=1" in last(tools) and "re-plan" in last(tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=eee5555 APPROVED", "Reviewer", tools)
    for c in ("eee4444", "eee6666", "eee7777"):
        await deliver(ng, f"@b @nap-guard [exam] stage=1 verdict=FAIL passed=5/10 commit={c}", "Examiner", tools)
    assert "break=2" in last(tools) and "one grader is enough" in last(tools)
    await ng.settle()  # the approval already on record is checked right away
    gate = posted[-1]["content"] if posted else ""
    assert gate.startswith("[gate] stage=1 ACCEPTED") and "review=approved" in gate and "carried forward" in gate

    # stage 2: three blocked commits after two breaks -> the third break gates on the checker alone
    ng2, posted2, runs2 = dark_guard({"fff9999": 2})
    tools2 = FakeAgentTools(participants=CREW)
    for c in ("aaa0001", "aaa0002", "aaa0003", "aaa0004", "aaa0005", "aaa0006"):
        await deliver(ng2, f"@b @nap-guard [exam] stage=2 verdict=FAIL passed=5/10 commit={c}", "Examiner", tools2)
    assert "break=2" in last(tools2)
    for c in ("fff7777", "fff8888", "fff9999"):
        await deliver(ng2, f"@b @nap-guard [review] stage=2 commit={c} BLOCKED: city parser", "Reviewer", tools2)
    assert "break=3" in last(tools2) and "review effort is spent" in last(tools2)
    await ng2.settle()
    assert runs2[-1] == (2, "fff9999")
    gate = posted2[-1]["content"]
    assert gate.startswith("[gate] stage=2 ACCEPTED commit=fff9999") and "review=carried" in gate


async def test_dark_repeated_verdicts_on_one_commit_count_once(monkeypatch):
    """A Builder re-posting [ready] for one commit and a Reviewer re-blocking it is one blocked commit, not a stall."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({"abc0001": 1})
    tools = FakeAgentTools(participants=CREW)
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=14/14 commit=abc0001", "Examiner", tools)
    for _ in range(5):
        await deliver(ng, "@b @nap-guard [review] stage=1 commit=abc0001 BLOCKED: greedy city", "Reviewer", tools)
        await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=14/14 commit=abc0001", "Examiner", tools)
    assert not any(m["content"].startswith("[chill]") for m in tools.messages_sent)
    # blocks on two more distinct commits are two in a row: that is a stall
    for c in ("abc0002", "abc0003"):
        await deliver(ng, f"@b @nap-guard [review] stage=1 commit={c} BLOCKED: greedy city", "Reviewer", tools)
    assert last(tools).startswith("[chill] stage=1 break=1 reason=review-thrash")
    # an approval resets the count; the gate then runs the checker on the approved, passed commit
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=14/14 commit=abc0004", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=abc0004 APPROVED", "Reviewer", tools)
    await ng.settle()
    assert runs == [(1, "abc0004")]


async def test_dark_after_two_chill_breaks_a_passing_exam_and_the_checker_accept_the_stage(monkeypatch):
    """Run N: the exam passed at 93% while the Reviewer kept blocking edge cases; after two breaks the exam's pass and
    the checker's claim are enough, and the review findings carry forward."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({"bbb0007": 1})
    tools = FakeAgentTools(participants=CREW)
    for c in ("bbb0001", "bbb0002", "bbb0003", "bbb0004"):  # two blocked commits in a row are a stall
        await deliver(ng, f"@b @nap-guard [exam] stage=1 verdict=PASS passed=14/15 commit={c}", "Examiner", tools)
        await deliver(ng, f"@b @nap-guard [review] stage=1 commit={c} BLOCKED: empty exact search", "Reviewer", tools)
    assert "break=2" in last(tools)
    await ng.settle()
    assert runs and runs[-1] == (1, "bbb0004") and posted[-1]["content"].startswith("[gate] stage=1 WAITING")
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=14/15 commit=bbb0007", "Examiner", tools)
    await ng.settle()
    gate = posted[-1]["content"]
    assert gate.startswith("[gate] stage=1 ACCEPTED commit=bbb0007") and "review=carried" in gate


async def test_a_verdict_with_a_garbled_stage_counts_for_the_open_stage(monkeypatch):
    """Run O's Reviewer wrote `stage=<commit>`; that blocked review still counts, for the stage that is open."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, posted, runs = dark_guard({})
    tools = FakeAgentTools(participants=CREW)
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=FAIL passed=5/10 commit=ccc0001", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=ccc0001 commit=ccc0001 BLOCKED: x", "Reviewer", tools)
    await deliver(ng, "@b @nap-guard [review] stage=ccc0002 BLOCKED: y commit=ccc0002", "Reviewer", tools)
    assert last(tools).startswith("[chill] stage=1 break=1 reason=review-thrash")


async def test_dark_failing_verdicts_on_work_the_checker_doesnt_claim_are_not_a_stall(monkeypatch):
    """Run R's stage 2: two handoffs of a barely started stage were blocked, and that counted as a stall 14 minutes
    in. A stall is graders failing work the checker claims; until then the failures are the work still to do."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    early = {"aaa0001", "aaa0002", "aaa0003", "aaa0004"}
    ng, posted, runs = dark_guard({}, unclaimed=early)
    tools = FakeAgentTools(participants=CREW)
    for c in sorted(early):
        await deliver(ng, f"@b @nap-guard [review] stage=2 commit={c} BLOCKED: no screens yet", "Reviewer", tools)
        await deliver(ng, f"@b @nap-guard [exam] stage=2 verdict=FAIL passed=3/14 commit={c}", "Examiner", tools)
    assert not any(m["content"].startswith("[chill]") for m in tools.messages_sent)
    for c in ("bbb0001", "bbb0002"):  # claimed by the checker, still blocked: that is a stall
        await deliver(ng, f"@b @nap-guard [review] stage=2 commit={c} BLOCKED: edge case", "Reviewer", tools)
    assert last(tools).startswith("[chill] stage=2 break=1 reason=review-thrash")


def test_checker_claimed_reads_the_checker_reports(tmp_path, monkeypatch):
    from onsen.napguard import checker_claimed
    import json
    monkeypatch.setenv("ONSEN_CHECKS_DIR", str(tmp_path))
    for name, claimed, rev in (("stage2-c312718-134428", None, "c3127183892f"), ("stage2-abc1234-140000", 2, "abc12345"),
                               ("stage1-abc1234-130000", 1, "abc12345")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "report.json").write_text(json.dumps({"state": "completed", "claimed_stage": claimed,
                                                                 "revision": rev}))
    assert not checker_claimed(2, "c312718") and checker_claimed(2, "abc1234") and checker_claimed(1, "abc1234")
    assert not checker_claimed(3, "abc1234") and not checker_claimed(2, None)


async def test_dark_a_report_before_the_run_is_over_is_answered_not_receipted(monkeypatch):
    """Run T's Architect reported three minutes in; the receipt ended the run. In a dark run Nap Guard now answers a
    report that comes before the last stage is accepted, or before the open stage's time is spent, with [decide]."""
    import time
    from onsen import napguard
    monkeypatch.setenv("ONSEN_DARK", "1")
    monkeypatch.setattr(napguard, "run_plan", lambda: {"stages": 4, "stage_budget_min": 120,
                                                       "started_at": time.time() - 180})
    ng, posted, runs = dark_guard({})
    tools = FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [report] stage 1 not accepted", "Architect", tools)
    assert last(tools).startswith("[decide] The run isn't over: stage 1 has been open for 3 of its 120 minutes")
    monkeypatch.setattr(napguard, "run_plan", lambda: {"stages": 4, "stage_budget_min": 120,
                                                       "started_at": time.time() - 121 * 60})
    await deliver(ng, "@nap-guard [report] stage 1 not accepted: the budget is spent", "Architect", tools)
    assert last(tools).startswith("[receipt]")
