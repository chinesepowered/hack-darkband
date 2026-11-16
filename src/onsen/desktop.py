"""Run the coding crew (Architect, Builder, Reviewer) as BAND Desktop agents.

BAND Desktop's daemon (jamd) owns each crew agent's OpenCode runtime. When a room message mentions the agent, the
daemon starts OpenCode through ``opencode/bin/onsen-opencode-<role>`` (Qwen 3.8 on W&B, the role's permission
profile), hands it the message, and posts what the agent says back to the room. Scout, the Examiner and Nap Guard stay
band-sdk agents (``onsen-scout``, ``onsen-examiner``, ``onsen-nap-guard``).

    uv run onsen-desktop prepare --workspace <run folder>   # before each run: instructions + working directory
    uv run onsen-desktop status

One-time setup is in docs/band-desktop.md: adopt the three crew agents into BAND Desktop (``band adopt``) and give
each an OpenCode runtime in its Runtime tab. They keep their BAND identities, so past rooms still show them.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import httpx
import yaml

from .common import NAMES, REPO_ROOT, agent_config_path, load_env, onsen_home
from .crew import instructions
from .watch import API

CREW = ("architect", "builder", "reviewer")
ROLES = ("architect", "builder", "reviewer", "scout", "examiner", "napguard")


def scope(role: str) -> str:
    """The local peer name each crew agent was adopted under (``band adopt --session onsen-<role>``)."""
    return f"onsen-{role}"


def handles() -> dict[str, str]:
    """Each agent's BAND handle (owner/slug), asked of BAND with the agent's own key."""
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    out: dict[str, str] = {}
    with httpx.Client(base_url=API, timeout=30) as c:
        for role in ROLES:
            key = (cfg.get(role) or {}).get("api_key")
            if not key:
                continue
            r = c.get("/api/v1/agent/me", headers={"X-API-Key": key})
            if r.status_code < 400:
                out[role] = r.json()["data"]["handle"]
    return out


DESKTOP_NOTES = """
## Working in BAND Desktop

You run inside BAND Desktop. Everyone in the room, and how to mention them:

{roster}

How to talk in the room:
- Send every protocol message yourself with BAND's send command (your BAND briefing shows it with this room's id):
  `band ... send <room> "@handle @handle [tag] key=value … free text"`. Put the handles first, then the tag line.
  "Post X to @Examiner and @Reviewer" in these instructions means one `band send` that starts with both handles.
- Only `band send` speaks for you. Onsen's launcher keeps the text you end a turn with out of the room, so you never
  need to stay silent. Finish each turn normally; a one-line note is fine. Don't put protocol messages in that
  closing text; send them.
- If the message that woke you needs nothing from you, just finish the turn.
- Never mention the human. Only Nap Guard wakes the capybara.
- For multi-line messages, write the body to a file in the workspace and use `--body-file`.
"""


def roster_table(hs: dict[str, str]) -> str:
    rows = ["| Agent | Mention it as |", "|---|---|"]
    rows += [f"| {NAMES[r]} | `@{hs[r]}` |" for r in ROLES if r in hs]
    return "\n".join(rows)


def instructions_text(role: str, hs: dict[str, str]) -> str:
    return instructions(role).rstrip() + "\n" + DESKTOP_NOTES.format(roster=roster_table(hs))


def band(*args: str, check: bool = True) -> str:
    exe = shutil.which("band")
    if not exe:
        raise SystemExit("The `band` CLI isn't on PATH. Install BAND Desktop first (docs/band-desktop.md).")
    p = subprocess.run([exe, *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"band {' '.join(args)} failed: {(p.stderr or p.stdout).strip()[:400]}")
    return p.stdout


def prepare(workspace: Path) -> None:
    """Write each crew agent's instructions and point its runtime at this run's workspace."""
    hs = handles()
    out = onsen_home() / "desktop"
    out.mkdir(parents=True, exist_ok=True)
    for role in CREW:
        f = out / f"{role}.md"
        f.write_text(instructions_text(role, hs))
        band("agent", "instructions", "set", "--session", scope(role), "--instructions-file", str(f))
        band("runtime", "template", "set", "--session", scope(role), "--spawn-cwd", str(workspace),
             "--apply-and-restart")
        # --apply-and-restart leaves a stopped worker stopped (stop-factory.sh stops them), so start it here.
        # It can report stale rooms from older runs; the worker still starts.
        band("restart", "--session", scope(role), check=False)
        print(f"✔ {NAMES[role]} ({hs.get(role, '?')}): instructions {f.name}, working directory {workspace}")


def status() -> None:
    print(band("daemon", "status", check=False).strip())
    print(band("list", check=False).strip())


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="write instructions and set each crew agent's working directory")
    p.add_argument("--workspace", required=True)
    sub.add_parser("status", help="show the BAND Desktop daemon and the local crew agents")
    w = sub.add_parser("instructions", help="print (or --write) the generated instructions for each crew agent")
    w.add_argument("--write", action="store_true", help="rewrite the live-linked files only; no restart")
    args = ap.parse_args(argv)
    if args.cmd == "prepare":
        prepare(Path(args.workspace).resolve())
    elif args.cmd == "status":
        status()
    else:
        hs = handles()
        for role in CREW:
            if args.write:
                (onsen_home() / "desktop" / f"{role}.md").write_text(instructions_text(role, hs))
                print(f"rewrote {role}.md")
            else:
                print(f"===== {NAMES[role]} =====\n{instructions_text(role, hs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["CREW", "instructions_text", "prepare", "scope", "REPO_ROOT"]
