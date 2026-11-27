"""Nap Guard's quiet-room rule, for a dark run.

BAND Desktop starts a seat only when a message mentions it. If a seat ends its turn mid-stage without handing
anything off, nothing would ever wake it again, and in a dark run nobody may step in. So while a run is open,
this watches the room: when no seat is mid-turn and none has done anything (no message, thought or tool call) for
ONSEN_QUIET_MIN minutes (default 6), it posts `[nudge]` as Nap Guard to the Architect and the Builder, at most
ONSEN_MAX_NUDGES times (default 30). A seat mid-turn is working even when the room shows nothing (a long check, a long
answer), so the room isn't idle then; but a turn that shows nothing for ONSEN_STUCK_MIN minutes (default 30, longer
than any capped check) is stuck, and the watcher interrupts it and says so. It exits once the room has a `[report]` or
`[receipt]`.

The late-handoff rule: a seat mid-turn hears nothing, so a Builder that keeps polishing a revision the acceptance
checker already claims leaves the graders idle. When a checker run (in ONSEN_CHECKS_DIR) claims the open stage on a
commit and no `[ready]` for that commit or a later one follows within ONSEN_HANDOFF_MIN minutes (default 5), this
interrupts the Builder's turn (`band runtime interrupt`) and posts `[nudge] handoff=late` to it, once per commit.

The closed-stage rule: once Nap Guard accepts a stage, its folder is final, but a Builder mid-turn keeps editing it and
can't see the next stage's handoff. On each newly accepted stage this interrupts the Builder's turn and posts
`[nudge] stage=N closed`.

    uv run onsen-quiet-watch <room>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

from .common import NAMES, agent_config_path, load_env

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")
MENTIONS = re.compile(r"^(?:\s*@\[\[[0-9a-f-]+\]\]|\s*@[\w./-]+(?: Guard)?)+")


def _ts(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def turn_state(msgs: list[dict]) -> dict[str, str]:
    """Each seat's state from BAND Desktop's turn events: "idle" after a turn completes, "busy" after a turn starts or
    any activity since (a tool call, a result, a message). Status lines (context size, runtime ready) don't count, and
    Nap Guard, which has no turns, isn't a seat here."""
    state: dict[str, str] = {}
    for m in sorted(msgs, key=lambda m: m.get("inserted_at") or ""):
        who = m.get("sender_name") or ""
        if str(m.get("sender_type", "")).lower() != "agent" or who == NAMES["napguard"]:
            continue
        if m.get("message_type") == "task":
            try:
                event = (json.loads(m.get("content") or "") or {}).get("event")
            except (ValueError, AttributeError):
                event = None
            if event == "turn_complete":
                state[who] = "idle"
            elif event == "turn_started":
                state[who] = "busy"
        else:
            state[who] = "busy"
    return state


