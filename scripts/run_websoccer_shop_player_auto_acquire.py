#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sync_websoccer_local_profile_from_api import SYNC_PATH, update_db  # noqa: E402
from websoccer_trade_api import db_path, profile_metadata, request_json  # noqa: E402


ACTIVE_PROFILE = Path.home() / "Library" / "Containers" / "jp.novelapproach.WebSoccer" / "Data"
PLAYER_DATA_PATH = REPO_ROOT / "app" / "data.json"
SHOP_LISTUP_PATH = "/shop_player/listup/{team_id}/{world_id}.json"
SHOP_DROP_PATH = "/shop_player/drop/{team_id}/{world_id}.json"
SHOP_ACQUIRE_PATH = "/shop_player/acquire/{team_id}/{world_id}.json"
POSITION_TO_ID = {
    "fw": 1,
    "mf": 2,
    "df": 3,
    "gk": 4,
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Auto-listup/acquire WebSoccer shop players from a priority wanted list."
    )
    p.add_argument(
        "--profile-data",
        default=str(ACTIVE_PROFILE),
        help=f"Profile Data directory used for auth. Default: active app profile {ACTIVE_PROFILE}",
    )
    p.add_argument(
        "--config",
        default="",
        help=(
            "Optional JSON config. Supported keys: wanted, blockedRelease, position, "
            "reserveP, maxListups, listupType."
        ),
    )
    p.add_argument(
        "--wanted",
        action="append",
        default=[],
        help="Wanted players in priority order. May be repeated or comma-separated. Accepts player id/name/fullName.",
    )
    p.add_argument(
        "--blocked-release",
        action="append",
        default=[],
        help="Release-block players. May be repeated or comma-separated. Accepts player id/name/fullName.",
    )
    p.add_argument(
        "--position",
        choices=("auto", "fw", "mf", "df", "gk", "omakase"),
        default="auto",
        help="Shop category. auto uses the only wanted position if unambiguous, otherwise omakase. Default: auto.",
    )
    p.add_argument("--reserve-p", type=int, default=100, help="Stop before listup when P is this value or less. Default: 100.")
    p.add_argument("--max-listups", type=int, default=50, help="Safety cap for paid listups. Default: 50.")
    p.add_argument("--listup-type", type=int, default=1, help="shop_player listup type. Default: 1.")
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument(
        "--execute",
        action="store_true",
        help="Actually spend P and call listup/drop/acquire. Without this, no shop mutation API is called.",
    )
    p.add_argument(
        "--no-sync-profile",
        action="store_true",
        help="Do not update the local profile DB from /sync/all after execution.",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a Model.sqlite backup before local profile sync.",
    )
    return p.parse_args()


