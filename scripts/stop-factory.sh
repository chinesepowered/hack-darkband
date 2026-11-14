#!/usr/bin/env bash
# Stop every process scripts/run-factory.sh started.
set -uo pipefail
pids="${ONSEN_HOME:-$HOME/.onsen}/factory.pids"
[ -f "$pids" ] || { echo "nothing to stop"; exit 0; }
while read -r pid name; do
  if kill "$pid" 2>/dev/null; then echo "stopped $name ($pid)"; fi
done < "$pids"
: > "$pids"
