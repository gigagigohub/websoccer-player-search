#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import plistlib
import random
import secrets
import shutil
import sqlite3
import ssl
import string
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as uuidlib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from fetch_cc_all_worlds_completed import API_HOST, UA_FALLBACK, AuthHeaders, local_auth_from_container
from sync_websoccer_local_profile_from_api import SYNC_PATH, update_db


DEFAULT_PROFILE_DATA = Path.home() / "Library/Containers/jp.novelapproach.WebSoccer/Data"
DEFAULT_SESSION_DIR = Path.home() / "charles_sessions"
DEFAULT_MASTER_DB_ROOTS = [
    Path.home() / "Codex/WebSoccer/wsc_data/websoccer_master_db",
]
FORMAL_PATH = "/creating_team/formal.json"
CHECK_NAME_PATH = "/creating_team/checkName.json"
INFORMAL_PATH = "/creating_team/informal.json"
STATUS_PATH_TMPL = "/creating_team/status/{uuid}.json"
CREATION_TEAM_ID = "99999999999"
RANDOM_NAME_ALPHABET = string.ascii_letters
RANDOM_NAME_MIN_LEN = 5
RANDOM_NAME_MAX_LEN = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Complete an already-created WebSoccer tutorial team via /creating_team/formal.json."
    )
    p.add_argument(
        "--profile-data",
        default=str(DEFAULT_PROFILE_DATA),
        help=f"Data directory containing Documents/Model/Model.sqlite (default: {DEFAULT_PROFILE_DATA})",
    )
    p.add_argument(
        "--create-team",
        action="store_true",
        help="Run checkName/informal before formal, then complete tutorial in one flow.",
    )
    p.add_argument(
        "--team-name",
        default="",
        help="Team name for --create-team. Default: random alphabetic 5-10 character name.",
    )
    p.add_argument(
        "--owner-name",
        default="",
        help="Owner/manager name for --create-team. Default: random alphabetic 5-10 character name.",
    )
    p.add_argument("--owner-retries", type=int, default=10, help="Random name retry count for checkName.")
    p.add_argument("--wanted-world-id", type=int, default=0, help="wanted_world_id for informal (default: 0).")
    p.add_argument("--prefecture-id", type=int, default=1, help="prefecture_id for informal (default: 1).")
    p.add_argument("--device-type", type=int, default=1, help="device_type for informal (default: 1).")
    p.add_argument(
        "--reuse-profile-uuid",
        action="store_true",
        help="Use the existing profile UUID for --create-team. Default creates a fresh UUID.",
    )
    p.add_argument("--player-id", type=int, required=True, help="Initial player id to select. This is explicit by design.")
    p.add_argument(
        "--headcoach-id",
        type=int,
        default=0,
        help="Initial headcoach id. Default: randomly select from existing WSM headcoach ids.",
    )
    p.add_argument(
        "--formation-ids",
        default="",
        help=(
            "Comma-separated initial formation ids. Default: randomly select 3 WSM formation ids "
            "after excluding formations with no available coach."
        ),
    )
    p.add_argument("--team-id", type=int, default=0, help="Override team id; defaults to local ZMOTEAMDATA.")
    p.add_argument("--world-id", type=int, default=0, help="Override world id; defaults to local ZMOTEAMDATA.")
    p.add_argument(
        "--league-id",
        type=int,
        default=0,
        help="Override server league id; defaults to ZMOLEAGUE.ZID joined from local ZMOTEAMDATA.ZLEAGUE.",
    )
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument(
        "--master-db",
        default="",
        help="WSM sqlite DB used for random headcoach/formation selection. Default: latest wsm_*.sqlite3.",
    )
    p.add_argument("--random-seed", type=int, default=None, help="Optional deterministic seed for dry-run/debugging.")
    p.add_argument(
        "--creation-session-file",
        default="",
        help=(
            "Charles .chlz/.chlsx/.chlsj file containing a creation Websoccer-gate-key. "
            "If omitted, ~/charles_sessions is scanned."
        ),
    )
    p.add_argument(
        "--creation-session-dir",
        default=str(DEFAULT_SESSION_DIR),
        help=f"Directory scanned for creation auth when --creation-session-file is omitted (default: {DEFAULT_SESSION_DIR})",
    )
    p.add_argument("--execute", action="store_true", help="Actually POST formal.json. Without this, only print payload.")
    p.add_argument(
        "--sync",
        action="store_true",
        help="After successful formal POST, fetch /sync/all.json and update the local profile DB.",
    )
    p.add_argument("--backup", action="store_true", help="Back up Model.sqlite before --sync writes.")
    p.add_argument(
        "--no-update-prefs",
        action="store_true",
        help="Do not mark local tutorial prefs complete after successful formal POST.",
    )
    return p.parse_args()


