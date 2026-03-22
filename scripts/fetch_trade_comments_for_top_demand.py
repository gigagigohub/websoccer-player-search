#!/usr/bin/env python3
"""
Fetch trade/search results for top-demand players and export comments CSV.

Flow:
  1) Read top N player_ids from ranking CSV (default: trade_demand_supply_gap_prefer_nr_from_raw.csv)
  2) Fetch /trade/search/.json for each id using auth from Charles session file
  3) Save raw JSON per id
  4) Export rows/comments to CSV
"""

from __future__ import annotations

import argparse
import csv
import json
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


API_HOST = "api.app.websoccer.jp"
SEARCH_PATH = "/trade/search/.json"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fetch trade comments for top-demand players")
    ap.add_argument(
        "--session-file",
        default=str(Path.home() / "Desktop" / "Desktop.chlz"),
        help="Path to Charles export (.chlz/.chlsj/.chlsx) that includes /trade/search/.json request.",
    )
    ap.add_argument(
        "--ranking-csv",
        default=str(Path.home() / "Desktop" / "trade_csv" / "trade_demand_supply_gap_prefer_nr_from_raw.csv"),
        help="Ranking CSV that includes player_id and rank (default: trade demand-supply gap CSV).",
    )
    ap.add_argument("--top-n", type=int, default=30, help="Top N players to fetch (default: 30).")
    ap.add_argument(
        "--out-root",
        default=str(Path.home() / "Desktop" / "trade_csv"),
        help="Output root directory (default: ~/Desktop/trade_csv).",
    )
    ap.add_argument(
        "--player-master",
        default=str(Path.cwd() / "app" / "data.json"),
        help="Path to player master data.json for name lookup.",
    )
    ap.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout seconds.")
    ap.add_argument("--delay-sec", type=float, default=0.05, help="Delay between requests.")
    ap.add_argument("--progress-every", type=int, default=5, help="Print progress every N players.")
    ap.add_argument("--force", action="store_true", help="Refetch even if output JSON exists.")
    ap.add_argument("--insecure", action="store_true", help="Disable TLS cert verification.")
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


def extract_auth_from_session(session_file: Path) -> Optional[Dict[str, str]]:
    if not session_file.exists():
        return None

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


def load_top_ids(ranking_csv: Path, top_n: int) -> List[int]:
    out: List[int] = []
    with ranking_csv.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if len(out) >= top_n:
                break
            pid = row.get("player_id")
            if not pid:
                continue
            try:
                out.append(int(pid))
            except Exception:
                continue
    return out


def load_player_name_map(player_master: Path) -> Dict[int, str]:
    obj = json.loads(player_master.read_text(encoding="utf-8"))
    players = obj.get("players") if isinstance(obj, dict) else obj
    out: Dict[int, str] = {}
    if isinstance(players, list):
        for p in players:
            if not isinstance(p, dict):
                continue
            if "id" not in p:
                continue
            try:
                pid = int(p["id"])
            except Exception:
                continue
            out[pid] = str(p.get("name") or "")
    return out


def row_to_record(target_id: int, target_name: str, row: list, listed_name_map: Dict[int, str]) -> list:
    vals = list(row) + [""] * max(0, 15 - len(row))
    listed_id = vals[5]
    listed_name = ""
    try:
        listed_name = listed_name_map.get(int(listed_id), "")
    except Exception:
        listed_name = ""
    return [
        target_id,
        target_name,
        vals[0],
        vals[1],
        vals[2],
        vals[3],
        vals[4],
        vals[5],
        listed_name,
        vals[6],
        vals[7],
        vals[8],
        vals[9],
        vals[10],
        vals[11],
        vals[12],
        vals[13],
        vals[14],
    ]