def split_values(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (int, float)):
            out.append(str(int(value)))
            continue
        if isinstance(value, dict):
            candidate = value.get("id") or value.get("playerId") or value.get("player_id") or value.get("name")
            if candidate is not None:
                out.extend(split_values([candidate]))
            continue
        for part in str(value).replace("\n", ",").split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_config(path: str) -> dict[str, Any]:
    if not path:
        return {}
    fp = Path(path).expanduser().resolve()
    data = json.loads(fp.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("--config must be a JSON object")
    return data


def load_player_catalog() -> dict[int, dict[str, Any]]:
    data = json.loads(PLAYER_DATA_PATH.read_text(encoding="utf-8"))
    raw_players = data.get("players") if isinstance(data, dict) else []
    if isinstance(raw_players, dict):
        raw_players = list(raw_players.values())
    players: dict[int, dict[str, Any]] = {}
    for raw in raw_players or []:
        if not isinstance(raw, dict):
            continue
        raw_id = raw.get("id") or raw.get("playerId") or raw.get("player_id")
        try:
            player_id = int(raw_id)
        except Exception:
            continue
        players[player_id] = raw
    return players


def display_name(players: dict[int, dict[str, Any]], player_id: int) -> str:
    player = players.get(int(player_id)) or {}
    return str(player.get("name") or player.get("fullName") or player_id)


def player_position(players: dict[int, dict[str, Any]], player_id: int) -> str:
    player = players.get(int(player_id)) or {}
    return str(player.get("position") or "").strip().upper()


def resolve_players(raw_values: list[Any], players: dict[int, dict[str, Any]], *, label: str) -> list[int]:
    values = split_values(raw_values)
    name_to_ids: dict[str, set[int]] = {}
    for player_id, player in players.items():
        for key in ("name", "fullName", "fullname"):
            name = str(player.get(key) or "").strip()
            if name:
                name_to_ids.setdefault(name, set()).add(player_id)
    resolved: list[int] = []
    for value in values:
        if value.isdigit():
            player_id = int(value)
        else:
            matches = sorted(name_to_ids.get(value) or [])
            if not matches:
                raise ValueError(f"{label}: unknown player {value!r}")
            if len(matches) > 1:
                raise ValueError(f"{label}: ambiguous player {value!r}: {matches}")
            player_id = matches[0]
        if player_id not in players:
            raise ValueError(f"{label}: player id not found in app/data.json: {player_id}")
        if player_id not in resolved:
            resolved.append(player_id)
    return resolved


def profile_world_id(profile: Path) -> int:
    db = db_path(profile)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("select ZWORLD_ID from ZMOTEAMDATA limit 1").fetchone()
        if row and row["ZWORLD_ID"] is not None:
            return int(row["ZWORLD_ID"])
    finally:
        con.close()
    return 1


def fetch_sync(profile: Path, timeout_sec: float) -> dict[str, Any]:
    ok, payload = request_json("GET", SYNC_PATH, profile, timeout_sec=timeout_sec)
    if not ok or not isinstance(payload, dict) or payload.get("code") != "000":
        raise RuntimeError(f"/sync/all failed: {payload}")
    return payload


def sync_profile_db(profile: Path, payload: dict[str, Any], *, backup: bool) -> dict[str, Any]:
    db = db_path(profile)
    if backup:
        stamp = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d_%H%M%S")
        backup_path = db.with_suffix(db.suffix + f".pre_shop_sync_{stamp}.bak")
        shutil.copy2(db, backup_path)
    con = sqlite3.connect(str(db))
    try:
        con.execute("begin")
        summary = update_db(con, payload)
        con.commit()
        return summary
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def choose_position(position: str, wanted: list[int], players: dict[int, dict[str, Any]]) -> tuple[str, int | None]:
    if position != "auto":
        return position, POSITION_TO_ID.get(position)
    positions = {player_position(players, pid).lower() for pid in wanted if player_position(players, pid)}
    if len(positions) == 1:
        only = next(iter(positions))
        if only in POSITION_TO_ID:
            return only, POSITION_TO_ID[only]
    return "omakase", None


def listup_payload(listup_type: int, position_id: int | None) -> dict[str, int]:
    payload = {"type": int(listup_type)}
    if position_id is not None:
        payload["position"] = int(position_id)
    return payload


def compact_sync(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": payload.get("code"),
        "season": payload.get("season"),
        "world": payload.get("world"),
        "P": int(payload.get("P") or 0),
        "B": int(payload.get("B") or 0),
        "G": int(payload.get("G") or 0),
        "players": len((payload.get("team_data") or {}).get("players") or []),
    }


def annotate_listup(listup: dict[str, Any], players: dict[int, dict[str, Any]], wanted_rank: dict[int, int], blocked: set[int]) -> dict[str, Any]:
    release_id = int(listup.get("r0") or 0)
    offers = []
    for key in ("s1", "s2", "s3", "s4"):
        player_id = int(listup.get(key) or 0)
        offers.append(
            {
                "slot": key,
                "playerId": player_id,
                "name": display_name(players, player_id),
                "position": player_position(players, player_id),
                "wantedRank": wanted_rank.get(player_id),
            }
        )
    wanted_offers = [offer for offer in offers if offer["playerId"] in wanted_rank]
    wanted_offers.sort(key=lambda offer: int(offer["wantedRank"]))
    return {
        "id": int(listup.get("id") or 0),
        "season": int(listup.get("szn") or 0),
        "positionId": int(listup.get("position_id") or 0),
        "created": listup.get("created"),
        "release": {
            "playerId": release_id,
            "name": display_name(players, release_id),
            "position": player_position(players, release_id),
            "blocked": release_id in blocked,
        },
        "offers": offers,
        "bestWantedOffer": wanted_offers[0] if wanted_offers else None,
    }


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    profile = Path(args.profile_data).expanduser().resolve()
    meta = profile_metadata(profile)
    world_id = profile_world_id(profile)
    players = load_player_catalog()

    wanted = resolve_players([*listify(config.get("wanted")), *args.wanted], players, label="wanted")
    blocked_release = resolve_players(
        [*listify(config.get("blockedRelease") or config.get("blocked_release")), *args.blocked_release],
        players,
        label="blocked-release",
    )
    if not wanted:
        raise ValueError("wanted list is empty")

    position_arg = str(config.get("position") or args.position).lower()
    if position_arg not in {"auto", "fw", "mf", "df", "gk", "omakase"}:
        raise ValueError(f"invalid position: {position_arg}")
    reserve_p = int(config.get("reserveP") or config.get("reserve_p") or args.reserve_p)
    max_listups = int(config.get("maxListups") or config.get("max_listups") or args.max_listups)
    listup_type = int(config.get("listupType") or config.get("listup_type") or args.listup_type)
    chosen_position, position_id = choose_position(position_arg, wanted, players)
    wanted_rank = {player_id: idx for idx, player_id in enumerate(wanted)}
    blocked = set(blocked_release)

    before = fetch_sync(profile, args.timeout_sec)
    result: dict[str, Any] = {
        "execute": bool(args.execute),
        "profile": str(profile),
        "team": {
            "teamId": meta["teamId"],
            "teamName": meta["teamName"],
            "worldId": world_id,
            "season": meta["season"],
        },
        "settings": {
            "wanted": [
                {"playerId": pid, "name": display_name(players, pid), "position": player_position(players, pid)}
                for pid in wanted
            ],
            "blockedRelease": [
                {"playerId": pid, "name": display_name(players, pid), "position": player_position(players, pid)}
                for pid in blocked_release
            ],
            "position": chosen_position,
            "positionId": position_id,
            "reserveP": reserve_p,
            "maxListups": max_listups,
            "listupType": listup_type,
        },
        "before": compact_sync(before),
        "actions": [],
    }

    if not args.execute:
        result["status"] = "dry-run"
        result["note"] = "No shop mutation API was called. Add --execute to spend P and run listup/drop/acquire."
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    current = before
    listup_count = 0
    while int(current.get("P") or 0) > reserve_p and listup_count < max_listups:
        listup_count += 1
        request_body = listup_payload(listup_type, position_id)
        ok, response = request_json(
            "POST",
            SHOP_LISTUP_PATH.format(team_id=meta["teamId"], world_id=world_id),
            profile,
            payload=request_body,
            timeout_sec=args.timeout_sec,
        )
        action: dict[str, Any] = {
            "step": listup_count,
            "currentPBeforeListup": int(current.get("P") or 0),
            "request": request_body,
            "listupOk": ok,
            "listupResponse": response,
        }
        result["actions"].append(action)
        if not ok or not isinstance(response, dict) or str(response.get("code")) != "000":
            action["decision"] = "stop-listup-failed"
            break

        listup = annotate_listup(response.get("listup") or {}, players, wanted_rank, blocked)
        action["listup"] = listup
        if listup["release"]["blocked"]:
            ok_drop, drop_response = request_json(
                "POST",
                SHOP_DROP_PATH.format(team_id=meta["teamId"], world_id=world_id),
                profile,
                payload={"listup_id": listup["id"]},
                timeout_sec=args.timeout_sec,
            )
            action.update({"decision": "drop-blocked-release", "dropOk": ok_drop, "dropResponse": drop_response})
            current = fetch_sync(profile, args.timeout_sec)
            action["after"] = compact_sync(current)
            if not ok_drop or not isinstance(drop_response, dict) or str(drop_response.get("code")) != "000":
                action["decision"] = "stop-drop-failed"
                break
            continue

        best = listup["bestWantedOffer"]
        if not best:
            ok_drop, drop_response = request_json(
                "POST",
                SHOP_DROP_PATH.format(team_id=meta["teamId"], world_id=world_id),
                profile,
                payload={"listup_id": listup["id"]},
                timeout_sec=args.timeout_sec,
            )
            action.update({"decision": "drop-no-wanted-offer", "dropOk": ok_drop, "dropResponse": drop_response})
            current = fetch_sync(profile, args.timeout_sec)
            action["after"] = compact_sync(current)
            if not ok_drop or not isinstance(drop_response, dict) or str(drop_response.get("code")) != "000":
                action["decision"] = "stop-drop-failed"
                break
            continue

        ok_acquire, acquire_response = request_json(
            "POST",
            SHOP_ACQUIRE_PATH.format(team_id=meta["teamId"], world_id=world_id),
            profile,
            payload={"listup_id": listup["id"], "acquire_id": int(best["playerId"])},
            timeout_sec=args.timeout_sec,
        )
        action.update(
            {
                "decision": "acquire-wanted-offer",
                "acquireOk": ok_acquire,
                "acquireResponse": acquire_response,
                "acquired": best,
            }
        )
        current = fetch_sync(profile, args.timeout_sec)
        action["after"] = compact_sync(current)
        if not ok_acquire or not isinstance(acquire_response, dict) or str(acquire_response.get("code")) != "000":
            action["decision"] = "stop-acquire-failed"
            break

    else:
        if listup_count >= max_listups:
            result["status"] = "stopped-max-listups"
        else:
            result["status"] = "stopped-reserve-p"

    if "status" not in result:
        result["status"] = "stopped-reserve-p" if int(current.get("P") or 0) <= reserve_p else "stopped"

    final_payload = fetch_sync(profile, args.timeout_sec)
    result["after"] = compact_sync(final_payload)
    result["spentP"] = int(result["before"]["P"]) - int(result["after"]["P"])

    if not args.no_sync_profile:
        result["profileSync"] = sync_profile_db(profile, final_payload, backup=not args.no_backup)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
