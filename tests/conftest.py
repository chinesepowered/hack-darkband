from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))

# Use the sandbox's preinstalled Chromium when present (cloud dev boxes); locally Playwright finds its own.
if Path("/opt/pw-browsers/chromium").exists():
    os.environ.setdefault("ONSEN_CHROMIUM_PATH", "/opt/pw-browsers/chromium")


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ONSEN_HOME", str(tmp_path / "onsen-home"))
    monkeypatch.setenv("ONSEN_EXAMINER_LLM", "off")
    monkeypatch.delenv("ONSEN_CHILL_ACTION", raising=False)
    return tmp_path


def participant(name: str, kind: str = "Agent", pid: str | None = None) -> dict:
    slug = name.lower().replace(" ", "-")
    return {"id": pid or f"id-{slug}", "name": name, "type": kind, "handle": f"me/{slug}" if kind == "Agent" else slug,
            "status": "active", "role": "member"}


CREW = [participant(n) for n in ("Architect", "Builder", "Reviewer", "Scout", "Examiner", "Nap Guard")] + [
    participant("Capy Human", kind="User", pid="id-human")
]


def message(content: str, sender: str, *, room: str = "room-1", kind: str = "Agent"):
    from band.core.types import PlatformMessage

    sender_id = "id-human" if kind == "User" else f"id-{sender.lower().replace(' ', '-')}"
    return PlatformMessage(id=f"m-{abs(hash(content)) % 10**8}", room_id=room, content=content, sender_id=sender_id,
                           sender_type=kind, sender_name=sender, message_type="text", metadata={},
                           created_at=datetime.now(UTC))


async def deliver(adapter, content: str, sender: str, tools, *, kind: str = "Agent", room: str = "room-1"):
    await adapter.on_message(message(content, sender, kind=kind, room=room), tools, [], None, None,
                             is_session_bootstrap=False, room_id=room)
