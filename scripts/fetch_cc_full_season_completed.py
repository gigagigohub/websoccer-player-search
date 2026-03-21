#!/usr/bin/env python3
"""
One-command runner for CC full-season fetch:
  1) Group league completed matches
  2) Tournament completed matches

This wraps:
  - fetch_cc_group_league_completed.py
  - fetch_cc_all_worlds_completed.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch full CC season (group + tournament) in one command")
    ap.add_argument(
        "--match-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_json"),
        help="Root folder for saved data (default: ~/Desktop/CC_match_result_json)",
    )
    ap.add_argument("--session-file", default="", help="Specific .chlsx/.chlsj path (optional)")
    ap.add_argument("--team-id", default="", help="Team ID (optional; inferred from gate-key if omitted)")
    ap.add_argument("--worlds", default="1-21", help='World range/list, e.g. "1-21" or "1,2,20"')
    ap.add_argument(
        "--season",
        type=int,
        default=0,
        help="Season selector (0=current, 1=previous). Applied to both scripts.",
    )
    ap.add_argument("--groups", default="0-8", help='Group index range/list (default: "0-8")')
    ap.add_argument("--round-max", type=int, default=12, help="Max tournament round index (default: 12)")
    ap.add_argument("--delay-sec", type=float, default=0.08, help="Delay between summary requests")
    ap.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout")
    ap.add_argument("--summary-tail", default="", help='Summary tail override (e.g. "0" or "1")')
    ap.add_argument("--progress-every", type=int, default=20, help="Print progress every N targets")
    ap.add_argument("--force", action="store_true", help="Refetch even if output exists")
    ap.add_argument("--dry-run", action="store_true", help="Only list targets, do not fetch summaries")
    return ap.parse_args()


def build_common_args(args: argparse.Namespace) -> List[str]:
    out = [
        "--match-root",
        args.match_root,
        "--worlds",
        args.worlds,
        "--delay-sec",
        str(args.delay_sec),
        "--timeout-sec",
        str(args.timeout_sec),
        "--progress-every",
        str(args.progress_every),
    ]
    if args.session_file:
        out += ["--session-file", args.session_file]
    if args.team_id:
        out += ["--team-id", args.team_id]
    if args.summary_tail:
        out += ["--summary-tail", args.summary_tail]
    if args.force:
        out.append("--force")
    if args.dry_run:
        out.append("--dry-run")
    return out


def run_step(label: str, cmd: List[str]) -> int:
    print(f"\n[STEP] {label}", flush=True)
    print("[CMD] " + " ".join(cmd), flush=True)
    cp = subprocess.run(cmd)
    if cp.returncode != 0:
        print(f"[ERROR] step failed: {label} (exit={cp.returncode})", flush=True)
    else:
        print(f"[OK] step completed: {label}", flush=True)
    return cp.returncode


def main() -> int:
    args = parse_args()
    base = Path(__file__).resolve().parent
    group_script = base / "fetch_cc_group_league_completed.py"
    tour_script = base / "fetch_cc_all_worlds_completed.py"

    common = build_common_args(args)
    group_cmd = [
        sys.executable,
        str(group_script),
        "--season-sel",
        str(args.season),
        "--groups",
        args.groups,
        *common,
    ]
    tour_cmd = [
        sys.executable,
        str(tour_script),
        "--flg-szn",
        str(args.season),
        "--round-max",
        str(args.round_max),
        *common,
    ]

    print("[INFO] Full-season run starts (group league -> tournament).", flush=True)
    rc = run_step("Group league", group_cmd)
    if rc != 0:
        return rc
    rc = run_step("Tournament", tour_cmd)
    if rc != 0:
        return rc
    print("\n[DONE] Full-season fetch finished.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

