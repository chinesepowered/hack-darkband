#!/usr/bin/env bash
# One dark-factory run: a fresh room with the five seats, Nap Guard in dark mode, the four BAND Desktop seats pointed
# at the result repository, and the task posted as the only human message.
#
#   scripts/run-dark.sh <result repository> <task file> [room title]
#
# Needs: BAND Desktop's daemon (scripts/band-desktop-daemon.sh), the seats adopted with OpenCode runtimes
# (docs/band-desktop.md), and the checker settings (ONSEN_CHECKER_DIR, ONSEN_CHECKER_PY, ONSEN_TRACK) in the env.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
set -a; [ -f .env ] && . ./.env; [ -n "${ONSEN_ENV_FILE:-}" ] && . "$ONSEN_ENV_FILE"
[ -n "${ONSEN_EVENT_ENV:-}" ] && . "$ONSEN_EVENT_ENV"; set +a
repo="$(realpath "$1")"; task="$(realpath "$2")"; title="${3:-Onsen · $(basename "$repo")}"
export ONSEN_DARK=1 ONSEN_CHILL_ACTION=notice
export ONSEN_HOME="${ONSEN_HOME:-$HOME/.onsen}"
run="$(basename "$repo")-$(date +%H%M)"
logs="$ONSEN_HOME/logs/$run"; mkdir -p "$logs"
band daemon status 2>/dev/null | grep -q "daemon running" || scripts/band-desktop-daemon.sh

uv run onsen-cleanup --all >/dev/null || true        # old rooms can't wake the seats mid-run
pkill -f "onsen-nap-guard" 2>/dev/null || true
nohup uv run onsen-nap-guard > "$logs/napguard.log" 2>&1 &
echo "$! napguard" > "$ONSEN_HOME/factory.pids"
uv run onsen-desktop prepare --workspace "$repo"
for _ in $(seq 1 90); do grep -q "Agent started" "$logs/napguard.log" 2>/dev/null && break; sleep 1; done
grep -q "Agent started" "$logs/napguard.log" && echo "✔ Nap Guard online (dark mode)" || { echo "✘ Nap Guard not online: $logs/napguard.log"; exit 1; }

room="$(uv run onsen-kickoff --title "$title" --skip scout --say-file "$task")"
echo "$room" > "$ONSEN_HOME/last-room"
echo "room: $room"
echo "logs: $logs"
