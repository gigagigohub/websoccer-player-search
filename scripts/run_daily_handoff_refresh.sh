#!/bin/zsh
set -eu

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"
SCRIPT_DIR="${0:A:h}"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/daily-handoff-refresh.lock"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily handoff refresh already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

notify_failure() {
  local rc="$1"
  local detail="$2"
  python3 "$SCRIPT_DIR/notify_pushover.py" \
    --env-file "$HOME/.handoff_pushover.env" \
    --token-env-var HANDOFF_PUSHOVER_APP_TOKEN \
    --user-env-var HANDOFF_PUSHOVER_USER_KEY \
    --title "Handoff refresh failed: $(basename "$REPO_DIR")" \
    --message "docs/daily_handoff.md was not refreshed. Exit code: $rc. Detail: $detail. Log: ~/Library/Logs/websoccer-player-search/daily-handoff-refresh.err.log" \
    --priority 0 || true
}

set +e
cd "$REPO_DIR"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily handoff refresh failed: cd $REPO_DIR"
  notify_failure "$rc" "could not cd to workdir"
  exit "$rc"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily handoff refresh start"
set +e
python3 "$SCRIPT_DIR/refresh_daily_handoff.py"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily handoff refresh failed with exit code $rc"
  notify_failure "$rc" "refresh script failed"
  exit "$rc"
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily handoff refresh done"
