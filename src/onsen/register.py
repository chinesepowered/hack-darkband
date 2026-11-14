"""Register Onsen's SDK agents on BAND and store their keys OUTSIDE the repo.

    uv run onsen-register                  # scout, examiner, napguard
    uv run onsen-register --only scout
    uv run onsen-register --check          # show plan limits and existing agents only

Needs BAND_USER_KEY (a user API key from app.band.ai) in the environment or .env.
Keys land in ~/.onsen/agent_config.yaml (chmod 600), never in the working tree.
The Desktop crew (Architect, Builder, Reviewer) is created in BAND Desktop instead.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
import yaml

from .common import NAMES, agent_config_path, load_env

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")

AGENTS = {
    "scout": (NAMES["scout"], "Answers the factory's questions from the live web via Nimble, with sources and "
                              "confidence grades. Builders ask me before they ask a human."),
    "examiner": (NAMES["examiner"], "Holds the sealed acceptance exam. Grades each stage against hidden scenarios "
                                    "and reports only what a user would notice. Never edits code."),
    "napguard": (NAMES["napguard"], "The only agent allowed to wake the human. Gates stages, batches open questions, "
                                    "calls chill breaks on thrashing work, and posts the run receipt."),
}


def _client(user_key: str) -> httpx.Client:
    return httpx.Client(base_url=API, headers={"X-API-Key": user_key}, timeout=30)


def show_limits(c: httpx.Client) -> tuple[int, int]:
    me = c.get("/api/v1/me").raise_for_status().json()["data"]
    limits = me.get("limits") or {}
    used, cap = int(limits.get("external_agent_count_used", 0)), int(limits.get("max_external_agent_count", 0))
    print(f"Plan: {me.get('plan', {}).get('tier')} · remote agents used {used}/{cap} · "
          f"concurrent agents limit {limits.get('max_concurrent_agents')}")
    return used, cap


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=sorted(AGENTS), action="append")
    ap.add_argument("--check", action="store_true", help="show limits and existing agents, register nothing")
    args = ap.parse_args(argv)

    user_key = os.environ.get("BAND_USER_KEY")
    if not user_key:
        print("Set BAND_USER_KEY (app.band.ai → Settings → API keys) in your environment or .env", file=sys.stderr)
        return 2
    cfg_path: Path = agent_config_path()
    cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
    cfg = cfg or {}

    with _client(user_key) as c:
        used, cap = show_limits(c)
        existing = c.get("/api/v1/me/agents", params={"page_size": 100}).raise_for_status().json()["data"]
        names = {a["name"] for a in existing}
        if args.check:
            print("Existing agents:", ", ".join(sorted(names)) or "none")
            return 0
        wanted = [k for k in (args.only or AGENTS) if k not in cfg]
        if not wanted:
            print(f"Nothing to do: {', '.join(args.only or AGENTS)} already in {cfg_path}")
            return 0
        if used + len(wanted) > cap:
            print(f"Not enough agent slots: need {len(wanted)}, have {cap - used}. Delete unused agents at "
                  "app.band.ai/agents or upgrade the plan, then re-run.", file=sys.stderr)
            return 3
        for key in wanted:
            name, description = AGENTS[key]
            if name in names:
                print(f"⚠ An agent named {name!r} already exists on the account but its key isn't in {cfg_path}. "
                      "Delete it or rename ours with ONSEN_*_NAME, then re-run.", file=sys.stderr)
                continue
            resp = c.post("/api/v1/me/agents/register", json={"agent": {"name": name, "description": description}})
            if resp.status_code >= 400:
                print(f"✘ {name}: HTTP {resp.status_code} {resp.text[:300]}", file=sys.stderr)
                continue
            data = resp.json()["data"]
            cfg[key] = {"agent_id": data["agent"]["id"], "api_key": data["credentials"]["api_key"]}
            print(f"✔ registered {name} ({data['agent']['id']})")

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=True))
    os.chmod(cfg_path, 0o600)
    print(f"Saved keys to {cfg_path} (outside the repo, chmod 600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