def main() -> int:
    args = parse_args()
    session_file = Path(args.session_file).expanduser().resolve()
    ranking_csv = Path(args.ranking_csv).expanduser().resolve()
    out_root = Path(args.out_root).expanduser().resolve()
    player_master = Path(args.player_master).expanduser().resolve()

    if not ranking_csv.exists():
        print(f"[ERROR] ranking csv not found: {ranking_csv}")
        return 2
    if not player_master.exists():
        print(f"[ERROR] player master not found: {player_master}")
        return 2

    top_ids = load_top_ids(ranking_csv, max(1, int(args.top_n)))
    if not top_ids:
        print(f"[ERROR] no top ids found from: {ranking_csv}")
        return 2
    name_map = load_player_name_map(player_master)

    headers = extract_auth_from_session(session_file)
    if not headers:
        print(f"[ERROR] could not extract auth headers from: {session_file}")
        return 2

    json_dir = out_root / "top_demand_search_json"
    json_dir.mkdir(parents=True, exist_ok=True)
    out_ids = out_root / "top_demand_target_ids.csv"
    out_rows = out_root / "top_demand_comments_rows.csv"
    out_comments = out_root / "top_demand_comments_only.csv"

    print(f"[INFO] session: {session_file}")
    print(f"[INFO] ranking: {ranking_csv}")
    print(f"[INFO] top_n: {len(top_ids)}")
    print(f"[INFO] json out: {json_dir}")

    all_records: List[list] = []
    total = len(top_ids)
    ok = 0
    fail = 0
    skip = 0
    started = time.time()
    every = max(1, int(args.progress_every))

    for i, pid in enumerate(top_ids, start=1):
        target_name = name_map.get(pid, "")
        out_json = json_dir / f"{pid}.json"
        data = None
        if out_json.exists() and not args.force:
            skip += 1
            try:
                data = json.loads(out_json.read_text(encoding="utf-8"))
            except Exception:
                data = None
        else:
            ok_req, resp = request_search(pid, headers, args.timeout_sec, insecure=args.insecure)
            if not ok_req:
                fail += 1
                print(f"[WARN] id={pid} fetch failed: {resp}")
                data = None
            else:
                ok += 1
                data = resp
                out_json.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")

        rows = []
        if isinstance(data, dict):
            lst = data.get("list")
            if isinstance(lst, list) and lst:
                first = lst[0]
                if isinstance(first, list):
                    rows = first
        for row in rows:
            if isinstance(row, list):
                all_records.append(row_to_record(pid, target_name, row, name_map))

        if i == 1 or i % every == 0 or i == total:
            elapsed = time.time() - started
            print(
                f"[PROGRESS] {i}/{total} ok={ok} skip={skip} fail={fail} records={len(all_records)} elapsed={elapsed:.1f}s last=id={pid}",
                flush=True,
            )
        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    with out_ids.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "target_player_id", "target_player_name"])
        for i, pid in enumerate(top_ids, start=1):
            w.writerow([i, pid, name_map.get(pid, "")])

    with out_rows.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "target_player_id",
                "target_player_name",
                "code",
                "trade_id_a",
                "trade_id_b",
                "kind",
                "listed_player_id",
                "listed_player_name",
                "listed_season",
                "seller_name",
                "comment",
                "status",
                "created_at",
                "updated_at",
                "extra_10",
                "extra_11",
                "extra_12",
                "extra_13",
                "extra_14",
            ]
        )
        w.writerows(all_records)

    with out_comments.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "target_player_id",
                "target_player_name",
                "listed_player_id",
                "listed_player_name",
                "comment",
                "trade_id_b",
                "seller_name",
            ]
        )
        for rec in all_records:
            # indices from row_to_record
            w.writerow([rec[0], rec[1], rec[7], rec[8], rec[11], rec[4], rec[10]])

    elapsed = time.time() - started
    print(f"[DONE] ok={ok} skip={skip} fail={fail} records={len(all_records)} elapsed={elapsed:.1f}s")
    print(f"[OUT] {out_ids}")
    print(f"[OUT] {out_rows}")
    print(f"[OUT] {out_comments}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
