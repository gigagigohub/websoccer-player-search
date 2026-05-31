#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUN_CHAIN = SCRIPT_DIR / "run_trade_chain.py"
NOTIFY = SCRIPT_DIR / "notify_pushover.py"
DEFAULT_STATE_DIR = Path("local/trade_chain")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sequential scheduler for multiple WebSoccer trade chains.")
    p.add_argument(
        "--query",
        action="append",
        default=[],
        help="Query as 'player:term' or 'player term'. Can be repeated. Example: --query 'ヨルセン:6'",
    )
    p.add_argument(
        "--from-state-dir",
        action="store_true",
        help="Run every non-stopped state JSON under local/trade_chain instead of --query.",
    )
    p.add_argument("--interval-sec", type=int, default=300)
    p.add_argument("--retries", type=int, default=2, help="Retry a failed query this many additional times per cycle.")
    p.add_argument("--retry-delay-sec", type=int, default=15)
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument("--once", action="store_true", help="Run one scheduler cycle and exit.")
    p.add_argument("--execute", action="store_true", help="Pass --execute to run_trade_chain.py.")
    p.add_argument("--dry-run-json", action="store_true", help="Pass --dry-run-json to run_trade_chain.py.")
    p.add_argument("--notify-pushover", action="store_true", help="Pass --notify-pushover to run_trade_chain.py.")
    p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    p.add_argument("--max-new-teams", type=int, default=10)
    p.add_argument("--allow-managed-team-quota-use", action="store_true")
    return p.parse_args()


def parse_query(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if ":" in text:
        player, term = text.rsplit(":", 1)
    else:
        parts = text.split()
        if len(parts) != 2:
            raise ValueError(f"invalid query: {raw!r}; use 'player:term' or 'player term'")
        player, term = parts
    term = term.strip().removesuffix("期").removesuffix("期目")
    if not term.isdigit():
        raise ValueError(f"invalid term in query: {raw!r}")
    return player.strip(), term


def state_queries(state_dir: Path) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    for path in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("stopped"):
            continue
        query = data.get("query") or {}
        player = str(query.get("player") or "").strip()
        term = str(query.get("term") or "").strip()
        if player and term.isdigit():
            queries.append((player, term))
    return queries


def run_one(args: argparse.Namespace, player: str, term: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(RUN_CHAIN),
        player,
        term,
        "--max-new-teams",
        str(args.max_new_teams),
        "--timeout-sec",
        str(args.timeout_sec),
    ]
    if args.execute:
        cmd.append("--execute")
    if args.dry_run_json:
        cmd.append("--dry-run-json")
    if args.notify_pushover:
        cmd.append("--notify-pushover")
    if args.allow_managed_team_quota_use:
        cmd.append("--allow-managed-team-quota-use")
    attempts = []
    max_attempts = 1 + max(0, int(args.retries))
    for attempt in range(1, max_attempts + 1):
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        attempts.append(
            {
                "attempt": attempt,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
        if proc.returncode == 0 or attempt == max_attempts:
            break
        time.sleep(max(1, int(args.retry_delay_sec)))
    final = attempts[-1]
    return {
        "player": player,
        "term": term,
        "returncode": final["returncode"],
        "attempts": len(attempts),
        "stdout": "".join(item["stdout"] for item in attempts if item["stdout"]),
        "stderr": "".join(
            f"[attempt {item['attempt']}]\n{item['stderr']}" for item in attempts if item["stderr"]
        ),
    }


def sanitize_error_text(text: str) -> str:
    tail = (text or "")[-800:]
    patterns = [
        (r'"uuid"\s*:\s*"[^"]+"', '"uuid":"<redacted>"'),
        (r'"viewer_id"\s*:\s*"[^"]+"', '"viewer_id":"<redacted>"'),
        (r'"invite_code"\s*:\s*"[^"]+"', '"invite_code":"<redacted>"'),
        (r'"team_name"\s*:\s*"[^"]+"', '"team_name":"<redacted>"'),
        (r'"owner_name"\s*:\s*"[^"]+"', '"owner_name":"<redacted>"'),
        (r"Websoccer-gate-key[=:]\S+", "Websoccer-gate-key=<redacted>"),
        (r"Cookie[=:][^\s]+", "Cookie=<redacted>"),
        (r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}", "<redacted-uuid>"),
    ]
    for pattern, repl in patterns:
        tail = re.sub(pattern, repl, tail)
    return " ".join(tail.split())[:300]


def notify_scheduler_error(player: str, term: str, result: dict[str, Any]) -> None:
    detail = sanitize_error_text(result.get("stderr") or result.get("stdout") or "")
    message = f"{player}{term}期 要確認: scheduler failed rc={result.get('returncode')} attempts={result.get('attempts')}"
    if detail:
        message = f"{message} / {detail}"
    subprocess.run(
        [sys.executable, str(NOTIFY), "--title", "WebSoccer Trade Error", "--message", message],
        check=False,
    )


def scheduler_queries(args: argparse.Namespace) -> list[tuple[str, str]]:
    if args.from_state_dir:
        state_dir = Path(args.state_dir)
        if not state_dir.is_absolute():
            state_dir = (Path.cwd() / state_dir).resolve()
        return state_queries(state_dir)
    return [parse_query(raw) for raw in args.query]


def main() -> int:
    args = parse_args()
    if not args.query and not args.from_state_dir:
        raise SystemExit("[ERROR] pass at least one --query or use --from-state-dir")
    while True:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        queries = scheduler_queries(args)
        print(json.dumps({"cycleStartedAt": started, "queries": queries}, ensure_ascii=False), flush=True)
        for player, term in queries:
            result = run_one(args, player, term)
            print(json.dumps({k: v for k, v in result.items() if k not in {"stdout", "stderr"}}, ensure_ascii=False), flush=True)
            if result["stdout"]:
                print(result["stdout"], end="", flush=True)
            if result["stderr"]:
                print(result["stderr"], end="", file=sys.stderr, flush=True)
            if args.notify_pushover and result["returncode"] != 0:
                notify_scheduler_error(player, term, result)
        if args.once:
            return 0
        time.sleep(max(1, int(args.interval_sec)))


if __name__ == "__main__":
    raise SystemExit(main())
