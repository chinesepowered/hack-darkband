#!/usr/bin/env bash
# One command, one factory run, all headless:
#   scripts/run-factory.sh [spec]          (default spec: capyfinder)
#
# Starts `opencode serve` (Qwen 3.8 on W&B) in a fresh product workspace, starts all six BAND agents,
# opens the room as you with a single "@Architect build SPEC.md", and follows the room until the receipt.
# The script only launches processes and posts the kickoff; every handoff after that happens between
# agents in the BAND room. Stop everything with scripts/stop-factory.sh.
#
# Needs in the environment (or .env): BAND_USER_KEY, NIMBLE_API_KEY, WANDB_API_KEY, and agents
# registered with `uv run onsen-register`.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
set -a; [ -f .env ] && . ./.env; [ -n "${ONSEN_ENV_FILE:-}" ] && . "$ONSEN_ENV_FILE"; set +a

spec="${1:-capyfinder}"
export ONSEN_HOME="${ONSEN_HOME:-$HOME/.onsen}"
export ONSEN_WORKSPACE="${ONSEN_WORKSPACE:-$(scripts/new-run.sh "$spec" "${ONSEN_RUNS_ROOT:-$HOME/onsen-runs}")}"
export OPENCODE_CONFIG="${OPENCODE_CONFIG:-$here/opencode/opencode.json}"
opencode_bin="${OPENCODE_BIN:-opencode}"
port="${ONSEN_OPENCODE_PORT:-4096}"
export ONSEN_OPENCODE_URL="http://127.0.0.1:$port"

run="$(basename "$ONSEN_WORKSPACE")"
logs="$ONSEN_HOME/logs/$run"
mkdir -p "$logs"
: > "$ONSEN_HOME/factory.pids"
echo "workspace: $ONSEN_WORKSPACE"
echo "logs:      $logs"

start() {  # start <name> <command...>
  local name="$1"; shift
  nohup "$@" > "$logs/$name.log" 2>&1 &
  echo "$! $name" >> "$ONSEN_HOME/factory.pids"
}

# OpenCode works inside the workspace; agent keys and the sealed exam live under $ONSEN_HOME, outside it.
( cd "$ONSEN_WORKSPACE" && start opencode "$opencode_bin" serve --hostname=127.0.0.1 --port="$port" )
for _ in $(seq 1 60); do curl -fsS -m 5 "$ONSEN_OPENCODE_URL/config" >/dev/null 2>&1 && break; sleep 1; done

start scout     uv run onsen-scout
start examiner  uv run onsen-examiner
start napguard  uv run onsen-nap-guard
start architect uv run onsen-crew architect
start builder   uv run onsen-crew builder
start reviewer  uv run onsen-crew reviewer

for name in scout examiner napguard architect builder reviewer; do
  for _ in $(seq 1 90); do grep -q "Agent started" "$logs/$name.log" 2>/dev/null && break; sleep 1; done
  if grep -q "Agent started" "$logs/$name.log"; then echo "✔ $name online"; else echo "✘ $name not online — see $logs/$name.log"; fi
done

room="$(uv run onsen-kickoff --title "Onsen · ${spec} · ${run}")"
echo "$room" > "$ONSEN_HOME/last-room"
echo "room: $room"
mkdir -p "$ONSEN_HOME/transcripts"
uv run onsen-watch "$room" --out "$ONSEN_HOME/transcripts/$run.json"
