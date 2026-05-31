#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEDULER = REPO_ROOT / "scripts" / "run_trade_chain_scheduler.py"
LOG_DIR = REPO_ROOT / "local" / "trade_chain" / "logs"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Start run_trade_chain_scheduler.py in a detached screen session.")
    p.add_argument("--query", action="append", required=True, help="Query as 'player:term'. Can be repeated.")
    p.add_argument("--session-name", default="", help="screen session name. Default is derived from queries.")
    p.add_argument("--interval-sec", type=int, default=300)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--retry-delay-sec", type=int, default=15)
    p.add_argument("--timeout-sec", type=float, default=30.0)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--notify-pushover", action="store_true")
    p.add_argument("--dry-run-json", action="store_true")
    p.add_argument("--allow-managed-team-quota-use", action="store_true")
    p.add_argument("--max-new-teams", type=int, default=10)
    p.add_argument("--replace", action="store_true", help="Quit an existing screen session with the same name first.")
    return p.parse_args()


def safe_session_name(queries: list[str]) -> str:
    joined = "_".join(queries)
    asciiish = re.sub(r"[^A-Za-z0-9_]+", "_", joined).strip("_")
    if not asciiish:
        asciiish = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    return f"trade_chain_{asciiish[:40]}"


def screen_sessions() -> set[str]:
    proc = subprocess.run(["screen", "-ls"], text=True, capture_output=True, check=False)
    sessions: set[str] = set()
    for line in proc.stdout.splitlines():
        match = re.search(r"\d+\.([^\s]+)\s+\(", line)
        if match:
            sessions.add(match.group(1))
    return sessions


def main() -> int:
    args = parse_args()
    if not shutil.which("screen"):
        raise SystemExit("[ERROR] screen command not found")
    session_name = args.session_name or safe_session_name(args.query)
    if session_name in screen_sessions():
        if not args.replace:
            raise SystemExit(f"[ERROR] screen session already exists: {session_name}; pass --replace to restart it")
        subprocess.run(["screen", "-S", session_name, "-X", "quit"], check=False)
        time.sleep(1)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"trade_chain_scheduler_{stamp}_{session_name}.log"
    cmd = [
        sys.executable,
        "-u",
        str(SCHEDULER),
        "--interval-sec",
        str(args.interval_sec),
        "--retries",
        str(args.retries),
        "--retry-delay-sec",
        str(args.retry_delay_sec),
        "--timeout-sec",
        str(args.timeout_sec),
        "--max-new-teams",
        str(args.max_new_teams),
    ]
    for query in args.query:
        cmd.extend(["--query", query])
    if args.execute:
        cmd.append("--execute")
    if args.notify_pushover:
        cmd.append("--notify-pushover")
    if args.dry_run_json:
        cmd.append("--dry-run-json")
    if args.allow_managed_team_quota_use:
        cmd.append("--allow-managed-team-quota-use")

    shell_cmd = (
        f"cd {str(REPO_ROOT)!r} && "
        f"{' '.join(repr(part) for part in cmd)} >> {str(log_path)!r} 2>&1"
    )
    subprocess.run(["screen", "-dmS", session_name, "bash", "-lc", shell_cmd], check=True)
    print(f"[STARTED] session={session_name}")
    print(f"[LOG] {log_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
