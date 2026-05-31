#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fetch_cc_all_worlds_completed import API_HOST, UA_FALLBACK, local_auth_from_container


TRADE_INDEX_PATH = "/trade/index/{team_id}/.json"
TRADE_DETAIL_PATH = "/trade/detail/{team_id}/{trade_id}/.json"
TRADE_REGIST_PATH = "/trade/regist/.json"
TRADE_REQUEST_PATH = "/trade/request/.json"
TRADE_EXECUTE_PATH = "/trade/execute/.json"
TRADE_CANCEL_PATH = "/trade/cancel/.json"
TRADE_RESCIND_PATH = "/trade/rescind/.json"
TRADE_NOTIFICATED_PATH = "/trade/notificated/.json"
AWAY_TEAM_INDEX_PATH = "/away_team/index/{team_id}/{away_team_id}.json"


def db_path(profile: Path) -> Path:
    return profile / "Documents" / "Model" / "Model.sqlite"


def profile_metadata(profile: Path) -> dict[str, Any]:
    db = db_path(profile)
    if not db.exists():
        raise FileNotFoundError(f"Model.sqlite not found: {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("select ZTEAM_ID, ZNAME, ZOWNER_NAME, ZSZN from ZMOTEAMDATA limit 1").fetchone()
        if not row:
            raise RuntimeError(f"ZMOTEAMDATA has no rows: {db}")
        return {
            "teamId": int(row["ZTEAM_ID"]),
            "teamName": str(row["ZNAME"] or ""),
            "ownerName": str(row["ZOWNER_NAME"] or ""),
            "season": int(row["ZSZN"] or 0),
            "profileData": str(profile),
        }
    finally:
        con.close()


def auth_for_profile(profile: Path):
    auth = local_auth_from_container(profile)
    if not auth:
        raise RuntimeError(f"could not generate auth from profile: {profile}")
    return auth


def request_json(
    method: str,
    path: str,
    profile: Path,
    *,
    payload: list[Any] | dict[str, Any] | None = None,
    timeout_sec: float = 15.0,
) -> tuple[bool, dict[str, Any] | str]:
    auth = auth_for_profile(profile)
    data = None
    headers = {
        "Accept": "*/*",
        "Websoccer-gate-key": auth.current_gate_key(),
        "User-Agent": auth.user_agent or UA_FALLBACK,
        "Accept-Language": "ja",
        "Connection": "keep-alive",
    }
    if payload is not None:
        data = urllib.parse.urlencode({"json": json.dumps(payload, separators=(",", ":"))}).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if auth.cookie:
        headers["Cookie"] = auth.cookie
    req = urllib.request.Request(f"https://{API_HOST}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl._create_unverified_context()) as res:
            raw = res.read().decode("utf-8", errors="replace")
        return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:300]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def trade_index(profile: Path, timeout_sec: float = 15.0) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    return request_json("GET", TRADE_INDEX_PATH.format(team_id=meta["teamId"]), profile, timeout_sec=timeout_sec)


def trade_detail(profile: Path, listing_team_id: int, trade_id: int, timeout_sec: float = 15.0) -> tuple[bool, dict[str, Any] | str]:
    return request_json(
        "GET",
        TRADE_DETAIL_PATH.format(team_id=int(listing_team_id), trade_id=int(trade_id)),
        profile,
        timeout_sec=timeout_sec,
    )


def trade_regist(
    profile: Path,
    player_id: int,
    acquired_season: int,
    *,
    comment: str = "A",
    condition: int = 15,
    timeout_sec: float = 15.0,
) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    payload = [meta["teamId"], 0, 1, int(player_id), int(acquired_season), meta["ownerName"], comment, int(condition)]
    return request_json("POST", TRADE_REGIST_PATH, profile, payload=payload, timeout_sec=timeout_sec)


def trade_request(
    profile: Path,
    listing_team_id: int,
    listing_trade_id: int,
    offered_player_id: int,
    offered_acquired_season: int,
    *,
    timeout_sec: float = 15.0,
) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    payload = [
        meta["teamId"],
        0,
        int(listing_team_id),
        int(listing_trade_id),
        int(offered_player_id),
        int(offered_acquired_season),
        meta["ownerName"],
    ]
    return request_json("POST", TRADE_REQUEST_PATH, profile, payload=payload, timeout_sec=timeout_sec)


def trade_execute(
    profile: Path,
    own_listing_trade_id: int,
    request_team_id: int,
    request_trade_id: int,
    *,
    timeout_sec: float = 15.0,
) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    payload = [meta["teamId"], int(own_listing_trade_id), int(request_team_id), int(request_trade_id)]
    return request_json("POST", TRADE_EXECUTE_PATH, profile, payload=payload, timeout_sec=timeout_sec)


def trade_cancel(profile: Path, trade_id: int, *, timeout_sec: float = 15.0) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    return request_json("POST", TRADE_CANCEL_PATH, profile, payload=[meta["teamId"], int(trade_id)], timeout_sec=timeout_sec)


def trade_rescind(profile: Path, request_trade_id: int, *, timeout_sec: float = 15.0) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    return request_json("POST", TRADE_RESCIND_PATH, profile, payload=[meta["teamId"], int(request_trade_id)], timeout_sec=timeout_sec)


def trade_notificated(profile: Path, request_trade_ids: list[int], *, timeout_sec: float = 15.0) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    return request_json(
        "POST",
        TRADE_NOTIFICATED_PATH,
        profile,
        payload=[meta["teamId"], [int(v) for v in request_trade_ids]],
        timeout_sec=timeout_sec,
    )


def away_team_index(profile: Path, away_team_id: int, *, timeout_sec: float = 15.0) -> tuple[bool, dict[str, Any] | str]:
    meta = profile_metadata(profile)
    return request_json(
        "GET",
        AWAY_TEAM_INDEX_PATH.format(team_id=meta["teamId"], away_team_id=int(away_team_id)),
        profile,
        timeout_sec=timeout_sec,
    )
