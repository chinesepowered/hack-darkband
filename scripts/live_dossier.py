"""Ask one stage folder for a company's dossier on the live web (Nimble), for the submission's live dossier file.

    uv run python scripts/live_dossier.py <stage folder> <domain> --out <file> [--host-network]

Builds the folder's Dockerfile and starts it the way the participant guide's live-dossier steps do: PORT, the Nimble
settings (NIMBLE_API_KEY from this environment, passed to Docker by name so it never appears on a command line;
NIMBLE_BASE_URL defaults to Nimble's endpoint), and placeholder keys with the real base URLs for the other providers,
so only Nimble answers. Then it signs up a user, asks for the dossier, polls until the build finishes, and writes the
GET response body.
`--host-network` runs the container on the host's network and passes HTTPS_PROXY through, for machines whose only
way out is a proxy on the host's loopback.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

NIMBLE = "https://sdk.nimbleway.com"
# The other providers get a placeholder key and their real endpoint, as in the guide, so only Nimble answers.
OTHERS = {"TAVILY": "https://api.tavily.com", "KERNEL": "https://api.onkernel.com",
          "BROWSERBASE": "https://api.browserbase.com"}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("domain")
    ap.add_argument("--out", required=True)
    ap.add_argument("--host-network", action="store_true")
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    if not os.environ.get("NIMBLE_API_KEY"):
        raise SystemExit("NIMBLE_API_KEY is not set")
    env = dict(os.environ, NIMBLE_BASE_URL=os.environ.get("NIMBLE_BASE_URL") or NIMBLE)
    tag = f"onsen-live-{Path(a.folder).resolve().name}-{uuid.uuid4().hex[:6]}"
    print(f"building {a.folder} ...", flush=True)
    subprocess.run(["docker", "build", "-q", "-t", tag, a.folder], check=True, stdout=subprocess.DEVNULL)
    port = free_port()
    name = f"onsen-live-{uuid.uuid4().hex[:8]}"
    run = ["docker", "run", "-d", "--rm", "--name", name, "-e", f"PORT={port}", "-e", "NIMBLE_API_KEY",
           "-e", "NIMBLE_BASE_URL"]
    for provider, url in OTHERS.items():
        run += ["-e", f"{provider}_API_KEY=unavailable", "-e", f"{provider}_BASE_URL={url}"]
    if a.host_network:
        run += ["--network", "host"] + [x for k in ("HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy")
                                        if env.get(k) for x in ("-e", k)]
    else:
        run += ["-p", f"127.0.0.1:{port}:{port}"]
    subprocess.run(run + [tag], check=True, env=env, stdout=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=base, timeout=30, trust_env=False) as c:
            for _ in range(120):
                try:
                    if c.get("/health").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise SystemExit("the service never became healthy")
            r = c.post("/auth/signup", json={"email": f"live-{uuid.uuid4().hex[:6]}@onsen.example",
                                             "password": secrets.token_urlsafe(12), "display_name": "Onsen"})
            r.raise_for_status()
            h = {"Authorization": f"Bearer {r.json()['token']}"}
            r = c.post("/dossiers", json={"domain": a.domain}, headers={**h, "Idempotency-Key": uuid.uuid4().hex})
            print(f"POST /dossiers -> {r.status_code}", flush=True)
            r.raise_for_status()
            deadline = time.time() + a.timeout
            while time.time() < deadline:
                g = c.get(f"/dossiers/{a.domain}", headers=h)
                state = g.json().get("state") if g.status_code == 200 else None
                if state and state != "building":
                    break
                time.sleep(5)
            body = g.json()
            Path(a.out).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            known = [k for k, v in (body.get("fields") or {}).items() if isinstance(v, dict) and v.get("status") == "known"]
            print(f"state={body.get('state')} known fields: {', '.join(known) or 'none'} -> {a.out}")
            if body.get("state") != "ready":
                print("the build did not finish ready; the service's last log lines:")
                subprocess.run(["docker", "logs", "--tail", "60", name])
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
