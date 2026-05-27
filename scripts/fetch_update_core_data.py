#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Optional, Sequence

from fetch_cc_all_worlds_completed import API_HOST, UA_FALLBACK, AuthHeaders, _iter_tx_from_session


REPO_ROOT = Path(__file__).resolve().parents[1]
WSC_DATA = REPO_ROOT.parent / "wsc_data"
DEFAULT_CORE_ROOT = WSC_DATA
DEFAULT_SESSION_DIR = Path.home() / "charles_sessions"
SESSION_SUFFIXES = {".chlsx", ".chlsj", ".chlz"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch authenticated WebSoccer update_core_data player JSON.")
    p.add_argument("--core-root", default=str(DEFAULT_CORE_ROOT), help="Directory containing update_core_data_* folders")
    p.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR))
    p.add_argument("--session-file", default="")
    p.add_argument("--ids", default="", help='Explicit player ids, e.g. "3211-3220" or "3211,3212"')
    p.add_argument("--start-id", type=int, default=0, help="First id to probe. Default: latest local core id + 1")
    p.add_argument("--max-id", type=int, default=0, help="Last id to probe. Default: start-id + 49")
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--timeout-sec", type=float, default=12.0)
    p.add_argument("--delay-sec", type=float, default=0.1)
    p.add_argument("--auth-check", action="store_true", help="Only check whether API auth can be extracted")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="Overwrite an existing output directory")
    return p.parse_args()


def parse_ids(spec: str) -> list[int]:
    out: set[int] = set()
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            lo, hi = sorted((int(a), int(b)))
            out.update(range(lo, hi + 1))
        else:
            out.add(int(chunk))
    return sorted(out)


def iter_session_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SESSION_SUFFIXES)


def newest_session_files(root: Path) -> list[Path]:
    return sorted(iter_session_files(root), key=lambda p: p.stat().st_mtime, reverse=True)


def extract_api_auth_from_session_files(files: Sequence[Path]) -> Optional[AuthHeaders]:
    best_ms = -1
    best_auth: Optional[AuthHeaders] = None
    for fp in files:
        for host, _path, ms, hdrs in _iter_tx_from_session(fp):
            if host != API_HOST:
                continue
            gate = hdrs.get("websoccer-gate-key", "")
            if not gate or ms < best_ms:
                continue
            best_ms = ms
            best_auth = AuthHeaders(
                cookie=hdrs.get("cookie", ""),
                gate_key=gate,
                user_agent=hdrs.get("user-agent", UA_FALLBACK),
            )
    return best_auth


def request_json(path: str, auth: AuthHeaders, timeout_sec: float) -> tuple[bool, dict | str]:
    req = urllib.request.Request(
        f"https://{API_HOST}{path}",
        headers={
            "Accept": "*/*",
            "expire": "",
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
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl._create_unverified_context()) as res:
            text = res.read().decode("utf-8", errors="replace")
        return True, json.loads(text)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def latest_local_core_id(core_root: Path) -> int:
    latest = 0
    for path in core_root.glob("update_core_data_*"):
        for file in path.glob("*.json"):
            for value in re.findall(r"\d+", file.stem):
                latest = max(latest, int(value))
    return latest


def batched(values: Sequence[int], size: int) -> Iterable[list[int]]:
    size = max(1, size)
    for i in range(0, len(values), size):
        yield list(values[i : i + size])


def merge_unique(rows: list[dict], key: str) -> list[dict]:
    seen: set[int] = set()
    out: list[dict] = []
    for row in rows:
        try:
            value = int(row.get(key))
        except Exception:
            continue
        if value in seen:
            continue
        seen.add(value)
        out.append(row)
    return out


def main() -> int:
    args = parse_args()
    core_root = Path(args.core_root).expanduser().resolve()
    files = [Path(args.session_file).expanduser().resolve()] if args.session_file else newest_session_files(
        Path(args.session_dir).expanduser().resolve()
    )
    auth = extract_api_auth_from_session_files(files)
    if not auth:
        print("[ERROR] could not extract WebSoccer API auth from Charles sessions")
        return 2
    if args.auth_check:
        print(
            "[DONE] API auth extracted: "
            f"gate_key=yes cookie={'yes' if auth.cookie else 'no'} user_agent={'yes' if auth.user_agent else 'no'}"
        )
        return 0

    explicit_ids = bool((args.ids or "").strip())
    ids = parse_ids(args.ids)
    if not ids:
        start_id = args.start_id or (latest_local_core_id(core_root) + 1)
        max_id = args.max_id or (start_id + 49)
        ids = list(range(start_id, max_id + 1))
    if not ids:
        print("[INFO] no ids to probe")
        return 0

    all_players: list[dict] = []
    all_params: list[dict] = []
    for batch in batched(ids, args.batch_size):
        label = ",".join(str(x) for x in batch)
        ok_player, player_data = request_json(f"/update_core_data/player/{label}/.json", auth, args.timeout_sec)
        if not ok_player:
            level = "WARN" if explicit_ids or all_players else "INFO"
            print(f"[{level}] player {label}: {player_data}")
            if not explicit_ids and not all_players:
                break
            continue
        player_obj = player_data if isinstance(player_data, dict) else {}
        players = player_obj.get("players") if player_obj.get("code") == "000" else []
        if not isinstance(players, list) or not players:
            code = player_obj.get("code") if isinstance(player_obj, dict) else None
            print(f"[INFO] player {label}: no rows code={code}")
            continue

        ok_param, param_data = request_json(f"/update_core_data/players_param/{label}/.json", auth, args.timeout_sec)
        if not ok_param:
            print(f"[WARN] players_param {label}: {param_data}")
            continue
        param_obj = param_data if isinstance(param_data, dict) else {}
        params = param_obj.get("players_param") if param_obj.get("code") == "000" else []
        if not isinstance(params, list):
            params = []

        print(f"[FOUND] {label}: players={len(players)} players_param={len(params)}")
        all_players.extend(x for x in players if isinstance(x, dict))
        all_params.extend(x for x in params if isinstance(x, dict))
        if args.delay_sec > 0:
            time.sleep(args.delay_sec)

    all_players = merge_unique(all_players, "player_id")
    found_ids = sorted({int(x["player_id"]) for x in all_players if str(x.get("player_id", "")).isdigit()})
    if not found_ids:
        print("[DONE] no new core player rows found")
        return 0

    id_label = ",".join(str(x) for x in found_ids)
    out_dir = core_root / f"update_core_data_{found_ids[0]}_{found_ids[-1]}"
    print(f"[INFO] output: {out_dir}")
    if args.dry_run:
        print(f"[DONE] dry-run core rows: players={len(all_players)} players_param={len(all_params)} ids={id_label}")
        return 0
    if out_dir.exists() and not args.force:
        raise FileExistsError(f"output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"player_{id_label}.json").write_text(
        json.dumps({"code": "000", "players": all_players}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / f"players_param_{id_label}.json").write_text(
        json.dumps({"code": "000", "players_param": all_params}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[DONE] saved core rows: players={len(all_players)} players_param={len(all_params)} ids={id_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
