"""Assemble the demo video from a real factory run.

    uv run python scripts/make_video.py --transcript ~/.onsen/transcripts/<run>.json \
        --scenes demo/scenes.json --app-url http://localhost:8000 --out demo/onsen-demo.mp4

- Narration: the `> VO:` lines of demo/script.md, one ElevenLabs clip per scene (voice: Jessica).
- Visuals per scene (demo/scenes.json):
    {"n": 1, "kind": "card", "card": "title"}
    {"n": 3, "kind": "replay", "from": null, "to": "[task] stage=1"}   # transcript window, by message text
    {"n": 6, "kind": "app"}                                            # a recording of the app the factory built
- Each scene's visuals are timed to its narration, then everything is joined with ffmpeg.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_replay  # noqa: E402
import voiceover  # noqa: E402

W, H = 1280, 720
CARD_CSS = """
body{margin:0;width:1280px;height:720px;display:grid;place-items:center;background:#0f1419;color:#e6edf3;
font-family:Inter,ui-sans-serif,system-ui,sans-serif}
.wrap{text-align:center;max-width:1040px} h1{font-size:72px;margin:8px 0 4px;letter-spacing:-.02em}
.tag{font-size:28px;color:#f7b733;font-weight:700} p{font-size:22px;color:#9fb0c0;margin:14px 0}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:22px;text-align:left}
.cell{background:#161c23;border:1px solid #2a3440;border-radius:14px;padding:16px}
.cell b{font-size:22px} .cell div{color:#9fb0c0;font-size:16px;margin-top:6px} .cell i{font-style:normal;font-size:13px;color:#f7b733}
.foot{margin-top:26px;font-size:18px;color:#8b98a5}
"""
CARDS = {
    "title": """<div class="wrap"><img src="capybara.svg" width="260"><h1>Onsen</h1>
      <div class="tag">A dark software factory on BAND</div><p>One rule: don't wake the capybara.</p></div>""",
    "crew": """<div class="wrap"><div class="tag">Six agents · one BAND room · one human message</div><div class="grid">
      <div class="cell"><b>Architect</b><div>plans, hands out stages</div><i>OpenCode · Qwen 3.8</i></div>
      <div class="cell"><b>Builder</b><div>builds each stage</div><i>OpenCode · Qwen 3.8</i></div>
      <div class="cell"><b>Reviewer</b><div>reads every diff, says no</div><i>OpenCode · read-only</i></div>
      <div class="cell"><b>Scout</b><div>asks the live web, not the human</div><i>Nimble web agents</i></div>
      <div class="cell"><b>Examiner</b><div>sealed, hidden exam</div><i>Qwen 3.8 + Playwright</i></div>
      <div class="cell"><b>Nap Guard</b><div>the only one who wakes you</div><i>deterministic</i></div>
      </div><div class="foot">Qwen 3.8 27B on W&amp;B Inference · BAND rooms · Nimble · ElevenLabs</div></div>""",
    "outro": """<div class="wrap"><img src="capybara.svg" width="220"><h1>Onsen</h1>
      <p>Specs go in. Software comes out. The capybara keeps napping.</p>
      <div class="foot">Built on BAND · with Nimble · Qwen 3.8 on W&amp;B</div></div>""",
}


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


async def render_card(name: str, out_png: Path) -> Path:
    from playwright.async_api import async_playwright

    html = out_png.with_suffix(".html")
    html.write_text(f"<!doctype html><meta charset=utf-8><style>{CARD_CSS}</style>{CARDS[name]}")
    shutil.copyfile(ROOT / "assets" / "capybara.svg", html.parent / "capybara.svg")
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": W, "height": H})
        await page.goto(html.resolve().as_uri())
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(out_png))
        await b.close()
    return out_png


async def record_app(url: str, out: Path, seconds: float) -> Path:
    """Drive the app the factory built, the way a visitor would, using only the spec's labels."""
    from playwright.async_api import async_playwright

    from screencast import screencast

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": W, "height": H})
        pause = max(600, int(seconds * 1000 / 9))

        async def attempt(coro):
            try:
                await coro
            except Exception as exc:  # noqa: BLE001 - a missing control just skips that beat
                print(f"  (skipped a step: {str(exc).splitlines()[0][:80]})")

        async def tour() -> None:
            await page.goto(url)
            await page.wait_for_timeout(pause)
            await attempt(page.get_by_label("Search spots").fill("izu"))
            await attempt(page.get_by_label("Search spots").press("Enter"))
            await page.wait_for_timeout(pause)
            await attempt(page.get_by_label("Search spots").fill(""))
            await attempt(page.get_by_label("Search spots").press("Enter"))
            await page.wait_for_timeout(pause // 2)
            await attempt(page.get_by_label("Country").select_option(label="JP"))
            await page.wait_for_timeout(pause)
            await attempt(page.get_by_label("Hot spring spots only").check())
            await page.wait_for_timeout(pause)
            await attempt(page.get_by_test_id("spot-card").first.get_by_role("link").first.click())
            await page.wait_for_timeout(pause * 2)
            await attempt(page.get_by_role("link", name="Back to all spots").click())
            await page.wait_for_timeout(pause)

        await screencast(page, tour, out.with_suffix(".mp4"))
        await b.close()
    return out.with_suffix(".mp4")


def mux(visual: Path, audio: Path, out: Path, seconds: float, still: bool) -> Path:
    if still:
        ffmpeg("-loop", "1", "-i", str(visual), "-i", str(audio), "-t", f"{seconds:.2f}",
               "-vf", f"scale={W}:{H},fps=30,format=yuv420p", "-af", "apad",
               "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", str(out))
    else:
        ffmpeg("-i", str(visual), "-i", str(audio), "-t", f"{seconds:.2f}",
               "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration=60,scale={W}:{H},fps=30,format=yuv420p[v];[1:a]apad[a]",
               "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", str(out))
    return out


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--scenes", default=str(ROOT / "demo" / "scenes.json"))
    ap.add_argument("--script", default=str(ROOT / "demo" / "script.md"))
    ap.add_argument("--app-url", default="http://localhost:8000")
    ap.add_argument("--work", default=str(ROOT / "demo" / "build"))
    ap.add_argument("--out", default=str(ROOT / "demo" / "onsen-demo.mp4"))
    ap.add_argument("--reuse-audio", action="store_true", help="don't re-synthesize narration that already exists")
    ap.add_argument("--silent", type=float, help="test mode: N seconds of silence instead of narration")
    ap.add_argument("--only", type=int, action="append", help="build only these scene numbers")
    args = ap.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    narration = {n: text for n, _title, text in voiceover.scenes(Path(args.script).read_text())}
    scenes = json.loads(Path(args.scenes).read_text())
    transcript = Path(args.transcript)
    msgs = json.loads(transcript.read_text())
    msgs.sort(key=lambda m: m.get("inserted_at") or "")
    parts: list[Path] = []
    cursor = -1
    for sc in scenes:
        n = sc["n"]
        audio = work / f"vo-{n:02d}.mp3"
        if args.silent:
            ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(args.silent), "-c:a", "libmp3lame", str(audio))
        elif not (args.reuse_audio and audio.exists()):
            voiceover.synthesize(narration[n], audio)
        if args.only and n not in args.only:
            if sc["kind"] == "replay" and sc.get("to"):
                start = cursor + 1 if sc.get("from") is None else make_replay.text_index(msgs, sc["from"])
                try:
                    cursor = make_replay.text_index(msgs, sc["to"], start - 1)
                except LookupError:
                    pass
            continue
        seconds = ffprobe_duration(audio) + 0.7
        part = work / f"scene-{n:02d}.mp4"
        print(f"scene {n} ({sc['kind']}): {seconds:.1f}s")
        if sc["kind"] == "card":
            png = asyncio.run(render_card(sc["card"], work / f"card-{n:02d}.png"))
            mux(png, audio, part, seconds, still=True)
        elif sc["kind"] == "replay":
            start = cursor + 1 if sc.get("from") is None else make_replay.text_index(msgs, sc["from"])
            end = make_replay.text_index(msgs, sc["to"], start - 1) if sc.get("to") else None
            if sc.get("to_last"):
                end = len([m for m in msgs if m.get("message_type", "text") == "text"]) - 1
            cursor = end if end is not None else cursor
            out_dir = work / f"replay-{n:02d}"
            html = make_replay.write_html(transcript, out_dir, sc.get("title", "Onsen · CapyFinder"), 1.0,
                                          sc.get("events", 2), sc.get("note", "Replay of the real BAND room transcript."),
                                          start=start, end=end, target_s=max(4.0, seconds - 2.0))
            video = asyncio.run(make_replay.record(html, out_dir / "replay.mp4", 1800))
            mux(video, audio, part, seconds, still=False)
        elif sc["kind"] == "app":
            video = asyncio.run(record_app(args.app_url, work / f"app-{n:02d}.mp4", seconds))
            mux(video, audio, part, seconds, still=False)
        parts.append(part)
    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(args.out))
    print(f"video: {args.out} ({ffprobe_duration(Path(args.out)):.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
