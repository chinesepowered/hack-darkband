"""Render the README's drawn images, in the look of the video cards (scripts/make_video.py):

- assets/social-preview.png (1280x640): the README banner, also GitHub's social preview image
- assets/architecture.png (1280x720 at 2x): who is in the room and what each agent talks to

    uv run python scripts/make_readme_images.py

The screenshots in assets/ come from elsewhere: room.png from `make_replay.py --screenshot`, band-desktop.png from
the run 7 screen recording.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_video  # noqa: E402


def svg(name: str, size: int) -> str:
    # Inline the SVG: a page built from a string can't load local files.
    return (ROOT / "assets" / name).read_text().replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


BANNER_CSS = """
body{width:1280px;height:640px;place-items:center}
.hero{display:grid;grid-template-columns:420px 1fr;align-items:center;gap:34px;text-align:left;width:1120px}
.hero h1{font-size:120px;margin:0} .hero .tag{font-size:38px} .hero .sub{font-size:28px}
.badges{display:flex;gap:10px;margin-top:26px}
.badges span{font-size:19px;font-weight:600;padding:7px 16px;border-radius:999px;background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.13);color:#fff6e8}
"""


def banner() -> str:
    return (f"<style>{BANNER_CSS}</style>{make_video.STEAM}"
            f'<div class="hero"><div class="halo">{svg("capybara.svg", 380)}</div><div><h1>Onsen</h1>'
            '<div class="tag">A dark software factory on BAND</div><div class="sub">One rule: don\'t wake the capybara.</div>'
            '<div class="badges"><span>BAND Desktop</span><span>GPT-6 Luna</span><span>Nimble</span>'
            "<span>a sealed exam</span></div></div></div>")


ARCH_CSS = """
body{display:block}
.box{position:absolute}
.human{left:470px;top:22px;width:340px;height:78px;border-radius:999px;background:rgba(255,184,77,.12);
  border:2px solid rgba(255,184,77,.6);display:flex;align-items:center;gap:14px;padding:0 22px}
