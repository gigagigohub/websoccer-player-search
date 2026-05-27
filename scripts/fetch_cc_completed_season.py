#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from fetch_cc_all_worlds_completed import (
    API_HOST,
    DEFAULT_MATCH_ROOT,
    AuthHeaders,
    extract_auth_from_session_files,
    extract_summary_tails_from_session_files,
    is_completed_row,
    iter_match_rows,
    parse_worlds,
    request_json,
    session_files,
)


@dataclass(frozen=True, order=True)
class MatchTarget:
    match_id: int
    world_id: int
    source: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch completed CC group-league and tournament summaries.")
    p.add_argument("--match-root", default=str(DEFAULT_MATCH_ROOT), help=f"CC JSON root (default: {DEFAULT_MATCH_ROOT})")
    p.add_argument("--session-file", default="", help="Specific Charles .chlsx/.chlsj/.chlz session")
    p.add_argument("--team-id", default="", help="Team ID. Default: infer from gate-key prefix")
    p.add_argument("--worlds", default="1-21", help='World range/list, e.g. "1-21" or "1,2,20"')
    p.add_argument("--season", type=int, default=1, help="Season selector: 0=current, 1=previous")
    p.add_argument("--groups", default="0-8", help='Group index range/list, e.g. "0-8" or "0,2,3"')
    p.add_argument("--round-max", type=int, default=12, help="Max tournament round index")
    p.add_argument("--delay-sec", type=float, default=0.08, help="Delay between summary requests")
    p.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout")
    p.add_argument("--summary-tail", default="", help='Summary tail override, e.g. "0" or "1"')
    p.add_argument("--progress-every", type=int, default=20, help="Print progress every N targets")
    p.add_argument("--force", action="store_true", help="Refetch even if output exists")
    p.add_argument("--dry-run", action="store_true", help="List targets only; do not fetch summaries")
    p.add_argument("--skip-group", action="store_true", help="Skip group-league targets")
    p.add_argument("--skip-tournament", action="store_true", help="Skip tournament targets")
    return p.parse_args()


def parse_int_set(raw: str) -> list[int]:
    raw = (raw or "").strip()
    if "-" in raw and "," not in raw:
        start, end = [int(x) for x in raw.split("-", 1)]
        lo, hi = min(start, end), max(start, end)
        return list(range(lo, hi + 1))
    values: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            values.add(int(part))
    return sorted(values)


def completed_match_ids(payload: object) -> list[int]:
    mids: set[int] = set()
    obj = payload if isinstance(payload, dict) else {}
    if obj.get("code") != "000":
        return []
    for row in iter_match_rows(obj.get("m_data")):
        if not isinstance(row, dict) or not is_completed_row(row):
            continue
        try:
            mids.add(int(row.get("id")))
        except Exception:
            continue
    return sorted(mids)


def list_group_targets(
    team_id: str,
    worlds: Sequence[int],
    groups: Sequence[int],
    season: int,
    auth: AuthHeaders,
    timeout_sec: float,
) -> list[MatchTarget]:
    targets: list[MatchTarget] = []
    for world_id in worlds:
        world_targets: dict[int, str] = {}
        for group_idx in groups:
            source = f"/cc/preliminary/{team_id}/{world_id}/{group_idx}/{season}.json"
            ok, data = request_json(source, auth, timeout_sec)
            if not ok:
                continue
            for match_id in completed_match_ids(data):
                world_targets.setdefault(match_id, source)
        for match_id, source in sorted(world_targets.items()):
            targets.append(MatchTarget(match_id=match_id, world_id=world_id, source=source))
        print(f"[LIST] kind=group world={world_id} completed_matches={len(world_targets)}", flush=True)
    return targets


def list_tournament_targets(
    team_id: str,
    worlds: Sequence[int],
    season: int,
    round_max: int,
    auth: AuthHeaders,
    timeout_sec: float,
) -> list[MatchTarget]:
    targets: list[MatchTarget] = []
    for world_id in worlds:
        world_targets: dict[int, str] = {}
        empty_rounds = 0
        for round_idx in range(1, max(1, round_max) + 1):
            source = f"/cc/tournament/{team_id}/{world_id}/1/{season}/{round_idx}.json"
            ok, data = request_json(source, auth, timeout_sec)
            if not ok:
                continue
            mids = completed_match_ids(data)
            if mids:
                empty_rounds = 0
                for match_id in mids:
                    world_targets.setdefault(match_id, source)
            else:
                empty_rounds += 1
                if empty_rounds >= 3 and round_idx >= 4:
                    break
        for match_id, source in sorted(world_targets.items()):
            targets.append(MatchTarget(match_id=match_id, world_id=world_id, source=source))
        print(f"[LIST] kind=tournament world={world_id} completed_matches={len(world_targets)}", flush=True)
    return targets


