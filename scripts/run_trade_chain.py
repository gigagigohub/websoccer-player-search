#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filter_websoccer_trade_comment_targets import (
    APP_DATA,
    analyze_comment,
    display_wanted,
    load_site_players,
    nr_player_names,
    resolve_listed_player,
    search_records,
    split_player_and_category,
    unique_player_names,
)
from search_websoccer_trade_listings import (
    DEFAULT_SEARCH_PROFILE,
    current_season,
    load_player_names,
    post_search,
    rows_from_payload,
)
from fetch_cc_all_worlds_completed import local_auth_from_container, request_json as get_api_json
from sync_websoccer_local_profile_from_api import SYNC_PATH, update_db
from websoccer_trade_api import (
    away_team_index,
    trade_detail,
    trade_execute,
    trade_index,
    trade_notificated,
    trade_regist,
    trade_request,
)


DEFAULT_INDEX = Path.home() / "Codex/WebSoccer/websoccer_local_backups/account_transfer/_index/players_index.json"
DEFAULT_STATE_DIR = Path("local/trade_chain")
DEFAULT_NEW_TEAM_BASE_PROFILE = Path.home() / (
    "Codex/WebSoccer/websoccer_local_backups/account_transfer/WebSoccer_Data_before_transfer_20260530_092648"
)
DEFAULT_NEW_TEAM_WORK_ROOT = Path("local/trade_chain/profiles")
DEFAULT_OPEN_OFFER_ROTATION_STATE = DEFAULT_STATE_DIR / "open_offer_rotation.json"
DEFAULT_MAX_NEW_TEAMS_PER_CHAIN = 10
EXCLUDED_CANDIDATE_TEAM_IDS = {10527301}
MANAGED_TEAM_IDS = {10052201, 9710901, 9725201, 9737901}
DEFAULT_FALLBACK_WANTED = "ドールマン"
STOP_OWNER_DEFAULT = "ギガギゴ"
DEFAULT_ACCEPT_OWNER_ALIASES = ("ギガギゴ", "ギガギゴ.")
ACTIVE_NR_PLAYER_IDS: set[int] = set()
OPEN_OFFER_CANDIDATES = [
    {"name": "カヌー", "playerId": 239, "terms": (1, 2, 3)},
    {"name": "ヒメネス", "playerId": 158, "terms": (1, 2, 3)},
    {"name": "コーク", "playerId": 577, "terms": (1, 2, 3)},
    {"name": "ヴェンゲル", "playerId": 264, "terms": (1, 2, 3)},
    {"name": "ボアス　玲偉", "playerId": 628, "terms": (1, 2, 3)},
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run a stateful WebSoccer trade chain for one player/term query.")
    p.add_argument("player", help="Target listed player name, e.g. ヒューズ or ヒューズNR.")
    p.add_argument("term", type=int, help="Target listed player term.")
    p.add_argument("--category", default="", help="Target listed player category. Default: NR or suffix in player arg.")
    p.add_argument("--app-data", default=str(APP_DATA))
    p.add_argument("--players-index", default=str(DEFAULT_INDEX))
    p.add_argument("--state-file", default="", help="Default: local/trade_chain/<query>.json")
    p.add_argument("--auth-profile", default="", help="Profile used for trade search auth. Default: search script default.")
    p.add_argument("--execute", action="store_true", help="Actually POST trade regist/request/execute.")
    p.add_argument("--watch", action="store_true", help="Poll until a completion is confirmed.")
    p.add_argument("--interval-sec", type=int, default=300)
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument("--comment", default="A", help="Comment used for trade registration.")
    p.add_argument(
        "--accept-owner",
        default=STOP_OWNER_DEFAULT,
        help="Owner accepted for incoming offers. Default accepts ギガギゴ and ギガギゴ.",
    )
    p.add_argument("--notify-pushover", action="store_true")
    p.add_argument(
        "--new-team-profile-data",
        default="",
        help="Existing work Profile Data path to use if a new team must be created. If omitted, one is copied automatically.",
    )
    p.add_argument(
        "--new-team-base-profile",
        default=str(DEFAULT_NEW_TEAM_BASE_PROFILE),
        help=f"Full Data profile copied when a new team is needed (default: {DEFAULT_NEW_TEAM_BASE_PROFILE})",
    )
    p.add_argument(
        "--new-team-work-root",
        default=str(DEFAULT_NEW_TEAM_WORK_ROOT),
        help=f"Local ignored root for auto-created new-team work profiles (default: {DEFAULT_NEW_TEAM_WORK_ROOT})",
    )
    p.add_argument(
        "--max-new-teams",
        type=int,
        default=DEFAULT_MAX_NEW_TEAMS_PER_CHAIN,
        help=f"Maximum auto-created teams per initial player/term chain (default: {DEFAULT_MAX_NEW_TEAMS_PER_CHAIN})",
    )
    p.add_argument(
        "--allow-managed-team-quota-use",
        action="store_true",
        help="Allow iPhone-managed teams to be used for trade registration/offers. Default protects their trade quota.",
    )
    p.add_argument(
        "--approve-paused-last-existing-same-term-offer",
        action="store_true",
        help="Approve and resume a state paused because an existing same-player/same-term offer would leave no reserve.",
    )
    p.add_argument("--dry-run-json", action="store_true", help="Print machine-readable action plan.")
    return p.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(text: str) -> str:
    value = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠ー]+", "_", text).strip("_")
    return value or "trade_chain"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def acquire_state_lock(state_path: Path):
    lock_path = state_path.with_suffix(state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w", encoding="utf-8")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def validate_profile_data(profile: Path) -> None:
    required = [
        profile / "Documents" / "Model" / "Model.sqlite",
        profile / "Library" / "Preferences" / "jp.novelapproach.WebSoccer.plist",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"profile is missing required files: {missing}")


def prepare_new_team_profile(args: argparse.Namespace, wanted_name: str, player_id: int) -> Path:
    if args.new_team_profile_data:
        profile = Path(args.new_team_profile_data).expanduser().resolve()
        validate_profile_data(profile)
        return profile

    base = Path(args.new_team_base_profile).expanduser().resolve()
    validate_profile_data(base)
    work_root = Path(args.new_team_work_root)
    if not work_root.is_absolute():
        work_root = (Path.cwd() / work_root).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = work_root / f"{slugify(wanted_name)}_{int(player_id)}_{stamp}" / "Data"
    if dest.exists():
        dest = work_root / f"{slugify(wanted_name)}_{int(player_id)}_{stamp}_{uuid.uuid4().hex[:8]}" / "Data"
    dest.parent.mkdir(parents=True, exist_ok=False)
    shutil.copytree(base, dest, symlinks=True)
    validate_profile_data(dest)
    return dest


def load_players_index(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"players index not found: {path}; run scripts/build_websoccer_local_player_index.py")
    return json.loads(path.read_text(encoding="utf-8"))


def profile_player_rows(profile: Path) -> list[dict[str, Any]]:
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        team = con.execute("select ZTEAM_ID, ZNAME, ZOWNER_NAME, ZSZN from ZMOTEAMDATA limit 1").fetchone()
        if not team:
            return []
        rows = []
        for row in con.execute(
            """
            select
              p.ZPLAYER_ID,
              p.ZPERSON_ID,
              p.ZNAME,
              p.ZFULLNAME,
              p.ZRARITY,
              tp.ZGET_SEASON,
              tp.ZPLAYER_NO
            from ZMOTEAMSPLAYER tp
            left join ZMOPLAYER p on p.Z_PK = tp.ZPLAYER
            where p.ZPLAYER_ID is not null
            """
        ):
            acquired = int(row["ZGET_SEASON"] or 0)
            season = int(team["ZSZN"] or 0)
            rows.append(
                {
                    "name": str(row["ZNAME"] or ""),
                    "fullName": str(row["ZFULLNAME"] or ""),
                    "playerId": int(row["ZPLAYER_ID"] or 0),
                    "personId": int(row["ZPERSON_ID"] or 0),
                    "termNo": season - acquired + 1 if season and acquired else None,
                    "rarity": row["ZRARITY"],
                    "acquiredSeason": acquired,
                    "rosterNo": row["ZPLAYER_NO"],
                    "teamName": str(team["ZNAME"] or ""),
                    "teamId": int(team["ZTEAM_ID"] or 0),
                    "ownerName": str(team["ZOWNER_NAME"] or ""),
                    "teamSeason": season,
                    "profileData": str(profile),
                    "summaryPath": "",
                    "source": "trade_chain_profile",
                }
            )
        return rows
    except sqlite3.Error:
        return []
    finally:
        con.close()


def merge_trade_chain_profile_rows(index: dict[str, Any], work_root: Path) -> dict[str, Any]:
    if not work_root.is_absolute():
        work_root = (Path.cwd() / work_root).resolve()
    rows = list(index.get("rows") or [])
    seen = {
        (str(row.get("profileData")), int(row.get("playerId") or 0), int(row.get("acquiredSeason") or 0))
        for row in rows
    }
    for profile in sorted(work_root.glob("*/Data")):
        for row in profile_player_rows(profile):
            key = (str(row.get("profileData")), int(row.get("playerId") or 0), int(row.get("acquiredSeason") or 0))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    merged = dict(index)
    merged["rows"] = rows
    return merged


def global_active_offer_locks(state_dir: Path) -> set[tuple[str, str, str]]:
    if not state_dir.is_absolute():
        state_dir = (Path.cwd() / state_dir).resolve()
    locks: set[tuple[str, str, str]] = set()
    for path in state_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("requests") or []:
            if item.get("status") not in {"requested", "pending", "executed"}:
                continue
            locks.add((str(item.get("requestTeamId")), str(item.get("offeredPlayerId")), str(item.get("offeredAcquiredSeason"))))
    return locks


def offer_lock_key_from_row(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("teamId")), str(row.get("playerId")), str(row.get("acquiredSeason")))


