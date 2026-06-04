#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fetch_cc_all_worlds_completed import local_auth_from_container, request_json
from sync_websoccer_local_profile_from_api import SYNC_PATH, update_db


REPO_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_TRANSFER_ROOT = Path.home() / "Codex/WebSoccer/websoccer_local_backups/account_transfer"
MANAGED_TEAMS_ROOT = ACCOUNT_TRANSFER_ROOT / "teams"
TRADE_PROFILE_ROOT = REPO_ROOT / "local" / "trade_chain" / "profiles"
NUMBERED_PROFILE_ALIAS_ROOT = REPO_ROOT / "local" / "trade_chain" / "profiles_by_no"
INDEX_SCRIPT = REPO_ROOT / "scripts" / "build_websoccer_local_player_index.py"
ROSTER_REPORT_SCRIPT = REPO_ROOT / "scripts" / "build_websoccer_local_roster_report.py"
SNAPSHOT_SCRIPT = REPO_ROOT / "scripts" / "export_websoccer_local_profile_snapshot.py"
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_pushover.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync every stored WebSoccer profile used by trade automation.")
    p.add_argument("--execute", action="store_true", help="Write synced payloads to local Model.sqlite files.")
    p.add_argument("--backup", action="store_true", default=True, help="Back up Model.sqlite before writes.")
    p.add_argument("--timeout-sec", type=float, default=30.0)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--retry-delay-sec", type=int, default=5)
    p.add_argument("--notify-pushover", action="store_true")
    p.add_argument("--no-snapshots", action="store_true", help="Skip profile snapshots and index rebuild after --execute.")
    p.add_argument(
        "--numbered-trade-profiles-only",
        action="store_true",
        help="Sync only trade-chain profiles referenced by local/trade_chain/profiles_by_no.",
    )
    p.add_argument(
        "--managed-teams-only",
        action="store_true",
        help="Sync only managed account-transfer teams under account_transfer/teams/*/current.",
    )
    return p.parse_args()


def db_path(profile: Path) -> Path:
    return profile / "Documents" / "Model" / "Model.sqlite"


def failed_new_team_profiles() -> set[Path]:
    failed: set[Path] = set()
    state_dir = REPO_ROOT / "local" / "trade_chain"
    for state_path in state_dir.glob("*.json"):
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in state.get("skippedListings") or []:
            if item.get("status") != "new_team_creation_failed":
                continue
            command = ((item.get("teamCreation") or {}).get("command") or [])
            for idx, part in enumerate(command):
                if part == "--profile-data" and idx + 1 < len(command):
                    failed.add(Path(str(command[idx + 1])).expanduser().resolve())
    return failed


def current_team_summary(profile: Path) -> dict[str, Any]:
    db = db_path(profile)
    if not db.exists():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("select ZTEAM_ID, ZNAME, ZSZN from ZMOTEAMDATA limit 1").fetchone()
        return dict(row) if row else {}
    finally:
        con.close()


def collect_numbered_trade_profiles() -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for alias in sorted(NUMBERED_PROFILE_ALIAS_ROOT.iterdir() if NUMBERED_PROFILE_ALIAS_ROOT.exists() else []):
        if not alias.name.isdigit():
            continue
        profile = alias / "Data"
        if not db_path(profile).exists():
            continue
        try:
            key = profile.resolve()
        except Exception:
            key = profile
        if key in seen:
            continue
        seen.add(key)
        out.append(profile)
    return out


def collect_managed_team_profiles() -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for profile in sorted(MANAGED_TEAMS_ROOT.glob("*/current")):
        if not db_path(profile).exists():
            continue
        try:
            key = profile.resolve()
        except Exception:
            key = profile
        if key in seen:
            continue
        seen.add(key)
        out.append(profile)
    return out


