#!/bin/zsh
set -eu

REPO_DIR="${WEBSOCCER_PLAYER_SEARCH_REPO:-/Users/gigagigo/Codex/WebSoccer/websoccer-player-search}"

cd "$REPO_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] trade-chain maintenance sweep is retired; running daily sync instead"
exec /bin/zsh scripts/run_daily_login_bonus_and_profile_sync.sh
