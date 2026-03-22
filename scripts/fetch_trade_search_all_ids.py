#!/usr/bin/env python3
"""
Bulk fetch trade/search results by player_id.

Inputs:
  - Charles .chlz/.chlsj/.chlsx that contains at least one /trade/search/.json request
  - id range (start..end)

Outputs:
  - one JSON per player_id under:
      <out_root>/api.app.websoccer.jp/trade/search_by_id/<player_id>.json
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


API_HOST = "api.app.websoccer.jp"
SEARCH_PATH = "/trade/search/.json"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch WebSoccer trade/search for all player IDs")
    ap.add_argument(
        "--session-file",
        default=str(Path.home() / "Desktop" / "Desktop.chlz"),
        help="Path to Charles export (.chlz/.chlsj/.chlsx) that includes /trade/search/.json request.",
    )
    ap.add_argument("--start-id", type=int, default=1, help="Start player_id (inclusive).")
    ap.add_argument("--end-id", type=int, default=3600, help="End player_id (inclusive).")
    ap.add_argument(
        "--out-root",
        default=str(Path.home() / "Desktop"),
        help="Root output folder (default: ~/Desktop)",
    )
    ap.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout seconds.")
    ap.add_argument("--delay-sec", type=float, default=0.05, help="Delay between requests.")
    ap.add_argument("--progress-every", type=int, default=50, help="Print progress every N ids.")
    ap.add_argument("--force", action="store_true", help="Refetch even if output file exists.")
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS cert verification (useful when local Python trust store is stale).",
    )
    ap.add_argument(
        "--stop-on-auth-fail",
        action="store_true",
        help="Stop immediately on auth-like failures (HTTP 401/403 or code 203/201).",
    )
    return ap.parse_args()


def _parse_start_ms(start_str: str) -> int:
    s = str(start_str or "").strip()
    if not s:
        return 0
    try:
        return int(datetime.fromisoformat(s).timestamp() * 1000)
    except Exception:
        return 0


def _headers_from_meta(meta: dict) -> Dict[str, str]:
    req = (meta or {}).get("request") or {}
    header = req.get("header") or {}
    hs = header.get("headers") or []
    out: Dict[str, str] = {}
    for h in hs:
        if not isinstance(h, dict):
            continue
        k = str(h.get("name") or "").strip()
        v = str(h.get("value") or "")
        if k:
            out[k] = v
    return out


def extract_auth_from_chlz(session_file: Path) -> Optional[Dict[str, str]]:
    if not session_file.exists():
        return None

    # .chlz is zip with *-meta.json
    if session_file.suffix.lower() == ".chlz" and zipfile.is_zipfile(session_file):
        best: Tuple[int, Dict[str, str]] = (0, {})
        with zipfile.ZipFile(session_file) as zf:
            for name in zf.namelist():
                if not name.endswith("-meta.json"):
                    continue
                try:
                    meta = json.loads(zf.read(name).decode("utf-8"))
                except Exception:
                    continue
                host = str(meta.get("host") or "")
                path = str(meta.get("path") or "")
                method = str(meta.get("method") or "").upper()
                if host != API_HOST or path != SEARCH_PATH or method != "POST":
                    continue
                headers = _headers_from_meta(meta)
                gate = headers.get("Websoccer-gate-key") or headers.get("websoccer-gate-key")
                if not gate:
                    continue
                start_ms = _parse_start_ms(((meta.get("times") or {}).get("start") or ""))
                if start_ms >= best[0]:
                    best = (start_ms, headers)
        return best[1] or None

    # Fallback: raw JSON export (rare)
    try:
        obj = json.loads(session_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    txs = obj if isinstance(obj, list) else obj.get("transactions", [])
    best: Tuple[int, Dict[str, str]] = (0, {})
    for tx in txs:
        if not isinstance(tx, dict):
            continue
        host = str(tx.get("host") or "")
        path = str(tx.get("path") or "")
        method = str(tx.get("method") or "").upper()
        if host != API_HOST or path != SEARCH_PATH or method != "POST":
            continue
        headers = _headers_from_meta(tx)
        gate = headers.get("Websoccer-gate-key") or headers.get("websoccer-gate-key")
        if not gate:
            continue
        start_ms = _parse_start_ms(((tx.get("times") or {}).get("start") or ""))
        if start_ms >= best[0]:
            best = (start_ms, headers)
    return best[1] or None


def request_search(player_id: int, headers: Dict[str, str], timeout_sec: float, insecure: bool = False) -> Tuple[bool, object]:
    body = f"json=[{player_id},0]".encode("utf-8")
    req = urllib.request.Request(f"https://{API_HOST}{SEARCH_PATH}", data=body, method="POST")

    # Keep only useful request headers.
    keep = {
        "Accept",
        "Accept-Encoding",
        "Accept-Language",
        "Content-Type",
        "Connection",
        "User-Agent",
        "Websoccer-gate-key",
        "Cookie",
        "expire",
    }
    lower_map = {k.lower(): v for k, v in headers.items()}
    for k in sorted(keep):
        v = headers.get(k)
        if v is None:
            v = lower_map.get(k.lower())
        if v is not None:
            req.add_header(k, v)
    if "Content-Type" not in req.headers:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ctx),
    )
    try:
        with opener.open(req, timeout=timeout_sec) as res:
            raw = res.read().decode("utf-8")
            try:
                return True, json.loads(raw)
            except Exception:
                return False, f"invalid_json:{raw[:200]}"
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", "ignore")
        except Exception:
            msg = str(e)
        return False, f"http_{e.code}:{msg[:220]}"
    except Exception as e:
        return False, str(e)


def is_empty_trade_search(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("code") != "000":
        return False
    lst = obj.get("list")
    if not isinstance(lst, list) or not lst:
        return True
    first = lst[0]
    return isinstance(first, list) and len(first) == 0


def main() -> int:
    args = parse_args()
    session_file = Path(args.session_file).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    out_dir = out_root / API_HOST / "trade" / "search_by_id"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.start_id < 1 or args.end_id < args.start_id:
        print(f"[ERROR] invalid id range: {args.start_id}-{args.end_id}")
        return 2

    headers = extract_auth_from_chlz(session_file)
    if not headers:
        print(f"[ERROR] could not extract auth headers from: {session_file}")
        return 2
    gate = headers.get("Websoccer-gate-key") or headers.get("websoccer-gate-key") or ""
    print(f"[INFO] session: {session_file}")
    print(f"[INFO] gate-key prefix: {gate.split(':', 1)[0] if gate else '-'}")
    print(f"[INFO] range: {args.start_id}-{args.end_id} ({args.end_id - args.start_id + 1} ids)")
    print(f"[INFO] out: {out_dir}")

    total = args.end_id - args.start_id + 1
    ok = 0
    empty = 0
    non_empty = 0
    skip = 0
    fail = 0
    started = time.time()
    every = max(1, int(args.progress_every or 50))

    for i, pid in enumerate(range(args.start_id, args.end_id + 1), start=1):
        out = out_dir / f"{pid}.json"
        if out.exists() and not args.force:
            skip += 1
            if i == 1 or i % every == 0 or i == total:
                elapsed = time.time() - started
                print(f"[PROGRESS] {i}/{total} ok={ok} non_empty={non_empty} empty={empty} skip={skip} fail={fail} elapsed={elapsed:.1f}s last=skip id={pid}", flush=True)
            continue

        ok_req, data = request_search(pid, headers, args.timeout_sec, insecure=args.insecure)
        if ok_req:
            out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            ok += 1
            if is_empty_trade_search(data):
                empty += 1
            else:
                non_empty += 1
                rows = ((data.get("list") or [[]])[0] if isinstance(data, dict) else [])
                print(f"[HIT] id={pid} rows={len(rows)}", flush=True)
        else:
            fail += 1
            msg = str(data)
            if args.stop_on_auth_fail and ("http_401" in msg or "http_403" in msg or "code\": \"203\"" in msg or "code\": \"201\"" in msg):
                elapsed = time.time() - started
                print(f"[STOP] auth-like failure at id={pid}: {msg}")
                print(f"[DONE] ok={ok} non_empty={non_empty} empty={empty} skip={skip} fail={fail} total={total} elapsed={elapsed:.1f}s")
                return 1
            if i == 1 or i % every == 0:
                print(f"[WARN] id={pid} {msg}", flush=True)

        if i == 1 or i % every == 0 or i == total:
            elapsed = time.time() - started
            print(f"[PROGRESS] {i}/{total} ok={ok} non_empty={non_empty} empty={empty} skip={skip} fail={fail} elapsed={elapsed:.1f}s last=id={pid}", flush=True)
        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    elapsed = time.time() - started
    print(f"[DONE] ok={ok} non_empty={non_empty} empty={empty} skip={skip} fail={fail} total={total} elapsed={elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
