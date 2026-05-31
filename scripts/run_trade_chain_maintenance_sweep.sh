#!/bin/zsh
set -eu

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"
LOG_DIR="$HOME/Library/Logs/websoccer-player-search"
LOCK_DIR="$HOME/Library/Application Support/websoccer-player-search/trade-chain-maintenance-sweep.lock"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] trade-chain maintenance sweep already running"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

cd "$REPO_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] trade-chain maintenance sweep start"
python3 scripts/run_trade_chain_maintenance_sweep.py --execute --notify-pushover
echo "[$(date '+%Y-%m-%d %H:%M:%S')] trade-chain maintenance sweep done"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] all profile sync start"
python3 scripts/sync_all_websoccer_profiles.py --execute --notify-pushover
echo "[$(date '+%Y-%m-%d %H:%M:%S')] all profile sync done"