.human b{font-size:24px;display:block} .human span{font-size:17px;color:#a9c0cf}
.room{left:40px;top:150px;width:1200px;height:320px;border-radius:28px;background:rgba(255,255,255,.035);
  border:2px solid rgba(155,231,242,.32)}
.title{left:0;top:162px;width:1280px;text-align:center;font-size:19px;color:#9fc3d1}
.title b{font-family:'Inter Display',Inter,sans-serif;font-size:27px;font-weight:800;color:#fff6e8;margin-right:6px}
.group{top:212px;width:564px;height:236px;border-radius:20px;border:2px dashed rgba(255,255,255,.17);background:rgba(0,0,0,.14)}
.glabel{top:224px;font-size:16px;font-weight:700;border-radius:999px;padding:4px 13px}
.agent{top:264px;width:165px;height:166px;border-radius:18px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
  text-align:center;padding-top:14px}
.agent .av{width:52px;height:52px;margin:0 auto 8px;font-size:20px;grid-row:auto}
.agent b{font-size:23px;display:block;letter-spacing:-.01em}
.agent span{font-size:16.5px;color:#c6d4de;display:block;margin:3px 10px 0;line-height:1.3}
.tile{top:560px;height:112px;border-radius:18px;background:rgba(255,255,255,.065);border:1px solid rgba(255,255,255,.11);
  padding:20px 24px 0 30px;overflow:hidden}
.tile:before{content:"";position:absolute;left:0;top:0;bottom:0;width:8px;background:var(--c)}
.tile b{font-size:25px;display:block;letter-spacing:-.01em} .tile span{font-size:18px;color:#c6d4de}
.lbl{transform:translate(-50%,-50%);white-space:nowrap;font-size:17px;font-weight:600;color:#d7f3f8;background:#0f2433;
  border:1px solid rgba(155,231,242,.38);border-radius:999px;padding:3px 13px}
svg.wires{position:absolute;left:0;top:0}
"""

AGENTS = [  # x of the card's left edge, initials, color, name, what it does
    (84, "A", "#f2cc60", "Architect", "plans, hands off whole stages"),
    (268, "B", "#d2a8ff", "Builder", "writes every line"),
    (452, "E", "#ff7b72", "Examiner", "🔒 a sealed, executable exam"),
    (636, "R", "#79c0ff", "Reviewer", "read-only, can block a commit"),
    (949, "NG", "#ffa657", "Nap Guard", "gates every stage, no model"),
]


def architecture() -> str:
    x = {name: left + 82 for left, _, _, name, _ in AGENTS}  # card centers
    top, bottom, wire = 264, 430, "#9be7f2"
    wires = f"""<svg class="wires" width="1280" height="720" viewBox="0 0 1280 720"><defs>
      <marker id="tip" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0L10 5L0 10z" fill="{wire}"/></marker></defs>
      <g fill="none" stroke="{wire}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity=".9">
        <path d="M470 61H{x['Architect'] + 18}q-18 0-18 18V{top - 4}" marker-end="url(#tip)"/>
        <path d="M244 448V554" marker-end="url(#tip)"/>
        <path d="M{x['Builder']} {bottom + 4}V496q0 16 16 16H624q16 0 16 16V554" marker-end="url(#tip)"/>
        <path d="M{x['Nap Guard']} {bottom + 4}V554" marker-end="url(#tip)"/>
      </g>
      <path d="M{x['Nap Guard']} {top - 4}V79q0-18-18-18H814" fill="none" stroke="#a9c0cf" stroke-width="2.4"
        stroke-dasharray="3 9" stroke-linecap="round" opacity=".75"/></svg>"""

    def at(cx: int, cy: int, text: str, quiet: bool = False) -> str:
        style = "color:#a9c0cf;border-color:rgba(169,192,207,.35)" if quiet else ""
        return f'<div class="box lbl" style="left:{cx}px;top:{cy}px;{style}">{text}</div>'

    cards = "".join(
        f'<div class="box agent" style="left:{left}px"><div class="av" style="background:{color}">{initials}</div>'
        f"<b>{name}</b><span>{what}</span></div>" for left, initials, color, name, what in AGENTS)
    return (f"<style>{ARCH_CSS}</style>"  # no steam here: it would show through the cards
            '<div class="box room"></div>'
            '<div class="box title"><b>One BAND room</b> a message reaches only the seats it mentions</div>'
            '<div class="box group" style="left:64px;width:760px"></div>'
            '<div class="box group" style="left:848px;width:368px"></div>'
            '<div class="box glabel" style="left:258px;color:#ffcf85;background:rgba(255,184,77,.12);'
            'border:1px solid rgba(255,184,77,.3)">BAND Desktop · OpenCode · GPT-6 Luna</div>'
            '<div class="box glabel" style="left:870px;color:#a8f0f8;background:rgba(155,231,242,.1);'
            'border:1px solid rgba(155,231,242,.3)">band-sdk</div>'
            + cards + wires
            + f'<div class="box human">{svg("capybara-badge.svg", 54)}<div><b>You, the capybara</b>'
              "<span>napping in the hot spring</span></div></div>"
            '<div class="box tile" style="left:64px;width:360px;--c:#ffbe00"><b>OpenAI · GPT-6 Luna</b>'
            "<span>every coding seat's model calls</span></div>"
            '<div class="box tile" style="left:460px;width:360px;--c:#fff6e8"><b>The result repository</b>'
            "<span>stage-1 … stage-4 and exams/</span></div>"
            '<div class="box tile" style="left:856px;width:360px;--c:#7ee2b8"><b>The event\'s checker</b>'
            "<span>suites 1 to N, on the mock web</span></div>"
            + at(300, 61, "one message: the task") + at(980, 61, "never wakes you", quiet=True)
            + at(244, 503, "every model call") + at(510, 512, "commits")
            + at(x["Nap Guard"], 503, "runs it before every gate"))


FLOW_CSS = ARCH_CSS + """
.node{border-radius:18px;background:rgba(255,255,255,.065);border:1px solid rgba(255,255,255,.12);padding:18px 22px}
.node b{font-size:24px;display:block;letter-spacing:-.01em} .node span{font-size:18px;color:#c6d4de;display:block;margin-top:2px}
.node code{font-size:19px;background:none;padding:0;color:#fff6e8;font-weight:600;white-space:nowrap}
.filter{margin-top:12px;font-size:17px;color:#ffcf85;background:rgba(255,184,77,.12);border:1px solid rgba(255,184,77,.35);
  border-radius:12px;padding:7px 12px}
.filter code{font-size:17px;color:#ffcf85}
"""


def desktop_flow() -> str:
    """How one wake-up runs: a mention reaches BAND Desktop, which starts the agent; the agent answers with band send."""
    wire = "#9be7f2"
    wires = f"""<svg class="wires" width="1280" height="390" viewBox="0 0 1280 390"><defs>
      <marker id="tip" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0L10 5L0 10z" fill="{wire}"/></marker></defs>
      <g fill="none" stroke="{wire}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" opacity=".9">
        <path d="M270 112H464" marker-end="url(#tip)"/>
        <path d="M790 112H914" marker-end="url(#tip)"/>
        <path d="M1080 206V254" marker-start="url(#tip)" marker-end="url(#tip)"/>
        <path d="M920 314H173q-18 0-18-18V168" marker-end="url(#tip)"/>
      </g></svg>"""

    def at(cx: int, cy: int, text: str) -> str:
        return f'<div class="box lbl" style="left:{cx}px;top:{cy}px">{text}</div>'

    return (f"<style>{FLOW_CSS}</style>"
            '<div class="box node" style="left:40px;top:62px;width:230px;height:100px"><b>BAND room</b>'
            "<span>where the crew talks</span></div>"
            '<div class="box node" style="left:470px;top:62px;width:320px;height:100px"><b>BAND Desktop daemon</b>'
            "<span>jamd · shows every step live</span></div>"
            '<div class="box node" style="left:920px;top:30px;width:320px;height:176px"><code>onsen-opencode-builder</code>'
            '<span>role profile · Qwen 3.8</span><div class="filter"><code>acp_filter.py</code> keeps closing remarks out'
            "</div></div>"
            '<div class="box node" style="left:920px;top:260px;width:320px;height:100px"><code>opencode acp</code>'
            "<span>the agent reads, edits and runs</span></div>"
            + wires
            + at(367, 82, "mentions @Builder") + at(852, 82, "starts it")
            + at(1124, 231, "ACP") + at(540, 314, "band send @examiner @reviewer [ready] …"))


async def render(body: str, out: Path, width: int, height: int, scale: int) -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
        css = make_video.CARD_CSS.replace("width:1280px;height:720px", f"width:{width}px;height:{height}px")
        await page.set_content(f"<!doctype html><meta charset=utf-8><style>{css}</style>{body}")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(out))
        await b.close()


async def main() -> None:
    await render(banner(), ROOT / "assets" / "social-preview.png", 1280, 640, 1)
    await render(architecture(), ROOT / "assets" / "architecture.png", 1280, 720, 2)
    await render(desktop_flow(), ROOT / "assets" / "band-desktop-flow.png", 1280, 390, 2)


if __name__ == "__main__":
    asyncio.run(main())
    print("assets/social-preview.png assets/architecture.png assets/band-desktop-flow.png")