def last_existing_same_term_offer_approval_key(rec: dict[str, Any], row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(listing_key(rec)),
            str(row.get("teamId")),
            str(row.get("playerId")),
            str(row.get("acquiredSeason")),
        ]
    )


def new_team_profile_roots(state: dict[str, Any]) -> set[str]:
    roots: set[str] = set()
    for item in state.get("newTeams") or []:
        profile = str(item.get("profileData") or "")
        if profile:
            roots.add(str(Path(profile).expanduser().resolve()))
    return roots


def is_new_team_acquired_offer_row(state: dict[str, Any], row: dict[str, Any]) -> bool:
    profile = str(row.get("profileData") or "")
    if profile:
        resolved = str(Path(profile).expanduser().resolve())
        if resolved in new_team_profile_roots(state):
            return True
    return False


def active_offer_locks_for_state(state: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {
        (str(item.get("requestTeamId")), str(item.get("offeredPlayerId")), str(item.get("offeredAcquiredSeason")))
        for item in state.get("requests") or []
        if item.get("status") in {"requested", "pending", "executed"}
    }


def should_pause_last_existing_same_term_offer(
    *,
    args: argparse.Namespace,
    state: dict[str, Any],
    rec: dict[str, Any],
    row: dict[str, Any],
    index: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
) -> dict[str, Any] | None:
    if is_new_team_acquired_offer_row(state, row):
        return None
    try:
        player_id = int(row.get("playerId") or 0)
        term_no = int(row.get("termNo") or 0)
    except (TypeError, ValueError):
        return None
    if not player_id or not term_no:
        return None
    approval_key = last_existing_same_term_offer_approval_key(rec, row)
    if approval_key in set(state.get("approvedLastExistingSameTermOffers") or []):
        return None
    locked = set(global_locks)
    locked.update(active_offer_locks_for_state(state))
    offer_key = offer_lock_key_from_row(row)
    reserve_rows = []
    for candidate in owned_rows_for_player_ids(
        index,
        {player_id},
        term_no,
        allow_managed_team_quota_use=bool(args.allow_managed_team_quota_use),
    ):
        candidate_key = offer_lock_key_from_row(candidate)
        if candidate_key == offer_key:
            continue
        if candidate_key in locked:
            continue
        reserve_rows.append(candidate)
    if reserve_rows:
        return None
    return {
        "type": "request",
        "status": "last_existing_same_term_offer_requires_approval",
        "approvalKey": approval_key,
        "listingKey": listing_key(rec),
        "listingTeamId": rec.get("listingTeamId"),
        "listingTradeId": rec.get("tradeId"),
        "listingOwner": rec.get("owner"),
        "offeredPlayerId": player_id,
        "offeredPlayerName": row.get("name"),
        "offeredTerm": term_no,
        "offeredAcquiredSeason": row.get("acquiredSeason"),
        "requestTeamId": row.get("teamId"),
        "requestTeamName": row.get("teamName"),
        "createdAt": now_iso(),
    }


def normalized_names(name: str) -> set[str]:
    names = {name}
    if name.endswith("ー"):
        names.add(name.rstrip("ー"))
    else:
        names.add(name + "ー")
    return {n for n in names if n}


def resolve_nr_player_ids(players: list[dict[str, Any]], name: str) -> tuple[list[int], str]:
    ids, canonical = resolve_listed_player(players, name, "NR")
    return ids, canonical


def active_nr_player_ids(players: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for player in players:
        if str(player.get("category") or "").upper() != "NR":
            continue
        if player.get("retired"):
            continue
        player_id = player.get("id") or player.get("playerId")
        if player_id is not None:
            ids.add(int(player_id))
    return ids


def is_active_nr_player_id(player_id: Any) -> bool:
    try:
        value = int(player_id)
    except (TypeError, ValueError):
        return False
    return value in ACTIVE_NR_PLAYER_IDS


def accepted_owner_names(accept_owner: str) -> set[str]:
    owners = {part.strip() for part in str(accept_owner or "").split(",") if part.strip()}
    if not owners or owners == {STOP_OWNER_DEFAULT}:
        owners.update(DEFAULT_ACCEPT_OWNER_ALIASES)
    return owners


def is_accepted_owner(owner: str, accept_owner: str) -> bool:
    owner = str(owner or "").strip()
    if not owner:
        return False
    return owner in accepted_owner_names(accept_owner)


def comment_allows_same_player(comment: Any) -> bool:
    return "若返り" in str(comment or "")


def rotation_state_path() -> Path:
    return (Path.cwd() / DEFAULT_OPEN_OFFER_ROTATION_STATE).resolve()


def load_open_offer_rotation() -> dict[str, Any]:
    path = rotation_state_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    index = int(data.get("nextIndex") or 0) if str(data.get("nextIndex") or "0").isdigit() else 0
    return {"nextIndex": index % len(OPEN_OFFER_CANDIDATES)}


def write_open_offer_rotation(data: dict[str, Any]) -> None:
    path = rotation_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, data)


def rotated_open_offer_candidates(start_index: int) -> list[dict[str, Any]]:
    if not OPEN_OFFER_CANDIDATES:
        return []
    count = len(OPEN_OFFER_CANDIDATES)
    return [
        {**OPEN_OFFER_CANDIDATES[(start_index + offset) % count], "rotationIndex": (start_index + offset) % count}
        for offset in range(count)
    ]


def advance_open_offer_rotation(candidate: dict[str, Any]) -> None:
    try:
        index = int(candidate.get("rotationIndex"))
    except (TypeError, ValueError):
        return
    write_open_offer_rotation(
        {
            "nextIndex": (index + 1) % len(OPEN_OFFER_CANDIDATES),
            "lastUsedAt": now_iso(),
            "lastUsedName": candidate.get("name"),
            "lastUsedPlayerId": candidate.get("playerId"),
        }
    )


def owned_rows_for_player_ids(
    index: dict[str, Any],
    player_ids: set[int],
    term: int | None = None,
    *,
    allow_managed_team_quota_use: bool = False,
) -> list[dict[str, Any]]:
    rows = []
    for row in index.get("rows") or []:
        try:
            player_id = int(row.get("playerId") or 0)
            term_no = int(row.get("termNo") or 0)
            team_id = int(row.get("teamId") or 0)
        except (TypeError, ValueError):
            continue
        if team_id in EXCLUDED_CANDIDATE_TEAM_IDS:
            continue
        if not allow_managed_team_quota_use and team_id in MANAGED_TEAM_IDS:
            continue
        if player_id not in player_ids:
            continue
        if ACTIVE_NR_PLAYER_IDS and player_id not in ACTIVE_NR_PLAYER_IDS:
            continue
        if term is not None and term_no != term:
            continue
        if not row.get("profileData") or not row.get("acquiredSeason"):
            continue
        rows.append(row)
    rows.sort(key=lambda r: (int(r.get("termNo") or 0), str(r.get("teamName") or ""), int(r.get("playerId") or 0)))
    return rows


def choose_offer_player(
    *,
    wanted_name: str,
    wanted_terms: list[int] | None = None,
    site_players: list[dict[str, Any]],
    index: dict[str, Any],
    state: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
    allow_managed_team_quota_use: bool,
    excluded_player_ids: set[int] | None = None,
) -> dict[str, Any] | None:
    effective_name = wanted_name or DEFAULT_FALLBACK_WANTED
    ids, canonical = resolve_nr_player_ids(site_players, effective_name)
    if not ids:
        return {
            "needsNewTeam": True,
            "wantedName": effective_name,
            "canonicalWantedName": effective_name,
            "reason": "wanted_nr_player_not_found",
        }
    excluded_player_ids = excluded_player_ids or set()
    if excluded_player_ids and set(ids).issubset(excluded_player_ids):
        return {
            "needsNewTeam": False,
            "wantedName": effective_name,
            "canonicalWantedName": canonical,
            "playerIds": ids,
            "reason": "same_player_offer_not_allowed",
        }
    requested_terms = sorted({int(v) for v in (wanted_terms or []) if int(v) >= 1})
    search_terms = requested_terms or [1]
    locked = set(global_locks)
    locked.update(
        (str(item.get("requestTeamId")), str(item.get("offeredPlayerId")), str(item.get("offeredAcquiredSeason")))
        for item in state.get("requests") or []
        if item.get("status") in {"requested", "pending", "executed"}
    )
    for term in search_terms:
        for row in owned_rows_for_player_ids(
            index,
            set(ids),
            term,
            allow_managed_team_quota_use=allow_managed_team_quota_use,
        ):
            key = (str(row.get("teamId")), str(row.get("playerId")), str(row.get("acquiredSeason")))
            if key in locked:
                continue
            return {
                "needsNewTeam": False,
                "wantedName": effective_name,
                "canonicalWantedName": canonical,
                "term": term,
                "row": row,
            }
    if requested_terms and any(term >= 2 for term in requested_terms):
        return {
            "needsNewTeam": False,
            "wantedName": effective_name,
            "canonicalWantedName": canonical,
            "wantedTerms": requested_terms,
            "reason": "requested_term_not_owned_no_new_team_for_term_2_or_later",
        }
    return {
        "needsNewTeam": True,
        "wantedName": effective_name,
        "canonicalWantedName": canonical,
        "playerIds": ids,
        "wantedTerms": search_terms,
        "reason": "wanted_player_not_owned_in_term_1",
    }


def choose_offer_candidate(
    *,
    candidate: dict[str, Any],
    site_players: list[dict[str, Any]],
    index: dict[str, Any],
    state: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
    allow_managed_team_quota_use: bool,
    excluded_player_ids: set[int] | None = None,
) -> dict[str, Any] | None:
    wanted_name = str(candidate.get("name") or "")
    if candidate.get("playerId"):
        ids = [int(candidate["playerId"])]
        canonical = wanted_name
    else:
        ids, canonical = resolve_nr_player_ids(site_players, wanted_name)
    if not ids:
        return None
    excluded_player_ids = excluded_player_ids or set()
    if excluded_player_ids and set(ids).issubset(excluded_player_ids):
        return None
    locked = set(global_locks)
    locked.update(
        (str(item.get("requestTeamId")), str(item.get("offeredPlayerId")), str(item.get("offeredAcquiredSeason")))
        for item in state.get("requests") or []
        if item.get("status") in {"requested", "pending", "executed"}
    )
    terms = tuple(int(v) for v in candidate.get("terms") or (1, 2, 3))
    for term in terms:
        for row in owned_rows_for_player_ids(
            index,
            set(ids),
            term,
            allow_managed_team_quota_use=allow_managed_team_quota_use,
        ):
            key = (str(row.get("teamId")), str(row.get("playerId")), str(row.get("acquiredSeason")))
            if key in locked:
                continue
            return {
                "needsNewTeam": False,
                "wantedName": wanted_name,
                "canonicalWantedName": canonical,
                "term": term,
                "openOfferCandidate": candidate,
                "row": row,
            }
    return {
        "needsNewTeam": True,
        "wantedName": wanted_name,
        "canonicalWantedName": canonical,
        "playerIds": ids,
        "openOfferCandidate": candidate,
        "reason": "wanted_player_not_owned_in_condition_terms",
    }


def choose_open_request_offer_player(
    *,
    condition: Any,
    site_players: list[dict[str, Any]],
    index: dict[str, Any],
    state: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
    allow_managed_team_quota_use: bool,
    excluded_player_ids: set[int] | None = None,
    skipped_rotation_indices: set[int] | None = None,
) -> dict[str, Any]:
    rotation = load_open_offer_rotation()
    start_index = int(rotation.get("nextIndex") or 0)
    skipped_rotation_indices = skipped_rotation_indices or set()
    for candidate in rotated_open_offer_candidates(start_index):
        if int(candidate.get("rotationIndex") or 0) in skipped_rotation_indices:
            continue
        choice = choose_offer_candidate(
            candidate=candidate,
            site_players=site_players,
            index=index,
            state=state,
            global_locks=global_locks,
            allow_managed_team_quota_use=allow_managed_team_quota_use,
            excluded_player_ids=excluded_player_ids,
        )
        if not choice:
            continue
        return choice
    return {
        "needsNewTeam": True,
        "wantedName": DEFAULT_FALLBACK_WANTED,
        "canonicalWantedName": DEFAULT_FALLBACK_WANTED,
        "reason": "no_open_offer_candidate_found",
    }


def non_creatable_missing_term_choice(choice: dict[str, Any] | None) -> bool:
    return bool(
        choice
        and not choice.get("needsNewTeam")
        and not choice.get("row")
        and choice.get("reason") == "requested_term_not_owned_no_new_team_for_term_2_or_later"
    )


def choose_comment_offer_player(
    *,
    analysis: dict[str, Any],
    site_players: list[dict[str, Any]],
    index: dict[str, Any],
    state: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
    allow_managed_team_quota_use: bool,
    excluded_player_ids: set[int] | None = None,
    skipped_comment_candidates: set[str] | None = None,
    skipped_wanted_names: set[str] | None = None,
) -> dict[str, Any]:
    fallback_choice: dict[str, Any] | None = None
    skipped_comment_candidates = skipped_comment_candidates or set()
    skipped_wanted_names = skipped_wanted_names or set()
    for candidate in analysis.get("candidates") or []:
        if not candidate.get("include"):
            continue
        candidate_text = str(candidate.get("candidate") or "")
        if candidate_text in skipped_comment_candidates:
            continue
        wanted_name = str(candidate.get("wantedPlayerName") or "").strip()
        if not wanted_name:
            continue
        if wanted_name in skipped_wanted_names:
            continue
        choice = choose_offer_player(
            wanted_name=wanted_name,
            wanted_terms=candidate.get("wantedTerms") or [],
            site_players=site_players,
            index=index,
            state=state,
            global_locks=global_locks,
            allow_managed_team_quota_use=allow_managed_team_quota_use,
            excluded_player_ids=excluded_player_ids,
        )
        choice["commentCandidate"] = candidate.get("candidate")
        if choice.get("reason") == "same_player_offer_not_allowed":
            fallback_choice = fallback_choice or choice
            continue
        if non_creatable_missing_term_choice(choice):
            fallback_choice = fallback_choice or choice
            continue
        return choice
    if fallback_choice:
        return fallback_choice
    return {
        "needsNewTeam": True,
        "wantedName": str(analysis.get("wantedPlayerName") or DEFAULT_FALLBACK_WANTED),
        "canonicalWantedName": str(analysis.get("wantedPlayerName") or DEFAULT_FALLBACK_WANTED),
        "reason": "no_usable_comment_candidate",
    }


def listing_key(rec: dict[str, Any]) -> str:
    return f"{rec.get('listingTeamId')}:{rec.get('tradeId')}"


def init_state(path: Path, query: dict[str, Any]) -> dict[str, Any]:
    state = load_json(
        path,
        {
            "createdAt": now_iso(),
            "query": query,
            "registered": [],
            "registrationAttempts": [],
            "requests": [],
            "skippedListings": [],
            "offeredOwners": [],
            "newTeams": [],
            "completed": [],
            "stopped": False,
        },
    )
    state["updatedAt"] = now_iso()
    state.setdefault("query", query)
    state.setdefault("registered", [])
    state.setdefault("registrationAttempts", [])
    state.setdefault("requests", [])
    state.setdefault("skippedListings", [])
    state.setdefault("offeredOwners", [])
    state.setdefault("newTeams", [])
    state.setdefault("completed", [])
    state.setdefault("approvedLastExistingSameTermOffers", [])
    return state


def send_pushover(title: str, message: str) -> None:
    subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "notify_pushover.py"), "--title", title, "--message", message],
        check=False,
    )


