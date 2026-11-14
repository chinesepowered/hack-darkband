"""Run one member of the coding crew as an OpenCode agent in BAND.

    uv run onsen-crew architect      # or: builder | reviewer | auditor

Each role is its own BAND agent identity, with its own OpenCode session per room, on one shared
`opencode serve` that works in the product workspace (ONSEN_WORKSPACE). The model comes from
opencode.json (Qwen 3.8 27B on W&B Inference by default). The role's instructions are the
"Instructions" section of crew/<role>.md, and its OpenCode agent profile sets its permissions:
the Reviewer and Auditor can't edit files.
"""

from __future__ import annotations

import os
import re
import sys

from band.adapters import OpencodeAdapter, OpencodeAdapterConfig

from .common import REPO_ROOT, build_agent, load_env, run_agent

ROLES: dict[str, dict[str, object]] = {
    "architect": {"profile": "onsen-architect", "timeout": 1200.0},
    "builder": {"profile": "onsen-builder", "timeout": 2400.0},
    "reviewer": {"profile": "onsen-reviewer", "timeout": 1200.0},
    "auditor": {"profile": "onsen-reviewer", "timeout": 900.0, "file": "accessibility-auditor"},
}


def instructions(role: str) -> str:
    name = str(ROLES[role].get("file", role))
    text = (REPO_ROOT / "crew" / f"{name}.md").read_text()
    m = re.search(r"^## Instructions[^\n]*\n(.+)", text, re.S | re.M)
    body = (m.group(1) if m else text).strip()
    protocol = (REPO_ROOT / "crew" / "PROTOCOL.md").read_text()
    return f"{body}\n\n---\n{protocol}"


def build_adapter(role: str) -> OpencodeAdapter:
    workspace = os.environ.get("ONSEN_WORKSPACE")
    if not workspace:
        raise SystemExit("Set ONSEN_WORKSPACE to the product workspace (scripts/new-run.sh prints it)")
    cfg = OpencodeAdapterConfig(
        base_url=os.environ.get("ONSEN_OPENCODE_URL", "http://127.0.0.1:4096"),
        directory=workspace,
        provider_id=os.environ.get("ONSEN_OPENCODE_PROVIDER", "wandb"),
        model_id=os.environ.get("ONSEN_LLM_MODEL", "Qwen/Qwen3.8-27B"),
        agent=str(ROLES[role]["profile"]),
        custom_section=instructions(role),
        include_base_instructions=True,
        # A dark factory: nobody is there to click "approve". Permissions are enforced by each
        # role's OpenCode profile instead (the Reviewer's profile denies edits).
        approval_mode="auto_accept",
        question_mode="auto_reject",
        turn_timeout_s=float(ROLES[role]["timeout"]),  # type: ignore[arg-type]
        session_title_prefix=f"Onsen {role}",
    )
    return OpencodeAdapter(config=cfg)


def main() -> None:
    load_env()
    if len(sys.argv) != 2 or sys.argv[1] not in ROLES:
        raise SystemExit(f"usage: onsen-crew {{{'|'.join(ROLES)}}}")
    role = sys.argv[1]
    run_agent(build_agent(role, build_adapter(role)))


if __name__ == "__main__":
    main()
