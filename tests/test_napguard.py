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


async def test_dark_run_never_wakes_the_human(monkeypatch):
    """ONSEN_DARK=1: the dispatched task is the only human input, so Nap Guard gates, answers and reports
    without ever mentioning the human."""
    monkeypatch.setenv("ONSEN_DARK", "1")
    ng, tools = NapGuardAdapter(), FakeAgentTools(participants=CREW)
    await deliver(ng, "@nap-guard [seal] stage=1 sha256=" + "c" * 64, "Examiner", tools)

    # an approval without the checker's claim for the stage doesn't open the gate
    await deliver(ng, "@b @nap-guard [exam] stage=1 verdict=PASS passed=9/9 satisfaction=100% commit=abc1234", "Examiner", tools)
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=abc1234 APPROVED claimed=none", "Reviewer", tools)
    assert not any(m["content"].startswith("[gate] stage=1 ACCEPTED") for m in tools.messages_sent)

    # with the claim, the stage is accepted, and the Examiner is asked to publish the exam
    await deliver(ng, "@b @nap-guard [review] stage=1 commit=abc1234 APPROVED claimed=1 checks pass", "Reviewer", tools)
    gate = last(tools)
    assert gate.startswith("[gate] stage=1 ACCEPTED") and "Examiner: publish" in gate

    # a question for the human is answered by Nap Guard, not escalated
    await deliver(ng, "@nap-guard [blocking-question] which time zone should timestamps use?", "Builder", tools)
    assert last(tools).startswith("[decide]")

    # a stall is a notice to the Architect; nobody is removed or woken
    for sat in ("50%", "50%", "40%"):
        await deliver(ng, f"@b @nap-guard [exam] stage=2 verdict=FAIL satisfaction={sat} commit=def5678", "Examiner", tools)
    assert last(tools).startswith("[chill] stage=2")
    assert not tools.participants_removed

    # the Architect's final report ends the run with a receipt
    await deliver(ng, "@nap-guard [report] stages accepted: 1; stage 2 blocked on history ordering", "Architect", tools)
    receipt = last(tools)
    assert receipt.startswith("[receipt]") and "wake-ups: 0" in receipt
    assert all("id-human" not in str(m["mentions"]) for m in tools.messages_sent)