def summarize_error_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        if isinstance(payload.get("response"), dict):
            return summarize_error_payload(payload.get("response"))
        parts = []
        if payload.get("code") is not None:
            parts.append(f"code={payload.get('code')}")
        message = str(payload.get("message") or payload.get("error") or "").replace("\n", " ").strip()
        if message:
            parts.append(message[:80])
        return " / ".join(parts)
    return str(payload or "")[:100]


def attention_message_for_action(action: dict[str, Any], player_name: str, term: int) -> str | None:
    status = str(action.get("status") or "")
    action_type = str(action.get("type") or "")
    if status in {"max_new_teams_reached", "new_team_creation_failed", "needs_new_team_no_player_id", "ineligible_player_not_active_nr"}:
        trade_id = action.get("listingTradeId")
        wanted = ((action.get("wanted") or {}).get("canonicalWantedName") or (action.get("wanted") or {}).get("wantedName") or "")
        detail = summarize_error_payload(action.get("teamCreation") or action.get("response"))
        return f"{player_name}{term}期 要確認: {status} trade_id={trade_id} wanted={wanted} {detail}".strip()
    if action_type == "request" and action.get("ok") and response_code(action.get("response")) and response_code(action.get("response")) != "000":
        if is_selected_player_unacquirable_response(action.get("response")):
            return None
        trade_id = action.get("listingTradeId")
        wanted = ((action.get("wanted") or {}).get("canonicalWantedName") or (action.get("wanted") or {}).get("wantedName") or "")
        return f"{player_name}{term}期 要確認: request_failed trade_id={trade_id} wanted={wanted} {summarize_error_payload(action.get('response'))}".strip()
    if status == "last_existing_same_term_offer_requires_approval":
        offered = str(action.get("offeredPlayerName") or "")
        offered_term = action.get("offeredTerm")
        suffix = f": {offered}{offered_term}期" if offered and offered_term else ""
        return f"{player_name}{term}期 要確認: 提示すると提示外の同名同期が0名になります{suffix}。チャットで継続可否を指示してください"
    if action_type == "watch_registered" and status == "missing_trade_id":
        return f"{player_name}{term}期 要確認: 登録済み監視に trade_id がありません"
    register_acquired = action.get("registerAcquired") or {}
    register_status = str(register_acquired.get("status") or "")
    if register_status in {"sync_failed", "register_failed"}:
        return f"{player_name}{term}期 要確認: {register_status} {summarize_error_payload(register_acquired.get('response') or register_acquired.get('register'))}".strip()
    return None


