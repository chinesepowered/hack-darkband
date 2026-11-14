"""Turn a real BAND room transcript into an animated replay (HTML), and optionally record it to video.

    uv run python scripts/make_replay.py <transcript.json> --out demo/replay/out [--record] [--clean-copy runs/<run>/room.json]

The replay only shows what happened in the room: every message is the agents' own words. It renames the human
to "You (the capybara)", turns @[[uuid]] mention tokens into @Names, and shortens local paths. It also time-compresses
the run, so long builds play in seconds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
HUMAN = "You (the capybara)"
ROLES = {
    "Architect": ("OpenCode · Qwen 3.8", "#f2cc60"),
    "Builder": ("OpenCode · Qwen 3.8", "#d2a8ff"),
    "Reviewer": ("OpenCode · Qwen 3.8 · read-only", "#79c0ff"),
    "Scout": ("Nimble web agents", "#56d364"),
    "Examiner": ("sealed exam · Qwen + Playwright", "#ff7b72"),
    "Nap Guard": ("the only one who wakes you", "#ffa657"),
    "Accessibility Auditor": ("OpenCode · recruited at runtime", "#a5d6ff"),
}
UUID_MENTION = re.compile(r"@\[\[([0-9a-f-]{36})\]\]")
PATH_RE = re.compile(r"/tmp/claude-[^\s\"']*?/runs/([^/\s\"']+)")


def clean_text(text: str, names: dict[str, str]) -> str:
    text = UUID_MENTION.sub(lambda m: "@" + names.get(m.group(1), "someone"), text or "")
    text = PATH_RE.sub(r"~/onsen-runs/\1", text)
    text = re.sub(r"/tmp/claude-[^\s\"']+", "~/.onsen", text)
    return text.strip()


def collect_names(msgs: list[dict]) -> dict[str, str]:
    names: dict[str, str] = {}
    for m in msgs:
        if m.get("sender_id") and m.get("sender_name"):
            names[m["sender_id"]] = HUMAN if m.get("sender_type") == "User" else m["sender_name"]
        for men in (m.get("metadata") or {}).get("mentions", []) or []:
            if men.get("id") and men.get("name"):
                names.setdefault(men["id"], HUMAN if men.get("type") == "user" else men["name"])
    return names


def clean_copy(msgs: list[dict]) -> list[dict]:
    """A transcript safe to commit: names cleaned, paths shortened, delivery bookkeeping dropped."""
    names = collect_names(msgs)
    out = []
    for m in msgs:
        out.append({
            "at": m.get("inserted_at"),
            "from": names.get(m.get("sender_id"), m.get("sender_name") or "?"),
            "type": m.get("message_type", "text"),
            "content": clean_text(m.get("content") or "", names),
            "mentions": [names.get(x.get("id"), x.get("name")) for x in (m.get("metadata") or {}).get("mentions", []) or []],
        })
    return out


def event_line(m: dict) -> str | None:
    if m.get("message_type") != "tool_call":
        return None
    try:
        j = json.loads(m.get("content") or "{}")
    except json.JSONDecodeError:
        return None
    name, args = j.get("name", ""), j.get("args") or {}
    if name.startswith("band_") or name in ("todowrite", "todoread"):
        return None
    if name == "bash":
        return "bash: " + (args.get("command") or "").splitlines()[0][:110]
    target = args.get("filePath") or args.get("path") or args.get("pattern") or args.get("url") or ""
    return f"{name}: {Path(str(target)).name if '/' in str(target) else target}"[:120]


def build_items(msgs: list[dict], speed: float, events_per_gap: int, start: int = 0, end: int | None = None,
                target_s: float | None = None) -> list[dict]:
    """Messages before text-message index `start` render instantly (context); [start, end] play; the rest is cut.
    With `target_s`, the played part is scaled to last that long."""
    names = collect_names(msgs)
    items: list[dict] = []
    pending_events: list[dict] = []
    text_idx = -1
    for m in msgs:
        if m.get("message_type", "text") == "text":
            text_idx += 1
            if end is not None and text_idx > end:
                break
        when = (m.get("inserted_at") or "")[11:19]
        sender = names.get(m.get("sender_id"), m.get("sender_name") or "?")
        if m.get("message_type", "text") != "text":
            line = event_line(m)
            if line:
                pending_events.append({"kind": "event", "sender_id": m.get("sender_id"), "sender": sender,
                                       "text": clean_text(line, names), "time": when, "delay": int(160 / speed)})
            continue
        items += pending_events[-events_per_gap:]
        pending_events = []
        text = clean_text(m.get("content") or "", names)
        text = re.sub(r"^(?:@[A-Z][\w]*(?: Guard)?\s+)+", "", text) if m.get("sender_type") != "User" else text
        human = m.get("sender_type") == "User"
        delay = min(5200, 1500 + 12 * len(text)) / speed
        items.append({"kind": "msg", "sender_id": m.get("sender_id"), "sender": sender, "text": text[:900],
                      "time": when, "human": human, "delay": int(delay), "idx": text_idx})
    # context before the window: instant
    first = next((i for i, it in enumerate(items) if it.get("idx", -1) >= start), len(items))
    for it in items[:first]:
        it["delay"] = 0
    played = items[first:]
    if target_s and played:
        total = sum(it["delay"] for it in played) or 1
        k = target_s * 1000 / total
        for it in played:
            it["delay"] = max(40, int(it["delay"] * k))
    return items


def people(msgs: list[dict]) -> list[dict]:
    names = collect_names(msgs)
    seen: dict[str, dict] = {}
    for pid, name in names.items():
        role, color = ROLES.get(name, ("the human", "#f7b733") if name == HUMAN else ("agent", "#8b98a5"))
        initials = "".join(w[0] for w in name.replace("(", "").split()[:2]).upper()
        seen[pid] = {"id": pid, "name": name, "role": role, "color": color, "initials": initials,
                     "img": "capybara.svg" if name == HUMAN else None}
    order = [*ROLES, HUMAN]
    return sorted(seen.values(), key=lambda p: order.index(p["name"]) if p["name"] in order else 99)


def text_index(msgs: list[dict], pattern: str, after: int = -1) -> int:
    """Index (among text messages) of the first message after `after` whose content contains `pattern`."""
    idx = -1
    for m in msgs:
        if m.get("message_type", "text") != "text":
            continue
        idx += 1
        if idx > after and pattern in (m.get("content") or ""):
            return idx
    raise LookupError(f"no message contains {pattern!r}")


def write_html(transcript: Path, out: Path, title: str, speed: float, events_per_gap: int, note: str,
               start: int = 0, end: int | None = None, target_s: float | None = None) -> Path:
    msgs = json.loads(transcript.read_text())
    msgs.sort(key=lambda m: m.get("inserted_at") or "")
    items = build_items(msgs, speed, events_per_gap, start, end, target_s)
    data = {"title": title, "people": people(msgs), "items": items,
            "note": note, "speedLabel": f"replay · real transcript · {speed:g}× compressed"}
    out.mkdir(parents=True, exist_ok=True)
    html = (ROOT / "demo" / "replay" / "replay.html").read_text().replace(
        "__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    (out / "index.html").write_text(html)
    shutil.copyfile(ROOT / "assets" / "capybara.svg", out / "capybara.svg")
    return out / "index.html"


async def record(html: Path, video: Path, timeout_s: float) -> Path:
    """Play the replay in headless Chromium and save it as MP4 (Chrome screencast + ffmpeg)."""
    from playwright.async_api import async_playwright

    from screencast import screencast

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": 1280, "height": 720})
        await page.goto(html.resolve().as_uri())

        async def play() -> None:
            await page.wait_for_function("window.__done === true", timeout=timeout_s * 1000, polling=250)

        await screencast(page, play, video.with_suffix(".mp4"), tail_s=2.0)
        await b.close()
    return video.with_suffix(".mp4")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--out", default=str(ROOT / "demo" / "replay" / "out"))
    ap.add_argument("--title", default="Onsen · CapyFinder")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--events", type=int, default=3, help="tool-call lines shown before each message")
    ap.add_argument("--record", help="write an .mp4 recording here")
    ap.add_argument("--clean-copy", help="also write a commit-safe transcript here")
    ap.add_argument("--note", default="Replay of the real BAND room transcript. Agents' messages are unedited; mentions are shown by name.")
    args = ap.parse_args()
    transcript = Path(args.transcript)
    html = write_html(transcript, Path(args.out), args.title, args.speed, args.events, args.note)
    print(f"replay: {html}")
    if args.clean_copy:
        Path(args.clean_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.clean_copy).write_text(json.dumps(clean_copy(json.loads(transcript.read_text())), indent=1,
                                                    ensure_ascii=False))
        print(f"clean transcript: {args.clean_copy}")
    if args.record:
        print(f"video: {asyncio.run(record(html, Path(args.record), 1800))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
