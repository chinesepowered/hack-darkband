"""Render assets/social-preview.png (1280x640): the README banner and GitHub's social preview image.

    uv run python scripts/make_social_preview.py

It uses the video cards' look (scripts/make_video.py) and the mascot in assets/capybara.svg.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import make_video  # noqa: E402

EXTRA_CSS = """
body{width:1280px;height:640px;place-items:center}
.hero{display:grid;grid-template-columns:420px 1fr;align-items:center;gap:34px;text-align:left;width:1120px}
.hero h1{font-size:120px;margin:0} .hero .tag{font-size:38px} .hero .sub{font-size:28px}
.badges{display:flex;gap:10px;margin-top:26px}
.badges span{font-size:19px;font-weight:600;padding:7px 16px;border-radius:999px;background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.13);color:#fff6e8}
"""


def html() -> str:
    # Inline the SVG: a page built from a string can't load local files.
    svg = (ROOT / "assets" / "capybara.svg").read_text().replace("<svg ", '<svg width="380" height="380" ', 1)
    return (f"<!doctype html><meta charset=utf-8><style>{make_video.CARD_CSS}{EXTRA_CSS}</style>{make_video.STEAM}"
            f'<div class="hero"><div class="halo">{svg}</div><div><h1>Onsen</h1>'
            '<div class="tag">A dark software factory on BAND</div><div class="sub">One rule: don\'t wake the capybara.</div>'
            '<div class="badges"><span>BAND Desktop</span><span>Nimble</span><span>Qwen 3.8 on W&amp;B</span>'
            "<span>a sealed exam</span></div></div></div>")


async def main() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("ONSEN_CHROMIUM_PATH") or None, args=["--no-sandbox"])
        page = await b.new_page(viewport={"width": 1280, "height": 640})
        await page.set_content(html())
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(ROOT / "assets" / "social-preview.png"))
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
    print("assets/social-preview.png")
