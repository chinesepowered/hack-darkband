#!/usr/bin/env bash
# Stop every process scripts/run-factory.sh started.
set -uo pipefail
pids="${ONSEN_HOME:-$HOME/.onsen}/factory.pids"
[ -f "$pids" ] || { echo "nothing to stop"; exit 0; }
while read -r pid name; do
  if kill "$pid" 2>/dev/null; then echo "stopped $name ($pid)"; fi
done < "$pids"
: > "$pids"
# Whatever the builders started in the background (the app on :8000, watchdogs) goes too.
fuser -k "${ONSEN_APP_PORT:-8000}/tcp" 2>/dev/null && echo "stopped the app on :${ONSEN_APP_PORT:-8000}"
pkill -f "watchdog.sh" 2>/dev/null && echo "stopped leftover watchdogs"
exit 0
