"""Open the factory room as the human and post the one kickoff message.

    uv run onsen-kickoff                       # all registered agents + you, "@Architect build SPEC.md"
    uv run onsen-kickoff --title "Onsen · CapyFinder run 3"

Prints the room id. Uses BAND_USER_KEY (Human API): this is human touch #1.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx
import yaml

from .common import NAMES, agent_config_path, load_env

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")
ORDER = ["architect", "builder", "reviewer", "scout", "examiner", "napguard"]


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="Onsen · CapyFinder")
    ap.add_argument("--say", default="build SPEC.md")
    ap.add_argument("--skip", action="append", default=[], help="agent keys to leave out of the room")
    args = ap.parse_args(argv)
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    members = [k for k in ORDER if k in cfg and k not in args.skip]
    if "architect" not in members:
        print("The Architect isn't registered (uv run onsen-register).", file=sys.stderr)
        return 2
    arch = cfg["architect"]["agent_id"]
    body = {"chat": {
        "title": args.title,
        "participants": [{"participant_id": cfg[k]["agent_id"], "role": "member"} for k in members],
        "message": {"content": f"@{NAMES['architect']} {args.say}",
                    "mentions": [{"id": arch, "name": NAMES["architect"]}]},
    }}
    with httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30) as c:
        r = c.post("/api/v1/me/chats", json=body)
        if r.status_code >= 400:
            print(f"Could not open the room: HTTP {r.status_code} {r.text[:400]}", file=sys.stderr)
            return 1
        room = r.json()["data"]["id"]
    print(room)
    print(f"Room open with {', '.join(NAMES[k] for k in members)} + you. Kickoff sent.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
