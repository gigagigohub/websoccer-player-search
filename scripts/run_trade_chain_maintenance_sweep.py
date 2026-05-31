#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from fetch_cc_all_worlds_completed import local_auth_from_container, request_json
from sync_websoccer_local_profile_from_api import SYNC_PATH, update_db


DEFAULT_STATE_DIR = Path("local/trade_chain")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sweep stale trade-chain states after Sunday maintenance/new season.")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p.add_argument("--execute", action="store_true", help="Write DB/state changes and send notification.")
    p.add_argument("--backup", action="store_true", default=True)
    p.add_argument("--notify-pushover", action="store_true", help="Send iPhone notification with completion summary.")
    p.add_argument("--timeout-sec", type=float, default=15.0)
    return p.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def roster(profile: Path) -> dict[int, str]:
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            select p.ZPLAYER_ID, p.ZNAME
            from ZMOTEAMSPLAYER tp
            join ZMOPLAYER p on p.Z_PK = tp.ZPLAYER
            """
        ).fetchall()
        return {int(pid): str(name or "") for pid, name in rows}
    finally:
        con.close()


def sync_profile(profile: Path, timeout_sec: float, execute: bool, backup: bool) -> dict[str, Any]:
    before = roster(profile)
    auth = local_auth_from_container(profile)
    if not auth:
        return {"profileData": str(profile), "ok": False, "error": "could not generate auth", "before": before, "after": before}
    ok, payload = request_json(SYNC_PATH, auth, timeout_sec)
    if not ok or not isinstance(payload, dict) or payload.get("code") != "000":
        return {"profileData": str(profile), "ok": False, "error": payload, "before": before, "after": before}
    if execute:
        db = profile / "Documents" / "Model" / "Model.sqlite"
        if backup and db.exists():
            backup_path = db.with_suffix(db.suffix + ".pre_trade_sweep.bak")
            if backup_path.exists():
                backup_path = db.with_suffix(db.suffix + f".pre_trade_sweep_{backup_path.stat().st_mtime_ns}.bak")
            shutil.copy2(db, backup_path)
        con = sqlite3.connect(str(db))
        try:
            con.execute("begin")
            update_summary = update_db(con, payload)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    else:
        update_summary = {}
    after = roster(profile) if execute else roster_from_payload(payload)
    return {
        "profileData": str(profile),
        "ok": True,
        "season": payload.get("season"),
        "teamName": payload.get("name"),
        "before": before,
        "after": after,
        "updated": update_summary,
    }


def roster_from_payload(payload: dict[str, Any]) -> dict[int, str]:
    return {int(p["id"]): str(p.get("name") or p["id"]) for p in ((payload.get("team_data") or {}).get("players") or [])}


def collect_profiles(states: list[dict[str, Any]]) -> set[str]:
    profiles: set[str] = set()
    for state in states:
        for section in ("requests", "registered"):
            for item in state.get(section) or []:
                profile = str(item.get("profileData") or "").strip()
                if profile:
                    profiles.add(profile)
    return profiles


def analyze_state(state: dict[str, Any], syncs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    completions: list[dict[str, Any]] = []
    canceled: list[dict[str, Any]] = []
    for item in state.get("requests") or []:
        if item.get("status") not in {"requested", "pending", "maybe_completed_or_ended"}:
            continue
        sync = syncs.get(str(item.get("profileData") or ""))
        after = sync.get("after") if sync else {}
        listed_id = int(item.get("listedPlayerId") or 0)
        offered_id = int(item.get("offeredPlayerId") or 0)
        if listed_id and listed_id in after and (not offered_id or offered_id not in after):
            item["status"] = "completed_after_maintenance_sweep"
            completions.append(
                {
                    "kind": "request_completed",
                    "playerId": listed_id,
                    "playerName": item.get("listedPlayerName") or after.get(listed_id) or str(listed_id),
                    "teamId": item.get("requestTeamId"),
                    "teamName": item.get("requestTeamName"),
                    "listingKey": item.get("listingKey"),
                }
            )
        else:
            item["status"] = "maintenance_canceled"
            canceled.append({"kind": "request_canceled", "listingKey": item.get("listingKey"), "teamId": item.get("requestTeamId")})

    for item in state.get("registered") or []:
        if item.get("status") not in {"registered", "registered_unverified"}:
            continue
        sync = syncs.get(str(item.get("profileData") or ""))
        before = sync.get("before") if sync else {}
        after = sync.get("after") if sync else {}
        player_id = int(item.get("playerId") or 0)
        added_ids = sorted(set(after) - set(before))
        if player_id and player_id not in after and added_ids:
            item["status"] = "completed_after_maintenance_sweep"
            for pid in added_ids:
                completions.append(
                    {
                        "kind": "registered_completed",
                        "playerId": pid,
                        "playerName": after.get(pid) or str(pid),
                        "teamId": item.get("teamId"),
                        "teamName": item.get("teamName"),
                        "registeredTradeId": item.get("tradeId"),
                    }
                )
        else:
            item["status"] = "maintenance_canceled"
            canceled.append({"kind": "registered_canceled", "tradeId": item.get("tradeId"), "teamId": item.get("teamId")})
    return {"completed": completions, "canceled": canceled}


def send_pushover(title: str, message: str) -> None:
    subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "notify_pushover.py"), "--title", title, "--message", message],
        check=False,
    )


def notification_message(completions: list[dict[str, Any]], canceled_count: int) -> str:
    if not completions:
        return f"メンテ明け確認完了。成立0件、未成立キャンセル{canceled_count}件。"
    counts = Counter(str(item.get("playerName") or item.get("playerId")) for item in completions)
    parts = [f"{name} {count}件" for name, count in counts.most_common()]
    return f"メンテ明け確認完了。成立{len(completions)}件: " + " / ".join(parts) + f"。未成立キャンセル{canceled_count}件。"


def main() -> int:
    args = parse_args()
    state_dir = Path(args.state_dir)
    if not state_dir.is_absolute():
        state_dir = (Path.cwd() / state_dir).resolve()
    state_paths = sorted(state_dir.glob("*.json"))
    states = []
    for path in state_paths:
        try:
            states.append({"path": path, "data": load_json(path)})
        except Exception as exc:
            print(f"[WARN] skip unreadable state {path}: {exc}", file=sys.stderr)

    profile_paths = collect_profiles([item["data"] for item in states])
    syncs = {
        profile: sync_profile(Path(profile).expanduser().resolve(), args.timeout_sec, args.execute, args.backup)
        for profile in sorted(profile_paths)
    }

    all_completed: list[dict[str, Any]] = []
    all_canceled: list[dict[str, Any]] = []
    for item in states:
        state = item["data"]
        analysis = analyze_state(state, syncs)
        all_completed.extend(analysis["completed"])
        all_canceled.extend(analysis["canceled"])
        if analysis["completed"] or analysis["canceled"]:
            state.setdefault("maintenanceSweeps", []).append(
                {
                    "completed": analysis["completed"],
                    "canceled": analysis["canceled"],
                    "syncProfiles": sorted(profile_paths),
                }
            )
            state["stopped"] = True
            if args.execute:
                write_json(item["path"], state)

    result = {
        "states": len(states),
        "profilesSynced": len(syncs),
        "completed": all_completed,
        "canceledCount": len(all_canceled),
        "execute": bool(args.execute),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.execute and args.notify_pushover:
        send_pushover("WebSoccer Trade Sweep", notification_message(all_completed, len(all_canceled)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
