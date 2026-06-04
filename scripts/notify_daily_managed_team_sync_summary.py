#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_pushover.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send one daily summary notification for managed WebSoccer teams.")
    p.add_argument("--login-summary", required=True, help="JSON output from run_all_websoccer_login_bonus.py.")
    p.add_argument("--sync-summary", required=True, help="JSON output from sync_all_websoccer_profiles.py.")
    p.add_argument("--notify-pushover", action="store_true", help="Send the Pushover notification.")
    return p.parse_args()


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_summary(login: dict[str, Any], sync: dict[str, Any]) -> dict[str, Any]:
    login_failed = login.get("failed") or []
    sync_failed = sync.get("failed") or []
    sync_skipped = sync.get("skipped") or []
    profile_count = int(sync.get("profileCount") or login.get("profileCount") or 0)
    failed_count = len(login_failed) + len(sync_failed)

    if failed_count:
        message = (
            f"管理チーム日次 要確認: {failed_count}失敗 / "
            f"ログボ対象 {login.get('loginBonusTargetCount', 0)}件 / "
            f"プレゼント回収 {login.get('acceptedCount', 0)}件 / "
            f"同期 {sync.get('okCount', 0)}/{sync.get('profileCount', 0)}成功"
        )
    else:
        message = (
            f"管理チーム日次完了: {profile_count}チーム / "
            f"ログボ対象 {login.get('loginBonusTargetCount', 0)}件 / "
            f"プレゼント回収 {login.get('acceptedCount', 0)}件 / "
            f"同期 {sync.get('okCount', 0)}/{sync.get('profileCount', 0)}成功"
        )
    if sync_skipped:
        message += f" / スキップ{len(sync_skipped)}"

    return {
        "profileCount": profile_count,
        "loginProfileCount": int(login.get("profileCount") or 0),
        "syncProfileCount": int(sync.get("profileCount") or 0),
        "loginBonusTargetCount": int(login.get("loginBonusTargetCount") or 0),
        "acceptedCount": int(login.get("acceptedCount") or 0),
        "syncOkCount": int(sync.get("okCount") or 0),
        "syncSkippedCount": len(sync_skipped),
        "failedCount": failed_count,
        "message": message,
    }


def notify(message: str) -> int:
    proc = subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "--title", "WebSoccer Managed Teams", "--message", message],
        check=False,
    )
    return int(proc.returncode or 0)


def main() -> int:
    args = parse_args()
    summary = build_summary(load_json(args.login_summary), load_json(args.sync_summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.notify_pushover:
        return notify(summary["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