def notify_attention_events(actions: list[dict[str, Any]], player_name: str, term: int) -> None:
    seen: set[str] = set()
    for action in actions:
        message = attention_message_for_action(action, player_name, term)
        if not message or message in seen:
            continue
        seen.add(message)
        send_pushover("WebSoccer Trade Error", message)


def command_tail(text: str) -> str:
    if not text:
        return ""
    tail = text[-2000:]
    patterns = [
        (r'"uuid"\s*:\s*"[^"]+"', '"uuid":"<redacted>"'),
        (r'"viewer_id"\s*:\s*"[^"]+"', '"viewer_id":"<redacted>"'),
        (r'"invite_code"\s*:\s*"[^"]+"', '"invite_code":"<redacted>"'),
        (r'"team_name"\s*:\s*"[^"]+"', '"team_name":"<redacted>"'),
        (r'"owner_name"\s*:\s*"[^"]+"', '"owner_name":"<redacted>"'),
        (r'"ZNAME"\s*:\s*"[^"]+"', '"ZNAME":"<redacted>"'),
        (r'"ZOWNER_NAME"\s*:\s*"[^"]+"', '"ZOWNER_NAME":"<redacted>"'),
        (r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}", "<redacted-uuid>"),
    ]
    for pattern, repl in patterns:
        tail = re.sub(pattern, repl, tail)
    return tail


def response_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("code") or "")


def mark_registered_notified_for_completion(state: dict[str, Any], completion: dict[str, Any]) -> bool:
    register_acquired = completion.get("registerAcquired") or {}
    owned = register_acquired.get("ownedPlayer") or {}
    register_action = register_acquired.get("register") or {}
    trade_id = register_action.get("verifiedTradeId")
    keys = {
        "teamId": owned.get("teamId"),
        "playerId": owned.get("playerId"),
        "acquiredSeason": owned.get("acquiredSeason"),
    }
    marked = False
    for item in state.get("registered") or []:
        if trade_id and str(item.get("tradeId")) == str(trade_id):
            item["notified"] = True
            marked = True
            continue
        if all(str(item.get(key)) == str(value) for key, value in keys.items() if value is not None):
            item["notified"] = True
            marked = True
    return marked


def notify_trade_events(state: dict[str, Any], state_path: Path, player_name: str, term: int) -> None:
    changed = False
    for item in state.get("completed") or []:
        if item.get("notified"):
            continue
        if item.get("kind") == "accepted_incoming":
            registered = item.get("registered") or {}
            send_pushover(
                "WebSoccer Trade Completed",
                f"{player_name}{term}期 獲得完了",
            )
            item["notified"] = True
            changed = True
            continue
        register_acquired = item.get("registerAcquired") or {}
        if register_acquired.get("status") == "registered":
            send_pushover(
                "WebSoccer Trade Completed",
                f"{player_name}{term}期 成立・登録完了: メイン提示して下さい",
            )
            mark_registered_notified_for_completion(state, item)
            item["notified"] = True
            changed = True
            continue
        send_pushover(
            "WebSoccer Trade Completed",
            f"{player_name}{term}期 成立確認",
        )
        item["notified"] = True
        changed = True
    for item in state.get("registered") or []:
        if item.get("status") not in {"registered", "registered_unverified"} or item.get("notified"):
            continue
        send_pushover(
            "WebSoccer Trade Registered",
            f"{player_name}{term}期 登録: メイン提示して下さい",
        )
        item["notified"] = True
        changed = True
    for item in state.get("requests") or []:
        if item.get("status") != "requested" or item.get("notified"):
            continue
        send_pushover(
            "WebSoccer Trade Requested",
            (
                f"{player_name}{term}期 提示: "
                f"{item.get('offeredPlayerName')} -> {item.get('listedPlayerName')}"
            ),
        )
        item["notified"] = True
        changed = True
    if changed:
        write_json(state_path, state)


def owned_player_from_profile(profile: Path, player_id: int) -> dict[str, Any]:
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        raise FileNotFoundError(f"Model.sqlite not found after team creation: {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        team = con.execute("select ZTEAM_ID, ZNAME, ZOWNER_NAME, ZSZN from ZMOTEAMDATA limit 1").fetchone()
        row = con.execute(
            """
            select p.ZPLAYER_ID, tp.ZGET_SEASON, p.ZNAME
            from ZMOTEAMSPLAYER tp
            left join ZMOPLAYER p on p.Z_PK = tp.ZPLAYER
            where p.ZPLAYER_ID = ?
            order by tp.ZGET_SEASON desc
            limit 1
            """,
            (int(player_id),),
        ).fetchone()
        if not team:
            raise RuntimeError(f"ZMOTEAMDATA has no rows: {db}")
        if not row:
            raise RuntimeError(f"created team does not own player_id={player_id}: {db}")
        return {
            "teamId": int(team["ZTEAM_ID"]),
            "teamName": str(team["ZNAME"] or ""),
            "ownerName": str(team["ZOWNER_NAME"] or ""),
            "teamSeason": int(team["ZSZN"] or 0),
            "playerId": int(row["ZPLAYER_ID"]),
            "name": str(row["ZNAME"] or ""),
            "acquiredSeason": int(row["ZGET_SEASON"]),
            "profileData": str(profile),
        }
    finally:
        con.close()


def create_team_for_wanted_player(args: argparse.Namespace, player_id: int, wanted_name: str) -> tuple[bool, dict[str, Any]]:
    if ACTIVE_NR_PLAYER_IDS and int(player_id) not in ACTIVE_NR_PLAYER_IDS:
        return False, {"error": "ineligible_player_not_active_nr", "playerId": int(player_id), "wantedName": wanted_name}
    try:
        profile = prepare_new_team_profile(args, wanted_name or f"player_{player_id}", player_id)
    except Exception as exc:  # noqa: BLE001
        return False, {"error": str(exc)}
    cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "complete_websoccer_tutorial.py"),
        "--profile-data",
        str(profile),
        "--create-team",
        "--player-id",
        str(player_id),
        "--sync",
        "--backup",
        "--execute",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    result = {
        "command": cmd,
        "returncode": proc.returncode,
        "stdoutTail": command_tail(proc.stdout),
        "stderrTail": command_tail(proc.stderr),
    }
    if proc.returncode != 0:
        return False, result
    result["ownedPlayer"] = owned_player_from_profile(profile, player_id)
    return True, result


def register_owned_target(args: argparse.Namespace, state: dict[str, Any], target_row: dict[str, Any]) -> dict[str, Any]:
    action = {"type": "register", "row": target_row, "execute": bool(args.execute)}
    if ACTIVE_NR_PLAYER_IDS and not is_active_nr_player_id(target_row.get("playerId")):
        action.update({"ok": False, "status": "ineligible_player_not_active_nr"})
        state.setdefault("registrationAttempts", []).append({**action, "createdAt": now_iso()})
        return action
    if not args.execute:
        return action
    profile = Path(str(target_row["profileData"])).expanduser().resolve()
    ok, payload = trade_regist(
        profile,
        int(target_row["playerId"]),
        int(target_row["acquiredSeason"]),
        comment=args.comment,
        timeout_sec=args.timeout_sec,
    )
    action.update({"ok": ok, "response": payload})
    attempt = {
        "createdAt": now_iso(),
        "teamId": target_row.get("teamId"),
        "teamName": target_row.get("teamName"),
        "ownerName": target_row.get("ownerName"),
        "playerId": target_row.get("playerId"),
        "playerName": target_row.get("name"),
        "acquiredSeason": target_row.get("acquiredSeason"),
        "profileData": target_row.get("profileData"),
        "comment": args.comment,
        "status": "registered" if ok and isinstance(payload, dict) and payload.get("code") == "000" else "failed",
        "response": payload,
    }
    state.setdefault("registrationAttempts", []).append(attempt)
    if ok and isinstance(payload, dict) and payload.get("code") == "000":
        trade_id = None
        verify_source = ""
        index_ok, index_payload = trade_index(profile, timeout_sec=args.timeout_sec)
        if index_ok and isinstance(index_payload, dict) and index_payload.get("code") == "000":
            raw_list = index_payload.get("list")
            own_rows = raw_list[0] if isinstance(raw_list, list) and raw_list and isinstance(raw_list[0], list) else []
            for row in own_rows:
                vals = list(row) + [None] * 10
                if int(vals[3] or 0) == int(target_row["playerId"]) and int(vals[4] or 0) == int(target_row["acquiredSeason"]):
                    trade_id = vals[1]
                    verify_source = "own_trade_index"
                    break
        if trade_id is None:
            search_profile = Path(args.auth_profile).expanduser().resolve() if args.auth_profile else DEFAULT_SEARCH_PROFILE
            try:
                from fetch_cc_all_worlds_completed import local_auth_from_container

                auth = local_auth_from_container(search_profile)
                if auth:
                    names = load_player_names(search_profile)
                    season = current_season(search_profile)
                    search_ok, search_payload = post_search(int(target_row["playerId"]), auth, args.timeout_sec)
                    if search_ok and isinstance(search_payload, dict) and search_payload.get("code") == "000":
                        for rec in rows_from_payload(int(target_row["playerId"]), search_payload, names, season):
                            if (
                                int(rec.get("listingTeamId") or 0) == int(target_row["teamId"])
                                and int(rec.get("playerId") or 0) == int(target_row["playerId"])
                                and int(rec.get("acquiredSeason") or 0) == int(target_row["acquiredSeason"])
                                and str(rec.get("comment") or "") == str(args.comment)
                            ):
                                trade_id = rec.get("tradeId")
                                verify_source = "openai_trade_search"
                                break
            except Exception as exc:  # noqa: BLE001
                action["searchVerifyError"] = str(exc)
        action["verifiedTradeId"] = trade_id
        action["verifiedBy"] = verify_source
        state["registered"].append(
            {
                "status": "registered" if trade_id else "registered_unverified",
                "createdAt": now_iso(),
                "teamId": target_row.get("teamId"),
                "teamName": target_row.get("teamName"),
                "ownerName": target_row.get("ownerName"),
                "playerId": target_row.get("playerId"),
                "playerName": target_row.get("name"),
                "acquiredSeason": target_row.get("acquiredSeason"),
                "profileData": target_row.get("profileData"),
                "comment": args.comment,
                "tradeId": trade_id,
                "verifiedBy": verify_source,
                "response": payload,
            }
        )
    return action


