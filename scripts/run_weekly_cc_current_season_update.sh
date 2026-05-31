#!/bin/zsh
set -eu

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"
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
  --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
  --auth-source local \
  --skip-capture \
  --season 0 \
  --commit-push \
  --notify-pushover
echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly current-season CC update done"
