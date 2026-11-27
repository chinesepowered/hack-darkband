"""The measured facts of one run: who committed what, when each stage was accepted, what the models cost.

    uv run python scripts/run_facts.py <result repository> <room id> [--exam-dir <dir>] [--json out.json]

- Commits: `git log` of the result repository, by author (every seat commits under its own name).
- Stages: Nap Guard's `[gate] stage=N ACCEPTED` messages in the room, with the time from the task to each one.
- Delivery time: from the first to the last message a seat sent, which is how the event reads it.
- Model spend: OpenCode's own per-session token counts and costs for the sessions that worked in this run's
  directories (the repository and the Examiner's workspace), from its local database.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SEATS = ("Architect", "Builder", "Examiner", "Reviewer", "Nap Guard")


def room_messages(room: str) -> list[dict]:
    out, cursor = [], None
    for _ in range(200):
        args = ["band", "room", "messages", room, "--json"] + (["--cursor", cursor] if cursor else [])
        page = json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)
        msgs = page.get("data") or page.get("messages") or page.get("items") or []
        out += msgs
        cursor = page.get("next_cursor") or (page.get("metadata") or {}).get("next_cursor")
        if not cursor or not msgs:
            break
    seen, uniq = set(), []
    for m in out:
        if m.get("id") not in seen:
            seen.add(m.get("id"))
            uniq.append(m)
    return sorted(uniq, key=lambda m: m.get("inserted_at") or m.get("insertedAt") or "")


def ts(m: dict) -> datetime:
    return datetime.fromisoformat((m.get("inserted_at") or m.get("insertedAt")).replace("Z", "+00:00"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("room")
    ap.add_argument("--exam-dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()

    log = subprocess.run(["git", "-C", str(repo), "log", "--format=%an\t%aI\t%s"], capture_output=True, text=True,
                         check=True).stdout.splitlines()
    commits = collections.Counter(line.split("\t")[0] for line in log)

    msgs = room_messages(a.room)
    text = [m for m in msgs if (m.get("message_type") or m.get("messageType") or "text") == "text"]
    by_seat = [m for m in text if (m.get("sender_name") or m.get("senderName")) in SEATS]
    human = [m for m in text if str(m.get("sender_type") or m.get("senderType") or "").lower() == "user"]
    start = ts(human[0]) if human else ts(text[0])
    gates = {}
    for m in by_seat:
        body = m.get("content") or ""
        g = re.search(r"\[gate\] stage=(\d+) ACCEPTED commit=(\w+)", body)
        if g and g.group(1) not in gates:
            first = body.split("\n", 1)[0]
            exam = re.search(r"\bexam=(\S+)", first)
            review = re.search(r"\breview=(\w+)", first)
            shipped = re.search(r"\((\d+)/(\d+) shipped checks\)", first)
            gates[g.group(1)] = {"commit": g.group(2), "at": ts(m).strftime("%H:%M"),
                                 "minutes_from_task": round((ts(m) - start).total_seconds() / 60),
                                 "exam_curve": exam.group(1) if exam else None,
                                 "review": review.group(1) if review else None,
                                 "shipped_checks": f"{shipped.group(1)}/{shipped.group(2)}" if shipped else None}
    tags = collections.Counter()
    for m in by_seat:
        t = re.search(r"\[([a-z-]+)\]", m.get("content") or "")
        if t:
            tags[f"{m.get('sender_name') or m.get('senderName')} [{t.group(1)}]"] += 1

    db = Path.home() / ".local/share/opencode/opencode.db"
    dirs = {str(repo)} | ({str(Path(a.exam_dir).resolve())} if a.exam_dir else set())
    spend = {}
    if db.exists():
        con = sqlite3.connect(db)
        since = int(start.timestamp() * 1000) - 120_000
        for agent, cost, ti, to, tr, cr, cw in con.execute(
                "select agent, cost, tokens_input, tokens_output, tokens_reasoning, tokens_cache_read, "
                "tokens_cache_write from session where time_created >= ? and directory in (%s)"
                % ",".join("?" * len(dirs)), (since, *dirs)):
            s = spend.setdefault((agent or "?").replace("onsen-", "").title(),
                                 {"usd": 0.0, "input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0})
            s["usd"] += cost or 0
            s["input"] += ti or 0
            s["output"] += to or 0
            s["reasoning"] += tr or 0
            s["cache_read"] += cr or 0
            s["cache_write"] += cw or 0
    facts = {
        "room": a.room,
        "task_at": start.isoformat(timespec="seconds"),
        "human_messages": len(human),
        "delivery_minutes": round((ts(by_seat[-1]) - ts(by_seat[0])).total_seconds() / 60) if by_seat else None,
        "seat_messages": collections.Counter(m.get("sender_name") or m.get("senderName") for m in by_seat),
        "tags": dict(sorted(tags.items())),
        "stages_accepted": gates,
        "commits": dict(commits),
        "model_spend": {k: {**v, "usd": round(v["usd"], 2)} for k, v in sorted(spend.items())},
        "model_spend_total_usd": round(sum(v["usd"] for v in spend.values()), 2),
    }
    out = json.dumps(facts, indent=2, default=str)
    print(out)
    if a.json:
        Path(a.json).write_text(out + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
