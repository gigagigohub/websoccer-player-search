#!/bin/zsh
set -u

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/updatefile-core-watch.lock"
ORDINARY_PUSHOVER_ENV="${WEBSOCCER_ORDINARY_PUSHOVER_ENV:-$HOME/.websoccer_ordinary_pushover.env}"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*"
}

notify_pushover() {
  local title="$1"
  local message="$2"
  if python3 scripts/notify_pushover.py --env-file "$ORDINARY_PUSHOVER_ENV" --title "$title" --message "$message"; then
    log "Pushover notification sent: $title"
  else
    local rc=$?
    log "Pushover notification skipped/failed for $title with exit code $rc"
  fi
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
python3 scripts/fetch_update_core_data.py \
  --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
  --auth-check || true

validate_out="$(mktemp)"
probe_out="$(mktemp)"
save_out="$(mktemp)"
trap 'rm -f "$validate_out" "$probe_out" "$save_out"; rmdir "$LOCK_DIR"' EXIT

log "validating latest local core-data id: $latest_core_id"
python3 scripts/fetch_update_core_data.py \
  --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
  --ids "$latest_core_id" \
  --dry-run >"$validate_out" 2>&1
cat "$validate_out"

if ! grep -q '^\[FOUND\]' "$validate_out"; then
  log "latest core-data validation did not return rows with OpenAI auth; skipping Charles fallback to keep auth source fixed"
fi

if grep -q '^\[FOUND\]' "$validate_out"; then
  log "probing for new core-data rows"
  python3 scripts/fetch_update_core_data.py \
    --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
    --dry-run >"$probe_out" 2>&1
  cat "$probe_out"

  if grep -q '^\[FOUND\]' "$probe_out"; then
    found_line="$(grep '^\[FOUND\]' "$probe_out" | paste -sd ';' -)"
    output_line="$(grep '^\[INFO\] output:' "$probe_out" | tail -n 1 | sed 's/^\[INFO\] output: //')"
    log "new core-data rows found; saving"
    notify_pushover \
      "WebSoccer Core Data" \
      "新しい update_core_data が見つかりました: ${found_line:-details unavailable}"
    python3 scripts/fetch_update_core_data.py \
      --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current \
      >"$save_out" 2>&1
    save_rc=$?
    cat "$save_out"
    if [[ "$save_rc" -eq 0 ]]; then
      done_line="$(grep '^\[DONE\] saved core rows:' "$save_out" | tail -n 1)"
      saved_output_line="$(grep '^\[INFO\] output:' "$save_out" | tail -n 1 | sed 's/^\[INFO\] output: //')"
      notify_pushover \
        "WebSoccer Core Data Complete" \
        "${done_line:-update_core_data の保存が完了しました}${saved_output_line:+ / output: $saved_output_line}"
    else
      notify_pushover \
        "WebSoccer Core Data Failed" \
        "update_core_data の保存に失敗しました: exit=$save_rc${output_line:+ / planned output: $output_line}"
    fi
  else
    log "no new core-data rows found"
  fi
else
  log "core-data validation still failed; skipping new-id probe"
fi

log "git status after run:"
git status --short || true
log "updatefile/core-data watch done"