def collect_profiles(*, numbered_trade_profiles_only: bool = False, managed_teams_only: bool = False) -> list[Path]:
    if numbered_trade_profiles_only:
        return collect_numbered_trade_profiles()
    if managed_teams_only:
        return collect_managed_team_profiles()

    paths: list[Path] = []
    paths.extend(sorted(MANAGED_TEAMS_ROOT.glob("*/current")))
    paths.extend(sorted(TRADE_PROFILE_ROOT.glob("*/Data")))
    out: list[Path] = []
    seen: set[Path] = set()
    failed_profiles = failed_new_team_profiles()
    for path in paths:
        if not db_path(path).exists():
            continue
        try:
            key = path.resolve()
        except Exception:
            key = path
        if key in failed_profiles:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def sync_one(profile: Path, args: argparse.Namespace) -> dict[str, Any]:
    before = current_team_summary(profile)
    auth = local_auth_from_container(profile)
    if not auth:
        return {"profileData": str(profile), "ok": False, "error": "could not generate auth", "before": before}
    ok, payload = request_json(SYNC_PATH, auth, args.timeout_sec)
    if not ok or not isinstance(payload, dict) or payload.get("code") != "000":
        if isinstance(payload, dict) and str(payload.get("code")) == "398":
            return {
                "profileData": str(profile),
                "ok": True,
                "skipped": True,
                "reason": "sync_unavailable_code_398",
                "before": before,
            }
        return {"profileData": str(profile), "ok": False, "error": payload, "before": before}

    result: dict[str, Any] = {
        "profileData": str(profile),
        "ok": True,
        "execute": bool(args.execute),
        "before": before,
        "fetched": {
            "teamId": before.get("ZTEAM_ID"),
            "teamName": payload.get("name"),
            "season": payload.get("season"),
            "world": payload.get("world"),
            "league": payload.get("league"),
            "players": len((payload.get("team_data") or {}).get("players") or []),
        },
    }
    if not args.execute:
        return result

    db = db_path(profile)
    if args.backup and db.exists():
        backup = db.with_suffix(db.suffix + ".pre_all_profile_sync.bak")
        if backup.exists():
            backup = db.with_suffix(db.suffix + f".pre_all_profile_sync_{backup.stat().st_mtime_ns}.bak")
        shutil.copy2(db, backup)
        result["backup"] = str(backup)

    con = sqlite3.connect(str(db))
    try:
        con.execute("begin")
        result["updated"] = update_db(con, payload)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return result


def sync_with_retries(profile: Path, args: argparse.Namespace) -> dict[str, Any]:
    attempts = 1 + max(0, int(args.retries))
    last: dict[str, Any] = {}
    for attempt in range(1, attempts + 1):
        last = sync_one(profile, args)
        last["attempt"] = attempt
        if last.get("ok") or last.get("skipped") or attempt == attempts:
            return last
        time.sleep(max(1, int(args.retry_delay_sec)))
    return last


def run_post_sync_outputs(profiles: list[Path]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for profile in profiles:
        proc = subprocess.run(
            [sys.executable, str(SNAPSHOT_SCRIPT), "--profile-data", str(profile)],
            text=True,
            capture_output=True,
            check=False,
        )
        outputs.append({"type": "snapshot", "profileData": str(profile), "returncode": proc.returncode})
    for script, kind in ((INDEX_SCRIPT, "player_index"), (ROSTER_REPORT_SCRIPT, "roster_report")):
        proc = subprocess.run([sys.executable, str(script)], text=True, capture_output=True, check=False)
        outputs.append({"type": kind, "returncode": proc.returncode})
    return outputs


def notify(result: dict[str, Any]) -> None:
    failed = result.get("failed") or []
    skipped_count = int(result.get("skippedCount") or 0)
    message = (
        f"全チーム同期完了: {result.get('okCount')}成功/{result.get('profileCount')}件"
        if not failed
        else f"全チーム同期 要確認: {len(failed)}失敗/{result.get('profileCount')}件"
    )
    if skipped_count:
        message = f"{message} / スキップ{skipped_count}件"
    subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "--title", "WebSoccer Profile Sync", "--message", message],
        check=False,
    )


def main() -> int:
    args = parse_args()
    if args.numbered_trade_profiles_only and args.managed_teams_only:
        raise SystemExit("[ERROR] --numbered-trade-profiles-only and --managed-teams-only cannot be combined")
    profiles = collect_profiles(
        numbered_trade_profiles_only=bool(args.numbered_trade_profiles_only),
        managed_teams_only=bool(args.managed_teams_only),
    )
    results = [sync_with_retries(profile, args) for profile in profiles]
    failed = [item for item in results if not item.get("ok")]
    skipped = [item for item in results if item.get("skipped")]
    post_outputs: list[dict[str, Any]] = []
    if args.execute and not args.no_snapshots:
        post_outputs = run_post_sync_outputs(
            [Path(item["profileData"]) for item in results if item.get("ok") and not item.get("skipped")]
        )
        failed.extend(item for item in post_outputs if item.get("returncode") != 0)
    result = {
        "profileCount": len(profiles),
        "okCount": sum(1 for item in results if item.get("ok") and not item.get("skipped")),
        "skippedCount": len(skipped),
        "skipped": skipped,
        "failed": failed,
        "execute": bool(args.execute),
        "results": results,
        "postSyncOutputs": post_outputs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.notify_pushover:
        notify(result)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
