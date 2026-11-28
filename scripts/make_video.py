"""Assemble the demo video from a real factory run.

    uv run python scripts/make_video.py --transcript ~/.onsen/transcripts/<run>.json \
        --scenes demo/scenes.json --app-url http://localhost:8000 --out demo/onsen-demo.mp4

- Narration: the `> VO:` lines of demo/script.md, one ElevenLabs clip per scene (voice: Jessica).
- Visuals per scene (demo/scenes.json):
    {"n": 1, "kind": "card", "card": "title"}
    {"n": 3, "kind": "replay", "from": null, "to": "[task] stage=1"}   # transcript window, by message text
    {"n": 6, "kind": "clip", "file": "rec.mkv", "start": 760, "end": 1000, "crop": "1180:900:0:0", "label": "…"}
                                                                       # a screen recording, sped up, in a window
    {"n": 7, "kind": "app"}                                            # a recording of the app the factory built
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
# One look for every card: a night onsen (deep teal-navy), cream type, yuzu-orange accents, faint steam.
CARD_CSS = """
*{box-sizing:border-box}
body{margin:0;width:1280px;height:720px;display:grid;place-items:center;overflow:hidden;position:relative;color:#fff6e8;
  font-family:Inter,ui-sans-serif,system-ui,sans-serif;
  background:radial-gradient(1100px 620px at 50% 118%,#1d4a5e 0%,#122a3a 48%,#0b1620 100%)}
.steam{position:absolute;inset:0;pointer-events:none;opacity:.055}
.wrap{position:relative;text-align:center;max-width:1100px}
.wide{max-width:1180px;width:1180px}
h1{font-family:'Inter Display',Inter,sans-serif;font-size:112px;font-weight:800;letter-spacing:-.035em;margin:6px 0 2px;color:#fff6e8}
.tag{font-family:'Inter Display',Inter,sans-serif;font-size:36px;font-weight:700;color:#ffb84d;letter-spacing:-.01em}
.sub{font-size:26px;color:#a9c0cf;margin:14px 0 0}
.halo{display:inline-block;padding:18px;border-radius:50%;
  background:radial-gradient(circle,rgba(155,231,242,.22) 0%,rgba(155,231,242,.06) 55%,rgba(155,231,242,0) 70%)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:30px;text-align:left}
.cell{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.09);border-radius:20px;padding:20px 22px;
  display:grid;grid-template-columns:56px 1fr;column-gap:16px;align-items:center}
.av{width:56px;height:56px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:22px;color:#1a1a1a;grid-row:span 3}
.cell b{font-size:28px;font-weight:700;letter-spacing:-.01em}
.cell .what{font-size:19px;color:#c6d4de;margin-top:2px}
.chip{display:inline-block;margin-top:8px;font-size:15px;font-weight:600;color:#ffcf85;background:rgba(255,184,77,.12);
  border:1px solid rgba(255,184,77,.28);border-radius:999px;padding:3px 11px;width:max-content}
.foot{margin-top:26px;font-size:20px;color:#8fa6b6}
.grid.five{grid-template-columns:repeat(6,1fr)}.grid.five .cell{grid-column:span 2}
.grid.five .cell:nth-child(4){grid-column:2 / span 2}
.rows code,.cell code{white-space:nowrap}
.corner{position:absolute;right:34px;bottom:30px;width:78px;height:78px}
.shot{border-radius:16px;border:1px solid rgba(255,255,255,.14);box-shadow:0 18px 50px rgba(0,0,0,.45)}
.chips{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:24px}
.chips span{font-size:18px;font-weight:600;color:#fff6e8;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);
  border-radius:999px;padding:8px 18px}
.rows{margin-top:26px;display:grid;gap:14px;text-align:left}
.row{display:grid;grid-template-columns:150px 1fr;gap:18px;align-items:center;background:rgba(255,255,255,.055);
  border:1px solid rgba(255,255,255,.09);border-radius:18px;padding:16px 22px}
.pill{font-family:'Inter Display',Inter,sans-serif;font-weight:800;font-size:22px;color:#1a1208;background:#ffb84d;border-radius:999px;
  padding:6px 0;text-align:center}
.row div{font-size:22px;line-height:1.35;color:#e9eef2}
.row em{font-style:normal;color:#7ee2b8}
code{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:.9em;background:rgba(0,0,0,.35);padding:1px 8px;border-radius:7px;color:#ffcf85}
.url{margin-top:22px;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:22px;color:#9be7f2}
"""
STEAM = """<svg class="steam" viewBox="0 0 1280 720" preserveAspectRatio="none"><g fill="none" stroke="#ffffff" stroke-width="16"
  stroke-linecap="round"><path d="M120 720c-40-60 40-110 0-170s40-110 0-170"/><path d="M1160 720c-40-60 40-110 0-170s40-110 0-170"/>
  <path d="M300 720c-30-50 30-90 0-140"/><path d="M980 720c-30-50 30-90 0-140"/></g></svg>"""


def _agent(initials: str, color: str, name: str, what: str, chip: str) -> str:
    return (f'<div class="cell"><div class="av" style="background:{color}">{initials}</div><b>{name}</b>'
            f'<div class="what">{what}</div><span class="chip">{chip}</span></div>')


CARDS = {
    "title": STEAM + """<div class="wrap"><div class="halo"><img src="capybara.svg" width="300"></div><h1>Onsen</h1>
      <div class="tag">A dark software factory on BAND</div><div class="sub">One rule: don't wake the capybara.</div></div>""",
    "crew": STEAM + '<div class="wrap wide"><div class="tag">Five seats · one BAND room · one human message</div><div class="grid five">'
      + _agent("A", "#f2cc60", "Architect", "plans, hands off whole stages", "BAND Desktop · OpenCode")
      + _agent("B", "#d2a8ff", "Builder", "writes every line of the service", "BAND Desktop · OpenCode")
      + _agent("E", "#ff7b72", "Examiner", "keeps a sealed, executable exam", "BAND Desktop · OpenCode")
      + _agent("R", "#79c0ff", "Reviewer", "reads every diff, can say no", "BAND Desktop · read-only")
      + _agent("NG", "#ffa657", "Nap Guard", "gates each stage; runs the checker itself", "band-sdk · no model")
      + """</div><div class="foot">Every coding seat: GPT-6 Luna through OpenCode, in BAND Desktop</div></div>
      <img class="corner" src="capybara-badge.svg">""",
    "desktop": STEAM + """<div class="wrap wide"><div class="tag">BAND Desktop runs the four coding seats</div>
      <div class="sub" style="margin-bottom:24px">Its daemon starts each seat's OpenCode runtime the moment a message mentions it.</div>
      <img class="shot" src="desktop-agents.png" style="width:1120px">
      <div class="chips"><span>🧑‍💻 OpenCode runtime per seat</span><span>🌙 GPT-6 Luna</span>
      <span>🔒 permissions per role</span><span>👀 live reasoning · Interrupt</span></div></div>
      <img class="corner" src="capybara-badge.svg">""",
    "gate": STEAM + """<div class="wrap wide" style="max-width:1080px;width:1080px"><div class="tag">No seat's word opens the gate</div>
      <div class="rows">
      <div class="row"><span class="pill">exam</span><div>The Examiner's checks are code, sealed by hash before any build exists.
        <em><code>onsen-exam</code> runs them and computes the verdict.</em></div></div>
      <div class="row"><span class="pill">review</span><div>The Reviewer reads the diff against the spec and probes the running commit.
        <em>Its seat can't edit or commit.</em></div></div>
      <div class="row"><span class="pill">gate</span><div>Nap Guard recounts the exam, then runs the event's checker on that exact commit itself.
        <em>Only then is the stage in.</em></div></div>
      </div></div><img class="corner" src="capybara-badge.svg">""",
    "lessons": STEAM + """<div class="wrap wide" style="max-width:1080px;width:1080px"><div class="tag">What the practice runs taught the factory</div>
      <div class="rows">
      <div class="row"><span class="pill">Exam</span><div>A model Examiner reported 26 checks after running one.
        <em>Verdicts are computed by tools now.</em></div></div>
      <div class="row"><span class="pill">Room</span><div>Seats argued by re-posting, and the gatekeeper counted every repeat.
        <em>A linter on <code>band send</code>: one tag owner, one verdict per commit.</em></div></div>
      <div class="row"><span class="pill">Closed</span><div>A Builder kept polishing a stage after it was accepted.
        <em>Accepted stages close: the repository refuses the commit.</em></div></div>
      <div class="row"><span class="pill">Hang</span><div>A busy-looping service froze the checker for everyone.
        <em>Checks are capped and say why.</em></div></div>
      </div></div><img class="corner" src="capybara-badge.svg">""",
    "outro": STEAM + """<div class="wrap"><div class="halo"><img src="capybara.svg" width="250"></div><h1>Onsen</h1>
      <div class="sub" style="color:#fff6e8;font-size:30px">Specs go in. Software comes out. The capybara keeps napping.</div>
      <div class="foot">Built on BAND · researched with Nimble · GPT-6 Luna via OpenCode</div>
      <div class="url">github.com/chinesepowered/hack-darkband</div></div>""",
}
# Recordings shown inside a window on the card background: the app as the factory built it, and BAND Desktop.
APP_X, APP_Y, APP_W, APP_H = 90, 84, 1100, 600
CLIP_Y, CLIP_H = 84, 600


def window_frame(x: int, y: int, w: int, h: int, title: str) -> str:
    """A window chrome whose content area sits exactly at (x, y, w, h); the recording is overlaid there."""
    return STEAM + f"""<div style="position:absolute;left:{x - 10}px;top:{y - 46}px;width:{w + 20}px;height:{h + 56}px;
  border-radius:16px;background:#e9edf1;box-shadow:0 24px 60px rgba(0,0,0,.5);border:1px solid rgba(255,255,255,.25)">
  <div style="height:46px;display:flex;align-items:center;gap:9px;padding:0 18px">
    <i style="width:13px;height:13px;border-radius:50%;background:#ff5f57"></i><i style="width:13px;height:13px;border-radius:50%;background:#febc2e"></i>
    <i style="width:13px;height:13px;border-radius:50%;background:#28c840"></i>
    <div style="margin-left:18px;flex:1;height:28px;border-radius:9px;background:#fff;display:flex;align-items:center;gap:8px;padding:0 10px;
      font:15px Inter,sans-serif;color:#3b4652;white-space:nowrap;overflow:hidden"><img src="capybara-badge.svg" width="18"> {title}</div>
  </div></div>"""


APP_FRAME = window_frame(APP_X, APP_Y, APP_W, APP_H, "Dossier, as the factory built it")


def ffmpeg_probe_width(path: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return int(out.stdout.strip())


def ffprobe_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


NUMBERS_CSS = """
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:34px}
.stat{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.09);border-radius:22px;padding:26px 18px}
.stat .v{font-family:'Inter Display',Inter,sans-serif;font-size:64px;font-weight:800;color:#fff6e8;letter-spacing:-.02em}
.stat .l{font-size:19px;color:#a9c0cf;margin-top:6px}
"""


def numbers_card() -> str:
    """The judged run's numbers, from the facts file the slides use (ONSEN_FACTS), so the video states only what the run
    measured: the highest stage claimed, the hours, the model spend, and the human's one message."""
    f = json.loads(Path(os.environ["ONSEN_FACTS"]).read_text())
    top = max((st["n"] for st in f.get("stages", []) if st.get("claimed")), default=0)
    tiles = [(str(top), "stages accepted"), (f.get("hours_text", "—"), "start to report"),
             (f.get("spend_short", "—"), "model spend"), (str(f.get("human_inputs", 1)), "human message")]
    cells = "".join(f'<div class="stat"><div class="v">{v}</div><div class="l">{label}</div></div>' for v, label in tiles)
    return (STEAM + f"<style>{NUMBERS_CSS}</style>"
            '<div class="wrap wide"><div class="tag">The judged run, in numbers</div>'
            f'<div class="stats">{cells}</div>'
            f'<div class="foot">{f.get("numbers_foot", "")}</div></div><img class="corner" src="capybara-badge.svg">')


async def render_card(name: str, out_png: Path) -> Path:
    from playwright.async_api import async_playwright

    html = out_png.with_suffix(".html")
    html.parent.mkdir(parents=True, exist_ok=True)
    body = numbers_card() if name == "numbers" else (CARDS.get(name) or name)
    html.write_text(f"<!doctype html><meta charset=utf-8><style>{CARD_CSS}</style>{body}")
    shutil.copyfile(ROOT / "assets" / "capybara.svg", html.parent / "capybara.svg")
    shutil.copyfile(ROOT / "assets" / "capybara-badge.svg", html.parent / "capybara-badge.svg")
    assets = os.environ.get("ONSEN_CARD_ASSETS")  # e.g. BAND Desktop screenshots for the "desktop" card
    if assets:
        for f in Path(assets).glob("*.png"):
            shutil.copyfile(f, html.parent / f.name)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": W, "height": H})
        await page.goto(html.resolve().as_uri())
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(out_png))
        await b.close()
    return out_png


async def record_app(url: str, out: Path, seconds: float) -> Path:
    """Drive the service the band built the way a reader would, through the spec's own element ids (`data-testid`):
    sign in, the dossier list and its search, one dossier with its citations, its evidence, the contested fields.

    The account and the dossiers come from `scripts/app_demo.py prepare`, which writes ONSEN_APP_DEMO (a JSON file with
    the email, password and the domains it researched), so the tour shows finished dossiers rather than a build."""
    from playwright.async_api import async_playwright

    from screencast import screencast

    demo = json.loads(Path(os.environ["ONSEN_APP_DEMO"]).read_text())
    domains = demo.get("domains") or []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": APP_W, "height": APP_H})
        pause = max(700, int(seconds * 1000 / 10))
        tid = page.get_by_test_id

        async def attempt(coro):
            try:
                await coro
            except Exception as exc:  # noqa: BLE001 - a missing control just skips that beat
                print(f"  (skipped a step: {str(exc).splitlines()[0][:80]})")

        async def tour() -> None:
            await page.goto(url.rstrip("/") + "/login")
            await page.wait_for_timeout(pause // 2)
            await attempt(tid("login-email").fill(demo["email"]))
            await attempt(tid("login-password").fill(demo["password"]))
            await attempt(tid("login-submit").click())
            await page.wait_for_timeout(pause)
            await attempt(page.goto(url.rstrip("/") + "/"))
            await page.wait_for_timeout(pause)
            if len(domains) > 1:
                await attempt(tid("dossier-search").fill(domains[1].split(".")[0][:4]))
                await page.wait_for_timeout(pause)
                await attempt(tid("dossier-search").fill(""))
                await page.wait_for_timeout(pause // 2)
            if domains:
                await attempt(tid(f"dossier-item-{domains[0]}").click())
                await page.wait_for_timeout(pause * 2)
                await attempt(page.mouse.wheel(0, 500))
                await page.wait_for_timeout(pause)
                await attempt(tid("dossier-evidence-link").click())
                await page.wait_for_timeout(pause * 2)
                await attempt(page.mouse.wheel(0, 600))
                await page.wait_for_timeout(pause)
            await attempt(page.goto(url.rstrip("/") + "/contested"))
            await page.wait_for_timeout(pause * 2)

        await screencast(page, tour, out.with_suffix(".mp4"), width=APP_W, height=APP_H)
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
        elif sc["kind"] == "clip":
            # {"kind": "clip", "file": "rec.mkv", "start": 760, "end": 1000, "crop": "1180:900:0:0"}: a stretch of a
            # screen recording (e.g. BAND Desktop during the run), sped up to fill the narration.
            src = Path(os.path.expandvars(sc["file"]))
            span = float(sc["end"]) - float(sc["start"])
            speed = max(1.0, span / seconds)
            crop = f"crop={sc['crop']}," if sc.get("crop") else ""
            raw = work / f"clip-raw-{n:02d}.mp4"
            ffmpeg("-ss", str(sc["start"]), "-t", f"{span:.2f}", "-i", str(src),
                   "-vf", f"{crop}scale=-2:{CLIP_H},setpts=PTS/{speed:.4f},fps=30,format=yuv420p",
                   "-an", "-c:v", "libx264", str(raw))
            cw = int(ffmpeg_probe_width(raw))
            # "speed_label" describes a clip that was cut beforehand (held frames, a sped-up scroll) better than one figure
            label = sc.get("label", "BAND Desktop · the room, live") + sc.get("speed_label", f" · {speed:.0f}× speed")
            frame = asyncio.run(render_card(window_frame((W - cw) // 2, CLIP_Y, cw, CLIP_H, label), work / f"clip-frame-{n:02d}.png"))
            video = work / f"clip-{n:02d}.mp4"
            ffmpeg("-loop", "1", "-i", str(frame), "-i", str(raw), "-filter_complex",
                   f"[0:v][1:v]overlay={(W - cw) // 2}:{CLIP_Y}:shortest=1,fps=30,format=yuv420p", "-c:v", "libx264", str(video))
            mux(video, audio, part, seconds, still=False)
        elif sc["kind"] == "app":
            raw = asyncio.run(record_app(args.app_url, work / f"app-{n:02d}.mp4", seconds))
            frame = asyncio.run(render_card(APP_FRAME, work / f"app-frame-{n:02d}.png"))
            video = work / f"app-framed-{n:02d}.mp4"
            ffmpeg("-loop", "1", "-i", str(frame), "-i", str(raw), "-filter_complex",
                   f"[1:v]scale={APP_W}:{APP_H}[app];[0:v][app]overlay={APP_X}:{APP_Y}:shortest=1,fps=30,format=yuv420p",
                   "-c:v", "libx264", str(video))
            mux(video, audio, part, seconds, still=False)
        parts.append(part)
    listing = work / "parts.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(args.out))
    print(f"video: {args.out} ({ffprobe_duration(Path(args.out)):.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
