#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STATE_DIR = Path("local/trade_chain")
REQUEST_STATUSES = {"requested", "pending", "maybe_completed_or_ended"}
REGISTERED_STATUSES = {"registered", "registered_unverified"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Detect trade-chain completions from daily profile sync roster diffs.")
    p.add_argument("--sync-summary", required=True, help="JSON output from sync_all_websoccer_profiles.py.")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p.add_argument("--execute", action="store_true", help="Update trade-chain state files after detected completions.")
    return p.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def path_keys(path_text: str) -> set[str]:
    raw = Path(path_text).expanduser()
    keys = {str(raw)}
    try:
        keys.add(str(raw.resolve()))
    except Exception:
        pass
    return keys


def sync_map(sync_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in sync_summary.get("results") or []:
        if not item.get("ok") or item.get("skipped"):
            continue
        profile = str(item.get("profileData") or "")
        if not profile:
            continue
        for key in path_keys(profile):
            out[key] = item
    return out


def player_id_set(roster: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for key in roster:
        try:
            ids.add(int(key))
        except Exception:
            continue
    return ids


def roster_name(roster: dict[str, Any], player_id: int, fallback: Any = "") -> str:
    return str(roster.get(str(player_id)) or fallback or player_id)


def sync_for_item(item: dict[str, Any], syncs: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    profile = str(item.get("profileData") or "")
    for key in path_keys(profile):
        if key in syncs:
            return syncs[key]
    return None


def request_completion(item: dict[str, Any], sync: dict[str, Any], state_path: Path) -> dict[str, Any] | None:
    before = sync.get("rosterBefore") or {}
    after = sync.get("rosterAfter") or {}
    before_ids = player_id_set(before)
    after_ids = player_id_set(after)
    listed_id = int(item.get("listedPlayerId") or 0)
    offered_id = int(item.get("offeredPlayerId") or 0)
    if not listed_id:
        return None
    acquired_listed = listed_id in after_ids and listed_id not in before_ids
    spent_offered = bool(offered_id and offered_id in before_ids and offered_id not in after_ids)
    if not acquired_listed and not (listed_id in after_ids and spent_offered):
        return None
    return {
        "at": now_iso(),
        "kind": "daily_sync_request_completed",
        "stateFile": str(state_path),
        "listingKey": item.get("listingKey"),
        "playerId": listed_id,
        "playerName": roster_name(after, listed_id, item.get("listedPlayerName")),
        "offeredPlayerId": offered_id or None,
        "offeredPlayerName": item.get("offeredPlayerName"),
        "teamId": item.get("requestTeamId"),
        "teamName": item.get("requestTeamName"),
        "profileData": item.get("profileData"),
    }


def registered_completion(item: dict[str, Any], sync: dict[str, Any], state_path: Path) -> list[dict[str, Any]]:
    before = sync.get("rosterBefore") or {}
    after = sync.get("rosterAfter") or {}
    before_ids = player_id_set(before)
    after_ids = player_id_set(after)
    player_id = int(item.get("playerId") or 0)
    if not player_id or player_id in after_ids:
        return []
    added_ids = sorted(after_ids - before_ids)
    if not added_ids:
        return []
    return [
        {
            "at": now_iso(),
            "kind": "daily_sync_registered_completed",
            "stateFile": str(state_path),
            "registeredTradeId": item.get("tradeId"),
            "registeredPlayerId": player_id,
            "registeredPlayerName": item.get("playerName"),
            "playerId": pid,
            "playerName": roster_name(after, pid),
            "teamId": item.get("teamId"),
            "teamName": item.get("teamName"),
            "profileData": item.get("profileData"),
        }
        for pid in added_ids
    ]


def analyze_state(path: Path, state: dict[str, Any], syncs: dict[str, dict[str, Any]], execute: bool) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []

    for item in state.get("requests") or []:
        if item.get("status") not in REQUEST_STATUSES:
            continue
        sync = sync_for_item(item, syncs)
        if not sync:
            continue
        completion = request_completion(item, sync, path)
        if not completion:
            continue
        completed.append(completion)
        if execute:
            item["status"] = "completed_after_daily_sync"
            item["notified"] = True

    for item in state.get("registered") or []:
        if item.get("status") not in REGISTERED_STATUSES:
            continue
        sync = sync_for_item(item, syncs)
        if not sync:
            continue
        item_completions = registered_completion(item, sync, path)
        if not item_completions:
            continue
        completed.extend(item_completions)
        if execute:
            item["status"] = "executed"
            item["notified"] = True

    if completed and execute:
        state.setdefault("dailySyncCompletions", []).append({"at": now_iso(), "completed": completed})
        existing_completed = state.setdefault("completed", [])
        for completion in completed:
            existing_completed.append({"notified": True, **completion})
        state["stopped"] = True
        state["stopReason"] = "daily_sync_completion_detected"
        state["updatedAt"] = now_iso()
        write_json(path, state)

    return completed


def completion_message(completed: list[dict[str, Any]]) -> str:
    if not completed:
        return ""
    counts = Counter(str(item.get("playerName") or item.get("playerId")) for item in completed)
    parts = [f"{name}{count}件" for name, count in counts.most_common()]
    return f"成立 {len(completed)}件: " + " / ".join(parts)


def main() -> int:
    args = parse_args()
    sync_summary = load_json(Path(args.sync_summary))
    syncs = sync_map(sync_summary)
    state_dir = Path(args.state_dir)
    if not state_dir.is_absolute():
        state_dir = (Path.cwd() / state_dir).resolve()

    all_completed: list[dict[str, Any]] = []
    states_scanned = 0
    states_updated = 0
    for path in sorted(state_dir.glob("*.json")):
        try:
            state = load_json(path)
        except Exception:
            continue
        if not isinstance(state, dict) or not (state.get("requests") or state.get("registered")):
            continue
        states_scanned += 1
        completed = analyze_state(path, state, syncs, bool(args.execute))
        if completed:
            states_updated += 1
            all_completed.extend(completed)

    result = {
        "statesScanned": states_scanned,
        "statesUpdated": states_updated,
        "completedCount": len(all_completed),
        "completed": all_completed,
        "message": completion_message(all_completed),
        "execute": bool(args.execute),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
