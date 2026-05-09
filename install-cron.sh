#!/usr/bin/env bash
# Installs (or replaces) the daily metrics dashboard cron entry for the
# current user. Idempotent: re-running updates the entry in place.
#
# Default schedule: 17:30 local time, Mon-Fri (weekday US close + buffer).
# Override with: SCHEDULE="<m h dom mon dow>" ./install-cron.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEDULE="${SCHEDULE:-30 17 * * 1-5}"
TAG="# metrics-dashboard"
PYTHON="${PYTHON:-$REPO_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python venv not found at $PYTHON" >&2
  echo "Create it first:" >&2
  echo "  python3 -m venv $REPO_DIR/.venv && $REPO_DIR/.venv/bin/pip install -r $REPO_DIR/requirements.txt" >&2
  exit 1
fi

LINE="$SCHEDULE cd $REPO_DIR && $PYTHON -m dashboard.daily >> $REPO_DIR/data/cron.log 2>&1 $TAG"

current="$(crontab -l 2>/dev/null || true)"
filtered="$(printf '%s\n' "$current" | grep -v "$TAG" || true)"
{
  if [[ -n "$filtered" ]]; then printf '%s\n' "$filtered"; fi
  printf '%s\n' "$LINE"
} | crontab -

echo "Installed cron entry:"
echo "  $LINE"
echo
echo "Inspect with: crontab -l"
echo "Remove with:  crontab -l | grep -v '$TAG' | crontab -"
