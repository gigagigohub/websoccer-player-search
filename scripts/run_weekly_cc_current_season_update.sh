#!/bin/zsh
set -eu

REPO_DIR="/Users/gigagigo/Documents/Codex/websoccer-player-search"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/weekly-cc.lock"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly CC update already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

cd "$REPO_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly current-season CC update start"
python3 scripts/run_cc_update_pipeline.py \
  --season 0 \
  --commit-push \
  --quit-first \
  --auto-navigate-websoccer \
  --wait-sec 900
echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly current-season CC update done"
