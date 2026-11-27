"""Nap Guard's quiet-room rule, for a dark run.

BAND Desktop starts a seat only when a message mentions it. If a seat ends its turn mid-stage without handing
anything off, nothing would ever wake it again, and in a dark run nobody may step in. So while a run is open,
this watches the room: when no seat has done anything (no message, thought or tool call) for ONSEN_QUIET_MIN
minutes (default 6), it posts `[nudge]` as Nap Guard to the Architect and the Builder. It nudges at most
ONSEN_MAX_NUDGES times (default 30) and exits once the room has a `[report]` or `[receipt]`.

The late-handoff rule: a seat mid-turn hears nothing, so a Builder that keeps polishing a revision the acceptance
checker already claims leaves the graders idle. When a checker run (in ONSEN_CHECKS_DIR) claims the open stage on a
commit and no `[ready]` for that commit or a later one follows within ONSEN_HANDOFF_MIN minutes (default 5), this
interrupts the Builder's turn (`band runtime interrupt`) and posts `[nudge] handoff=late` to it, once per commit.

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


def latest(c: httpx.Client, room: str) -> tuple[float, bool]:
    """(time of the newest seat activity, whether the run has ended)."""
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
    return newest, ended


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


def interrupt_builder(room: str) -> str:
    """Interrupt the Builder's active turn in this room: BAND Desktop keeps one host session per room, named after the
    seat and the room, besides a parked default one; the interrupt has to name the room's."""
    out = subprocess.run(["band", "status", "--session", "onsen-builder"], capture_output=True, text=True).stdout
    host = next((ln.split()[0] for ln in out.splitlines() if f"room={room}" in ln), "")
    if not host:
        return "no host session for this room"
    r = subprocess.run(["band", "runtime", "interrupt", "--session", "onsen-builder", "--host-session", host],
                       capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()[:200] or f"interrupted {host}"


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
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    me, arch, builder = cfg["napguard"], cfg["architect"], cfg["builder"]
    human = httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30)
    agent = httpx.Client(base_url=API, headers={"X-API-Key": me["api_key"]}, timeout=30)
    last_nudge, nudges = 0.0, 0
    started, nudged = float(os.environ.get("ONSEN_RUN_STARTED") or time.time()), set()
    checks_dir = Path(os.environ.get("ONSEN_CHECKS_DIR") or Path.home() / ".onsen" / "checks")
    wait = float(os.environ.get("ONSEN_HANDOFF_MIN", "5")) * 60
    print(f"watching {args.room}: nudge after {quiet / 60:.0f} quiet minutes, at most {budget} times", flush=True)
    while nudges < budget:
        time.sleep(60)
        try:
            newest, ended = latest(human, args.room)
            texts = text_messages(human, args.room)
            nudged |= already_nudged(texts)
            late = late_handoff(texts, claims(checks_dir, started), time.time(), nudged, wait)
        except httpx.HTTPError as exc:
            print(f"read failed: {exc}", flush=True)
            continue
        if ended:
            print("run reported; done", flush=True)
            return 0
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
            nudges += 1
            print(f"handoff nudge {nudges}: stage {stage} commit {sha} after {minutes}m -> HTTP {r.status_code}", flush=True)
            continue
        now = time.time()
        if newest and now - newest >= quiet and now - last_nudge >= quiet:
            minutes = int((now - newest) // 60)
            content = (f"@{NAMES['architect']} @{NAMES['builder']} [nudge] quiet={minutes}m\n"
                       f"😴 The room has been quiet for {minutes} minutes and the run isn't finished. Architect: check "
                       "where the current stage stands (the last handoff, the latest commit, the latest verdicts) and "
                       "hand the next step to the seat that owns it. Builder: if you were mid-task, carry on and post "
                       "your `[ready]` when the revision is committed.")
            body = {"message": {"content": content, "mentions": [
                {"id": arch["agent_id"], "name": NAMES["architect"]},
                {"id": builder["agent_id"], "name": NAMES["builder"]}]}}
            r = agent.post(f"/api/v1/agent/chats/{args.room}/messages", json=body)
            nudges += 1
            last_nudge = now
            print(f"nudge {nudges}: quiet {minutes}m -> HTTP {r.status_code}", flush=True)
    print("nudge budget spent; done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