def interrupt_seat(room: str, seat: str) -> str:
    """Interrupt a seat's active turn in this room: BAND Desktop keeps one host session per room, named after the seat
    and the room, besides a parked default one; the interrupt has to name the room's."""
    session = f"onsen-{seat.lower()}"
    out = subprocess.run(["band", "status", "--session", session], capture_output=True, text=True).stdout
    host = next((ln.split()[0] for ln in out.splitlines() if f"room={room}" in ln), "")
    if not host:
        return "no host session for this room"
    r = subprocess.run(["band", "runtime", "interrupt", "--session", session, "--host-session", host],
                       capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()[:200] or f"interrupted {host}"


def latest(c: httpx.Client, room: str) -> tuple[float, bool, dict[str, str]]:
    """(time of the newest seat activity, whether the run has ended, each seat's turn state)."""
    r = c.get(f"/api/v1/me/chats/{room}/messages", params={"page": 1, "page_size": 50})
    r.raise_for_status()
    body = r.json()
    msgs = body.get("data") or body.get("messages") or []
    newest, ended = 0.0, False
    for m in msgs:
        if str(m.get("sender_type", "")).lower() != "agent":
            continue  # the human's task mentions `[report]` too; only a seat can end the run
        if m.get("inserted_at"):
            newest = max(newest, _ts(m["inserted_at"]))
        if m.get("message_type", "text") == "text" and ends_run(m.get("content") or ""):
            ended = True
    return newest, ended, turn_state(msgs)


READY_RE = re.compile(r"\[ready\]\s+stage=(\d+)\s+commit=([0-9a-f]{7,40})")
ACCEPTED_RE = re.compile(r"\[gate\]\s+stage=(\d+)\s+ACCEPTED")


def claims(checks_dir: Path, since: float) -> list[tuple[int, str, float]]:
    """(stage, commit, time) of every finished checker run since `since` that claims a stage."""
    out = []
    for rep in checks_dir.glob("stage*/report.json"):
        try:
            t = rep.stat().st_mtime
            r = json.loads(rep.read_text())
        except (OSError, ValueError):
            continue
        if t >= since and r.get("state") == "completed" and str(r.get("claimed_stage") or "").isdigit():
            out.append((int(r["claimed_stage"]), str(r.get("revision") or "")[:7], t))
    return out


def late_handoff(texts: list[dict], claimed: list[tuple[int, str, float]], now: float, nudged: set,
                 wait: float) -> tuple[int, str, float] | None:
    """The first claimed commit of an open stage that wasn't handed off (nor a later commit) within `wait` seconds."""
    readies, accepted = [], set()
    for m in texts:
        body = m.get("content") or ""
        at = _ts(m["inserted_at"]) if m.get("inserted_at") else 0.0
        accepted |= {int(x) for x in ACCEPTED_RE.findall(body)}
        if MENTIONS.sub("", body).lstrip().startswith("[ready]"):  # a handoff, not a message quoting one
            readies += [(int(st), sha[:7], at) for st, sha in READY_RE.findall(body)]
    for stage, sha, t in sorted(claimed, key=lambda c: c[2]):
        if stage in accepted or (stage, sha) in nudged:
            continue
        if any(st == stage and (c == sha or rt >= t) for st, c, rt in readies):
            continue
        if now - t >= wait:
            return stage, sha, t
    return None


NUDGED_RE = re.compile(r"\[nudge\]\s+stage=(\d+)\s+handoff=late\s+commit=([0-9a-f]{7,40})")


def already_nudged(texts: list[dict]) -> set:
    """(stage, commit) pairs a late-handoff nudge in the room already covers (so a restarted watcher doesn't repeat)."""
    return {(int(st), sha[:7]) for m in texts for st, sha in NUDGED_RE.findall(m.get("content") or "")}


CLOSED_RE = re.compile(r"\[nudge\]\s+stage=(\d+)\s+closed")


def newly_accepted(texts: list[dict]) -> list[int]:
    """Stages Nap Guard has accepted that the Builder hasn't been told are closed yet."""
    accepted, closed = set(), set()
    for m in texts:
        body = m.get("content") or ""
        if MENTIONS.sub("", body).lstrip().startswith("[gate]"):
            accepted |= {int(x) for x in ACCEPTED_RE.findall(body)}
        closed |= {int(x) for x in CLOSED_RE.findall(body)}
    return sorted(accepted - closed)


def interrupt_builder(room: str) -> str:
    return interrupt_seat(room, NAMES["builder"])


def text_messages(c: httpx.Client, room: str) -> list[dict]:
    r = c.get(f"/api/v1/me/chats/{room}/messages", params={"page": 1, "page_size": 100, "message_type": "text"})
    r.raise_for_status()
    body = r.json()
    return body.get("data") or body.get("messages") or []


def ends_run(text: str) -> bool:
    """A message that *is* the Architect's report or Nap Guard's receipt, not one that mentions them."""
    body = MENTIONS.sub("", text).lstrip()
    return body.startswith("[report]") or body.startswith("[receipt]")


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("room")
    args = ap.parse_args(argv)
    quiet = float(os.environ.get("ONSEN_QUIET_MIN", "6")) * 60
    budget = int(os.environ.get("ONSEN_MAX_NUDGES", "30"))
    stuck = float(os.environ.get("ONSEN_STUCK_MIN", "30")) * 60
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    me, arch, builder = cfg["napguard"], cfg["architect"], cfg["builder"]
    human = httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30)
    agent = httpx.Client(base_url=API, headers={"X-API-Key": me["api_key"]}, timeout=30)
    last_nudge, nudges, unstuck = 0.0, 0, {}
    started, nudged = float(os.environ.get("ONSEN_RUN_STARTED") or time.time()), set()
    checks_dir = Path(os.environ.get("ONSEN_CHECKS_DIR") or Path.home() / ".onsen" / "checks")
    wait = float(os.environ.get("ONSEN_HANDOFF_MIN", "5")) * 60
    print(f"watching {args.room}: nudge after {quiet / 60:.0f} quiet minutes, at most {budget} times", flush=True)
    while True:  # the closed-stage and handoff rules hold until the run reports; only quiet nudges have a budget
        time.sleep(60)
        try:
            newest, ended, turns = latest(human, args.room)
            texts = text_messages(human, args.room)
            nudged |= already_nudged(texts)
            late = late_handoff(texts, claims(checks_dir, started), time.time(), nudged, wait)
        except httpx.HTTPError as exc:
            print(f"read failed: {exc}", flush=True)
            continue
        if ended:
            print("run reported; done", flush=True)
            return 0
        closing = newly_accepted(texts)
        if closing:
            # A stage's folder is final once it is accepted, but a Builder mid-turn keeps polishing it and won't see the
            # next stage's handoff until its turn ends: stop the turn and say so.
            stage = closing[0]
            print(f"interrupt: {interrupt_builder(args.room)}", flush=True)
            content = (f"@{NAMES['builder']} [nudge] stage={stage} closed\n"
                       f"🔒 Stage {stage} is accepted, so its folder is final: don't change it again. I interrupted your "
                       f"turn so this reaches you. Your next task is the Architect's handoff for stage {stage + 1}; work "
                       f"only in that stage's folder from now on.")
            r = agent.post(f"/api/v1/agent/chats/{args.room}/messages", json={"message": {"content": content,
                           "mentions": [{"id": builder["agent_id"], "name": NAMES["builder"]}]}})
            print(f"closed stage {stage} -> HTTP {r.status_code}", flush=True)
            continue
        if late:
            stage, sha, t = late
            nudged.add((stage, sha))
            minutes = int((time.time() - t) // 60)
            print(f"interrupt: {interrupt_builder(args.room)}", flush=True)
            content = (f"@{NAMES['builder']} [nudge] stage={stage} handoff=late commit={sha}\n"
                       f"⏰ The acceptance checker claimed stage {stage} on commit {sha} {minutes} minutes ago, and it "
                       "hasn't been handed off. I interrupted your turn so this reaches you. Builder: post `[ready] "
                       f"stage={stage} commit={sha}` (or a later commit the checker claims) to the Examiner and the "
                       "Reviewer now, then keep improving in new revisions.")
            r = agent.post(f"/api/v1/agent/chats/{args.room}/messages", json={"message": {"content": content,
                           "mentions": [{"id": builder["agent_id"], "name": NAMES["builder"]}]}})
            print(f"handoff nudge: stage {stage} commit {sha} after {minutes}m -> HTTP {r.status_code}", flush=True)
            continue
        now = time.time()
        busy = sorted(s for s, v in turns.items() if v == "busy")
        if busy and newest and now - newest >= stuck:
            # Nothing has shown in the room for longer than any capped check takes: the turn is stuck, not working.
            for seat in busy:
                if unstuck.get(seat) == newest:
                    continue  # already interrupted for this silence
                unstuck[seat] = newest
                minutes = int((now - newest) // 60)
                print(f"interrupt {seat}: {interrupt_seat(args.room, seat)}", flush=True)
                content = (f"@{seat} [nudge] stuck={minutes}m\n"
                           f"⏳ Your turn has shown nothing in the room for {minutes} minutes, longer than any check "
                           "takes, so I stopped it. Pick up where you were: commit what works, in smaller steps, and "
                           "carry on with the stage.")
                seat_id = (cfg.get(seat.lower()) or {}).get("agent_id")
                body = {"message": {"content": content,
                                    "mentions": [{"id": seat_id, "name": seat}] if seat_id else []}}
                r = agent.post(f"/api/v1/agent/chats/{args.room}/messages", json=body)
                print(f"stuck nudge: {seat} after {minutes}m -> HTTP {r.status_code}", flush=True)
            continue
        if busy or nudges >= budget:
            continue  # a seat mid-turn is working, even when the room shows nothing
        if newest and now - newest >= quiet and now - last_nudge >= quiet:
            minutes = int((now - newest) // 60)
            content = (f"@{NAMES['architect']} @{NAMES['builder']} [nudge] quiet={minutes}m\n"
                       f"😴 The room has been quiet for {minutes} minutes and the run isn't finished. Architect: check "
                       "where the current stage stands (the last handoff, the latest commit, the latest verdicts) and "
                       "hand the next step to the seat that owns it. Builder: if you were mid-task, carry on, and hand "
                       "a committed revision off with `[ready]` once the checker claims the stage on it.")
            body = {"message": {"content": content, "mentions": [
                {"id": arch["agent_id"], "name": NAMES["architect"]},
                {"id": builder["agent_id"], "name": NAMES["builder"]}]}}
            r = agent.post(f"/api/v1/agent/chats/{args.room}/messages", json=body)
            nudges += 1
            last_nudge = now
            print(f"nudge {nudges}: quiet {minutes}m -> HTTP {r.status_code}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
