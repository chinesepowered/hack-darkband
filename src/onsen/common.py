"""Shared helpers for Onsen's SDK agents (Scout, Examiner, Nap Guard).

Conventions every agent follows:
- Credentials live OUTSIDE the repo (default ~/.onsen/agent_config.yaml) so the
  coding agents working in the product workspace can never read them.
- Messages start with a tag such as ``[exam]`` or ``[review]`` followed by
  ``key=value`` pairs. See crew/PROTOCOL.md. Tags make handoffs machine-readable
  without an LLM in the routing path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from band import Agent
from band.config.loader import load_agent_config
from band.runtime.formatters import strip_leading_mentions

REPO_ROOT = Path(__file__).resolve().parents[2]

# Display names of the crew. Override with env vars if you name agents differently.
NAMES = {
    "architect": os.environ.get("ONSEN_ARCHITECT_NAME", "Architect"),
    "builder": os.environ.get("ONSEN_BUILDER_NAME", "Builder"),
    "reviewer": os.environ.get("ONSEN_REVIEWER_NAME", "Reviewer"),
    "scout": os.environ.get("ONSEN_SCOUT_NAME", "Scout"),
    "examiner": os.environ.get("ONSEN_EXAMINER_NAME", "Examiner"),
    "napguard": os.environ.get("ONSEN_NAPGUARD_NAME", "Nap Guard"),
}

TAG_RE = re.compile(r"^\s*\[([a-z][a-z0-9_-]*)\]\s*", re.IGNORECASE)


def onsen_home() -> Path:
    home = Path(os.environ.get("ONSEN_HOME", Path.home() / ".onsen")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return home


def state_dir(*parts: str) -> Path:
    path = onsen_home().joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_env() -> None:
    """Load .env from ONSEN_ENV_FILE or the repo root. Never overrides real env vars."""
    env_file = os.environ.get("ONSEN_ENV_FILE")
    load_dotenv(env_file or REPO_ROOT / ".env", override=False)


def agent_config_path() -> Path:
    return Path(
        os.environ.get("ONSEN_AGENT_CONFIG", onsen_home() / "agent_config.yaml")
    ).expanduser()


def build_agent(key: str, adapter: Any) -> Agent:
    """Create a BAND Agent from the keyed agent_config.yaml entry ``key``."""
    agent_id, api_key = load_agent_config(key, config_path=agent_config_path())
    return Agent.create(adapter=adapter, agent_id=agent_id, api_key=api_key)


def run_agent(agent: Agent) -> None:
    logging.basicConfig(
        level=os.environ.get("ONSEN_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    asyncio.run(agent.run())


def command_text(content: str | None) -> str:
    """Message text with the platform's leading @mention block removed."""
    return strip_leading_mentions(content or "").strip()


def parse_tagged(text: str) -> tuple[str | None, str]:
    """Split ``[tag] rest`` into ("tag", "rest"). Returns (None, text) if untagged."""
    m = TAG_RE.match(text)
    if not m:
        return None, text.strip()
    return m.group(1).lower(), text[m.end() :].strip()


KV_RE = re.compile(r"""(\w[\w.-]*)=("[^"]*"|'[^']*'|\S+)""")


def parse_kv(text: str) -> dict[str, str]:
    """Parse ``key=value`` pairs (values may be quoted) from free text."""
    out: dict[str, str] = {}
    for key, raw in KV_RE.findall(text):
        value = raw
        if raw[:1] in "\"'":
            try:
                value = shlex.split(raw)[0]
            except ValueError:
                value = raw.strip("\"'")
        out[key.lower()] = value
    return out


def first_line(text: str, limit: int = 160) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return line if len(line) <= limit else line[: limit - 1] + "…"


def clip(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def humans(participants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in participants if str(p.get("type") or "").lower() == "user"]


def find_participant(participants: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    wanted = name.lower().lstrip("@")
    for p in participants:
        handle = str(p.get("handle") or "").lower().lstrip("@")
        if (p.get("name") or "").lower() == wanted or handle == wanted or handle.endswith("/" + wanted):
            return p
    return None


class JsonState:
    """Tiny JSON-file-backed dict, one file per (agent, room). Survives restarts."""

    def __init__(self, agent: str, room_id: str, default: dict[str, Any]):
        safe_room = re.sub(r"[^A-Za-z0-9_.-]", "_", room_id)
        self.path = state_dir("state") / f"{agent}-{safe_room}.json"
        self.data: dict[str, Any] = default
        if self.path.exists():
            try:
                self.data = {**default, **json.loads(self.path.read_text())}
            except (OSError, json.JSONDecodeError):
                pass

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True, default=str))
        tmp.replace(self.path)


def now() -> float:
    return time.time()


def fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"
