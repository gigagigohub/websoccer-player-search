#!/bin/zsh
set -u

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/daily-login-bonus-sync.lock"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "daily login-bonus/profile sync already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

cd "$REPO_DIR" || exit 1

overall_rc=0

log "daily login-bonus/profile sync start"
log "git status before run:"
git status --short || true

log "daily login trigger and present-box accept start"
if python3 scripts/run_all_websoccer_login_bonus.py --execute --notify-pushover; then
  log "daily login trigger and present-box accept done"
else
  rc=$?
  log "daily login trigger and present-box accept failed with exit code $rc"
  overall_rc=1
fi

log "all profile sync start"
if python3 scripts/sync_all_websoccer_profiles.py --execute --notify-pushover; then
  log "all profile sync done"
else
  rc=$?
  log "all profile sync failed with exit code $rc"
  overall_rc=1
fi

log "git status after run:"
git status --short || true
log "daily login-bonus/profile sync done"
exit "$overall_rc"
