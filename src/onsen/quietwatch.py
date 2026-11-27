"""Nap Guard's quiet-room rule, for a dark run.

BAND Desktop starts a seat only when a message mentions it. If a seat ends its turn mid-stage without handing
anything off, nothing would ever wake it again, and in a dark run nobody may step in. So while a run is open,
this watches the room: when no seat has done anything (no message, thought or tool call) for ONSEN_QUIET_MIN
minutes (default 6), it posts `[nudge]` as Nap Guard to the Architect and the Builder. It nudges at most
ONSEN_MAX_NUDGES times (default 30) and exits once the room has a `[report]` or `[receipt]`.

    uv run onsen-quiet-watch <room>
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timezone

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
    print(f"watching {args.room}: nudge after {quiet / 60:.0f} quiet minutes, at most {budget} times", flush=True)
    while nudges < budget:
        time.sleep(60)
        try:
            newest, ended = latest(human, args.room)
        except httpx.HTTPError as exc:
            print(f"read failed: {exc}", flush=True)
            continue
        if ended:
            print("run reported; done", flush=True)
            return 0
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
