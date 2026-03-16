#!/usr/bin/env python3
"""
Fetch completed CC group-league match summaries across worlds.

Target list source:
  /cc/preliminary/{team_id}/{world_id}/{group_idx}/{season_sel}.json
where `group_idx` should be swept (typically 0-8) to collect all group-league matches.

Flow:
  1) Extract latest gate-key/user-agent(/cookie) from Charles .chlsx files
  2) Fetch preliminary list endpoints for each world/mode
  3) Keep only completed rows (game_status != 0 and numeric result present)
  4) Fetch /match/summary/cc/{match_id}/{world_id}/{tail}
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from fetch_cc_all_worlds_completed import (
    API_HOST,
    extract_auth_from_session_files,
    extract_summary_tails_from_session_files,
    is_completed_row,
    iter_match_rows,
    parse_worlds,
    request_json,
    session_files,
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch completed CC group-league summaries across worlds")
    ap.add_argument(
        "--match-root",
        default=str(Path.home() / "Desktop" / "match_result"),
        help="Root folder for saved data (default: ~/Desktop/match_result)",
    )
    ap.add_argument(
        "--session-file",
        default="",
        help="Specific .chlsx path (optional). If omitted, all .chlsx under match root are scanned.",
    )
    ap.add_argument(
        "--team-id",
        default="",
        help="Team ID used in list endpoints. Default: infer from gate-key prefix.",
    )
    ap.add_argument(
        "--worlds",
        default="1-21",
        help='World range/list, e.g. "1-21" or "1,2,20" (default: 1-21)',
    )
    ap.add_argument(
        "--season-sel",
        type=int,
        default=1,
        help="Season selector used by preliminary endpoints (0=current, 1=previous).",
    )
    ap.add_argument(
        "--groups",
        default="0-8",
        help='Group index range/list, e.g. "0-8" or "0,2,3" (default: 0-8).',
    )
    ap.add_argument("--delay-sec", type=float, default=0.08, help="Delay between summary requests")
    ap.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout")
    ap.add_argument("--force", action="store_true", help="Refetch even if output exists")
    ap.add_argument("--summary-tail", default="", help='Summary tail override (e.g. "0" or "1")')
    ap.add_argument("--dry-run", action="store_true", help="Only list targets, do not fetch summaries")
    return ap.parse_args()


def parse_groups(raw: str) -> List[int]:
    raw = (raw or "").strip()
    if "-" in raw and "," not in raw:
        a, b = raw.split("-", 1)
        s, e = int(a), int(b)
        lo, hi = min(s, e), max(s, e)
        return list(range(lo, hi + 1))
    out: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return sorted(set(out))


def output_path(match_root: Path, match_id: int, world_id: int) -> Path:
    return match_root / API_HOST / "match" / "summary" / "cc" / str(match_id) / str(world_id) / "1.json"


def fetch_summary(match_id: int, world_id: int, tails: Sequence[str], auth, timeout_sec: float) -> Tuple[bool, str]:
    last_err = "unknown"
    for tail in tails:
        path = f"/match/summary/cc/{match_id}/{world_id}/{tail}"
        ok, data = request_json(path, auth, timeout_sec)
        if not ok:
            last_err = str(data)
            continue
        obj = data if isinstance(data, dict) else {}
        code = obj.get("code")
        if code == "000":
            return True, json.dumps(obj, ensure_ascii=False)
        last_err = f"code={code}"
    return False, last_err


def fetch_world_pairs(
    team_id: str,
    world_id: int,
    season_sel: int,
    groups: Sequence[int],
    auth,
    timeout_sec: float,
) -> Tuple[List[int], str]:
    mids: set[int] = set()
    used: List[str] = []
    for group_idx in groups:
        p = f"/cc/preliminary/{team_id}/{world_id}/{group_idx}/{season_sel}.json"
        ok, data = request_json(p, auth, timeout_sec)
        if not ok:
            continue
        obj = data if isinstance(data, dict) else {}
        if obj.get("code") != "000":
            continue
        add = 0
        for row in iter_match_rows(obj.get("m_data")):
            if not isinstance(row, dict):
                continue
            if not is_completed_row(row):
                continue
            try:
                before = len(mids)
                mids.add(int(row.get("id")))
                if len(mids) > before:
                    add += 1
            except Exception:
                continue
        if add > 0:
            used.append(p)

    if not mids:
        return [], "no_completed_rows"
    src = " + ".join(used[:2]) if used else "unknown"
    if len(used) > 2:
        src += f" (+{len(used)-2} more)"
    return sorted(mids), src


def main() -> int:
    args = parse_args()
    match_root = Path(args.match_root).expanduser().resolve()
    match_root.mkdir(parents=True, exist_ok=True)

    files = [Path(args.session_file).expanduser().resolve()] if args.session_file else session_files(match_root)
    if not files:
        print("[ERROR] no .chlsx files found.")
        return 2

    auth = extract_auth_from_session_files(files)
    if not auth:
        print("[ERROR] could not extract gate-key from .chlsx files.")
        return 2

    team_id = (args.team_id or auth.gate_key.split(":", 1)[0]).strip()
    if not team_id.isdigit():
        print(f"[ERROR] invalid team_id: {team_id}")
        return 2

    worlds = parse_worlds(args.worlds)
    groups = parse_groups(args.groups)
    tails = [args.summary_tail] if args.summary_tail else (extract_summary_tails_from_session_files(files) or ["1", "0"])

    print(f"[INFO] session files: {len(files)}")
    print(f"[INFO] team_id: {team_id}")
    print(f"[INFO] season_sel: {args.season_sel}")
    print(f"[INFO] groups: {groups}")
    print(f"[INFO] worlds: {worlds[:5]} ... {worlds[-5:] if len(worlds) > 5 else worlds} (count={len(worlds)})")
    print(f"[INFO] summary tail candidates: {tails}")

    pairs: List[Tuple[int, int]] = []
    for wid in worlds:
        mids, src = fetch_world_pairs(team_id, wid, args.season_sel, groups, auth, args.timeout_sec)
        for mid in mids:
            pairs.append((mid, wid))
        print(f"[LIST] world={wid} completed_matches={len(mids)} source={src}")

    pairs = sorted(set(pairs))
    print(f"[INFO] total completed targets: {len(pairs)}")
    if not pairs:
        print("[ERROR] no completed match targets found.")
        return 2

    if args.dry_run:
        return 0

    ok_count = 0
    skip_count = 0
    fail_count = 0
    for i, (mid, wid) in enumerate(pairs, start=1):
        out = output_path(match_root, mid, wid)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not args.force:
            skip_count += 1
            continue
        ok, payload_or_err = fetch_summary(mid, wid, tails, auth, args.timeout_sec)
        if not ok:
            fail_count += 1
            print(f"[WARN] {i}/{len(pairs)} mid={mid} wid={wid} {payload_or_err}")
            continue
        out.write_text(payload_or_err, encoding="utf-8")
        ok_count += 1
        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    print(f"[DONE] ok={ok_count} skipped_exists={skip_count} failed={fail_count} total_targets={len(pairs)}")
    if fail_count:
        print("[HINT] Open one match on iPhone to refresh gate-key, then rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
