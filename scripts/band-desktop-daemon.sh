#!/usr/bin/env bash
# Start (or restart) BAND Desktop's daemon, jamd, for the Onsen crew.
#
# The daemon hands its own environment to every agent runtime it starts, so we give it a minimal one:
# home, PATH, locale, the network proxy and CA settings if the machine has them, and WANDB_API_KEY for Qwen 3.8
# on W&B. Tokens that happen to be in your shell (GitHub, cloud, ...) stay out of the agents' reach.
#
#   scripts/band-desktop-daemon.sh            # reads WANDB_API_KEY from the environment, .env or $ONSEN_ENV_FILE
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
set -a; [ -f "$here/.env" ] && . "$here/.env"; [ -n "${ONSEN_ENV_FILE:-}" ] && . "$ONSEN_ENV_FILE"; set +a
: "${WANDB_API_KEY:?WANDB_API_KEY is required (Qwen 3.8 on W&B Inference)}"
log="${ONSEN_HOME:-$HOME/.onsen}/logs/jamd.log"
mkdir -p "$(dirname "$log")"

keep=(HOME PATH LANG LC_ALL TERM USER SHELL TZ
      HTTPS_PROXY https_proxy HTTP_PROXY http_proxy NO_PROXY no_proxy
      SSL_CERT_FILE NODE_EXTRA_CA_CERTS REQUESTS_CA_BUNDLE CURL_CA_BUNDLE GIT_SSL_CAINFO NODE_OPTIONS
      WANDB_API_KEY OPENAI_API_KEY ONSEN_OPENCODE_BIN ONSEN_OPENCODE_CONFIG
      ONSEN_HOME ONSEN_CHECKER_DIR ONSEN_CHECKER_PY ONSEN_TRACK ONSEN_CHECKS_DIR)
# The seats' tools (onsen-check, onsen-serve) come first on their PATH.
PATH="$here/bin:$PATH"
envs=()
for v in "${keep[@]}"; do [ -n "${!v:-}" ] && envs+=("$v=${!v}"); done

running() { band daemon status 2>/dev/null | grep -q "daemon running"; }  # exits 0 either way; read the text
if running; then
  band daemon stop >/dev/null 2>&1 || true
  for _ in $(seq 1 30); do running || break; sleep 1; done
fi
nohup env -i "${envs[@]}" band daemon run >> "$log" 2>&1 &
for _ in $(seq 1 60); do running && break; sleep 1; done
band daemon status
