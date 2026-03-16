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
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


API_HOST = "api.app.websoccer.jp"
UA_FALLBACK = "WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0"


@dataclass
class AuthHeaders:
    cookie: str
    gate_key: str
    user_agent: str


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch completed CC summaries across worlds")
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
    ap.add_argument("--delay-sec", type=float, default=0.08, help="Delay between summary requests")
    ap.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout")
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
    return sorted(match_root.glob("*.chlsx"), key=lambda p: p.stat().st_mtime, reverse=True)


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
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            continue
        local_best_ms = -1
        latest_headers: Dict[str, str] = {}
        for tx in root.findall(".//transaction"):
            host = tx.attrib.get("host", "")
            path = tx.attrib.get("path", "")
            if host != API_HOST:
                continue
            if not (
                path.startswith("/match/summary/cc/")
                or path.startswith("/cc/tournament/")
                or path.startswith("/cc/preliminary/")
            ):
                continue
            try:
                ms = int(tx.attrib.get("startTimeMillis", "0"))
            except Exception:
                ms = 0
            headers_node = tx.find("./request/headers")
            if headers_node is None:
                continue
            hdrs: Dict[str, str] = {}
            for h in headers_node.findall("header"):
                n = (h.findtext("name") or "").strip().lower()
                v = (h.findtext("value") or "").strip()
                if n:
                    hdrs[n] = v
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
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            continue
        for tx in root.findall(".//transaction"):
            if tx.attrib.get("host", "") != API_HOST:
                continue
            path = tx.attrib.get("path", "")
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


def fetch_world_pairs(team_id: str, world_id: int, auth: AuthHeaders, timeout_sec: float) -> Tuple[List[int], str]:
    paths = [
        f"/cc/preliminary/{team_id}/{world_id}/0/0.json",
        f"/cc/tournament/{team_id}/{world_id}/0/1/1.json",
    ]
    last_err = "no_response"
    for p in paths:
        ok, data = request_json(p, auth, timeout_sec)
        if not ok:
            last_err = str(data)
            continue
        obj = data if isinstance(data, dict) else {}
        if obj.get("code") != "000":
            last_err = f"code={obj.get('code')}"
            continue
        m_data = obj.get("m_data")
        mids: List[int] = []
        for row in iter_match_rows(m_data):
            if not isinstance(row, dict):
                continue
            if not is_completed_row(row):
                continue
            try:
                mids.append(int(row.get("id")))
            except Exception:
                continue
        return sorted(set(mids)), p
    return [], last_err


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
    tails = [args.summary_tail] if args.summary_tail else (extract_summary_tails_from_session_files(files) or ["1", "0"])

    print(f"[INFO] session files: {len(files)}")
    print(f"[INFO] team_id: {team_id}")
    print(f"[INFO] worlds: {worlds[:5]} ... {worlds[-5:] if len(worlds) > 5 else worlds} (count={len(worlds)})")
    print(f"[INFO] summary tail candidates: {tails}")

    pairs: List[Tuple[int, int]] = []
    list_sources: Dict[int, str] = {}
    for wid in worlds:
        mids, src = fetch_world_pairs(team_id, wid, auth, args.timeout_sec)
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