def sync_profile_from_api(profile: Path, timeout_sec: float) -> dict[str, Any]:
    action: dict[str, Any] = {"type": "sync_profile", "profileData": str(profile)}
    auth = local_auth_from_container(profile)
    if not auth:
        action.update({"ok": False, "error": "could not generate auth"})
        return action
    ok, payload = get_api_json(SYNC_PATH, auth, timeout_sec)
    if not ok or not isinstance(payload, dict) or response_code(payload) != "000":
        action.update({"ok": False, "response": payload})
        return action
    db = profile / "Documents" / "Model" / "Model.sqlite"
    backup_path = db.with_suffix(db.suffix + f".pre_trade_chain_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
    shutil.copy2(db, backup_path)
    con = sqlite3.connect(str(db))
    try:
        con.execute("begin")
        update_summary = update_db(con, payload)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    action.update(
        {
            "ok": True,
            "teamName": payload.get("name"),
            "season": payload.get("season"),
            "backup": str(backup_path),
            "updated": update_summary,
        }
    )
    return action


def already_registered_chain_player(state: dict[str, Any], team_id: Any, player_id: Any, acquired_season: Any) -> bool:
    key = (str(team_id), str(player_id), str(acquired_season))
    for item in state.get("registered") or []:
        other = (str(item.get("teamId")), str(item.get("playerId")), str(item.get("acquiredSeason")))
        if other == key and item.get("status") in {"registered", "registered_unverified"}:
            return True
    return False


def has_active_registered_entries(state: dict[str, Any]) -> bool:
    return any(
        item.get("status") in {"registered", "registered_unverified"}
        for item in state.get("registered") or []
    )


def register_acquired_request_player(args: argparse.Namespace, state: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    action: dict[str, Any] = {"type": "register_acquired_request_player", "listingKey": item.get("listingKey")}
    if item.get("chainRegistered"):
        action["status"] = "already_chain_registered"
        return action
    profile = Path(str(item["profileData"])).expanduser().resolve()
    if not args.execute:
        action["status"] = "would_sync_and_register"
        return action
    sync_action = sync_profile_from_api(profile, args.timeout_sec)
    action["sync"] = sync_action
    if not sync_action.get("ok"):
        action["status"] = "sync_failed"
        return action
    try:
        owned = owned_player_from_profile(profile, int(item["listedPlayerId"]))
    except Exception as exc:  # noqa: BLE001
        action.update({"status": "acquired_player_not_found", "error": str(exc)})
        return action
    action["ownedPlayer"] = owned
    if already_registered_chain_player(state, owned.get("teamId"), owned.get("playerId"), owned.get("acquiredSeason")):
        action["status"] = "already_registered"
        item["chainRegistered"] = True
        return action
    register_action = register_owned_target(args, state, owned)
    action["register"] = register_action
    if register_action.get("ok") and response_code(register_action.get("response")) == "000":
        action["status"] = "registered"
        item["chainRegistered"] = True
        item["chainRegisteredAt"] = now_iso()
    else:
        action["status"] = "register_failed"
    return action


def is_trade_limit_response(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    message = str(payload.get("message") or "")
    return "今シーズンはこれ以上" in message or "トレードを行うことはできません" in message


def is_selected_player_unacquirable_response(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    message = str(payload.get("message") or "")
    return response_code(payload) == "301" and "相手チームが獲得できません" in message


def is_target_team_already_owns_offered_status(status: Any) -> bool:
    return str(status or "") == "target_team_already_owns_offered_player"


def request_action_succeeded(action: dict[str, Any]) -> bool:
    return bool(action.get("ok") and response_code(action.get("response")) == "000")


def retryable_request_item(item: dict[str, Any]) -> bool:
    if item.get("status") == "failed" and is_selected_player_unacquirable_response(item.get("response")):
        return True
    if is_target_team_already_owns_offered_status(item.get("status")):
        return True
    return (
        item.get("status") == "manual_canceled"
        and item.get("manualCancelReason") == "cancel_offer_that_should_have_paused_no_same_term_reserve"
    )


def previous_unacquirable_comment_failures(state: dict[str, Any], listing_key_value: str) -> tuple[set[str], set[str]]:
    comment_candidates: set[str] = set()
    wanted_names: set[str] = set()
    for item in state.get("requests") or []:
        if item.get("listingKey") != listing_key_value:
            continue
        if not (
            (item.get("status") == "failed" and is_selected_player_unacquirable_response(item.get("response")))
            or is_target_team_already_owns_offered_status(item.get("status"))
        ):
            continue
        wanted = item.get("wanted") or {}
        if wanted.get("commentCandidate"):
            comment_candidates.add(str(wanted.get("commentCandidate")))
        if wanted.get("canonicalWantedName"):
            wanted_names.add(str(wanted.get("canonicalWantedName")))
        elif item.get("offeredPlayerName"):
            wanted_names.add(str(item.get("offeredPlayerName")))
    return comment_candidates, wanted_names


def has_retryable_request_for_listing(state: dict[str, Any], listing_key_value: str) -> bool:
    return any(
        item.get("listingKey") == listing_key_value and retryable_request_item(item)
        for item in state.get("requests") or []
    )


def request_row_from_detail_payload(payload: Any, item: dict[str, Any]) -> list[Any] | None:
    if not isinstance(payload, dict):
        return None
    sections = payload.get("list")
    if not isinstance(sections, list) or len(sections) < 2 or not isinstance(sections[1], list):
        return None
    for row in sections[1]:
        vals = list(row) + [None] * 13
        try:
            if (
                int(vals[0] or 0) == int(item.get("requestTeamId") or 0)
                and int(vals[2] or 0) == int(item.get("listingTeamId") or 0)
                and int(vals[3] or 0) == int(item.get("listingTradeId") or 0)
                and int(vals[4] or 0) == int(item.get("offeredPlayerId") or 0)
                and int(vals[5] or 0) == int(item.get("offeredAcquiredSeason") or 0)
            ):
                return row
        except (TypeError, ValueError):
            continue
    return None


def ensure_request_trade_id(args: argparse.Namespace, item: dict[str, Any]) -> int | None:
    value = item.get("requestTradeId")
    if value:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    profile = Path(str(item.get("profileData") or "")).expanduser().resolve()
    ok, payload = trade_detail(profile, int(item["listingTeamId"]), int(item["listingTradeId"]), args.timeout_sec)
    if not ok or response_code(payload) != "000":
        return None
    row = request_row_from_detail_payload(payload, item)
    if not row:
        return None
    vals = list(row) + [None] * 13
    try:
        request_trade_id = int(vals[1])
    except (TypeError, ValueError):
        return None
    item["requestTradeId"] = request_trade_id
    return request_trade_id


def away_team_player_ids(profile: Path, away_team_id: int, timeout_sec: float) -> tuple[bool, set[int], Any]:
    ok, payload = away_team_index(profile, int(away_team_id), timeout_sec=timeout_sec)
    if not ok or response_code(payload) != "000":
        return False, set(), payload
    ids: set[int] = set()
    for raw in payload.get("players") or []:
        parts = str(raw).split(",")
        if not parts:
            continue
        try:
            ids.add(int(parts[0]))
        except (TypeError, ValueError):
            continue
    return True, ids, payload


def target_team_owns_offered_player(
    args: argparse.Namespace,
    rec: dict[str, Any],
    offered_player_id: int,
) -> dict[str, Any] | None:
    try:
        listed_player_id = int(rec.get("playerId") or 0)
        offered_id = int(offered_player_id)
    except (TypeError, ValueError):
        return None
    if not offered_id:
        return None
    if listed_player_id and offered_id == listed_player_id:
        return None
    check_profile = Path(args.auth_profile).expanduser().resolve() if args.auth_profile else DEFAULT_SEARCH_PROFILE
    ok, player_ids, payload = away_team_player_ids(check_profile, int(rec["listingTeamId"]), args.timeout_sec)
    if not ok:
        return {
            "status": "target_team_roster_check_failed",
            "response": summarize_error_payload(payload),
        }
    if offered_id not in player_ids:
        return None
    return {
        "status": "target_team_already_owns_offered_player",
        "targetTeamId": rec.get("listingTeamId"),
        "offeredPlayerId": offered_id,
        "listedPlayerId": listed_player_id,
    }


def create_team_and_register(args: argparse.Namespace, state: dict[str, Any], player_id: int, player_name: str) -> dict[str, Any]:
    action = {
        "type": "register_new_team",
        "playerId": int(player_id),
        "playerName": player_name,
        "execute": bool(args.execute),
    }
    if ACTIVE_NR_PLAYER_IDS and int(player_id) not in ACTIVE_NR_PLAYER_IDS:
        action["status"] = "ineligible_player_not_active_nr"
        state.setdefault("registrationAttempts", []).append({**action, "createdAt": now_iso()})
        return action
    if not args.execute:
        action["createTeamCommand"] = [
            sys.executable,
            str(Path(__file__).resolve().parent / "complete_websoccer_tutorial.py"),
            "--profile-data",
            f"<auto-copy {Path(args.new_team_base_profile).expanduser()} to {args.new_team_work_root}/{slugify(player_name)}_.../Data>",
            "--create-team",
            "--player-id",
            str(player_id),
            "--sync",
            "--backup",
            "--execute",
        ]
        return action
    if len(state.get("newTeams") or []) >= max(0, int(args.max_new_teams)):
        action.update(
            {
                "status": "max_new_teams_reached",
                "maxNewTeams": int(args.max_new_teams),
                "newTeamsCreated": len(state.get("newTeams") or []),
            }
        )
        state.setdefault("registrationAttempts", []).append({**action, "createdAt": now_iso()})
        return action
    created_ok, created = create_team_for_wanted_player(args, int(player_id), player_name)
    action["teamCreation"] = created
    if not created_ok:
        action["status"] = "new_team_creation_failed"
        state.setdefault("registrationAttempts", []).append({**action, "createdAt": now_iso()})
        return action
    owned = created["ownedPlayer"]
    state["newTeams"].append(
        {
            "createdAt": now_iso(),
            "wantedName": player_name,
            "playerId": int(player_id),
            "profileData": owned.get("profileData"),
            "teamId": owned.get("teamId"),
            "teamName": owned.get("teamName"),
            "ownerName": owned.get("ownerName"),
        }
    )
    register_action = register_owned_target(args, state, owned)
    action["register"] = register_action
    action["status"] = "registered" if register_action.get("ok") and isinstance(register_action.get("response"), dict) and register_action["response"].get("code") == "000" else "failed"
    return action


def register_target_with_fallback(
    args: argparse.Namespace,
    state: dict[str, Any],
    owned: list[dict[str, Any]],
    player_ids: list[int],
    player_name: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    attempted = {
        (str(item.get("teamId")), str(item.get("playerId")), str(item.get("acquiredSeason")))
        for item in state.get("registrationAttempts") or []
        if item.get("teamId") and item.get("playerId") and item.get("acquiredSeason")
    }
    for row in owned:
        key = (str(row.get("teamId")), str(row.get("playerId")), str(row.get("acquiredSeason")))
        if key in attempted:
            continue
        action = register_owned_target(args, state, row)
        actions.append(action)
        payload = action.get("response")
        if action.get("ok") and isinstance(payload, dict) and payload.get("code") == "000":
            return actions
        if is_trade_limit_response(payload):
            continue
        return actions
    if not state.get("registered") and player_ids:
        actions.append(create_team_and_register(args, state, int(player_ids[0]), player_name))
    return actions


def request_listing(
    args: argparse.Namespace,
    state: dict[str, Any],
    rec: dict[str, Any],
    offer_choice: dict[str, Any],
    index: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
) -> dict[str, Any]:
    key = listing_key(rec)
    owner = str(rec.get("owner") or "")
    base = {
        "type": "request",
        "listingKey": key,
        "listingTeamId": rec.get("listingTeamId"),
        "listingTradeId": rec.get("tradeId"),
        "listingOwner": owner,
        "wanted": offer_choice,
        "execute": bool(args.execute),
    }
    if offer_choice.get("needsNewTeam"):
        player_ids = offer_choice.get("playerIds") or []
        if player_ids:
            if args.new_team_profile_data:
                profile_arg = args.new_team_profile_data
            else:
                profile_arg = (
                    f"<auto-copy {Path(args.new_team_base_profile).expanduser()} "
                    f"to {Path(args.new_team_work_root) / (slugify(offer_choice.get('canonicalWantedName') or offer_choice.get('wantedName') or 'player') + '_...') / 'Data'}>"
                )
            base["createTeamCommand"] = [
                sys.executable,
                str(Path(__file__).resolve().parent / "complete_websoccer_tutorial.py"),
                "--profile-data",
                profile_arg,
                "--create-team",
                "--player-id",
                str(player_ids[0]),
                "--sync",
                "--backup",
                "--execute",
            ]
        if not args.execute:
            return {**base, "status": "needs_new_team"}
    if not offer_choice.get("needsNewTeam") and not offer_choice.get("row"):
        skipped = {**base, "status": str(offer_choice.get("reason") or "no_offer_candidate"), "createdAt": now_iso()}
        state["skippedListings"].append(skipped)
        return {**base, "status": skipped["status"]}
    if offer_choice.get("needsNewTeam"):
        if not player_ids:
            state["skippedListings"].append({**base, "status": "needs_new_team_no_player_id", "createdAt": now_iso()})
            return {**base, "status": "needs_new_team_no_player_id"}
        if ACTIVE_NR_PLAYER_IDS and int(player_ids[0]) not in ACTIVE_NR_PLAYER_IDS:
            skipped = {**base, "status": "ineligible_player_not_active_nr", "createdAt": now_iso(), "playerId": int(player_ids[0])}
            state["skippedListings"].append(skipped)
            return {**base, "status": "ineligible_player_not_active_nr"}
        target_owns = target_team_owns_offered_player(args, rec, int(player_ids[0]))
        if target_owns and target_owns.get("status") == "target_team_already_owns_offered_player":
            skipped = {
                **base,
                **target_owns,
                "createdAt": now_iso(),
                "wantedName": offer_choice.get("canonicalWantedName") or offer_choice.get("wantedName"),
            }
            state["skippedListings"].append(skipped)
            return {**base, **target_owns}
        if len(state.get("newTeams") or []) >= max(0, int(args.max_new_teams)):
            skipped = {
                **base,
                "status": "max_new_teams_reached",
                "createdAt": now_iso(),
                "maxNewTeams": int(args.max_new_teams),
                "newTeamsCreated": len(state.get("newTeams") or []),
            }
            state["skippedListings"].append(skipped)
            return {**base, "status": "max_new_teams_reached"}
        created_ok, created = create_team_for_wanted_player(
            args,
            int(player_ids[0]),
            str(offer_choice.get("canonicalWantedName") or offer_choice.get("wantedName") or ""),
        )
        base["teamCreation"] = created
        if not created_ok:
            state["skippedListings"].append({**base, "status": "new_team_creation_failed", "createdAt": now_iso()})
            return {**base, "status": "new_team_creation_failed"}
        state["newTeams"].append(
            {
                "createdAt": now_iso(),
                "wantedName": offer_choice.get("canonicalWantedName") or offer_choice.get("wantedName"),
                "playerId": int(player_ids[0]),
                "profileData": (created.get("ownedPlayer") or {}).get("profileData"),
                "teamId": (created.get("ownedPlayer") or {}).get("teamId"),
                "teamName": (created.get("ownedPlayer") or {}).get("teamName"),
                "ownerName": (created.get("ownedPlayer") or {}).get("ownerName"),
            }
        )
        row = created["ownedPlayer"]
        if ACTIVE_NR_PLAYER_IDS and not is_active_nr_player_id(row.get("playerId")):
            skipped = {**base, "status": "ineligible_player_not_active_nr", "createdAt": now_iso(), "createdOfferRow": row}
            state["skippedListings"].append(skipped)
            return {**base, "status": "ineligible_player_not_active_nr"}
        profile = Path(str(row["profileData"])).expanduser().resolve()
        ok, payload = trade_request(
            profile,
            int(rec["listingTeamId"]),
            int(rec["tradeId"]),
            int(row["playerId"]),
            int(row["acquiredSeason"]),
            timeout_sec=args.timeout_sec,
        )
        base.update({"ok": ok, "response": payload, "createdOfferRow": row})
        item = {
            "createdAt": now_iso(),
            "status": "requested" if ok and isinstance(payload, dict) and payload.get("code") == "000" else "failed",
            "listingKey": key,
            "listingTeamId": rec.get("listingTeamId"),
            "listingTradeId": rec.get("tradeId"),
            "listingOwner": owner,
            "listedPlayerId": rec.get("playerId"),
            "listedPlayerName": rec.get("playerName"),
            "requestTeamId": row.get("teamId"),
            "requestTeamName": row.get("teamName"),
            "requestOwnerName": row.get("ownerName"),
            "offeredPlayerId": row.get("playerId"),
            "offeredPlayerName": row.get("name"),
            "offeredAcquiredSeason": row.get("acquiredSeason"),
            "profileData": row.get("profileData"),
            "createdNewTeam": True,
            "teamCreation": created,
            "response": payload,
        }
        state["requests"].append(item)
        if item["status"] == "requested":
            ensure_request_trade_id(args, item)
        if item["status"] == "requested" and owner:
            state["offeredOwners"] = sorted({*state.get("offeredOwners", []), owner})
        if item["status"] == "requested" and offer_choice.get("openOfferCandidate"):
            advance_open_offer_rotation(offer_choice["openOfferCandidate"])
        return base
    row = offer_choice["row"]
    if ACTIVE_NR_PLAYER_IDS and not is_active_nr_player_id(row.get("playerId")):
        skipped = {**base, "status": "ineligible_player_not_active_nr", "createdAt": now_iso(), "row": row}
        state["skippedListings"].append(skipped)
        return {**base, "status": "ineligible_player_not_active_nr"}
    target_owns = target_team_owns_offered_player(args, rec, int(row["playerId"]))
    if target_owns and target_owns.get("status") == "target_team_already_owns_offered_player":
        skipped = {**base, **target_owns, "createdAt": now_iso(), "row": row}
        state["skippedListings"].append(skipped)
        return {**base, **target_owns}
    pause_action = should_pause_last_existing_same_term_offer(
        args=args,
        state=state,
        rec=rec,
        row=row,
        index=index,
        global_locks=global_locks,
    )
    if pause_action:
        try:
            offered_term = int(pause_action.get("offeredTerm") or 0)
            player_id = int(pause_action.get("offeredPlayerId") or 0)
        except (TypeError, ValueError):
            offered_term = 0
            player_id = 0
        if offered_term == 1 and player_id:
            fallback_choice = {
                **{k: v for k, v in offer_choice.items() if k != "row"},
                "needsNewTeam": True,
                "playerIds": [player_id],
                "wantedTerms": [1],
                "reason": "fallback_new_team_to_keep_same_term_reserve",
                "reservePauseWouldHaveTriggered": pause_action,
            }
            return request_listing(args, state, rec, fallback_choice, index, global_locks)
        state["stopped"] = True
        state["pauseReason"] = "last_existing_same_term_offer_requires_approval"
        state["pendingApproval"] = pause_action
        state["pausedAt"] = now_iso()
        state["skippedListings"].append({**base, **pause_action})
        return {**base, **pause_action}
    if not args.execute:
        return base
    profile = Path(str(row["profileData"])).expanduser().resolve()
    ok, payload = trade_request(
        profile,
        int(rec["listingTeamId"]),
        int(rec["tradeId"]),
        int(row["playerId"]),
        int(row["acquiredSeason"]),
        timeout_sec=args.timeout_sec,
    )
    base.update({"ok": ok, "response": payload})
    item = {
        "createdAt": now_iso(),
        "status": "requested" if ok and isinstance(payload, dict) and payload.get("code") == "000" else "failed",
        "listingKey": key,
        "listingTeamId": rec.get("listingTeamId"),
        "listingTradeId": rec.get("tradeId"),
        "listingOwner": owner,
        "listedPlayerId": rec.get("playerId"),
        "listedPlayerName": rec.get("playerName"),
        "requestTeamId": row.get("teamId"),
        "requestTeamName": row.get("teamName"),
        "requestOwnerName": row.get("ownerName"),
        "offeredPlayerId": row.get("playerId"),
        "offeredPlayerName": row.get("name"),
        "offeredAcquiredSeason": row.get("acquiredSeason"),
        "profileData": row.get("profileData"),
        "response": payload,
    }
    state["requests"].append(item)
    if item["status"] == "requested":
        ensure_request_trade_id(args, item)
    if item["status"] == "requested" and owner:
        state["offeredOwners"] = sorted({*state.get("offeredOwners", []), owner})
    if item["status"] == "requested" and offer_choice.get("openOfferCandidate"):
        advance_open_offer_rotation(offer_choice["openOfferCandidate"])
    return base


def search_and_plan(
    args: argparse.Namespace,
    state: dict[str, Any],
    site_players: list[dict[str, Any]],
    index: dict[str, Any],
    global_locks: set[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    player_name, category = split_player_and_category(args.player, args.category)
    player_ids, canonical = resolve_listed_player(site_players, player_name, category)
    if not player_ids:
        raise SystemExit(f"[ERROR] player not found: name={player_name} category={category}")
    auth_profile = Path(args.auth_profile).expanduser().resolve() if args.auth_profile else None
    if auth_profile:
        season, records = search_records(player_ids, auth_profile, args.timeout_sec)
    else:
        from search_websoccer_trade_listings import DEFAULT_SEARCH_PROFILE

        season, records = search_records(player_ids, DEFAULT_SEARCH_PROFILE, args.timeout_sec)
    records = [rec for rec in records if rec.get("term") == args.term]
    player_names = unique_player_names(site_players)
    nr_names = nr_player_names(site_players)
    for rec in records:
        rec["commentAnalysis"] = analyze_comment(rec.get("comment"), player_names, nr_names)
    matches = [rec for rec in records if (rec.get("commentAnalysis") or {}).get("include")]
    retryable_skip_statuses = {
        "new_team_creation_failed",
        "same_player_offer_not_allowed",
        "last_existing_same_term_offer_requires_approval",
        "skipped_same_owner",
        "target_team_already_owns_offered_player",
    }
    seen_listing_keys = {
        item.get("listingKey")
        for item in state.get("requests", []) or []
        if item.get("listingKey") and not retryable_request_item(item)
    }
    seen_listing_keys.update(
        item.get("listingKey")
        for item in state.get("skippedListings", []) or []
        if item.get("listingKey") and item.get("status") not in retryable_skip_statuses
    )
    offered_owners = set(state.get("offeredOwners") or [])
    actions = []
    for rec in matches:
        key = listing_key(rec)
        owner = str(rec.get("owner") or "")
        if key in seen_listing_keys:
            actions.append({"type": "skip", "reason": "listing_already_processed", "listingKey": key})
            continue
        if owner and owner in offered_owners and not has_retryable_request_for_listing(state, key):
            if args.execute:
                state["skippedListings"].append(
                    {
                        "createdAt": now_iso(),
                        "status": "skipped_same_owner",
                        "listingKey": key,
                        "listingTeamId": rec.get("listingTeamId"),
                        "listingTradeId": rec.get("tradeId"),
                        "listingOwner": owner,
                    }
                )
            actions.append({"type": "skip", "reason": "owner_already_offered", "listingKey": key, "owner": owner})
            continue
        wanted = display_wanted(rec)
        if wanted == "指定なし":
            excluded_player_ids = set() if comment_allows_same_player(rec.get("comment")) else {int(v) for v in player_ids}
            skipped_rotation_indices: set[int] = set()
            for _ in range(len(OPEN_OFFER_CANDIDATES)):
                choice = choose_open_request_offer_player(
                    condition=rec.get("condition"),
                    site_players=site_players,
                    index=index,
                    state=state,
                    global_locks=global_locks,
                    allow_managed_team_quota_use=bool(args.allow_managed_team_quota_use),
                    excluded_player_ids=excluded_player_ids,
                    skipped_rotation_indices=skipped_rotation_indices,
                )
                action = request_listing(args, state, rec, choice, index, global_locks)
                actions.append(action)
                if state.get("pauseReason") == "last_existing_same_term_offer_requires_approval":
                    break
                if request_action_succeeded(action):
                    break
                candidate = choice.get("openOfferCandidate") or {}
                if (
                    is_selected_player_unacquirable_response(action.get("response"))
                    or is_target_team_already_owns_offered_status(action.get("status"))
                ) and candidate:
                    try:
                        skipped_rotation_indices.add(int(candidate.get("rotationIndex")))
                    except (TypeError, ValueError):
                        break
                    continue
                break
            if state.get("pauseReason") == "last_existing_same_term_offer_requires_approval":
                break
            continue
        else:
            analysis = rec.get("commentAnalysis") or {}
            if analysis.get("matchType") == "same_player_first_term_comment":
                choice = choose_offer_player(
                    wanted_name=canonical or player_name,
                    wanted_terms=[1],
                    site_players=site_players,
                    index=index,
                    state=state,
                    global_locks=global_locks,
                    allow_managed_team_quota_use=bool(args.allow_managed_team_quota_use),
                    excluded_player_ids=set(),
                )
                choice["commentCandidate"] = analysis.get("matchedCandidate") or analysis.get("comment")
                action = request_listing(args, state, rec, choice, index, global_locks)
                actions.append(action)
            else:
                skipped_comment_candidates, skipped_wanted_names = previous_unacquirable_comment_failures(state, key)
                candidate_count = max(1, len(analysis.get("candidates") or []))
                for _ in range(candidate_count):
                    choice = choose_comment_offer_player(
                        analysis=analysis,
                        site_players=site_players,
                        index=index,
                        state=state,
                        global_locks=global_locks,
                        allow_managed_team_quota_use=bool(args.allow_managed_team_quota_use),
                        excluded_player_ids=set(),
                        skipped_comment_candidates=skipped_comment_candidates,
                        skipped_wanted_names=skipped_wanted_names,
                    )
                    action = request_listing(args, state, rec, choice, index, global_locks)
                    actions.append(action)
                    if state.get("pauseReason") == "last_existing_same_term_offer_requires_approval":
                        break
                    if request_action_succeeded(action):
                        break
                    if (
                        is_selected_player_unacquirable_response(action.get("response"))
                        or is_target_team_already_owns_offered_status(action.get("status"))
                    ):
                        if choice.get("commentCandidate"):
                            skipped_comment_candidates.add(str(choice.get("commentCandidate")))
                        if choice.get("canonicalWantedName"):
                            skipped_wanted_names.add(str(choice.get("canonicalWantedName")))
                        continue
                    break
        if state.get("pauseReason") == "last_existing_same_term_offer_requires_approval":
            break
    state["lastSearch"] = {
        "at": now_iso(),
        "season": season,
        "recordsSearched": len(records),
        "recordsMatched": len(matches),
    }
    return actions


def check_registered(args: argparse.Namespace, state: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in state.get("registered") or []:
        if item.get("status") not in {"registered", "registered_unverified"}:
            continue
        trade_id = item.get("tradeId") or item.get("registeredTradeId")
        if not trade_id:
            actions.append({"type": "watch_registered", "status": "missing_trade_id", "registered": item})
            continue
        profile = Path(str(item["profileData"])).expanduser().resolve()
        ok, payload = trade_detail(profile, int(item["teamId"]), int(trade_id), args.timeout_sec)
        action = {"type": "watch_registered", "teamId": item.get("teamId"), "tradeId": trade_id, "ok": ok}
        if ok and response_code(payload) == "000":
            offers = payload.get("list", [None, []])[1] if isinstance(payload.get("list"), list) and len(payload["list"]) > 1 else []
            for row in offers if isinstance(offers, list) else []:
                vals = list(row) + [None] * 13
                owner = str(vals[6] or "")
                status = vals[9]
                flag = vals[10]
                if is_accepted_owner(owner, args.accept_owner) and int(status or 0) == 2 and int(flag or 0) == 0:
                    if args.execute:
                        notify_ok, notify_payload = trade_notificated(profile, [int(vals[1])], timeout_sec=args.timeout_sec)
                        exec_ok, exec_payload = trade_execute(profile, int(trade_id), int(vals[0]), int(vals[1]), timeout_sec=args.timeout_sec)
                        action.update(
                            {
                                "notificatedOk": notify_ok,
                                "notificatedResponse": notify_payload,
                                "executeOk": exec_ok,
                                "executeResponse": exec_payload,
                            }
                        )
                        if exec_ok and isinstance(exec_payload, dict) and exec_payload.get("code") == "000":
                            item["status"] = "executed"
                            state["completed"].append({"at": now_iso(), "kind": "accepted_incoming", "registered": item, "offerRow": row})
                            state["stopped"] = True
                    else:
                        action.update({"wouldExecute": True, "offerRow": row})
        else:
            action["response"] = payload
        actions.append(action)
    return actions


def check_requests(args: argparse.Namespace, state: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in state.get("requests") or []:
        if item.get("status") != "requested":
            continue
        profile = Path(str(item["profileData"])).expanduser().resolve()
        ok, payload = trade_detail(profile, int(item["listingTeamId"]), int(item["listingTradeId"]), args.timeout_sec)
        action = {"type": "watch_request", "listingKey": item.get("listingKey"), "ok": ok}
        if ok and response_code(payload) == "301":
            completion = {"at": now_iso(), "kind": "request_detail_ended", "request": item, "detail": payload}
            register_action = register_acquired_request_player(args, state, item)
            action["registerAcquired"] = register_action
            if register_action.get("status") == "registered":
                item["status"] = "maybe_completed_or_ended"
                completion["registerAcquired"] = register_action
                state["completed"].append(completion)
                action["status"] = "completion_or_end_detected"
            else:
                item["status"] = "ended_without_acquisition"
                state.setdefault("endedRequests", []).append(
                    {
                        "at": now_iso(),
                        "kind": "request_detail_ended_without_acquisition",
                        "request": item,
                        "detail": payload,
                        "registerAcquired": register_action,
                    }
                )
                action["status"] = "ended_without_acquisition"
                continue
            state["stopped"] = True
        elif ok and isinstance(payload, dict):
            action["code"] = payload.get("code")
        else:
            action["response"] = payload
        actions.append(action)
    return actions


def main_once(args: argparse.Namespace, state_path: Path) -> dict[str, Any]:
    global ACTIVE_NR_PLAYER_IDS
    site_players = load_site_players(Path(args.app_data).expanduser().resolve())
    ACTIVE_NR_PLAYER_IDS = active_nr_player_ids(site_players)
    index = merge_trade_chain_profile_rows(
        load_players_index(Path(args.players_index).expanduser().resolve()),
        Path(args.new_team_work_root).expanduser(),
    )
    global_locks = global_active_offer_locks((Path.cwd() / DEFAULT_STATE_DIR).resolve())
    player_name, category = split_player_and_category(args.player, args.category)
    player_ids, canonical = resolve_listed_player(site_players, player_name, category)
    query = {"player": player_name, "canonicalPlayer": canonical, "category": category, "playerIds": player_ids, "term": args.term}
    state = init_state(state_path, query)
    actions: list[dict[str, Any]] = []
    if (
        args.approve_paused_last_existing_same_term_offer
        and state.get("pauseReason") == "last_existing_same_term_offer_requires_approval"
        and isinstance(state.get("pendingApproval"), dict)
    ):
        approval_key = str(state["pendingApproval"].get("approvalKey") or "")
        if approval_key:
            approvals = set(state.get("approvedLastExistingSameTermOffers") or [])
            approvals.add(approval_key)
            state["approvedLastExistingSameTermOffers"] = sorted(approvals)
        state["stopped"] = False
        state["pauseReason"] = ""
        state["approvedAt"] = now_iso()
        actions.append(
            {
                "type": "approval",
                "status": "approved_last_existing_same_term_offer",
                "approvalKey": approval_key,
                "pendingApproval": state.get("pendingApproval"),
            }
        )
        state["pendingApproval"] = None
    if state.get("stopped"):
        if state.get("pauseReason") == "last_existing_same_term_offer_requires_approval":
            state["updatedAt"] = now_iso()
            write_json(state_path, state)
            return {"stateFile": str(state_path), "execute": bool(args.execute), "actions": actions, "state": state}
        if has_active_registered_entries(state):
            actions.extend(check_registered(args, state))
            state["updatedAt"] = now_iso()
            write_json(state_path, state)
            return {"stateFile": str(state_path), "execute": bool(args.execute), "actions": actions, "state": state}
        state["updatedAt"] = now_iso()
        write_json(state_path, state)
        return {"stateFile": str(state_path), "execute": bool(args.execute), "actions": actions, "state": state}
    if not state.get("registered"):
        owned = owned_rows_for_player_ids(
            index,
            set(player_ids),
            args.term,
            allow_managed_team_quota_use=bool(args.allow_managed_team_quota_use),
        )
        if owned:
            actions.extend(register_target_with_fallback(args, state, owned, player_ids, canonical or player_name))
        else:
            actions.extend(search_and_plan(args, state, site_players, index, global_locks))
    else:
        actions.extend(search_and_plan(args, state, site_players, index, global_locks))

    if state.get("pauseReason") == "last_existing_same_term_offer_requires_approval":
        state["updatedAt"] = now_iso()
        write_json(state_path, state)
        return {"stateFile": str(state_path), "execute": bool(args.execute), "actions": actions, "state": state}

    actions.extend(check_registered(args, state))
    actions.extend(check_requests(args, state))
    state["updatedAt"] = now_iso()
    write_json(state_path, state)
    return {"stateFile": str(state_path), "execute": bool(args.execute), "actions": actions, "state": state}


def main() -> int:
    args = parse_args()
    player_name, category = split_player_and_category(args.player, args.category)
    state_path = (
        Path(args.state_file).expanduser().resolve()
        if args.state_file
        else (Path.cwd() / DEFAULT_STATE_DIR / f"{slugify(player_name)}_{category}_{args.term}.json").resolve()
    )
    lock_file = acquire_state_lock(state_path)
    if lock_file is None:
        print(json.dumps({"type": "skip", "reason": "state_lock_busy", "stateFile": str(state_path)}, ensure_ascii=False))
        return 0
    while True:
        result = main_once(args, state_path)
        if args.notify_pushover and args.execute:
            notify_trade_events(result["state"], state_path, player_name, args.term)
            notify_attention_events(result["actions"], player_name, args.term)
        if args.dry_run_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"[STATE] {state_path}")
            for action in result["actions"]:
                print(json.dumps(action, ensure_ascii=False, default=str))
        if not args.watch or result["state"].get("stopped"):
            return 0
        time.sleep(max(1, int(args.interval_sec)))


if __name__ == "__main__":
    raise SystemExit(main())
