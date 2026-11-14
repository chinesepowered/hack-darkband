"""Record a Playwright page to MP4 with Chrome's own screencast + the system ffmpeg.

Frames arrive only when the page changes; each frame keeps its real timestamp, so the video's timing
matches what happened on screen. No Playwright ffmpeg download needed.
"""

from __future__ import annotations

import asyncio
import base64
import shutil
import subprocess
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


async def screencast(page: Any, action: Callable[[], Awaitable[Any]], out: Path, *, width: int = 1280,
                     height: int = 720, tail_s: float = 1.0) -> Path:
    tmp = out.parent / f"_frames_{out.stem}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    frames: list[tuple[float, Path]] = []
    cdp = await page.context.new_cdp_session(page)

    async def on_frame(params: dict[str, Any]) -> None:
        path = tmp / f"f{len(frames):06d}.jpg"
        path.write_bytes(base64.b64decode(params["data"]))
        frames.append((float(params["metadata"].get("timestamp") or time.time()), path))
        try:
            await cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
        except Exception:  # noqa: BLE001 - the page may be closing
            pass

    cdp.on("Page.screencastFrame", lambda p: asyncio.ensure_future(on_frame(p)))
    await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": width,
                                            "maxHeight": height, "everyNthFrame": 1})
    await action()
    await asyncio.sleep(tail_s)
    end = time.time()
    await cdp.send("Page.stopScreencast")
    await asyncio.sleep(0.2)
    if not frames:
        raise RuntimeError("the page produced no frames")
    lines = []
    for i, (ts, path) in enumerate(frames):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else max(end, ts + 0.04)
        lines.append(f"file '{path.resolve()}'\nduration {max(0.001, nxt - ts):.3f}\n")
    lines.append(f"file '{frames[-1][1].resolve()}'\n")
    listing = tmp / "frames.txt"
    listing.write_text("".join(lines))
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return out
