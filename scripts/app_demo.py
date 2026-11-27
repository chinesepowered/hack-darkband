"""Prepare a running service for the video's app tour: an account and finished dossiers.

    uv run python scripts/app_demo.py <service url> --domains runway.com,example.com --out demo/app-demo.json

Signs up a user through the API, asks for each domain's dossier (POST /dossiers with an Idempotency-Key), waits until
none is still building, and writes {email, password, domains} for make_video.py's tour (ONSEN_APP_DEMO). The tour then
signs in through the service's own login screen.
"""

from __future__ import annotations

import argparse
import json
import secrets
import time
import uuid
from pathlib import Path

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--domains", required=True, help="comma-separated, researched in this order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    domains = [d.strip() for d in a.domains.split(",") if d.strip()]
    email, password = f"capybara-{uuid.uuid4().hex[:6]}@onsen.example", secrets.token_urlsafe(12)
    with httpx.Client(base_url=a.url.rstrip("/"), timeout=60, trust_env=False) as c:
        r = c.post("/auth/signup", json={"email": email, "password": password, "display_name": "Capybara"})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        for d in domains:
            r = c.post("/dossiers", json={"domain": d}, headers={**h, "Idempotency-Key": uuid.uuid4().hex})
            print(f"POST /dossiers {d} -> {r.status_code}", flush=True)
        deadline = time.time() + a.timeout
        while time.time() < deadline:
            states = {d: (c.get(f"/dossiers/{d}", headers=h).json() or {}).get("state") for d in domains}
            if all(s and s != "building" for s in states.values()):
                break
            time.sleep(5)
        print("states:", states, flush=True)
    Path(a.out).write_text(json.dumps({"email": email, "password": password, "domains": domains}, indent=1) + "\n")
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
