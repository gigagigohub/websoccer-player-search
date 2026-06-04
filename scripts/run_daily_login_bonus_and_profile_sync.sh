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

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/websoccer-daily-sync.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
  rmdir "$LOCK_DIR"
}
trap cleanup EXIT

cd "$REPO_DIR" || exit 1

overall_rc=0
LOGIN_JSON="$TMP_DIR/login_bonus_summary.json"
SYNC_JSON="$TMP_DIR/profile_sync_summary.json"
NOTIFY_JSON="$TMP_DIR/combined_notification_summary.json"

log "daily login-bonus/profile sync start"
log "git status before run:"
git status --short || true

log "daily login trigger, present-box accept, and ticket inventory start for numbered trade-chain profiles"
if python3 scripts/run_all_websoccer_login_bonus.py --execute --numbered-trade-profiles-only > "$LOGIN_JSON"; then
  log "daily login trigger and present-box accept done"
else
  rc=$?
  log "daily login trigger and present-box accept failed with exit code $rc"
  overall_rc=1
fi
cat "$LOGIN_JSON"

log "numbered trade-chain profile sync start"
if python3 scripts/sync_all_websoccer_profiles.py --execute --numbered-trade-profiles-only > "$SYNC_JSON"; then
  log "all profile sync done"
else
  rc=$?
  log "all profile sync failed with exit code $rc"
  overall_rc=1
fi
cat "$SYNC_JSON"

log "combined daily notification start"
if python3 scripts/notify_daily_login_bonus_and_profile_sync_summary.py \
  --login-summary "$LOGIN_JSON" \
  --sync-summary "$SYNC_JSON" \
  --notify-pushover > "$NOTIFY_JSON"; then
  log "combined daily notification done"
else
  rc=$?
  log "combined daily notification failed with exit code $rc"
  overall_rc=1
fi
cat "$NOTIFY_JSON"

log "git status after run:"
git status --short || true
log "daily login-bonus/profile sync done"
exit "$overall_rc"
