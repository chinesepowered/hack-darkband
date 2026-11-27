"""bin/band, the room linter in front of the real `band` CLI on the seats' PATH."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def send(tmp_path: Path, seat: str, body: str, room_messages: list | None = None) -> subprocess.CompletedProcess:
    """Send through the linter to a fake band, whose `room messages` prints `room_messages` (or nothing useful)."""
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    (tmp_path / "messages.json").write_text(json.dumps({"messages": room_messages}) if room_messages is not None
                                            else "not json")
    (fake / "band").write_text(f'#!/bin/sh\nif [ "$2" = messages ]; then cat {tmp_path / "messages.json"}; '
                               'else echo sent; fi\n')
    (fake / "band").chmod(0o755)
    env = dict(os.environ, PATH=f"{ROOT / 'bin'}:{fake}:/usr/bin:/bin", ONSEN_HOME=str(tmp_path / "home"),
               GIT_AUTHOR_NAME=seat)
    return subprocess.run([str(ROOT / "bin" / "band"), "send", "ROOM", body], capture_output=True, text=True, env=env)


def test_protocol_messages_pass_and_chatter_is_refused(tmp_path):
    assert send(tmp_path, "Builder", "@o/examiner @o/reviewer [ready] stage=1 commit=abc1234 ok").stdout == "sent\n"
    r = send(tmp_path, "Architect", "@o/nap-guard status stage=1?")
    assert r.returncode == 2 and "protocol tag" in r.stderr


def test_only_the_owner_posts_a_tag(tmp_path):
    r = send(tmp_path, "Examiner", "@o/builder @o/reviewer [task] stage=1 part=1/4 the spec")
    assert r.returncode == 2 and "Only the Architect posts [task]" in r.stderr
    assert send(tmp_path, "Architect", "@o/builder [task] stage=1 part=1/4 the spec").returncode == 0
    assert send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [exam] stage=1 passed=1/1").returncode == 2


def test_a_commit_is_handed_off_and_judged_once(tmp_path):
    assert send(tmp_path, "Builder", "@o/examiner [ready] stage=1 commit=abc1234").returncode == 0
    r = send(tmp_path, "Builder", "@o/examiner [ready] stage=1 commit=abc1234 again")
    assert r.returncode == 2 and "already handed off" in r.stderr
    assert send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [review] stage=1 commit=abc1234 BLOCKED: x").returncode == 0
    assert send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [review] stage=1 commit=abc1234 BLOCKED: y").returncode == 2
    assert send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [review] stage=1 commit=abc1234 APPROVED").returncode == 0


def test_a_verdict_must_carry_what_the_gate_reads(tmp_path):
    r = send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [review] stage=9aeebfd BLOCKED: x")
    assert r.returncode == 2 and "needs stage, commit" in r.stderr
    assert send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [review] stage=1 commit=9aeebfd BLOCKED: x").returncode == 0
    r = send(tmp_path, "Builder", "@o/examiner @o/reviewer [ready] stage=1 everything works")
    assert r.returncode == 2 and "commit" in r.stderr


def test_the_same_exam_result_is_posted_once(tmp_path):
    body = "@o/builder @o/nap-guard [exam] stage=1 verdict=FAIL passed=8/16 satisfaction=50% commit=b391762 exam=x"
    assert send(tmp_path, "Examiner", body).returncode == 0
    assert send(tmp_path, "Examiner", body).returncode == 2
    assert send(tmp_path, "Examiner", body.replace("passed=8/16", "passed=9/15")).returncode == 0  # after a void


def test_a_verdict_is_only_for_a_handed_off_commit(tmp_path):
    review = "@o/builder @o/nap-guard [review] stage=2 commit={c} BLOCKED: x"
    assert send(tmp_path, "Builder", "@o/examiner @o/reviewer [ready] stage=2 commit=abc1234 ok").returncode == 0
    assert send(tmp_path, "Reviewer", review.format(c="abc1234"), room_messages=[]).returncode == 0  # Builder's ledger
    quoted = {"content": "@[[0a1b2c3d-0000-4000-8000-00000000000a]] [nudge] stage=2 handoff=late commit=def5678 post `[ready] stage=2 commit=def5678`"}
    r = send(tmp_path, "Reviewer", review.format(c="def5678"), room_messages=[quoted])
    assert r.returncode == 2 and "No [ready] names commit def5678" in r.stderr
    exam = "@o/builder @o/nap-guard [exam] stage=2 verdict=FAIL passed=1/2 satisfaction=50% commit=def5678 exam=x"
    assert send(tmp_path, "Examiner", exam, room_messages=[quoted]).returncode == 2
    handoff = {"content": "@[[0a1b2c3d-0000-4000-8000-00000000000b]] @[[0a1b2c3d-0000-4000-8000-00000000000c]] [ready] stage=2 commit=def5678 Result: claims stage 2"}
    assert send(tmp_path, "Reviewer", review.format(c="def5678"), room_messages=[quoted, handoff]).returncode == 0
    # a room the linter can't read never blocks a verdict
    assert send(tmp_path, "Examiner", exam.replace("def5678", "0123abc")).returncode == 0


def test_nothing_more_happens_in_an_accepted_stage(tmp_path):
    state = tmp_path / "home" / "state" / "napguard-ROOM.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"stages": {"1": {"accepted": True}, "2": {"accepted": False}}}))
    r = send(tmp_path, "Builder", "@o/examiner @o/reviewer [ready] stage=1 commit=abc1234 late polish")
    assert r.returncode == 2 and "Stage 1 is accepted" in r.stderr and "stage 2" in r.stderr
    r = send(tmp_path, "Reviewer", "@o/builder @o/nap-guard [review] stage=1 commit=abc1234 BLOCKED: x")
    assert r.returncode == 2 and "closed" in r.stderr
    assert send(tmp_path, "Builder", "@o/examiner @o/reviewer [ready] stage=2 commit=abc1234 ok").returncode == 0
