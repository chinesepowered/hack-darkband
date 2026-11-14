"""Turn the `> VO:` lines in demo/script.md into MP3s with ElevenLabs.

    uv run python scripts/voiceover.py              # every scene -> demo/vo/NN-title.mp3
    uv run python scripts/voiceover.py --only 1     # one scene
    uv run python scripts/voiceover.py --dry-run    # count characters, call nothing

Needs ELEVENLABS_API_KEY. Default voice: Jessica (young, bright, warm). Override with --voice <voice_id>.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SCENE_RE = re.compile(r"^###\s+(\d+)\.\s+(.+?)\s*(?:\(.*\))?\s*$", re.M)
VO_RE = re.compile(r"^>\s*VO:\s*(.+)$", re.M)
JESSICA = "cgSgspJ2msm6clMCkdW9"


def scenes(script: str) -> list[tuple[int, str, str]]:
    heads = list(SCENE_RE.finditer(script))
    out = []
    for i, h in enumerate(heads):
        body = script[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(script)]
        vo = " ".join(m.group(1).strip() for m in VO_RE.finditer(body))
        if vo:
            out.append((int(h.group(1)), h.group(2).strip(), vo))
    return out


def synthesize(text: str, out: Path, *, voice: str = JESSICA, model: str = "eleven_v4", key: str | None = None) -> Path:
    """One narration clip. Used by make_video.py too."""
    key = key or os.environ["ELEVENLABS_API_KEY"]
    with httpx.Client(base_url="https://api.elevenlabs.io", headers={"xi-api-key": key}, timeout=120) as c:
        r = c.post(f"/v1/text-to-speech/{voice}", params={"output_format": "mp3_44100_128"},
                   json={"text": text, "model_id": model,
                         "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35}})
        r.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)
    return out


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=str(ROOT / "demo" / "script.md"))
    ap.add_argument("--out", default=str(ROOT / "demo" / "vo"))
    ap.add_argument("--voice", default=os.environ.get("ONSEN_VO_VOICE", JESSICA))
    ap.add_argument("--model", default=os.environ.get("ONSEN_VO_MODEL", "eleven_v4"))
    ap.add_argument("--only", type=int, action="append")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = [s for s in scenes(Path(args.script).read_text()) if not args.only or s[0] in args.only]
    total = sum(len(t) for _, _, t in items)
    print(f"{len(items)} scene(s), {total} characters, voice {args.voice}, model {args.model}")
    if args.dry_run:
        return 0
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        print("Set ELEVENLABS_API_KEY", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url="https://api.elevenlabs.io", headers={"xi-api-key": key}, timeout=120) as c:
        for n, title, text in items:
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            r = c.post(f"/v1/text-to-speech/{args.voice}", params={"output_format": "mp3_44100_128"},
                       json={"text": text, "model_id": args.model,
                             "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35}})
            if r.status_code >= 400:
                print(f"✘ scene {n}: HTTP {r.status_code} {r.text[:200]}", file=sys.stderr)
                return 1
            path = out / f"{n:02d}-{slug}.mp3"
            path.write_bytes(r.content)
            shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            print(f"✔ {shown} ({len(r.content) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
