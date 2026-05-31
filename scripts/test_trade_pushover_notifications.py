#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from run_trade_chain_maintenance_sweep import notification_message


NOTIFY = Path(__file__).resolve().parent / "notify_pushover.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send sample Pushover notifications for every trade automation message pattern.")
    p.add_argument("--sleep-sec", type=float, default=1.0, help="Delay between notifications.")
    return p.parse_args()


def send(title: str, message: str) -> int:
    proc = subprocess.run(
        [sys.executable, str(NOTIFY), "--title", title, "--message", "[TEST] " + message],
        text=True,
        check=False,
    )
    return proc.returncode


def main() -> int:
    args = parse_args()
    patterns = [
        (
            "WebSoccer Trade Completed",
            "ラミレス1期 成立・登録完了: メイン提示して下さい",
        ),
        (
            "WebSoccer Trade Completed",
            "ビーティー7期 獲得完了",
        ),
        (
            "WebSoccer Trade Requested",
            "ヨルセン7期 提示: ドールマン -> ヨルセン",
        ),
        (
            "WebSoccer Trade Error",
            "ヨルセン6期 要確認: request_failed trade_id=63330001 wanted=ドールマン code=301 / ランク制限の条件を満たしていません",
        ),
        (
            "WebSoccer Trade Sweep",
            notification_message(
                [
                    {"playerName": "ラミレス"},
                    {"playerName": "ヨルセン"},
                    {"playerName": "ヨルセン"},
                ],
                4,
            ),
        ),
        (
            "WebSoccer Trade Sweep",
            notification_message([], 6),
        ),
    ]
    rc = 0
    for idx, (title, message) in enumerate(patterns, start=1):
        print(f"[TEST] sending {idx}/{len(patterns)}: {title}")
        rc = max(rc, send(title, message))
        if idx != len(patterns):
            time.sleep(max(0.0, args.sleep_sec))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
