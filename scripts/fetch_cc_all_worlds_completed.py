#!/usr/bin/env python3
"""
Fetch completed CC match summaries for all worlds while avoiding upcoming matches (code 203).

Flow:
  1) Extract latest gate-key/user-agent(/cookie) from Charles .chlsx files
  2) Fetch per-world list endpoint (/cc/preliminary/... or /cc/tournament/...)
  3) Keep only completed rows (game_status != 0 and result present)
  4) Fetch /match/summary/cc/{match_id}/{world_id}/{tail} for those rows
"""

from __future__ import annotations

import argparse
import glob
import json
import ssl
import time
from datetime import datetime
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


API_HOST = "api.app.websoccer.jp"
UA_FALLBACK = "WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0"
DEFAULT_MATCH_ROOTS = [
    Path.home() / "Desktop" / "CC_match_result_json",
    Path.home() / "Desktop" / "match_result",
    Path.home() / "Desktop" / "CM_match_result_json",
]


@dataclass
class AuthHeaders:
    cookie: str
    gate_key: str
    user_agent: str


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch completed CC summaries across worlds")
    ap.add_argument(
        "--match-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_json"),
        help="Root folder for saved data (default: ~/Desktop/CC_match_result_json)",
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
        "--flg-szn",
        type=int,
        default=0,
        help="Season selector used by list endpoints (0=current, 1=previous in many cases).",
    )
    ap.add_argument(
        "--round-max",
        type=int,
        default=12,
        help="Max tournament round index to scan (default: 12).",
    )
    ap.add_argument("--delay-sec", type=float, default=0.08, help="Delay between summary requests")
    ap.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout")
    ap.add_argument("--progress-every", type=int, default=20, help="Print progress every N targets (default: 20)")
    ap.add_argument("--force", action="store_true", help="Refetch even if output exists")
    ap.add_argument("--summary-tail", default="", help='Summary tail override (e.g. "0" or "1")')
    ap.add_argument("--dry-run", action="store_true", help="Only list targets, do not fetch summaries")
    return ap.parse_args()


def parse_worlds(raw: str) -> List[int]:
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


