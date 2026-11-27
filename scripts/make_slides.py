"""Render the submission presentation as a PDF, in the look of the video cards (scripts/make_video.py).

    uv run python scripts/make_slides.py --facts facts.json --out onsen-slides.pdf

`facts.json` carries the judged run's numbers, so the deck never states something the run didn't do:
    {"stages": [{"n": 1, "claimed": true, "minutes": 95, "rounds": 3}], "human_inputs": 1, "wakeups": 0,
     "seats": 5, "commits": {"Builder": 40, "Examiner": 4, "Architect": 3}, "spend_usd": 4.1, "tokens": 18000000,
     "caught": "the Examiner's exam failed a commit that passed the shipped checks: …", "video": "…", "repo": "…"}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_video  # noqa: E402

SLIDE_CSS = """
@page { size: 1280px 720px; margin: 0 }
html, body { margin: 0; padding: 0; background: #0b1620 }
.slide { width: 1280px; height: 720px; position: relative; overflow: hidden; display: grid; place-items: center;
  color: #fff6e8; font-family: Inter, ui-sans-serif, system-ui, sans-serif; break-after: page;
  background: radial-gradient(1100px 620px at 50% 118%, #1d4a5e 0%, #122a3a 48%, #0b1620 100%) }
.slide:last-child { break-after: auto }
.k { font-family: 'Inter Display', Inter, sans-serif; font-weight: 800; font-size: 46px; letter-spacing: -.02em;
  color: #ffb84d; margin: 0 0 22px }
.body { width: 1080px; text-align: left }
.body li { font-size: 25px; line-height: 1.45; margin: 10px 0; color: #e9eef2 }
.body li b { color: #fff6e8 }
.big { font-family: 'Inter Display', Inter, sans-serif; font-size: 120px; font-weight: 800; margin: 0 }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; margin-top: 26px }
.stat { background: rgba(255,255,255,.055); border: 1px solid rgba(255,255,255,.09); border-radius: 20px;
  padding: 22px; text-align: center }
.stat .v { font-family: 'Inter Display', Inter, sans-serif; font-size: 54px; font-weight: 800; color: #fff6e8 }
.stat .l { font-size: 18px; color: #a9c0cf; margin-top: 4px }
img.wide { width: 1100px; border-radius: 18px; border: 1px solid rgba(255,255,255,.14) }
"""


def slide(inner: str) -> str:
    return f'<section class="slide">{make_video.STEAM}{inner}</section>'


def bullets(title: str, items: list[str]) -> str:
    lis = "".join(f"<li>{i}</li>" for i in items)
    return slide(f'<div class="body"><div class="k">{title}</div><ul>{lis}</ul></div>')


def stage_row(s: dict) -> str:
    parts = [f"<b>Stage {s['n']}:</b> " + ("claimed" if s.get("claimed") else "not claimed")]
    if s.get("minutes"):
        parts.append(f"{s['minutes']} min")
    if s.get("rounds"):
        parts.append(f"{s['rounds']} rounds")
    return "<li>" + " · ".join(parts) + "</li>"


def deck(f: dict) -> str:
    claimed = [s for s in f.get("stages", []) if s.get("claimed")]
    top = max((s["n"] for s in claimed), default=0)
    stage_rows = "".join(stage_row(s) for s in f.get("stages", []))
    commits = " · ".join(f"{k} {v}" for k, v in (f.get("commits") or {}).items())
    slides = [
        slide('<div style="text-align:center"><div class="halo"><img src="capybara.svg" width="260"></div>'
              '<h1 style="font-size:112px;margin:6px 0 0">Onsen</h1>'
              '<div class="tag">A dark software factory on BAND</div>'
              '<div class="sub">One rule: don\'t wake the capybara.</div></div>'),
        bullets("The problem", [
            "Coding agents can build overnight, but someone still has to <b>babysit</b> them.",
            "A dark factory has to answer its own questions, <b>catch its own bad work</b>, and keep going.",
            "The event's rule makes it real: <b>the dispatched task is the only human input</b>."]),
        slide('<div class="body"><div class="k">The band: five seats, one BAND room</div>'
              '<img class="wide" src="architecture.png"></div>'),
        bullets("One stage, step by step", [
            "<b>Architect</b> opens the stage's spec and hands off the <b>whole</b> spec, in numbered parts, plus the task.",
            "<b>Examiner</b> writes the stage's exam as <b>code</b>, from the spec alone, and <b>seals</b> it by SHA-256 before any build.",
            "<b>Builder</b> commits small steps; the moment the checker claims the stage it posts <b>[ready] commit=…</b>.",
            "<b>Examiner</b> grades that commit with <code>onsen-exam</code>; <b>Reviewer</b> reads the diff and probes the running service.",
            "<b>Nap Guard</b> recounts the exam, needs the approval on the <b>same commit</b>, then runs the checker itself."]),
        bullets("How it catches bad work", [
            "<b>No seat's word opens the gate</b>: tools compute the exam's verdict; Nap Guard runs the event's checker itself.",
            "<b>A hidden exam</b>: the Builder can't fit the code to checks it never sees; the seal makes it tamper-evident.",
            "<b>A room that stays a protocol</b>: <code>band send</code> is a linter; each tag has one owner, each commit one verdict.",
            "<b>Bounded review</b>: stalls escalate (re-plan, one grader, checker) instead of looping or ending the run.",
            f"<b>A bad result it caught:</b> {f.get('caught', '—')}"]),
        slide('<div class="body"><div class="k">The judged run</div>'
              f'<div class="stats"><div class="stat"><div class="v">{top}</div><div class="l">highest stage claimed</div></div>'
              f'<div class="stat"><div class="v">{f.get("human_inputs", 1)}</div><div class="l">human input</div></div>'
              f'<div class="stat"><div class="v">{f.get("wakeups", 0)}</div><div class="l">wake-ups</div></div>'
              f'<div class="stat"><div class="v">{f.get("seats", 5)}</div><div class="l">seats</div></div></div>'
              f'<ul style="margin-top:26px">{stage_rows}<li><b>Commits by seat:</b> {commits or "—"}</li></ul></div>'),
        bullets("What it cost", [
            f"<b>Model:</b> GPT-6 Luna (OpenAI) for every coding seat, through OpenCode · {f.get('tokens_text', '—')}",
            f"<b>Spend:</b> {f.get('spend_text', '—')}",
            f"<b>Time:</b> {f.get('time_text', '—')}",
            "<b>Why a small fast model:</b> cheap enough to let four seats work in parallel all day; the factory's "
            "tools and gate make up for what the model gets wrong."]),
        bullets("Built on", [
            "<b>BAND Desktop</b>: four OpenCode seats, live reasoning and Interrupt; the room's mention routing keeps the exam sealed.",
            "<b>band-sdk</b>: Nap Guard, a deterministic seat with no model, gates every stage.",
            "<b>Nimble</b> via WebRouter: the service researches every company on the live web, each value with its excerpt."]),
        slide('<div style="text-align:center"><div class="halo"><img src="capybara.svg" width="220"></div>'
              '<h1 style="font-size:96px;margin:6px 0 0">Onsen</h1>'
              '<div class="sub" style="color:#fff6e8">One message in. The capybara slept through all of it.</div>'
              f'<div class="url">{f.get("repo", "")}</div></div>'),
    ]
    return "".join(slides)


async def render(html: str, out: Path) -> None:
    from playwright.async_api import async_playwright

    tmp = out.with_suffix(".html")
    tmp.write_text(f"<!doctype html><meta charset=utf-8><style>{make_video.CARD_CSS}{SLIDE_CSS}</style>{html}")
    for name in ("capybara.svg", "architecture.png"):
        (tmp.parent / name).write_bytes((ROOT / "assets" / name).read_bytes())
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": 1280, "height": 720})
        await page.goto(tmp.resolve().as_uri())
        await page.wait_for_timeout(600)
        await page.pdf(path=str(out), width="1280px", height="720px", print_background=True)
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True)
    ap.add_argument("--out", default="onsen-slides.pdf")
    args = ap.parse_args()
    facts = json.loads(Path(args.facts).read_text())
    asyncio.run(render(deck(facts), Path(args.out)))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
