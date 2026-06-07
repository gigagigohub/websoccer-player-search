#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sync_all_websoccer_profiles import collect_numbered_trade_profiles, db_path  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_pushover.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send one daily summary notification for numbered trade-chain profiles.")
    p.add_argument("--login-summary", required=True, help="JSON output from run_all_websoccer_login_bonus.py.")
    p.add_argument("--sync-summary", required=True, help="JSON output from sync_all_websoccer_profiles.py.")
    p.add_argument("--trade-completion-summary", default="", help="JSON output from detect_daily_trade_chain_completions.py.")
    p.add_argument("--notify-pushover", action="store_true", help="Send the combined Pushover notification.")
    return p.parse_args()


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def profile_point(profile: Path) -> int:
    con = sqlite3.connect(f"file:{db_path(profile)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("select ZPOINT from ZMOTEAMFUNDS limit 1").fetchone()
        return int((row["ZPOINT"] if row else 0) or 0)
    finally:
        con.close()


def total_points() -> tuple[int, int]:
    profiles = collect_numbered_trade_profiles()
    return len(profiles), sum(profile_point(profile) for profile in profiles)


def format_ticket_totals(totals: dict[str, Any]) -> str:
    normalized = {str(key): int(value or 0) for key, value in totals.items()}
    for key in ("1", "2", "3"):
        normalized.setdefault(key, 0)
    return ", ".join(f"{key}:{value}" for key, value in sorted(normalized.items()))


def build_summary(login: dict[str, Any], sync: dict[str, Any], trade_completion: dict[str, Any] | None = None) -> dict[str, Any]:
    point_profile_count, point_total = total_points()
    login_failed = login.get("failed") or []
    ticket_failed = login.get("ticketInquiryFailed") or []
    sync_failed = sync.get("failed") or []
    sync_skipped = sync.get("skipped") or []
    ticket_totals = login.get("ticketTotalsByType") or {}
    message = f"Numbered Teams日次: {point_profile_count}チーム / 同期 {sync.get('okCount', 0)}/{sync.get('profileCount', 0)}成功"
    if sync_skipped:
        message += f" スキップ{len(sync_skipped)}"
    message += (
        f" / ログボ対象 {login.get('loginBonusTargetCount', 0)}件"
        f" / プレゼント回収 {login.get('acceptedCount', 0)}件"
        f" / 合計P {point_total:,}"
        f" / チケット {login.get('ticketTotalCount', 0)}枚 ({format_ticket_totals(ticket_totals)})"
    )
    trade_completion = trade_completion or {}
    if trade_completion.get("completedCount"):
        message += f" / {trade_completion.get('message')}"
    issue_parts: list[str] = []
    if login_failed:
        issue_parts.append(f"ログイン/受取失敗{len(login_failed)}")
    if ticket_failed:
        issue_parts.append(f"チケット確認失敗{len(ticket_failed)}")
    if sync_failed:
        issue_parts.append(f"同期/後処理失敗{len(sync_failed)}")
    if issue_parts:
        message += " / 要確認 " + ", ".join(issue_parts)
    return {
        "profileCount": point_profile_count,
        "pointTotal": point_total,
        "ticketTotalsByType": ticket_totals,
        "ticketTotalCount": int(login.get("ticketTotalCount") or 0),
        "loginProfileCount": int(login.get("profileCount") or 0),
        "syncProfileCount": int(sync.get("profileCount") or 0),
        "loginBonusTargetCount": int(login.get("loginBonusTargetCount") or 0),
        "acceptedCount": int(login.get("acceptedCount") or 0),
        "syncOkCount": int(sync.get("okCount") or 0),
        "syncSkippedCount": len(sync_skipped),
        "tradeCompletedCount": int(trade_completion.get("completedCount") or 0),
        "tradeCompletionMessage": str(trade_completion.get("message") or ""),
        "failedCount": len(login_failed) + len(ticket_failed) + len(sync_failed),
        "message": message,
    }


def notify(message: str) -> int:
    proc = subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "--title", "WebSoccer Numbered Teams", "--message", message],
        check=False,
    )
    return int(proc.returncode or 0)


def main() -> int:
    args = parse_args()
    trade_completion = load_json(args.trade_completion_summary) if args.trade_completion_summary else None
    summary = build_summary(load_json(args.login_summary), load_json(args.sync_summary), trade_completion)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.notify_pushover:
        return notify(summary["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
