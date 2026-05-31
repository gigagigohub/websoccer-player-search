#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from fetch_cc_all_worlds_completed import local_auth_from_container, request_json


SYNC_PATH = "/sync/all.json"

ENTITY = {
    "ZMOEMBLEMALBUM": (2, "MOEmblemAlbum"),
    "ZMOFORMATIONALBUM": (4, "MOFormationAlbum"),
    "ZMOHEADCOACHALBUM": (9, "MOHeadcoachAlbum"),
    "ZMOPLAYERALBUM": (16, "MOPlayerAlbum"),
    "ZMOSTADIUMALBUM": (21, "MOStadiumAlbum"),
    "ZMOTEAMSHEADCOACH": (25, "MOTeamsHeadcoach"),
    "ZMOTEAMSPLAYER": (26, "MOTeamsPlayer"),
    "ZMOTEAMSPLAYERRESULT": (27, "MOTeamsPlayerResult"),
    "ZMOUNIFORMALBUM": (30, "MOUniformAlbum"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch /sync/all.json and update a stored WebSoccer Mac profile DB.")
    p.add_argument("--profile-data", required=True, help="Stored or active Data directory containing Documents/Model/Model.sqlite.")
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument("--dry-run", action="store_true", help="Fetch and report only; do not change the DB.")
    p.add_argument("--backup", action="store_true", help="Copy Model.sqlite to .pre_api_sync_<stamp>.bak before writing.")
    return p.parse_args()


def dict_row(con: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    con.row_factory = sqlite3.Row
    row = con.execute(sql, params).fetchone()
    return dict(row) if row else None


def entity_id(table: str) -> int:
    return ENTITY[table][0]


def pk_name(table: str) -> str:
    return ENTITY[table][1]


def update_primary_key(con: sqlite3.Connection, table: str, max_pk: int) -> None:
    ent, name = ENTITY[table]
    con.execute("update Z_PRIMARYKEY set Z_MAX=? where Z_ENT=? and Z_NAME=?", (max_pk, ent, name))


def pk_by_id(con: sqlite3.Connection, table: str, id_col: str, value: int) -> int:
    row = con.execute(f"select Z_PK from {table} where {id_col}=?", (value,)).fetchone()
    if not row:
        raise RuntimeError(f"missing {table}.{id_col}={value}")
    return int(row[0])


def player_param_pk(con: sqlite3.Connection, player_id: int, season_no: int) -> int:
    row = con.execute(
        "select Z_PK from ZMOPLAYERSPARAM where ZPLAYER_ID=? and ZSZN_NO=?",
        (player_id, season_no),
    ).fetchone()
    if not row:
        raise RuntimeError(f"missing ZMOPLAYERSPARAM player_id={player_id} season_no={season_no}")
    return int(row[0])


def replace_team_players(con: sqlite3.Connection, payload: dict, team_season: int) -> None:
    players = list((payload.get("team_data") or {}).get("players") or [])
    result_ent = entity_id("ZMOTEAMSPLAYERRESULT")
    player_ent = entity_id("ZMOTEAMSPLAYER")
    con.execute("delete from ZMOTEAMSPLAYER")
    con.execute("delete from ZMOTEAMSPLAYERRESULT")
    for idx, player in enumerate(players, start=1):
        pid = int(player["id"])
        acquired_season = int(player["szn"])
        season_no = max(0, team_season - acquired_season)
        result_pk = idx
        con.execute(
            """
            insert into ZMOTEAMSPLAYERRESULT
              (Z_PK, Z_ENT, Z_OPT, ZAPPS, ZASSISTS, ZEVAL_PTS, ZGOALS, ZREDS, ZYELLOWS)
            values (?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_pk,
                result_ent,
                int(player.get("apps") or 0),
                int(player.get("assists") or 0),
                int(player.get("eval_pts") or 0),
                int(player.get("goals") or 0),
                int(player.get("reds") or 0),
                int(player.get("yellows") or 0),
            ),
        )
        con.execute(
            """
            insert into ZMOTEAMSPLAYER
              (Z_PK, Z_ENT, Z_OPT, ZGET_SEASON, ZPLAYER_NO, ZPOS_NO, ZPLAYER, ZPLAYER_PARAM, ZRESULT, Z23PLAYERS, Z_FOK_23PLAYERS)
            values (?, ?, 1, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                idx,
                player_ent,
                acquired_season,
                idx,
                int(player.get("pos") or 0),
                pk_by_id(con, "ZMOPLAYER", "ZPLAYER_ID", pid),
                player_param_pk(con, pid, season_no),
                result_pk,
            ),
        )
    update_primary_key(con, "ZMOTEAMSPLAYER", len(players))
    update_primary_key(con, "ZMOTEAMSPLAYERRESULT", len(players))


def replace_team_headcoach(con: sqlite3.Connection, payload: dict) -> None:
    headcoach = (payload.get("team_data") or {}).get("headcoach") or {}
    if not headcoach:
        con.execute("delete from ZMOTEAMSHEADCOACH")
        update_primary_key(con, "ZMOTEAMSHEADCOACH", 0)
        return
    con.execute("delete from ZMOTEAMSHEADCOACH")
    con.execute(
        """
        insert into ZMOTEAMSHEADCOACH
          (Z_PK, Z_ENT, Z_OPT, ZGET_SEASON, ZHEADCOACH, ZRATING)
        values (1, ?, 1, ?, ?, ?)
        """,
        (
            entity_id("ZMOTEAMSHEADCOACH"),
            int(headcoach.get("szn") or 0),
            pk_by_id(con, "ZMOHEADCOACH", "ZHEADCOACH_ID", int(headcoach["id"])),
            str(headcoach.get("Rt") or ""),
        ),
    )
    update_primary_key(con, "ZMOTEAMSHEADCOACH", 1)


def replace_simple_album(con: sqlite3.Connection, table: str, rows: list[dict], id_col: str, payload_id: str, count_col: str = "ZCNT", payload_count: str = "cnt") -> None:
    ent = entity_id(table)
    con.execute(f"delete from {table}")
    for idx, row in enumerate(rows, start=1):
        con.execute(
            f"insert into {table} (Z_PK, Z_ENT, Z_OPT, {count_col}, {id_col}) values (?, ?, 1, ?, ?)",
            (idx, ent, int(row.get(payload_count) or 0), int(row[payload_id])),
        )
    update_primary_key(con, table, len(rows))


def replace_formation_album(con: sqlite3.Connection, rows: list[dict]) -> None:
    table = "ZMOFORMATIONALBUM"
    con.execute(f"delete from {table}")
    ent = entity_id(table)
    for idx, row in enumerate(rows, start=1):
        con.execute(
            """
            insert into ZMOFORMATIONALBUM
              (Z_PK, Z_ENT, Z_OPT, ZCONCEDED, ZDRAWS, ZEVAL_PTS, ZFORMATION_ID, ZGOALS, ZLOSES, ZWINS)
            values (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idx,
                ent,
                int(row.get("conceded") or 0),
                int(row.get("draws") or 0),
                int(row.get("eval_pts") or 0),
                int(row["formation_id"]),
                int(row.get("goals") or 0),
                int(row.get("loses") or 0),
                int(row.get("wins") or 0),
            ),
        )
    update_primary_key(con, table, len(rows))


def replace_stadium_album(con: sqlite3.Connection, rows: list[dict]) -> None:
    table = "ZMOSTADIUMALBUM"
    con.execute(f"delete from {table}")
    ent = entity_id(table)
    for idx, row in enumerate(rows, start=1):
        con.execute(
            "insert into ZMOSTADIUMALBUM (Z_PK, Z_ENT, Z_OPT, ZSTADIUM_ID, ZUSE_CNT) values (?, ?, 1, ?, ?)",
            (idx, ent, int(row["stadium_id"]), int(row.get("use_cnt") or 0)),
        )
    update_primary_key(con, table, len(rows))


def update_db(con: sqlite3.Connection, payload: dict) -> dict:
    team = payload.get("team_data") or {}
    season = int(payload["season"])
    league_pk = pk_by_id(con, "ZMOLEAGUE", "ZID", int(payload["league"]))
    before = dict_row(con, "select ZTEAM_ID, ZNAME, ZOWNER_NAME, ZSZN, ZWORLD_ID, ZLEAGUE from ZMOTEAMDATA")
    con.execute(
        """
        update ZMOTEAMDATA
        set ZCAP_PID=?, ZCK_PID=?, ZFK_PID=?, ZPK_PID=?,
            ZSZN=?, ZTACTICS_ID=?, ZWORLD_ID=?, ZLEAGUE=?,
            ZEMBLEM=?, ZFORMATION=?, ZSTADIUM=?, ZUNIFORM=?,
            ZCOMMENT=?, ZNAME=?
        """,
        (
            int(team.get("cap_pid") or 0),
            int(team.get("ck_pid") or 0),
            int(team.get("fk_pid") or 0),
            int(team.get("pk_pid") or 0),
            season,
            int(team.get("tid") or 0),
            int(payload["world"]),
            league_pk,
            int(payload.get("emblem") or 0),
            int(team.get("fid") or payload.get("formation") or 0),
            int(payload.get("stadium") or 0),
            int(payload.get("uniform") or 0),
            str(payload.get("comment") or ""),
            str(payload.get("name") or ""),
        ),
    )
    con.execute(
        "update ZMOTEAMFUNDS set ZBONUS=?, ZGOLD=?, ZPOINT=?",
        (int(payload.get("B") or 0), int(payload.get("G") or 0), int(payload.get("P") or 0)),
    )
    replace_team_players(con, payload, season)
    replace_team_headcoach(con, payload)
    collections = payload.get("collections") or {}
    replace_simple_album(con, "ZMOEMBLEMALBUM", collections.get("emblems") or [], "ZEMBLEM_ID", "emblem_id")
    replace_simple_album(con, "ZMOUNIFORMALBUM", collections.get("uniforms") or [], "ZUNIFORM_ID", "uniform_id")
    replace_simple_album(con, "ZMOPLAYERALBUM", collections.get("players") or [], "ZPLAYER_ID", "player_id")
    replace_simple_album(con, "ZMOHEADCOACHALBUM", collections.get("headcoaches") or [], "ZHEADCOACH_ID", "headcoach_id")
    replace_formation_album(con, collections.get("formations") or [])
    replace_stadium_album(con, collections.get("stadiums") or [])
    after = dict_row(con, "select ZTEAM_ID, ZNAME, ZOWNER_NAME, ZSZN, ZWORLD_ID, ZLEAGUE from ZMOTEAMDATA")
    return {"before": before, "after": after, "players": len(team.get("players") or [])}


def main() -> int:
    args = parse_args()
    profile = Path(args.profile_data).expanduser().resolve()
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        raise FileNotFoundError(f"Model.sqlite not found: {db}")

    auth = local_auth_from_container(profile)
    if not auth:
        raise RuntimeError("could not generate auth from profile data")
    ok, payload = request_json(SYNC_PATH, auth, args.timeout_sec)
    if not ok or not isinstance(payload, dict) or payload.get("code") != "000":
        raise RuntimeError(f"sync failed: {payload}")

    safe = {k: payload.get(k) for k in ["code", "world", "season", "name", "league", "emblem", "stadium", "uniform", "P", "B", "G"]}
    safe["players"] = len((payload.get("team_data") or {}).get("players") or [])
    safe["headcoach"] = ((payload.get("team_data") or {}).get("headcoach") or {}).get("id")
    print(json.dumps({"fetched": safe}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0

    if args.backup:
        backup = db.with_suffix(db.suffix + ".pre_api_sync.bak")
        if backup.exists():
            backup = db.with_suffix(db.suffix + f".pre_api_sync_{backup.stat().st_mtime_ns}.bak")
        shutil.copy2(db, backup)
        print(f"[BACKUP] {backup}")

    con = sqlite3.connect(str(db))
    try:
        con.execute("begin")
        summary = update_db(con, payload)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    print(json.dumps({"updated": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
