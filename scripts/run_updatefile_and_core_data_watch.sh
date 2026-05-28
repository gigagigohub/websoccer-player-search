#!/bin/zsh
set -u

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Documents/Codex/websoccer-player-search}"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/updatefile-core-watch.lock"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*"
}

hour="$(date '+%H')"
case "$hour" in
  04|05|06)
    log "skip during WebSoccer maintenance hour: $hour"
    exit 0
    ;;
esac

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "updatefile/core-data watch already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

cd "$REPO_DIR" || exit 1

log "updatefile/core-data watch start"
log "git status before run:"
git status --short || true

log "running UpdateFile watcher"
if python3 scripts/watch_updatefile_and_refresh_site.py --commit-push; then
  log "UpdateFile watcher completed"
else
  rc=$?
  log "UpdateFile watcher failed with exit code $rc"
fi

latest_core_id="$(
  python3 - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))
from fetch_update_core_data import DEFAULT_CORE_ROOT, latest_local_core_id

print(latest_local_core_id(DEFAULT_CORE_ROOT))
PY
)"

if [[ -z "$latest_core_id" || "$latest_core_id" == "0" ]]; then
  log "could not determine latest local core-data id; skipping core-data probe"
  log "updatefile/core-data watch done"
  exit 0
fi

log "core-data auth check"
python3 scripts/fetch_update_core_data.py --auth-check || true

validate_out="$(mktemp)"
probe_out="$(mktemp)"
trap 'rm -f "$validate_out" "$probe_out"; rmdir "$LOCK_DIR"' EXIT

log "validating latest local core-data id: $latest_core_id"
python3 scripts/fetch_update_core_data.py --ids "$latest_core_id" --dry-run >"$validate_out" 2>&1
cat "$validate_out"

if ! grep -q '^\[FOUND\]' "$validate_out"; then
  log "latest core-data validation did not return rows; attempting fresh auth capture"
  python3 scripts/run_cc_update_pipeline.py \
    --season 0 \
    --quit-first \
    --auto-navigate-websoccer \
    --capture-only \
    --wait-sec 180 \
    --capture-warmup-sec 3

  log "re-validating latest local core-data id after capture: $latest_core_id"
  python3 scripts/fetch_update_core_data.py --ids "$latest_core_id" --dry-run >"$validate_out" 2>&1
  cat "$validate_out"
fi

if grep -q '^\[FOUND\]' "$validate_out"; then
  log "probing for new core-data rows"
  python3 scripts/fetch_update_core_data.py --dry-run >"$probe_out" 2>&1
  cat "$probe_out"

  if grep -q '^\[FOUND\]' "$probe_out"; then
    log "new core-data rows found; saving"
    python3 scripts/fetch_update_core_data.py
  else
    log "no new core-data rows found"
  fi
else
  log "core-data validation still failed; skipping new-id probe"
fi

log "git status after run:"
git status --short || true
log "updatefile/core-data watch done"