def db_path(profile: Path) -> Path:
    return profile / "Documents" / "Model" / "Model.sqlite"


def plist_path(profile: Path) -> Path:
    full = profile / "Library" / "Preferences" / "jp.novelapproach.WebSoccer.plist"
    if full.exists():
        return full
    return profile / "Preferences" / "jp.novelapproach.WebSoccer.plist"


def table_columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in con.execute(f"pragma table_info({table})")]


def profile_metadata(profile: Path) -> dict[str, Any]:
    db = db_path(profile)
    if not db.exists():
        raise FileNotFoundError(f"Model.sqlite not found: {db}")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        team = con.execute(
            "select ZTEAM_ID, ZNAME, ZOWNER_NAME, ZSZN, ZWORLD_ID, ZLEAGUE from ZMOTEAMDATA limit 1"
        ).fetchone()
        if not team:
            raise RuntimeError("ZMOTEAMDATA has no rows")
        league = con.execute("select ZID from ZMOLEAGUE where Z_PK=?", (int(team["ZLEAGUE"]),)).fetchone()
        if not league:
            raise RuntimeError(f"missing ZMOLEAGUE row for Z_PK={team['ZLEAGUE']}")
        player_count = 0
        if "ZMOTEAMSPLAYER" in table_names(con):
            player_count = int(con.execute("select count(*) from ZMOTEAMSPLAYER").fetchone()[0])
        return {
            "team_id": int(team["ZTEAM_ID"]),
            "team_name": team["ZNAME"],
            "owner_name": team["ZOWNER_NAME"],
            "season": int(team["ZSZN"]),
            "world_id": int(team["ZWORLD_ID"]),
            "league_pk": int(team["ZLEAGUE"]),
            "league_id": int(league["ZID"]),
            "players": player_count,
        }
    finally:
        con.close()


def profile_uuid(profile: Path) -> str:
    path = plist_path(profile)
    if not path.exists():
        raise FileNotFoundError(f"preferences plist not found: {path}")
    with path.open("rb") as fh:
        data = plistlib.load(fh)
    uuid = str(data.get("UUID") or "").strip()
    if not uuid:
        raise RuntimeError(f"UUID not found in preferences plist: {path}")
    return uuid


def set_profile_uuid(profile: Path, uuid_value: str) -> None:
    path = plist_path(profile)
    if not path.exists():
        raise FileNotFoundError(f"preferences plist not found: {path}")
    with path.open("rb") as fh:
        data = plistlib.load(fh)
    data["UUID"] = uuid_value
    with path.open("wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)


def table_names(con: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in con.execute("select name from sqlite_master where type='table'")}


def latest_master_db() -> Path:
    candidates: list[Path] = []
    for root in DEFAULT_MASTER_DB_ROOTS:
        if root.exists():
            candidates.extend(root.glob("wsm_*.sqlite3"))
    candidates = [p for p in candidates if p.is_file()]
    if not candidates:
        raise FileNotFoundError("could not find wsm_*.sqlite3 under known master DB roots")
    return sorted(candidates, key=lambda p: (p.name, p.stat().st_mtime), reverse=True)[0].resolve()


def resolve_master_db(raw: str) -> Path:
    if raw:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"master DB not found: {path}")
        return path
    return latest_master_db()


