#!/usr/bin/env bash
# Create a fresh product workspace for one factory run.
#   scripts/new-run.sh capyfinder            -> ~/onsen-runs/capyfinder-YYYYMMDD-HHMM
#   scripts/new-run.sh capyfinder /tmp/runs
# Point the Desktop crew's workspace and the Scout's ONSEN_WORKSPACE at the printed path.
# The factory repo (and the Examiner's sealed exam) stay outside it.
set -euo pipefail

spec="${1:-capyfinder}"
root="${2:-$HOME/onsen-runs}"
here="$(cd "$(dirname "$0")/.." && pwd)"
src="$here/specs/$spec.md"
[ -f "$src" ] || { echo "no spec at $src" >&2; exit 1; }

ws="$root/$spec-$(date +%Y%m%d-%H%M)"
mkdir -p "$ws/docs/vendor" "$ws/data"
cp "$src" "$ws/SPEC.md"
cat > "$ws/README.md" <<EOF
# $spec (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md). The builders fill in how to run it.
EOF
printf 'node_modules/\n.venv/\n__pycache__/\n.env\n' > "$ws/.gitignore"
( cd "$ws" && git init -q && git add -A && git commit -qm "Spec for $spec" )
echo "$ws"
