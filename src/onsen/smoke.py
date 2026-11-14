"""Live smoke test: open a BAND room as you, mention one SDK agent, print its reply.

    uv run onsen-smoke --agent scout --say "ask: Which zoo started the capybara hot-spring bath?"

Start the agent first in another terminal (e.g. `uv run onsen-scout`). Uses BAND_USER_KEY
(the Human API) to create the room and post as you; the agent answers over its own connection.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx
import yaml

from .common import NAMES, agent_config_path, load_env

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="scout", choices=["scout", "examiner", "napguard"])
    ap.add_argument("--say", default="help")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--title", default="Onsen smoke test")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    agent_id = cfg[args.agent]["agent_id"]
    name = NAMES[args.agent]
    with httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30) as c:
        body = {"chat": {
            "title": args.title,
            "participants": [{"participant_id": agent_id, "role": "member"}],
            "message": {"content": f"@{name} {args.say}", "mentions": [{"id": agent_id, "name": name}]},
        }}
        resp = c.post("/api/v1/me/chats", json=body)
        if resp.status_code >= 400:
            print(f"Could not create the room: HTTP {resp.status_code} {resp.text[:400]}", file=sys.stderr)
            return 1
        chat_id = resp.json()["data"]["id"]
        print(f"Room {chat_id} created; asked {name}: {args.say}")
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            time.sleep(4)
            msgs = c.get(f"/api/v1/me/chats/{chat_id}/messages", params={"page_size": 50}).raise_for_status().json()["data"]
            replies = [m for m in msgs if (m.get("sender_id") == agent_id or m.get("sender", {}).get("id") == agent_id)
                       and m.get("message_type", "text") == "text"]
            if replies:
                print(f"\n--- {name} replied ---\n{replies[-1].get('content')}")
                return 0
        print(f"No reply from {name} within {args.timeout:.0f}s. Is `uv run onsen-{args.agent.replace('napguard', 'nap-guard')}` running?",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