def session_files(match_root: Path) -> List[Path]:
    files = sorted(
        [*match_root.rglob("*.chlsx"), *match_root.rglob("*.chlsj")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if files:
        return files
    desktop = Path.home() / "Desktop"
    return sorted(
        [*desktop.rglob("*.chlsx"), *desktop.rglob("*.chlsj")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def resolve_match_root(raw: str) -> Path:
    req = Path(raw).expanduser()
    if req.exists():
        return req.resolve()
    for cand in DEFAULT_MATCH_ROOTS:
        if cand.exists():
            print(f"[INFO] --match-root not found, using existing root: {cand}")
            return cand.resolve()
    return req.resolve()


def _parse_start_ms_from_chlsj(tx: dict) -> int:
    start = str((tx.get("times") or {}).get("start") or "").strip()
    if not start:
        return 0
    try:
        # ISO8601, e.g. 2026-03-22T00:05:46.305+09:00
        return int(datetime.fromisoformat(start).timestamp() * 1000)
    except Exception:
        return 0


def _iter_tx_from_session(fp: Path):
    suffix = fp.suffix.lower()
    if suffix == ".chlsx":
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            return
        for tx in root.findall(".//transaction"):
            host = tx.attrib.get("host", "")
            path = tx.attrib.get("path", "")
            try:
                ms = int(tx.attrib.get("startTimeMillis", "0"))
            except Exception:
                ms = 0
            headers_node = tx.find("./request/headers")
            hdrs: Dict[str, str] = {}
            if headers_node is not None:
                for h in headers_node.findall("header"):
                    n = (h.findtext("name") or "").strip().lower()
                    v = (h.findtext("value") or "").strip()
                    if n:
                        hdrs[n] = v
            yield host, path, ms, hdrs
        return
    if suffix == ".chlsj":
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(arr, list):
            return
        for tx in arr:
            if not isinstance(tx, dict):
                continue
            host = str(tx.get("host") or "")
            path = str(tx.get("path") or "")
            ms = _parse_start_ms_from_chlsj(tx)
            hdrs: Dict[str, str] = {}
            for h in (((tx.get("request") or {}).get("header") or {}).get("headers") or []):
                if not isinstance(h, dict):
                    continue
                n = str(h.get("name") or "").strip().lower()
                v = str(h.get("value") or "").strip()
                if n:
                    hdrs[n] = v
            yield host, path, ms, hdrs


def iter_match_rows(node):
    if isinstance(node, dict):
        yield node
        return
    if isinstance(node, list):
        for x in node:
            yield from iter_match_rows(x)


def extract_auth_from_session_files(files: Sequence[Path]) -> Optional[AuthHeaders]:
    best_ms = -1
    best_auth: Optional[AuthHeaders] = None
    for fp in files:
        local_best_ms = -1
        latest_headers: Dict[str, str] = {}
        for host, path, ms, hdrs in _iter_tx_from_session(fp):
            if host != API_HOST:
                continue
            if not (
                path.startswith("/match/summary/cc/")
                or path.startswith("/cc/tournament/")
                or path.startswith("/cc/preliminary/")
            ):
                continue
            if ms >= local_best_ms:
                local_best_ms = ms
                latest_headers = hdrs
        gate = latest_headers.get("websoccer-gate-key", "")
        if not gate:
            continue
        auth = AuthHeaders(
            cookie=latest_headers.get("cookie", ""),
            gate_key=gate,
            user_agent=latest_headers.get("user-agent", UA_FALLBACK),
        )
        if local_best_ms >= best_ms:
            best_ms = local_best_ms
            best_auth = auth
    return best_auth


def extract_summary_tails_from_session_files(files: Sequence[Path]) -> List[str]:
    tails: set[str] = set()
    for fp in files:
        for host, path, _, _ in _iter_tx_from_session(fp):
            if host != API_HOST:
                continue
            parts = path.strip("/").split("/")
            if len(parts) == 6 and parts[:3] == ["match", "summary", "cc"]:
                tails.add(parts[-1])
    return sorted(tails)


def request_json(path: str, auth: AuthHeaders, timeout_sec: float) -> Tuple[bool, dict | str]:
    url = f"https://{API_HOST}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "Websoccer-gate-key": auth.gate_key,
            "User-Agent": auth.user_agent or UA_FALLBACK,
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        },
        method="GET",
    )
    if auth.cookie:
        req.add_header("Cookie", auth.cookie)
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ctx) as res:
            body = res.read().decode("utf-8", errors="replace")
        return True, json.loads(body)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def is_completed_row(row: dict) -> bool:
    gs = row.get("game_status")
    if isinstance(gs, str):
        try:
            gs = int(gs)
        except Exception:
            gs = 0
    if not isinstance(gs, int) or gs == 0:
        return False
    result = row.get("result")
    if not isinstance(result, list) or len(result) < 2:
        return False
    # completed rows usually carry numeric strings/ints
    for v in result[:2]:
        if v in ("", None):
            return False
        try:
            int(v)
        except Exception:
            return False
    return True


def fetch_world_pairs(
    team_id: str,
    world_id: int,
    flg_szn: int,
    round_max: int,
    auth: AuthHeaders,
    timeout_sec: float,
) -> Tuple[List[int], str]:
    mids: set[int] = set()
    sources: List[str] = []

    # 1) tournament rounds sweep (main source for full-season history)
    # NOTE:
    #   tournament endpoint order is:
    #     /cc/tournament/{team_id}/{world_id}/{p_g}/{flg_szn}/{round}.json
    #   (p_g then flg_szn)
    empty_rounds = 0
    for rnd in range(1, max(1, round_max) + 1):
        p = f"/cc/tournament/{team_id}/{world_id}/1/{flg_szn}/{rnd}.json"
        ok, data = request_json(p, auth, timeout_sec)
        if not ok:
            continue
        obj = data if isinstance(data, dict) else {}
        if obj.get("code") != "000":
            continue
        found_this_round = 0
        for row in iter_match_rows(obj.get("m_data")):
            if not isinstance(row, dict):
                continue
            if not is_completed_row(row):
                continue
            try:
                mids.add(int(row.get("id")))
                found_this_round += 1
            except Exception:
                continue
        if found_this_round > 0:
            sources.append(p)
            empty_rounds = 0
        else:
            empty_rounds += 1
            # stop early if tournament rounds seem exhausted
            if empty_rounds >= 3 and rnd >= 4:
                break

    # 2) preliminary (kept as supplement)
    # preliminary endpoint order is:
    #   /cc/preliminary/{team_id}/{world_id}/{group_idx}/{season_sel}.json
    p_pre = f"/cc/preliminary/{team_id}/{world_id}/0/{flg_szn}.json"
    ok, data = request_json(p_pre, auth, timeout_sec)
    if ok:
        obj = data if isinstance(data, dict) else {}
        if obj.get("code") == "000":
            added = 0
            for row in iter_match_rows(obj.get("m_data")):
                if not isinstance(row, dict):
                    continue
                if not is_completed_row(row):
                    continue
                try:
                    before = len(mids)
                    mids.add(int(row.get("id")))
                    if len(mids) > before:
                        added += 1
                except Exception:
                    continue
            if added > 0:
                sources.append(p_pre)

    if not mids:
        return [], "no_completed_rows"
    src_label = " + ".join(sources[:2]) if sources else "unknown"
    if len(sources) > 2:
        src_label += f" (+{len(sources)-2} more)"
    return sorted(mids), src_label


def output_path(match_root: Path, match_id: int, world_id: int) -> Path:
    return match_root / API_HOST / "match" / "summary" / "cc" / str(match_id) / str(world_id) / "1.json"


def fetch_summary(match_id: int, world_id: int, tails: Sequence[str], auth: AuthHeaders, timeout_sec: float) -> Tuple[bool, str]:
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


def main() -> int:
    args = parse_args()
    match_root = resolve_match_root(args.match_root)
    match_root.mkdir(parents=True, exist_ok=True)

    files = [Path(args.session_file).expanduser().resolve()] if args.session_file else session_files(match_root)
    if not files:
        print("[ERROR] no .chlsx/.chlsj files found.")
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
    tails = [args.summary_tail] if args.summary_tail else (extract_summary_tails_from_session_files(files) or ["1", "0"])

    print(f"[INFO] session files: {len(files)}")
    print(f"[INFO] team_id: {team_id}")
    print(f"[INFO] flg_szn: {args.flg_szn}")
    print(f"[INFO] worlds: {worlds[:5]} ... {worlds[-5:] if len(worlds) > 5 else worlds} (count={len(worlds)})")
    print(f"[INFO] summary tail candidates: {tails}")

    pairs: List[Tuple[int, int]] = []
    list_sources: Dict[int, str] = {}
    for wid in worlds:
        mids, src = fetch_world_pairs(
            team_id, wid, args.flg_szn, args.round_max, auth, args.timeout_sec
        )
        list_sources[wid] = src
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
    started = time.time()
    every = max(1, int(args.progress_every or 20))
    for i, (mid, wid) in enumerate(pairs, start=1):
        out = output_path(match_root, mid, wid)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not args.force:
            skip_count += 1
            if i == 1 or i % every == 0 or i == len(pairs):
                elapsed = time.time() - started
                print(
                    f"[PROGRESS] {i}/{len(pairs)} ok={ok_count} skip={skip_count} fail={fail_count} "
                    f"elapsed={elapsed:.1f}s last=skip mid={mid} wid={wid}",
                    flush=True,
                )
            continue
        ok, payload_or_err = fetch_summary(mid, wid, tails, auth, args.timeout_sec)
        if not ok:
            fail_count += 1
            print(f"[WARN] {i}/{len(pairs)} mid={mid} wid={wid} {payload_or_err}")
            if i == 1 or i % every == 0 or i == len(pairs):
                elapsed = time.time() - started
                print(
                    f"[PROGRESS] {i}/{len(pairs)} ok={ok_count} skip={skip_count} fail={fail_count} "
                    f"elapsed={elapsed:.1f}s last=fail mid={mid} wid={wid}",
                    flush=True,
                )
            continue
        out.write_text(payload_or_err, encoding="utf-8")
        ok_count += 1
        if i == 1 or i % every == 0 or i == len(pairs):
            elapsed = time.time() - started
            print(
                f"[PROGRESS] {i}/{len(pairs)} ok={ok_count} skip={skip_count} fail={fail_count} "
                f"elapsed={elapsed:.1f}s last=ok mid={mid} wid={wid}",
                flush=True,
            )
        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    print(f"[DONE] ok={ok_count} skipped_exists={skip_count} failed={fail_count} total_targets={len(pairs)}")
    if fail_count:
        print("[HINT] Open one match on iPhone to refresh gate-key, then rerun.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