def random_initial_choices(master_db: Path, rng: random.Random, formation_count: int = 3) -> dict[str, Any]:
    con = sqlite3.connect(f"file:{master_db}?mode=ro", uri=True)
    try:
        coach_rows = con.execute(
            """
            select distinct ZHEADCOACH_ID
            from ao__ZMOHEADCOACH
            where ZHEADCOACH_ID > 0 and coalesce(ZSTATUS, 1) = 1
            order by ZHEADCOACH_ID
            """
        ).fetchall()
        formation_rows = con.execute(
            """
            select distinct f.ZFORMATION_ID
            from ao__ZMOFORMATION f
            where f.ZFORMATION_ID > 0
              and exists (
                select 1
                from ao__ZMOHEADCOACHESUNDERSTANDING u
                join ao__ZMOHEADCOACH h on h.ZHEADCOACH_ID = u.ZHEADCOACH_ID
                where u.ZFORMATION_ID = f.ZFORMATION_ID
                  and h.ZHEADCOACH_ID > 0
                  and coalesce(h.ZSTATUS, 1) = 1
              )
            order by f.ZFORMATION_ID
            """
        ).fetchall()
    finally:
        con.close()
    coach_ids = [int(row[0]) for row in coach_rows]
    formation_ids = [int(row[0]) for row in formation_rows]
    if not coach_ids:
        raise RuntimeError(f"no selectable headcoaches in master DB: {master_db}")
    if len(formation_ids) < formation_count:
        raise RuntimeError(f"not enough selectable formations in master DB: {master_db}")
    return {
        "headcoach_id": rng.choice(coach_ids),
        "formation_ids": rng.sample(formation_ids, formation_count),
        "headcoach_pool_size": len(coach_ids),
        "formation_pool_size": len(formation_ids),
    }


def random_ascii_name(rng: random.Random | secrets.SystemRandom) -> str:
    length = rng.randint(RANDOM_NAME_MIN_LEN, RANDOM_NAME_MAX_LEN)
    return "".join(rng.choice(RANDOM_NAME_ALPHABET) for _ in range(length))


def random_team_owner_names(
    team_name: str,
    owner_name: str,
    rng: random.Random | secrets.SystemRandom,
) -> tuple[str, str]:
    candidate_team = team_name or random_ascii_name(rng)
    candidate_owner = owner_name or random_ascii_name(rng)
    while candidate_owner == candidate_team:
        if not owner_name:
            candidate_owner = random_ascii_name(rng)
        elif not team_name:
            candidate_team = random_ascii_name(rng)
        else:
            break
    return candidate_team, candidate_owner