def output_path(match_root: Path, target: MatchTarget) -> Path:
    return (
        match_root
        / API_HOST
        / "match"
        / "summary"
        / "cc"
        / str(target.match_id)
        / str(target.world_id)
        / "1.json"
    )


def fetch_summary(target: MatchTarget, tails: Sequence[str], auth: AuthHeaders, timeout_sec: float) -> tuple[bool, str]:
    last_err = "unknown"
    for tail in tails:
        path = f"/match/summary/cc/{target.match_id}/{target.world_id}/{tail}"
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


def resolve_auth(args: argparse.Namespace, match_root: Path) -> tuple[AuthHeaders, list[Path]]:
    files = [Path(args.session_file).expanduser().resolve()] if args.session_file else session_files(match_root)
    if not files:
        raise RuntimeError("no .chlsx/.chlsj/.chlz files found")
    auth = extract_auth_from_session_files(files)
    if not auth:
        raise RuntimeError("could not extract Websoccer-gate-key from Charles session files")
    return auth, files


def unique_targets(targets: Iterable[MatchTarget]) -> list[MatchTarget]:
    by_pair: dict[tuple[int, int], MatchTarget] = {}
    for target in targets:
        by_pair.setdefault((target.match_id, target.world_id), target)
    return sorted(by_pair.values(), key=lambda x: (x.world_id, x.match_id))


def main() -> int:
    args = parse_args()
    if args.skip_group and args.skip_tournament:
        print("[ERROR] both --skip-group and --skip-tournament were set", file=sys.stderr)
        return 2

    match_root = Path(args.match_root).expanduser().resolve()
    match_root.mkdir(parents=True, exist_ok=True)
    auth, files = resolve_auth(args, match_root)

    team_id = (args.team_id or auth.gate_key.split(":", 1)[0]).strip()
    if not team_id.isdigit():
        print(f"[ERROR] invalid team_id: {team_id}", file=sys.stderr)
        return 2

    worlds = parse_worlds(args.worlds)
    groups = parse_int_set(args.groups)
    tails = [args.summary_tail] if args.summary_tail else (extract_summary_tails_from_session_files(files) or ["1", "0"])

    print(f"[INFO] session files: {len(files)}")
    print(f"[INFO] team_id: {team_id}")
    print(f"[INFO] season: {args.season}")
    print(f"[INFO] worlds: {worlds[:5]} ... {worlds[-5:] if len(worlds) > 5 else worlds} (count={len(worlds)})")
    print(f"[INFO] groups: {groups}")
    print(f"[INFO] summary tail candidates: {tails}")

    targets: list[MatchTarget] = []
    if not args.skip_group:
        targets.extend(list_group_targets(team_id, worlds, groups, args.season, auth, args.timeout_sec))
    if not args.skip_tournament:
        targets.extend(list_tournament_targets(team_id, worlds, args.season, args.round_max, auth, args.timeout_sec))
    targets = unique_targets(targets)

    print(f"[INFO] total completed targets: {len(targets)}")
    if not targets:
        print("[ERROR] no completed match targets found", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0

    ok_count = 0
    skip_count = 0
    fail_count = 0
    started = time.time()
    every = max(1, int(args.progress_every or 20))
    for idx, target in enumerate(targets, start=1):
        out = output_path(match_root, target)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not args.force:
            skip_count += 1
            status = "skip"
        else:
            ok, payload_or_err = fetch_summary(target, tails, auth, args.timeout_sec)
            if ok:
                out.write_text(payload_or_err, encoding="utf-8")
                ok_count += 1
                status = "ok"
            else:
                fail_count += 1
                status = f"fail {payload_or_err}"
                print(f"[WARN] mid={target.match_id} wid={target.world_id} {payload_or_err}", flush=True)
        if idx == 1 or idx % every == 0 or idx == len(targets):
            elapsed = time.time() - started
            print(
                f"[PROGRESS] {idx}/{len(targets)} ok={ok_count} skip={skip_count} fail={fail_count} "
                f"elapsed={elapsed:.1f}s last={status} mid={target.match_id} wid={target.world_id}",
                flush=True,
            )
        if status == "ok" and args.delay_sec > 0:
            time.sleep(args.delay_sec)

    print(f"[DONE] ok={ok_count} skipped_exists={skip_count} failed={fail_count} total_targets={len(targets)}")
    if fail_count:
        print("[HINT] gate-key may be expired. Capture a fresh key with Charles and rerun.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
