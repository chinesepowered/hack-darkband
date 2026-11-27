"""Save a BAND room's whole message history as a transcript for make_replay.py and make_video.py.

    uv run python scripts/fetch_room.py <room id> --out transcript.json [--types text,tool_call,tool_result]

Pages through `band room messages <room> --json` (newest first, 100 at a time) and writes the messages oldest first,
each with `metadata.mentions` (id, name, type) built from the message's mention names, the shape the replay reads.
This is a working copy for rendering; the room file a submission commits is the one downloaded from the Band console.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def page(room: str, cursor: str | None, kind: str | None) -> dict:
    cmd = ["band", "room", "messages", room, "--json"]
    if cursor:
        cmd += ["--cursor", cursor]
    if kind:
        cmd += ["--type", kind]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60).stdout)


def fetch(room: str, kind: str | None = None) -> list[dict]:
    msgs, cursor = [], None
    while True:
        d = page(room, cursor, kind)
        msgs += d.get("messages") or []
        cursor = d.get("next_cursor")
        if not d.get("has_more") or not cursor:
            return msgs


def as_transcript(m: dict) -> dict:
    names = m.get("mention_names") or {}
    if isinstance(names, str):  # some pages carry it as a JSON string
        try:
            names = json.loads(names)
        except ValueError:
            names = {}
    mentions = [{"id": k, "name": v, "type": "agent"} for k, v in (names.items() if isinstance(names, dict) else [])]
    out = {k: m.get(k) for k in ("id", "inserted_at", "sender_id", "sender_name", "sender_type", "message_type",
                                 "content", "tool_name", "tool_call_id")}
    out["metadata"] = {"mentions": mentions}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--out", required=True)
    ap.add_argument("--types", default="", help="comma-separated message types (default: all)")
    a = ap.parse_args()
    kinds = [k for k in a.types.split(",") if k] or [None]
    seen, msgs = set(), []
    for kind in kinds:
        for m in fetch(a.room, kind):
            if m.get("id") not in seen:
                seen.add(m.get("id"))
                msgs.append(as_transcript(m))
    msgs.sort(key=lambda m: m.get("inserted_at") or "")
    Path(a.out).write_text(json.dumps(msgs, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(msgs)} messages -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
