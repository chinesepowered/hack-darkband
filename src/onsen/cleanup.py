"""Take the crew out of every room except the current one, so old rooms can't wake them.

    uv run onsen-cleanup                 # keep only the room in ~/.onsen/last-room
    uv run onsen-cleanup --keep <room>   # keep a specific room
    uv run onsen-cleanup --all           # leave every room

Agents rejoin every room they're in when they start. A leftover message in an old room (say, an
old exam failure) would otherwise start work in the new run's workspace. run-factory.sh runs this
before it opens a new room. The rooms and their transcripts stay; only our agents leave.
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx
import yaml

from .common import agent_config_path, load_env, onsen_home

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)
    keep = set(args.keep)
    if not args.all and not keep:
        last = onsen_home() / "last-room"
        if last.exists():
            keep.add(last.read_text().strip())
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    ours = {v["agent_id"] for v in cfg.values()}
    removed = 0
    with httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30) as c:
        page = 1
        while True:
            body = c.get("/api/v1/me/chats", params={"page": page, "page_size": 100}).raise_for_status().json()
            for room in body.get("data", []):
                if room["id"] in keep:
                    continue
                for agent in room.get("agents") or []:
                    if agent.get("id") in ours:
                        r = c.delete(f"/api/v1/me/chats/{room['id']}/participants/{agent['id']}")
                        if r.status_code < 400:
                            removed += 1
                            print(f"  {agent.get('name')} left {room.get('title') or room['id']}")
                        elif r.status_code != 404:
                            print(f"  could not remove {agent.get('name')} from {room['id']}: HTTP {r.status_code}",
                                  file=sys.stderr)
            meta = body.get("metadata") or {}
            if not meta.get("has_more"):
                break
            page += 1
    print(f"done: {removed} memberships removed; kept {', '.join(sorted(keep)) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
