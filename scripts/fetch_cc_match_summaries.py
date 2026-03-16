#!/usr/bin/env python3
"""
Fetch CC match summary JSON files in bulk using:
  1) saved list JSON files (/cc/tournament/.../*.json or /cc/preliminary/.../*.json)
  2) auth headers (Cookie + Websoccer-gate-key) extracted from Charles .chlsx

Typical flow:
  - Open one match/result on iPhone (through Charles) so fresh auth headers exist.
  - Run this script to fetch many /match/summary/cc/{match_id}/{world_id}/{tail} endpoints.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


API_HOST = "api.app.websoccer.jp"


@dataclass
class AuthHeaders:
    cookie: str
    gate_key: str
    user_agent: str


def iter_match_rows(node):
    """Yield dict rows recursively from m_data which can be nested lists."""
    if isinstance(node, dict):
        yield node
        return
    if isinstance(node, list):
        for x in node:
            yield from iter_match_rows(x)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bulk fetch WebSoccer CC match summary JSON")
    ap.add_argument(
        "--match-root",
        default=str(Path.home() / "Desktop" / "match_result"),
        help="Root folder used by Charles Mirror output (default: ~/Desktop/match_result)",
    )
    ap.add_argument(
        "--session-file",
        default="",
        help="Path to Charles .chlsx file. If omitted, latest .chlsx under --match-root is used.",
    )
    ap.add_argument(
        "--cookie",
        default="",
        help="Override Cookie header value (optional).",
    )
    ap.add_argument(
        "--gate-key",
        default="",
        help="Override Websoccer-gate-key header value (optional).",
    )
    ap.add_argument(
        "--user-agent",
        default="",
        help="Override User-Agent header value (optional).",
    )
    ap.add_argument(
        "--delay-sec",
        type=float,
        default=0.12,
        help="Delay between requests in seconds (default: 0.12)",
    )
    ap.add_argument(
        "--timeout-sec",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Refetch even if output JSON already exists.",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Fetch at most N matches (0 = no limit).",
    )
    ap.add_argument(
        "--summary-tail",
        default="",
        help="Override summary tail value (e.g. 0 or 1). Default: infer from session, fallback [1,0].",
    )
    return ap.parse_args()


def tournament_json_files(match_root: Path) -> List[Path]:
    patterns = [
        str(match_root / API_HOST / "cc" / "tournament" / "*" / "*" / "*" / "*" / "*.json"),
        str(match_root / API_HOST / "cc" / "preliminary" / "*" / "*" / "*" / "*.json"),
    ]
    out: set[Path] = set()
    for pat in patterns:
        for p in glob.glob(pat):
            out.add(Path(p))
    return sorted(out)


def extract_world_match_pairs(files: Sequence[Path]) -> List[Tuple[int, int]]:
    pairs: set[Tuple[int, int]] = set()
    for fp in files:
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        world_id = obj.get("world_id")
        m_data = obj.get("m_data")
        if not isinstance(world_id, (int, str)) or not isinstance(m_data, list):
            continue
        try:
            wid = int(world_id)
        except Exception:
            continue
        for row in iter_match_rows(m_data):
            mid = row.get("id")
            try:
                match_id = int(mid)
            except Exception:
                continue
            pairs.add((match_id, wid))
    return sorted(pairs)


def extract_pairs_from_session_tournament(chlsx_path: Path) -> List[Tuple[int, int]]:
    pairs: set[Tuple[int, int]] = set()
    try:
        root = ET.parse(chlsx_path).getroot()
    except Exception:
        return []

    for tx in root.findall(".//transaction"):
        host = tx.attrib.get("host", "")
        path = tx.attrib.get("path", "")
        if host != API_HOST:
            continue
        if not (path.startswith("/cc/tournament/") or path.startswith("/cc/preliminary/")):
            continue
        body_node = tx.find("./response/body")
        if body_node is None:
            continue
        body = (body_node.text or "").strip()
        if not body:
            continue
        try:
            obj = json.loads(body)
        except Exception:
            continue
        world_id = obj.get("world_id")
        m_data = obj.get("m_data")
        if not isinstance(world_id, (int, str)) or not isinstance(m_data, list):
            continue
        try:
            wid = int(world_id)
        except Exception:
            continue
        for row in iter_match_rows(m_data):
            mid = row.get("id")
            try:
                pairs.add((int(mid), wid))
            except Exception:
                continue
    return sorted(pairs)


def extract_summary_tails_from_session(chlsx_path: Path) -> List[str]:
    tails: set[str] = set()
    try:
        root = ET.parse(chlsx_path).getroot()
    except Exception:
        return []

    for tx in root.findall(".//transaction"):
        host = tx.attrib.get("host", "")
        path = tx.attrib.get("path", "")
        if host != API_HOST:
            continue
        parts = path.strip("/").split("/")
        # /match/summary/cc/{match_id}/{world_id}/{tail}
        if len(parts) == 6 and parts[:3] == ["match", "summary", "cc"]:
            tails.add(parts[-1])
    return sorted(tails)


def latest_session_file(match_root: Path) -> Optional[Path]:
    files = sorted(match_root.glob("*.chlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def extract_auth_from_chlsx(chlsx_path: Path) -> Optional[AuthHeaders]:
    try:
        root = ET.parse(chlsx_path).getroot()
    except Exception:
        return None

    latest_ms = -1
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
        millis_raw = tx.attrib.get("startTimeMillis", "0")
        try:
            millis = int(millis_raw)
        except Exception:
            millis = 0
        headers_node = tx.find("./request/headers")
        if headers_node is None:
            continue
        hdrs: Dict[str, str] = {}
        for h in headers_node.findall("header"):
            name = (h.findtext("name") or "").strip()
            value = (h.findtext("value") or "").strip()
            if name:
                hdrs[name.lower()] = value
        if millis >= latest_ms:
            latest_ms = millis
            latest_headers = hdrs

    cookie = latest_headers.get("cookie", "")
    gate_key = latest_headers.get("websoccer-gate-key", "")
    user_agent = latest_headers.get(
        "user-agent", "WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0"
    )
    if not gate_key:
        return None
    return AuthHeaders(cookie=cookie, gate_key=gate_key, user_agent=user_agent)


def output_path(match_root: Path, match_id: int, world_id: int) -> Path:
    return match_root / API_HOST / "match" / "summary" / "cc" / str(match_id) / str(world_id) / "1.json"


def fetch_one(
    match_id: int,
    world_id: int,
    headers: AuthHeaders,
    timeout_sec: float,
    summary_tails: Sequence[str],
) -> Tuple[bool, str]:
    last_err = "unknown"
    for tail in summary_tails:
        url = f"https://{API_HOST}/match/summary/cc/{match_id}/{world_id}/{tail}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "*/*",
                "Websoccer-gate-key": headers.gate_key,
                "User-Agent": headers.user_agent,
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            },
            method="GET",
        )
        if headers.cookie:
            req.add_header("Cookie", headers.cookie)
        try:
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout_sec, context=context) as res:
                body = res.read().decode("utf-8", errors="replace")
                return True, body
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}"
            try:
                detail = e.read().decode("utf-8", errors="replace")[:200]
                if detail:
                    msg += f" {detail}"
            except Exception:
                pass
            last_err = f"tail={tail} {msg}"
        except Exception as e:  # noqa: BLE001
            last_err = f"tail={tail} {e}"
    return False, last_err


def main() -> int:
    args = parse_args()
    match_root = Path(args.match_root).expanduser().resolve()
    if not match_root.exists():
        print(f"[ERROR] match root not found: {match_root}")
        return 2

    list_files = tournament_json_files(match_root)
    pairs: List[Tuple[int, int]] = []
    if list_files:
        pairs = extract_world_match_pairs(list_files)

    auth: Optional[AuthHeaders] = None
    sfile = Path(args.session_file).expanduser().resolve() if args.session_file else latest_session_file(match_root)

    # Fallback source for pairs: tournament responses inside Charles session file
    if not pairs and sfile and sfile.exists():
        pairs = extract_pairs_from_session_tournament(sfile)
        if pairs:
            print(f"[INFO] target pairs extracted from session tournament responses: {sfile}")

    if not pairs:
        print(f"[ERROR] no target pairs found.")
        print(f"- checked tournament JSON under: {match_root}")
        if sfile:
            print(f"- checked session file: {sfile}")
        print("Hint: open CC bracket/list at least once so tournament response is captured.")
        return 2

    if args.cookie and args.gate_key:
        auth = AuthHeaders(
            cookie=args.cookie.strip(),
            gate_key=args.gate_key.strip(),
            user_agent=(args.user_agent.strip() or "WebSoccer/1.3.28 CFNetwork/3860.400.51 Darwin/25.3.0"),
        )
    else:
        if not sfile or not sfile.exists():
            print("[ERROR] session file not found. Provide --session-file or place .chlsx under match root.")
            return 2
        auth = extract_auth_from_chlsx(sfile)
        if not auth:
            print(f"[ERROR] could not extract Cookie/Websoccer-gate-key from: {sfile}")
            return 2
        print(f"[INFO] auth extracted from: {sfile}")

    limit = args.limit if args.limit and args.limit > 0 else len(pairs)
    targets = pairs[:limit]
    if args.summary_tail:
        summary_tails = [args.summary_tail]
    else:
        inferred = extract_summary_tails_from_session(sfile) if sfile and sfile.exists() else []
        summary_tails = inferred or ["1", "0"]

    fetched_ok = 0
    skipped_exists = 0
    failed = 0

    print(f"[INFO] list files: {len(list_files)}")
    print(f"[INFO] unique targets: {len(pairs)}")
    print(f"[INFO] fetch count this run: {len(targets)}")
    print(f"[INFO] summary tail candidates: {summary_tails}")

    for idx, (mid, wid) in enumerate(targets, start=1):
        out = output_path(match_root, mid, wid)
        out.parent.mkdir(parents=True, exist_ok=True)

        if out.exists() and not args.force:
            skipped_exists += 1
            continue

        ok, data_or_err = fetch_one(mid, wid, auth, args.timeout_sec, summary_tails)
        if not ok:
            failed += 1
            print(f"[WARN] {idx}/{len(targets)} mid={mid} wid={wid} failed: {data_or_err}")
            continue

        # quick validity check
        try:
            payload = json.loads(data_or_err)
            code = payload.get("code")
            if code != "000":
                failed += 1
                print(f"[WARN] {idx}/{len(targets)} mid={mid} wid={wid} code={code}")
                continue
        except Exception:
            failed += 1
            print(f"[WARN] {idx}/{len(targets)} mid={mid} wid={wid} invalid JSON")
            continue

        out.write_text(data_or_err, encoding="utf-8")
        fetched_ok += 1

        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    print(
        f"[DONE] ok={fetched_ok} skipped_exists={skipped_exists} failed={failed} "
        f"total_targets={len(targets)}"
    )
    if failed > 0:
        print("[HINT] gate-key expiry is common. Open one match on iPhone, then rerun immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
