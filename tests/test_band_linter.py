"""bin/band, the room linter in front of the real `band` CLI on the seats' PATH."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def send(tmp_path: Path, seat: str, body: str) -> subprocess.CompletedProcess:
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    (fake / "band").write_text("#!/bin/sh\necho sent\n")
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