def session_files(args: argparse.Namespace) -> list[Path]:
    if args.creation_session_file:
        return [Path(args.creation_session_file).expanduser().resolve()]
    root = Path(args.creation_session_dir).expanduser()
    if not root.exists():
        return []
    return sorted(
        [*root.rglob("*.chlz"), *root.rglob("*.chlsx"), *root.rglob("*.chlsj")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def header_value(headers: list[dict[str, Any]], name: str) -> str:
    want = name.lower()
    for header in headers:
        if str(header.get("name") or "").lower() == want:
            return str(header.get("value") or "")
    return ""


def iter_session_headers(fp: Path):
    suffix = fp.suffix.lower()
    if suffix == ".chlz":
        try:
            with zipfile.ZipFile(fp) as zf:
                for name in sorted(n for n in zf.namelist() if n.endswith("-meta.json")):
                    try:
                        meta = json.loads(zf.read(name))
                    except Exception:
                        continue
                    headers = (((meta.get("request") or {}).get("header") or {}).get("headers") or [])
                    path = str(meta.get("path") or "")
                    yield fp, path, headers
        except Exception:
            return
    elif suffix == ".chlsx":
        try:
            root = ET.parse(fp).getroot()
        except Exception:
            return
        for tx in root.findall(".//transaction"):
            path = tx.attrib.get("path", "")
            headers_node = tx.find("./request/headers")
            headers: list[dict[str, str]] = []
            if headers_node is not None:
                for header in headers_node.findall("header"):
                    headers.append(
                        {
                            "name": (header.findtext("name") or "").strip(),
                            "value": (header.findtext("value") or "").strip(),
                        }
                    )
            yield fp, path, headers
    elif suffix == ".chlsj":
        try:
            payload = json.loads(fp.read_text())
        except Exception:
            return
        txs = payload if isinstance(payload, list) else payload.get("transactions") if isinstance(payload, dict) else []
        if not isinstance(txs, list):
            return
        for tx in txs:
            if not isinstance(tx, dict):
                continue
            request = tx.get("request") or {}
            headers = request.get("headers") or []
            path = request.get("path") or tx.get("path") or ""
            if isinstance(headers, dict):
                headers = [{"name": k, "value": v} for k, v in headers.items()]
            yield fp, str(path), headers


def creation_auth_from_sessions(files: list[Path]) -> AuthHeaders | None:
    for fp in files:
        for _source, path, headers in iter_session_headers(fp):
            gate = header_value(headers, "Websoccer-gate-key")
            if not gate.startswith(CREATION_TEAM_ID + ":"):
                continue
            user_agent = header_value(headers, "User-Agent") or UA_FALLBACK
            if "creating_team" in path or gate:
                return AuthHeaders(cookie="", gate_key=gate, user_agent=user_agent)
    return None


def post_json_form(path: str, payload: Any, auth, timeout_sec: float) -> tuple[bool, dict[str, Any] | str]:
    body = urllib.parse.urlencode({"json": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        f"https://{API_HOST}{path}",
        data=body,
        headers={
            "Accept": "*/*",
            "Websoccer-gate-key": auth.current_gate_key(),
            "User-Agent": auth.user_agent or UA_FALLBACK,
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    if auth.cookie:
        req.add_header("Cookie", auth.cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl._create_unverified_context()) as res:
            raw = res.read().decode("utf-8", errors="replace")
        return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def get_json(path: str, auth, timeout_sec: float) -> tuple[bool, dict[str, Any] | str]:
    req = urllib.request.Request(
        f"https://{API_HOST}{path}",
        headers={
            "Accept": "*/*",
            "Websoccer-gate-key": auth.current_gate_key(),
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
            raw = res.read().decode("utf-8", errors="replace")
        return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def team_creation_auth(args: argparse.Namespace, fallback_auth=None) -> AuthHeaders:
    creation_auth = creation_auth_from_sessions(session_files(args))
    if creation_auth:
        print("[INFO] creation auth source: Charles session")
        return creation_auth
    if fallback_auth:
        print("[WARN] creation auth source: local profile team auth; creating_team endpoints may return code 398")
        return fallback_auth
    raise RuntimeError("could not find creation WebSoccer auth in Charles sessions")


def check_name_with_retries(
    team_name: str,
    owner_name: str,
    owner_retries: int,
    auth: AuthHeaders,
    timeout_sec: float,
    rng: random.Random | secrets.SystemRandom,
) -> tuple[str, str, dict[str, Any]]:
    attempts = max(1, owner_retries if not team_name or not owner_name else 1)
    last_response: dict[str, Any] = {}
    for idx in range(attempts):
        candidate_team, candidate_owner = random_team_owner_names(team_name, owner_name, rng)
        payload = {"team_name": candidate_team, "owner_name": candidate_owner}
        ok, response = post_json_form(CHECK_NAME_PATH, payload, auth, timeout_sec)
        if isinstance(response, dict):
            last_response = response
        print(
            json.dumps(
                {
                    "checkName_attempt": idx + 1,
                    "team_name": candidate_team,
                    "owner_name": candidate_owner,
                    "ok": ok,
                    "response": response,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if ok and isinstance(response, dict) and response.get("code") == "000":
            return candidate_team, candidate_owner, response
        if team_name and owner_name:
            break
    raise RuntimeError(f"checkName did not return code 000 after {attempts} attempt(s): {last_response}")


def run_informal_creation(
    profile: Path,
    args: argparse.Namespace,
    auth: AuthHeaders,
    rng: random.Random | secrets.SystemRandom,
) -> dict[str, Any]:
    if args.reuse_profile_uuid:
        uuid = profile_uuid(profile)
    else:
        uuid = str(uuidlib.uuid4()).upper()
        set_profile_uuid(profile, uuid)
        print(f"[PROFILE] generated fresh UUID for new team: {uuid}")
    team_name, owner_name, check_response = check_name_with_retries(
        args.team_name,
        args.owner_name,
        args.owner_retries,
        auth,
        args.timeout_sec,
        rng,
    )
    payload = {
        "device_type": args.device_type,
        "wanted_world_id": args.wanted_world_id,
        "owner_name": owner_name,
        "prefecture_id": args.prefecture_id,
        "team_name": team_name,
        "uuid": uuid,
    }
    ok, response = post_json_form(INFORMAL_PATH, payload, auth, args.timeout_sec)
    print(json.dumps({"informal_payload": payload, "informal_ok": ok, "informal_response": response}, ensure_ascii=False, indent=2))
    if not ok or not isinstance(response, dict) or response.get("code") != "000" or not isinstance(response.get("data"), dict):
        raise RuntimeError(f"informal failed: {response}")
    data = dict(response["data"])
    update_local_profile_after_informal(profile, data)
    status_ok, status = get_json(STATUS_PATH_TMPL.format(uuid=uuid), auth, args.timeout_sec)
    print(json.dumps({"status_ok": status_ok, "status_response": status}, ensure_ascii=False, indent=2))
    return {"checkName": check_response, "informal": response, "data": data, "status": status}


def update_local_profile_after_informal(profile: Path, data: dict[str, Any]) -> None:
    db = db_path(profile)
    if not db.exists():
        raise FileNotFoundError(f"Model.sqlite not found; cannot update local profile after informal: {db}")
    league_id = int(data["league_id"])
    con = sqlite3.connect(str(db))
    try:
        row = con.execute("select Z_PK from ZMOLEAGUE where ZID=?", (league_id,)).fetchone()
        if not row:
            raise RuntimeError(f"local ZMOLEAGUE row not found for server league_id={league_id}")
        league_pk = int(row[0])
        con.execute(
            """
            update ZMOTEAMDATA
            set ZTEAM_ID=?, ZNAME=?, ZOWNER_NAME=?, ZSZN=?, ZWORLD_ID=?, ZLEAGUE=?,
                ZPREFECTURE=?, ZEMBLEM=?, ZUNIFORM=?, ZINVITE_CODE=?, ZVIEWER_ID=?, ZUUID=?
            """,
            (
                int(data["team_id"]),
                str(data["team_name"]),
                str(data["owner_name"]),
                int(data["szn"]),
                int(data["world_id"]),
                league_pk,
                int(data.get("prefecture_id") or 1),
                int(data.get("emblem_id") or 0),
                int(data.get("uniform_id") or 0),
                str(data.get("invite_code") or ""),
                str(data.get("viewer_id") or ""),
                str(data.get("uuid") or ""),
            ),
        )
        con.execute("delete from ZMOTEAMSPLAYER")
        con.execute("delete from ZMOTEAMSPLAYERRESULT")
        con.execute("delete from ZMOTEAMSHEADCOACH")
        con.commit()
    finally:
        con.close()

    path = plist_path(profile)
    if path.exists():
        with path.open("rb") as fh:
            plist = plistlib.load(fh)
        plist["teamName"] = str(data["team_name"])
        plist["ownerName"] = str(data["owner_name"])
        plist["UUID"] = str(data.get("uuid") or plist.get("UUID") or "")
        plist["hometownID"] = int(data.get("prefecture_id") or plist.get("hometownID") or 1)
        plist["viewerID"] = str(data.get("viewer_id") or plist.get("viewerID") or "")
        plist["informalCreateTeamFlg"] = True
        plist["isTutorialEnabled"] = True
        plist["tutorialStatus"] = 100
        with path.open("wb") as fh:
            plistlib.dump(plist, fh, sort_keys=False)
    print("[PROFILE] updated local team metadata after informal creation")


def parse_formation_ids(raw: str) -> list[int]:
    out = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not out:
        raise ValueError("--formation-ids must contain at least one id")
    return out


def sync_profile(profile: Path, auth, timeout_sec: float, backup: bool) -> dict[str, Any]:
    ok, payload = get_json(SYNC_PATH, auth, timeout_sec)
    if not ok or not isinstance(payload, dict) or payload.get("code") != "000":
        raise RuntimeError(f"sync failed: {payload}")
    db = db_path(profile)
    if backup:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = db.with_suffix(db.suffix + f".pre_tutorial_sync_{stamp}.bak")
        shutil.copy2(db, backup_path)
        print(f"[BACKUP] {backup_path}")
    con = sqlite3.connect(str(db))
    try:
        con.execute("begin")
        result = update_db(con, payload)
        con.commit()
        return result
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def mark_tutorial_prefs_complete(profile: Path) -> None:
    plist = plist_path(profile)
    if not plist.exists():
        print("[WARN] preferences plist not found; skipped local tutorial pref update")
        return
    commands = [
        ("tutorialStatus", "0"),
        ("isTutorialEnabled", "false"),
        ("informalCreateTeamFlg", "false"),
    ]
    for key, value in commands:
        subprocess.run(["/usr/libexec/PlistBuddy", "-c", f"Set :{key} {value}", str(plist)], check=True)
    subprocess.run(["killall", "cfprefsd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print("[PREFS] marked local tutorial flags complete")


def main() -> int:
    args = parse_args()
    profile = Path(args.profile_data).expanduser().resolve()
    rng = random.Random(args.random_seed)
    secure_rng: random.Random | secrets.SystemRandom = rng if args.random_seed is not None else secrets.SystemRandom()
    master_db = resolve_master_db(args.master_db)
    random_choices = random_initial_choices(master_db, rng)
    auth = local_auth_from_container(profile)
    creation_auth = team_creation_auth(args, auth)

    creation_result = None
    if args.create_team:
        if not args.execute:
            dry_team, dry_owner = random_team_owner_names(args.team_name, args.owner_name, secure_rng)
            dry_headcoach_id = args.headcoach_id or int(random_choices["headcoach_id"])
            dry_formation_ids = parse_formation_ids(args.formation_ids) if args.formation_ids else list(random_choices["formation_ids"])
            print(
                json.dumps(
                    {
                        "create_team_dry_run": {
                            "profile": str(profile),
                            "team_name": dry_team,
                            "owner_name_candidate": dry_owner,
                            "checkName_path": CHECK_NAME_PATH,
                            "informal_path": INFORMAL_PATH,
                            "informal_payload": {
                                "device_type": args.device_type,
                                "wanted_world_id": args.wanted_world_id,
                                "owner_name": dry_owner,
                                "prefecture_id": args.prefecture_id,
                                "team_name": dry_team,
                                "uuid": "<fresh UUID>",
                            },
                            "tutorial_selection": {
                                "player_id": args.player_id,
                                "headcoach_id": dry_headcoach_id,
                                "formation_ids": dry_formation_ids,
                                "headcoach": "override" if args.headcoach_id else "random",
                                "formation_ids_source": "override" if args.formation_ids else "random",
                                "headcoach_pool_size": random_choices["headcoach_pool_size"],
                                "formation_pool_size": random_choices["formation_pool_size"],
                            },
                            "note": "add --execute to run checkName/informal/formal/sync; formal team_id/world_id/league_id will come from informal response",
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        else:
            creation_result = run_informal_creation(profile, args, creation_auth, secure_rng)
            auth = local_auth_from_container(profile)
            if not auth:
                raise RuntimeError("could not generate normal team auth from profile after informal creation")

    meta = profile_metadata(profile)

    headcoach_id = args.headcoach_id or int(random_choices["headcoach_id"])
    formation_ids = parse_formation_ids(args.formation_ids) if args.formation_ids else list(random_choices["formation_ids"])

    payload = {
        "world_id": args.world_id or meta["world_id"],
        "formation_ids": formation_ids,
        "player_id": args.player_id,
        "headcoach_id": headcoach_id,
        "team_id": args.team_id or meta["team_id"],
        "league_id": args.league_id or meta["league_id"],
    }
    print(
        json.dumps(
            {
                "profile": str(profile),
                "current": meta,
                "selection": {
                    "master_db": str(master_db),
                    "random_seed": args.random_seed,
                    "headcoach": "override" if args.headcoach_id else "random",
                    "formation_ids": "override" if args.formation_ids else "random",
                    "headcoach_pool_size": random_choices["headcoach_pool_size"],
                    "formation_pool_size": random_choices["formation_pool_size"],
                },
                "formal_payload": payload,
                "creation": creation_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not args.execute:
        print("[DRY_RUN] add --execute to POST /creating_team/formal.json")
        return 0

    ok, response = post_json_form(FORMAL_PATH, payload, creation_auth, args.timeout_sec)
    print(json.dumps({"formal_ok": ok, "formal_response": response}, ensure_ascii=False, indent=2))
    if not ok or not isinstance(response, dict) or response.get("code") != "000":
        return 1

    if not args.no_update_prefs:
        mark_tutorial_prefs_complete(profile)

    if args.sync:
        result = sync_profile(profile, auth, args.timeout_sec, args.backup)
        print(json.dumps({"synced": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
