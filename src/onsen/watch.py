"""Follow a factory room as the human sees it (every message and event), and save the transcript.

    uv run onsen-watch <room_id>                    # follow until the receipt (or Ctrl-C)
    uv run onsen-watch <room_id> --once --out runs/run-1/transcript.json

Humans see everything in a BAND room, so this is the full record: the receipt, the exam curve,
every handoff. The saved JSON feeds the demo replay.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

from .common import load_env

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")


def fetch_all(c: httpx.Client, room: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        r = c.get(f"/api/v1/me/chats/{room}/messages", params={"page": page, "page_size": 100})
        r.raise_for_status()
        body = r.json()
        out += body.get("data", [])
        meta = body.get("metadata") or body.get("meta") or {}
        if not meta.get("has_more") and (meta.get("total_pages") in (None, page) or page >= (meta.get("total_pages") or 1)):
            break
        page += 1
    out.sort(key=lambda m: m.get("inserted_at") or m.get("created_at") or "")
    return out


def line(m: dict) -> str:
    sender = (m.get("sender_name") or (m.get("sender") or {}).get("name") or m.get("sender_type") or "?")
    kind = m.get("message_type", "text")
    ts = (m.get("inserted_at") or "")[11:19]
    content = (m.get("content") or "").strip()
    if kind != "text":
        content = content.splitlines()[0][:160] if content else ""
        return f"{ts}  · {sender} [{kind}] {content}"
    return f"{ts}  {sender}: {content}"


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--events", action="store_true", help="also print tool calls/thoughts")
    ap.add_argument("--out", help="save the transcript JSON here")
    ap.add_argument("--until", default="[receipt]", help="stop after a message containing this text")
    args = ap.parse_args(argv)
    seen: set[str] = set()
    with httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30) as c:
        while True:
            msgs = fetch_all(c, args.room)
            done = False
            for m in msgs:
                if m["id"] in seen:
                    continue
                seen.add(m["id"])
                if m.get("message_type", "text") == "text" or args.events:
                    print(line(m), flush=True)
                if args.until and args.until in (m.get("content") or ""):
                    done = True
            if args.out:
                Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.out).write_text(json.dumps(msgs, indent=1, ensure_ascii=False))
            if args.once or done:
                return 0
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
