"""Say something in the factory room as the human (the capybara's only lines are usually `ship` or `hold`).

    uv run onsen-say ship                      # to Nap Guard, in the last room run-factory.sh opened
    uv run onsen-say --to Architect "status?"  # anyone else
    uv run onsen-say --room <id> hold
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx
import yaml

from .common import NAMES, agent_config_path, load_env, onsen_home

API = os.environ.get("BAND_REST_URL", "https://app.band.ai").rstrip("/")
KEY_BY_NAME = {v.lower(): k for k, v in NAMES.items()}


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("text", nargs="+")
    ap.add_argument("--to", default=NAMES["napguard"], help="agent name, or several separated by commas")
    ap.add_argument("--room")
    args = ap.parse_args(argv)
    room = args.room or (onsen_home() / "last-room").read_text().strip()
    cfg = yaml.safe_load(agent_config_path().read_text()) or {}
    keys = [KEY_BY_NAME.get(t.strip().lower(), t.strip().lower()) for t in args.to.split(",") if t.strip()]
    unknown = [k for k in keys if k not in cfg]
    if unknown:
        print(f"Unknown agent(s) {unknown!r}", file=sys.stderr)
        return 2
    text = " ".join(args.text)
    names = [NAMES.get(k, k) for k in keys]
    body = {"message": {"content": " ".join(f"@{n}" for n in names) + f" {text}",
                        "mentions": [{"id": cfg[k]["agent_id"], "name": n} for k, n in zip(keys, names)]}}
    with httpx.Client(base_url=API, headers={"X-API-Key": os.environ["BAND_USER_KEY"]}, timeout=30) as c:
        r = c.post(f"/api/v1/me/chats/{room}/messages", json=body)
        if r.status_code >= 400:
            print(f"HTTP {r.status_code} {r.text[:300]}", file=sys.stderr)
            return 1
    print(f"said to {', '.join(names)}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
