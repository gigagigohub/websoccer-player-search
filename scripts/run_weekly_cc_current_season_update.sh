#!/bin/zsh
set -eu

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/weekly-cc.lock"
LOCK_PID="$LOCK_DIR/pid"
STALE_LOCK_SECONDS=$((6 * 60 * 60))

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  now=$(date +%s)
  lock_mtime=$(stat -f %m "$LOCK_DIR" 2>/dev/null || echo "$now")
  lock_age=$((now - lock_mtime))
  lock_pid=""
  if [ -f "$LOCK_PID" ]; then
    lock_pid="$(cat "$LOCK_PID" 2>/dev/null || true)"
  fi
  if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly CC update already running pid=$lock_pid"
    exit 0
  fi
  if [ "$lock_age" -lt "$STALE_LOCK_SECONDS" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly CC update lock exists without live pid; age=${lock_age}s"
    exit 0
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] removing stale weekly CC lock age=${lock_age}s pid=${lock_pid:-none}"
  rm -rf "$LOCK_DIR"
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly CC update already running after stale-lock retry"
    exit 0
  fi
fi
echo "$$" > "$LOCK_PID"
trap 'rm -f "$LOCK_PID"; rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

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
