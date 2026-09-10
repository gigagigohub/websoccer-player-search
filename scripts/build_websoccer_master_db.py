#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import sqlite3
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable, List, Tuple


JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CODEX_ROOT = REPO_ROOT.parent
WSC_DATA = CODEX_ROOT / "wsc_data"

SKIP_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".svg",
    ".mp3",
    ".m4a",
    ".wav",
    ".ogg",
    ".mp4",
    ".mov",
    ".avi",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
}


def default_updatefile_dir() -> Path:
    root = WSC_DATA
    candidates = []
    for p in root.glob("UpdateFile_p*_*"):
        m = re.fullmatch(r"UpdateFile_p(\d+)_(\d+)", p.name)
        if p.is_dir() and m:
            candidates.append((int(m.group(2)), int(m.group(1)), p))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]
    return root / "UpdateFile_p40_322"


def cc_source_stats(path: Path) -> tuple[int, int, int]:
    if not path.exists():
        return (0, 0, 0)
    try:
        conn = sqlite3.connect(str(path))
        try:
            tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "matches" in tables:
                row = conn.execute("SELECT COALESCE(MIN(season), 0), COALESCE(MAX(season), 0), COUNT(*) FROM matches").fetchone()
            elif "cc_matches" in tables:
                row = conn.execute("SELECT COALESCE(MIN(season), 0), COALESCE(MAX(season), 0), COUNT(*) FROM cc_matches").fetchone()
            else:
                return (0, 0, 0)
            return (int(row[0] or 0), int(row[1] or 0), int(row[2] or 0))
        finally:
            conn.close()
    except sqlite3.Error:
        return (0, 0, 0)


def default_cc_db() -> Path:
    wsc_data = WSC_DATA
    candidates = [
        wsc_data / "cc_match_result.sqlite3",
        Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3",
    ]
    candidates.extend(sorted((wsc_data / "websoccer_master_db").glob("wsm_*.sqlite3")))
    ranked = []
    for path in candidates:
        min_season, max_season, count = cc_source_stats(path)
        if count > 0:
            ranked.append((max_season, count, min_season, path.stat().st_mtime, path))
    if ranked:
        ranked.sort(reverse=True)
        return ranked[0][4]
    return wsc_data / "cc_match_result.sqlite3"


def default_product_sqlite() -> Path:
    local = WSC_DATA / "app original" / "Payload" / "Webサッカー.app" / "Product.sqlite"
    if local.exists():
        return local
    return Path.home() / "Desktop" / "app original" / "Payload" / "Webサッカー.app" / "Product.sqlite"


def historical_nation_db_candidates() -> list[Path]:
    master_dir = WSC_DATA / "websoccer_master_db"
    return [
        master_dir / "wsm_2605241243.sqlite3",
        master_dir / "wsm_2605211909.sqlite3",
    ]


def default_out_db() -> Path:
    out_dir = WSC_DATA / "websoccer_master_db"
    stamp = datetime.now(JST).strftime("%y%m%d%H%M")
    out = out_dir / f"wsm_{stamp}.sqlite3"
    if not out.exists():
        return out
    stamp = datetime.now(JST).strftime("%y%m%d%H%M%S")
    return out_dir / f"wsm_{stamp}.sqlite3"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build unified WebSoccer master SQLite DB from CC DB + Product.sqlite + UpdateFile zips + manual truth."
    )
    p.add_argument(
        "--out-db",
        default=str(default_out_db()),
    )
    p.add_argument(
        "--cc-db",
        default=str(default_cc_db()),
    )
    p.add_argument(
        "--product-sqlite",
        default=str(default_product_sqlite()),
    )
    p.add_argument(
        "--updatefile-dir",
        default=str(default_updatefile_dir()),
    )
    p.add_argument(
        "--app-data-json",
        default=str(REPO_ROOT / "app" / "data.json"),
    )
    p.add_argument(
        "--coaches-data-json",
        default=str(REPO_ROOT / "app" / "coaches_data.json"),
    )
    p.add_argument("--manual-source-db", default="", help="Existing master whose correction tables are inherited")
    p.add_argument("--bootstrap-site-json", action="store_true", help="Explicit one-time legacy migration only; never used by automation")
    p.add_argument(
        "--verbose",
        action="store_true",
    )
    return p.parse_args()


def now_jst_iso() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"output DB already exists: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta_sources (
          source_key TEXT PRIMARY KEY,
          source_path TEXT,
          loaded_at TEXT NOT NULL,
          note TEXT
        );

        CREATE TABLE IF NOT EXISTS cc_matches (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          datetime TEXT,
          title TEXT,
          referee TEXT,
          stadium_id INTEGER,
          stadium_name TEXT,
          stadium_capacity INTEGER,
          audience INTEGER,
          home_score INTEGER,
          away_score INTEGER,
          pk_home_goals INTEGER,
          pk_away_goals INTEGER,
          pk_home_attempts INTEGER,
          pk_away_attempts INTEGER,
          pk_winner_side TEXT,
          access_datetime TEXT,
          file_path TEXT,
          PRIMARY KEY (season, world_id, match_id)
        );

        CREATE TABLE IF NOT EXISTS cc_teams (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          side TEXT NOT NULL,
          team_id INTEGER,
          team_name TEXT,
          uniform_id INTEGER,
          formation_id INTEGER,
          formation_name TEXT,
          headcoach_id INTEGER,
          headcoach_name TEXT,
          headcoach_pts REAL,
          goals_for INTEGER,
          goals_against INTEGER,
          result TEXT,
          PRIMARY KEY (season, world_id, match_id, side)
        );

        CREATE TABLE IF NOT EXISTS cc_players (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          side TEXT NOT NULL,
          member_order INTEGER NOT NULL,
          is_starting11 INTEGER,
          player_id INTEGER,
          player_fullname TEXT,
          player_name TEXT,
          pos_code_1_4 INTEGER,
          pts REAL,
          team_id INTEGER,
          team_name TEXT,
          formation_id INTEGER,
          formation_name TEXT,
          PRIMARY KEY (season, world_id, match_id, side, member_order)
        );

        CREATE TABLE IF NOT EXISTS cc_goals (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          goal_index INTEGER NOT NULL,
          side TEXT,
          minute INTEGER,
          scorer_player_id INTEGER,
          PRIMARY KEY (season, world_id, match_id, goal_index)
        );

        CREATE TABLE IF NOT EXISTS cc_pk_events (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          side TEXT NOT NULL,
          pk_order INTEGER NOT NULL,
          minute INTEGER NOT NULL,
          player_id INTEGER,
          goal INTEGER NOT NULL,
          PRIMARY KEY (season, world_id, match_id, side, pk_order)
        );

        CREATE INDEX IF NOT EXISTS idx_cc_pk_events_match
          ON cc_pk_events(season, world_id, match_id);

        CREATE TABLE IF NOT EXISTS app_original_tables (
          table_name TEXT PRIMARY KEY,
          row_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS updatefile_archives (
          version INTEGER PRIMARY KEY,
          zip_name TEXT NOT NULL,
          zip_path TEXT NOT NULL,
          file_size INTEGER NOT NULL,
          mtime REAL NOT NULL,
          entry_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS updatefile_files (
          version INTEGER NOT NULL,
          entry_path TEXT NOT NULL,
          ext TEXT,
          is_text INTEGER NOT NULL DEFAULT 0,
          text_content TEXT,
          blob_content BLOB,
          sha1 TEXT NOT NULL,
          byte_size INTEGER NOT NULL,
          PRIMARY KEY (version, entry_path)
        );

        CREATE TABLE IF NOT EXISTS manual_player_category (
          player_id INTEGER PRIMARY KEY,
          category TEXT NOT NULL,
          category_membership_json TEXT NOT NULL,
          retired INTEGER NOT NULL DEFAULT 0,
          retired_reason TEXT,
          is_manual INTEGER NOT NULL DEFAULT 1,
          source_file TEXT NOT NULL,
          source_note TEXT
        );

        CREATE TABLE IF NOT EXISTS manual_scout_event (
          event_id INTEGER PRIMARY KEY,
          name TEXT,
          start TEXT,
          end TEXT,
          type INTEGER,
          version INTEGER,
          notes TEXT,
          name_raw TEXT,
          name_source TEXT,
          player_count INTEGER,
          player_ids_json TEXT,
          is_manual INTEGER NOT NULL DEFAULT 0,
          source_file TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS manual_cm_event (
          event_id INTEGER PRIMARY KEY,
          name TEXT,
          start TEXT,
          end TEXT,
          mode TEXT,
          version INTEGER,
          player_count INTEGER,
          player_ids_json TEXT,
          is_manual INTEGER NOT NULL DEFAULT 0,
          source_file TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS manual_player_model (
          person_id INTEGER PRIMARY KEY,
          model_name TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_method TEXT NOT NULL DEFAULT 'manual_update',
          is_manual INTEGER NOT NULL DEFAULT 1,
          notes TEXT,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS player_person_identity (
          player_id INTEGER PRIMARY KEY,
          raw_person_id INTEGER,
          canonical_person_id INTEGER NOT NULL,
          is_override INTEGER NOT NULL DEFAULT 0,
          source_method TEXT NOT NULL DEFAULT 'canonical_from_raw',
          notes TEXT,
          source_file TEXT,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS manual_coach_obtainable (
          coach_id INTEGER NOT NULL,
          coach_name TEXT,
          formation_id INTEGER NOT NULL,
          formation_name TEXT,
          from_season INTEGER,
          is_manual INTEGER NOT NULL DEFAULT 1,
          source_file TEXT NOT NULL,
          PRIMARY KEY (coach_id, formation_id)
        );
        """
    )


def put_source(conn: sqlite3.Connection, key: str, path: Path, note: str = "") -> None:
    conn.execute(
        """
        INSERT INTO meta_sources (source_key, source_path, loaded_at, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
          source_path=excluded.source_path,
          loaded_at=excluded.loaded_at,
          note=excluded.note
        """,
        (key, str(path), now_jst_iso(), note),
    )


def import_cc_db(conn: sqlite3.Connection, cc_db: Path) -> None:
    if not cc_db.exists():
        raise FileNotFoundError(f"cc db not found: {cc_db}")
    conn.execute("ATTACH DATABASE ? AS ccsrc", (str(cc_db),))
    try:
        tables = {str(r[0]) for r in conn.execute("SELECT name FROM ccsrc.sqlite_master WHERE type='table'")}
        if "matches" in tables:
            match_table = "matches"
            team_table = "teams"
            player_table = "players"
            goal_table = "goals"
        elif "cc_matches" in tables:
            match_table = "cc_matches"
            team_table = "cc_teams"
            player_table = "cc_players"
            goal_table = "cc_goals"
        else:
            raise sqlite3.OperationalError(f"cc source has no matches/cc_matches table: {cc_db}")

        match_cols = {str(r[1]) for r in conn.execute(f"PRAGMA ccsrc.table_info({match_table})").fetchall()}
        pk_cols = [
            "pk_home_goals",
            "pk_away_goals",
            "pk_home_attempts",
            "pk_away_attempts",
            "pk_winner_side",
        ]
        if all(c in match_cols for c in pk_cols):
            conn.execute(
                """
                INSERT INTO cc_matches
                (season, world_id, match_id, datetime, title, referee,
                 stadium_id, stadium_name, stadium_capacity, audience,
                 home_score, away_score,
                 pk_home_goals, pk_away_goals, pk_home_attempts, pk_away_attempts, pk_winner_side,
                 access_datetime, file_path)
                SELECT season, world_id, match_id, datetime, title, referee,
                       stadium_id, stadium_name, stadium_capacity, audience,
                       home_score, away_score,
                       pk_home_goals, pk_away_goals, pk_home_attempts, pk_away_attempts, pk_winner_side,
                       access_datetime, file_path
                FROM ccsrc.%s
                """
                % qident(match_table)
            )
        else:
            conn.execute(
                """
                INSERT INTO cc_matches
                (season, world_id, match_id, datetime, title, referee,
                 stadium_id, stadium_name, stadium_capacity, audience,
                 home_score, away_score, access_datetime, file_path)
                SELECT season, world_id, match_id, datetime, title, referee,
                       stadium_id, stadium_name, stadium_capacity, audience,
                       home_score, away_score, access_datetime, file_path
                FROM ccsrc.%s
                """
                % qident(match_table)
            )
        conn.execute(
            """
            INSERT INTO cc_teams
            (season, world_id, match_id, side, team_id, team_name,
             uniform_id, formation_id, formation_name, headcoach_id,
             headcoach_name, headcoach_pts, goals_for, goals_against, result)
            SELECT season, world_id, match_id, side, team_id, team_name,
                   uniform_id, formation_id, formation_name, headcoach_id,
                   headcoach_name, headcoach_pts, goals_for, goals_against, result
            FROM ccsrc.%s
            """
            % qident(team_table)
        )
        conn.execute(
            """
            INSERT INTO cc_players
            (season, world_id, match_id, side, member_order, is_starting11,
             player_id, player_fullname, player_name, pos_code_1_4, pts,
             team_id, team_name, formation_id, formation_name)
            SELECT season, world_id, match_id, side, member_order, is_starting11,
                   player_id, player_fullname, player_name, pos_code_1_4, pts,
                   team_id, team_name, formation_id, formation_name
            FROM ccsrc.%s
            """
            % qident(player_table)
        )
        conn.execute(
            """
            INSERT INTO cc_goals
            (season, world_id, match_id, goal_index, side, minute, scorer_player_id)
            SELECT season, world_id, match_id, goal_index, side, minute, scorer_player_id
            FROM ccsrc.%s
            """
            % qident(goal_table)
        )
        if "cc_pk_events" in tables:
            conn.execute(
                """
                INSERT OR IGNORE INTO cc_pk_events
                (season, world_id, match_id, side, pk_order, minute, player_id, goal)
                SELECT season, world_id, match_id, side, pk_order, minute, player_id, goal
                FROM ccsrc.cc_pk_events
                """
            )
    finally:
        try:
            conn.execute("DETACH DATABASE ccsrc")
        except sqlite3.OperationalError:
            pass


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def import_app_original(conn: sqlite3.Connection, product_sqlite: Path, verbose: bool = False) -> None:
    if not product_sqlite.exists():
        raise FileNotFoundError(f"product sqlite not found: {product_sqlite}")
    conn.execute("ATTACH DATABASE ? AS aosrc", (str(product_sqlite),))
    try:
        rows = conn.execute(
            "SELECT name FROM aosrc.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for i, r in enumerate(rows, start=1):
            t = str(r["name"])
            out_t = f"ao__{t}"
            conn.execute(f"CREATE TABLE {qident(out_t)} AS SELECT * FROM aosrc.{qident(t)}")
            c = conn.execute(f"SELECT COUNT(*) FROM {qident(out_t)}").fetchone()[0]
            conn.execute(
                "INSERT INTO app_original_tables (table_name, row_count) VALUES (?, ?)",
                (t, int(c)),
            )
            if verbose and i % 20 == 0:
                print(f"[APP] copied tables={i}/{len(rows)}", flush=True)
    finally:
        try:
            conn.execute("DETACH DATABASE aosrc")
        except sqlite3.OperationalError:
            pass


def restore_historical_nations(conn: sqlite3.Connection, verbose: bool = False) -> tuple[int, Path | None]:
    tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "ao__ZMONATION" not in tables:
        return 0, None

    for source in historical_nation_db_candidates():
        if not source.exists():
            continue
        conn.execute("ATTACH DATABASE ? AS hnsrc", (str(source),))
        try:
            src_tables = {
                str(r[0])
                for r in conn.execute("SELECT name FROM hnsrc.sqlite_master WHERE type='table'")
            }
            if "ao__ZMONATION" not in src_tables:
                continue
            rows = conn.execute(
                """
                SELECT r.Z_PK, r.Z_ENT, r.Z_OPT, r.ZNATION_ID, r.ZALPHA3, r.ZNAME
                FROM hnsrc.ao__ZMONATION r
                LEFT JOIN main.ao__ZMONATION n ON n.ZNATION_ID = r.ZNATION_ID
                WHERE n.ZNATION_ID IS NULL
                ORDER BY r.ZNATION_ID
                """
            ).fetchall()
            if not rows:
                return 0, source
            conn.executemany(
                """
                INSERT INTO main.ao__ZMONATION
                (Z_PK, Z_ENT, Z_OPT, ZNATION_ID, ZALPHA3, ZNAME)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [tuple(r) for r in rows],
            )
            if verbose:
                ids = ", ".join(str(r["ZNATION_ID"]) for r in rows)
                print(f"[APP] restored historical nations from {source}: {ids}", flush=True)
            return len(rows), source
        finally:
            try:
                conn.execute("DETACH DATABASE hnsrc")
            except sqlite3.OperationalError:
                pass
    return 0, None


def _core_snapshot_sort_key(path: Path) -> tuple[int, int, str]:
    nums = [int(x) for x in re.findall(r"\d+", path.name)]
    if not nums:
        return (0, 0, path.name)
    return (nums[0], nums[-1], path.name)


def _iter_core_snapshot_payloads(core_root: Path) -> Iterable[tuple[Path, dict, dict]]:
    if not core_root.exists():
        return []
    for snap_dir in ([core_root] if list(core_root.glob("player_*.json")) else sorted(core_root.glob("update_core_data_*"), key=_core_snapshot_sort_key)):
        if not snap_dir.is_dir():
            continue
        player_files = sorted(snap_dir.glob("player_*.json"))
        param_files = sorted(snap_dir.glob("players_param_*.json"))
        for player_file in player_files:
            try:
                player_obj = json.loads(player_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            # A normal snapshot has one param file. If not, combine all param files in the directory.
            param_rows = []
            for param_file in param_files:
                try:
                    param_obj = json.loads(param_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                rows = param_obj.get("players_param") if isinstance(param_obj, dict) else []
                if isinstance(rows, list):
                    param_rows.extend([r for r in rows if isinstance(r, dict)])
            yield snap_dir, player_obj, {"code": "000", "players_param": param_rows}


def _core_player_row(player: dict) -> tuple:
    player_id = int(player.get("player_id") or 0)
    return (
        player_id,
        0,
        0,
        0,
        int(player.get("age") or 0),
        0,
        0,
        0,
        int(player.get("nation_id") or 0),
        int(player.get("person_id") or player_id or 0),
        player_id,
        0,
        int(player.get("pos_type") or 0),
        int(player.get("rarity") or 0),
        0,
        int(player.get("tall") or 0),
        int(player.get("weight") or 0),
        player_id,
        player_id,
        str(player.get("fullname") or ""),
        str(player.get("name") or ""),
        str(player.get("nameruby") or ""),
    )


def _core_info_row(player: dict) -> tuple:
    player_id = int(player.get("player_id") or 0)
    return (
        player_id,
        0,
        0,
        str(player.get("description") or ""),
        str(player.get("type") or ""),
        str(player.get("subtitle") or ""),
    )


def _core_param_row(pk: int, row: dict) -> tuple:
    r = lambda key: int(row.get(key) or 0)
    return (
        pk,
        0,
        0,
        r("cap"),
        r("ck"),
        r("cst"),
        r("fk"),
        r("inte"),
        r("pk"),
        r("player_id"),
        r("pop"),
        r("pwr"),
        r("r1"),
        r("r10"),
        r("r11"),
        r("r12"),
        r("r13"),
        r("r14"),
        r("r15"),
        r("r16"),
        r("r17"),
        r("r18"),
        r("r2"),
        r("r3"),
        r("r4"),
        r("r5"),
        r("r6"),
        r("r7"),
        r("r8"),
        r("r9"),
        r("rgh"),
        r("sen"),
        r("spd"),
        r("stdp"),
        r("stm"),
        r("szn_no"),
        r("tec"),
        r("tmp"),
    )


def import_update_core_snapshots(conn: sqlite3.Connection, core_root: Path, verbose: bool = False) -> tuple[int, int, Path | None]:
    tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"ao__ZMOPLAYER", "ao__ZMOPLAYERSINFO", "ao__ZMOPLAYERSPARAM"}
    if not required <= tables:
        return (0, 0, None)

    existing_players = {
        int(r[0])
        for r in conn.execute("SELECT ZPLAYER_ID FROM ao__ZMOPLAYER WHERE ZPLAYER_ID IS NOT NULL")
    }
    existing_infos = {
        int(r[0])
        for r in conn.execute("SELECT Z_PK FROM ao__ZMOPLAYERSINFO WHERE Z_PK IS NOT NULL")
    }
    existing_params = {
        (int(r[0]), int(r[1]))
        for r in conn.execute(
            "SELECT ZPLAYER_ID, ZSZN_NO FROM ao__ZMOPLAYERSPARAM WHERE ZPLAYER_ID IS NOT NULL AND ZSZN_NO IS NOT NULL"
        )
    }
    next_param_pk = int(conn.execute("SELECT COALESCE(MAX(Z_PK), 0) FROM ao__ZMOPLAYERSPARAM").fetchone()[0] or 0) + 1
    player_rows = []
    info_rows = []
    param_rows = []
    used_root = None

    for snap_dir, player_obj, param_obj in _iter_core_snapshot_payloads(core_root):
        players = player_obj.get("players") if isinstance(player_obj, dict) and player_obj.get("code") == "000" else []
        params = param_obj.get("players_param") if isinstance(param_obj, dict) else []
        if not isinstance(players, list):
            players = []
        if not isinstance(params, list):
            params = []
        if players or params:
            used_root = core_root
        for player in [p for p in players if isinstance(p, dict)]:
            player_id = int(player.get("player_id") or 0)
            if player_id <= 0:
                continue
            if player_id not in existing_players:
                player_rows.append(_core_player_row(player))
                existing_players.add(player_id)
            if player_id not in existing_infos:
                info_rows.append(_core_info_row(player))
                existing_infos.add(player_id)
        for param in [p for p in params if isinstance(p, dict)]:
            player_id = int(param.get("player_id") or 0)
            szn_no = int(param.get("szn_no") or 0)
            if player_id <= 0 or (player_id, szn_no) in existing_params:
                continue
            param_rows.append(_core_param_row(next_param_pk, param))
            next_param_pk += 1
            existing_params.add((player_id, szn_no))

    if player_rows:
        conn.executemany(
            """
            INSERT INTO ao__ZMOPLAYER
            (Z_PK, Z_ENT, Z_OPT, ZACT_SZN, ZAGE, ZBASE_LINE, ZBASE_POS, ZFLG_LISTUP,
             ZNATION_ID, ZPERSON_ID, ZPLAYER_ID, ZPOS_ROLE, ZPOS_TYPE, ZRARITY, ZSTATUS,
             ZTALL, ZWEIGHT, ZINFO, ZPARAM, ZFULLNAME, ZNAME, ZNAMERUBY)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            player_rows,
        )
    if info_rows:
        conn.executemany(
            """
            INSERT INTO ao__ZMOPLAYERSINFO
            (Z_PK, Z_ENT, Z_OPT, ZDESCRIPTION_TEXT, ZPLAY_TYPE, ZSUBTITLE)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            info_rows,
        )
    if param_rows:
        conn.executemany(
            """
            INSERT INTO ao__ZMOPLAYERSPARAM
            (Z_PK, Z_ENT, Z_OPT, ZCAP, ZCK, ZCST, ZFK, ZINTE, ZPK, ZPLAYER_ID,
             ZPOP, ZPWR, ZR1, ZR10, ZR11, ZR12, ZR13, ZR14, ZR15, ZR16, ZR17, ZR18,
             ZR2, ZR3, ZR4, ZR5, ZR6, ZR7, ZR8, ZR9, ZRGH, ZSEN, ZSPD, ZSTDP,
             ZSTM, ZSZN_NO, ZTEC, ZTMP)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            param_rows,
        )
    if verbose and (player_rows or param_rows):
        print(
            f"[APP] imported update_core_data snapshots: players={len(player_rows)} params={len(param_rows)}",
            flush=True,
        )
    return (len(player_rows), len(param_rows), used_root)


def restore_historical_player_rows(conn: sqlite3.Connection, verbose: bool = False) -> tuple[int, int, Path | None]:
    tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"ao__ZMOPLAYER", "ao__ZMOPLAYERSINFO", "ao__ZMOPLAYERSPARAM"}
    if not required <= tables:
        return (0, 0, None)

    for source in historical_nation_db_candidates():
        if not source.exists():
            continue
        conn.execute("ATTACH DATABASE ? AS hpsrc", (str(source),))
        try:
            src_tables = {
                str(r[0])
                for r in conn.execute("SELECT name FROM hpsrc.sqlite_master WHERE type='table'")
            }
            if not required <= src_tables:
                continue
            player_ids = [
                int(r[0])
                for r in conn.execute(
                    """
                    SELECT s.ZPLAYER_ID
                    FROM hpsrc.ao__ZMOPLAYER s
                    LEFT JOIN main.ao__ZMOPLAYER m ON m.ZPLAYER_ID = s.ZPLAYER_ID
                    WHERE m.ZPLAYER_ID IS NULL
                    ORDER BY s.ZPLAYER_ID
                    """
                ).fetchall()
            ]
            if not player_ids:
                return (0, 0, source)
            placeholders = ",".join("?" for _ in player_ids)
            conn.execute(
                f"INSERT INTO main.ao__ZMOPLAYER SELECT * FROM hpsrc.ao__ZMOPLAYER WHERE ZPLAYER_ID IN ({placeholders})",
                player_ids,
            )
            conn.execute(
                f"INSERT INTO main.ao__ZMOPLAYERSINFO SELECT * FROM hpsrc.ao__ZMOPLAYERSINFO WHERE Z_PK IN ({placeholders})",
                player_ids,
            )
            existing_params = {
                (int(r[0]), int(r[1]))
                for r in conn.execute(
                    "SELECT ZPLAYER_ID, ZSZN_NO FROM main.ao__ZMOPLAYERSPARAM WHERE ZPLAYER_ID IS NOT NULL AND ZSZN_NO IS NOT NULL"
                )
            }
            rows = conn.execute(
                f"SELECT * FROM hpsrc.ao__ZMOPLAYERSPARAM WHERE ZPLAYER_ID IN ({placeholders}) ORDER BY ZPLAYER_ID, ZSZN_NO",
                player_ids,
            ).fetchall()
            columns = [str(r[1]) for r in conn.execute("PRAGMA hpsrc.table_info(ao__ZMOPLAYERSPARAM)").fetchall()]
            param_rows = []
            for row in rows:
                d = dict(zip(columns, row))
                key = (int(d["ZPLAYER_ID"]), int(d["ZSZN_NO"]))
                if key in existing_params:
                    continue
                param_rows.append(tuple(row))
                existing_params.add(key)
            if param_rows:
                qmarks = ",".join("?" for _ in columns)
                conn.executemany(
                    f"INSERT INTO main.ao__ZMOPLAYERSPARAM ({','.join(qident(c) for c in columns)}) VALUES ({qmarks})",
                    param_rows,
                )
            if verbose:
                print(
                    f"[APP] restored historical player rows from {source}: players={len(player_ids)} params={len(param_rows)}",
                    flush=True,
                )
            return (len(player_ids), len(param_rows), source)
        finally:
            try:
                conn.execute("DETACH DATABASE hpsrc")
            except sqlite3.OperationalError:
                pass
    return (0, 0, None)


def iter_update_zips(update_dir: Path) -> Iterable[Tuple[int, Path]]:
    for p in sorted(update_dir.glob("p*.zip"), key=lambda x: int(re.sub(r"[^0-9]", "", x.stem) or "0")):
        m = re.match(r"p(\d+)$", p.stem)
        if not m:
            continue
        yield int(m.group(1)), p


def is_non_image_entry(name: str) -> bool:
    lower = name.lower()
    if lower.endswith("/"):
        return False
    ext = Path(lower).suffix
    if ext in SKIP_EXT:
        return False
    if "/img/" in lower or "/images/" in lower:
        return False
    return True


def decode_text(data: bytes) -> Tuple[int, str]:
    # return (is_text, text_content)
    for enc in ("utf-8", "utf-8-sig", "cp932", "shift_jis", "latin-1"):
        try:
            return 1, data.decode(enc)
        except Exception:
            continue
    return 0, ""


def import_updatefiles(conn: sqlite3.Connection, update_dir: Path, verbose: bool = False) -> None:
    if not update_dir.exists():
        raise FileNotFoundError(f"update dir not found: {update_dir}")
    zips = list(iter_update_zips(update_dir))
    for i, (ver, zp) in enumerate(zips, start=1):
        st = zp.stat()
        with zipfile.ZipFile(zp, "r") as zf:
            infos = [x for x in zf.infolist() if is_non_image_entry(x.filename)]
            conn.execute(
                """
                INSERT INTO updatefile_archives
                (version, zip_name, zip_path, file_size, mtime, entry_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ver, zp.name, str(zp), int(st.st_size), float(st.st_mtime), len(infos)),
            )
            for inf in infos:
                raw = zf.read(inf.filename)
                sha1 = hashlib.sha1(raw).hexdigest()
                is_text, txt = decode_text(raw)
                ext = Path(inf.filename).suffix.lower()
                conn.execute(
                    """
                    INSERT INTO updatefile_files
                    (version, entry_path, ext, is_text, text_content, blob_content, sha1, byte_size)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ver,
                        inf.filename,
                        ext,
                        is_text,
                        txt if is_text else None,
                        raw,
                        sha1,
                        len(raw),
                    ),
                )
        conn.commit()
        if verbose and i % 20 == 0:
            print(f"[UPD] archives={i}/{len(zips)}", flush=True)


def _to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def import_manual_truth(
    conn: sqlite3.Connection,
    app_data_json: Path,
    coaches_data_json: Path,
) -> None:
    if not app_data_json.exists():
        raise FileNotFoundError(f"app data json not found: {app_data_json}")
    if not coaches_data_json.exists():
        raise FileNotFoundError(f"coaches data json not found: {coaches_data_json}")

    app = json.loads(app_data_json.read_text(encoding="utf-8"))
    coaches = json.loads(coaches_data_json.read_text(encoding="utf-8"))

    players = app.get("players") or []
    scout_history_names = {}
    for p in players:
        for h in p.get("scoutHistory") or []:
            try:
                event_id = int(h.get("eventId") or 0)
            except Exception:
                continue
            name = str(h.get("name") or "").strip()
            if event_id > 0 and name and event_id not in scout_history_names:
                scout_history_names[event_id] = name

    model_rows = {}
    for p in players:
        pid = int(p.get("id") or 0)
        if pid <= 0:
            continue
        cat = str(p.get("category") or "NR")
        membership = p.get("categoryMembership") or [cat]
        retired = 1 if p.get("retired") else 0
        retired_reason = str(p.get("retiredReason") or "")
        conn.execute(
            """
            INSERT INTO manual_player_category
            (player_id, category, category_membership_json, retired, retired_reason, is_manual, source_file, source_note)
            VALUES (?, ?, ?, ?, ?, 1, ?, 'category treated as manual truth')
            """,
            (pid, cat, _to_json(membership), retired, retired_reason, str(app_data_json)),
        )

        raw_person_id = int(p.get("personIdRaw") or p.get("personId") or 0)
        canonical_person_id = int(p.get("personId") or raw_person_id or 0)
        if canonical_person_id <= 0:
            canonical_person_id = raw_person_id if raw_person_id > 0 else pid
        is_override = 1 if p.get("personIdManualOverride") else 0
        if raw_person_id != canonical_person_id:
            is_override = 1
        source_method = "manual_canonical_person_id" if is_override else "canonical_from_raw"
        conn.execute(
            """
            INSERT INTO player_person_identity
              (player_id, raw_person_id, canonical_person_id, is_override, source_method, notes, source_file, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pid,
                raw_person_id if raw_person_id > 0 else None,
                canonical_person_id,
                is_override,
                source_method,
                "imported from site data person identity",
                str(app_data_json),
                now_jst_iso(),
            ),
        )

        model_name = str(p.get("modelPlayer") or "")
        model_source_method = str(p.get("modelPlayerSourceMethod") or "")
        model_notes = str(p.get("modelPlayerSourceNote") or "")
        model_manual = 1 if p.get("modelPlayerManual") else 0
        if model_name or model_source_method or model_notes or model_manual:
            model_rows[canonical_person_id] = (
                canonical_person_id,
                model_name,
                str(p.get("url") or ""),
                model_source_method or "manual_update",
                model_manual,
                model_notes,
                now_jst_iso(),
            )

    for row in sorted(model_rows.values(), key=lambda r: r[0]):
        conn.execute(
            """
            INSERT OR REPLACE INTO manual_player_model
            (person_id, model_name, source_url, source_method, is_manual, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )

    for s in app.get("scouts") or []:
        event_id = int(s.get("eventId") or 0)
        if event_id <= 0:
            continue
        recovered_name = scout_history_names.get(event_id, "")
        name = str(s.get("name") or recovered_name or "").strip()
        name_source = str(s.get("nameSource") or ("player_scout_history" if recovered_name else ""))
        is_manual = 1 if name_source in {
            "manual",
            "manual_fill",
            "manual_override",
            "manual_from_shop_button",
            "player_scout_history",
        } else 0
        conn.execute(
            """
            INSERT INTO manual_scout_event
            (event_id, name, start, end, type, version, notes, name_raw, name_source,
             player_count, player_ids_json, is_manual, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                name,
                s.get("start"),
                s.get("end"),
                int(s.get("type") or 0),
                int(s.get("version") or 0),
                s.get("notes"),
                s.get("nameRaw"),
                name_source,
                int(s.get("playerCount") or 0),
                _to_json(s.get("playerIds") or []),
                is_manual,
                str(app_data_json),
            ),
        )

    for c in app.get("cmEvents") or []:
        event_id = int(c.get("eventId") or 0)
        if event_id <= 0:
            continue
        conn.execute(
            """
            INSERT INTO manual_cm_event
            (event_id, name, start, end, mode, version, player_count, player_ids_json, is_manual, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                event_id,
                c.get("name"),
                c.get("start"),
                c.get("end"),
                c.get("mode"),
                int(c.get("version") or 0),
                int(c.get("playerCount") or 0),
                _to_json(c.get("playerIds") or []),
                str(app_data_json),
            ),
        )

    # Coaches obtainable: treat as manual truth per your operation policy.
    for c in coaches.get("coaches") or []:
        coach_id = int(c.get("id") or 0)
        coach_name = c.get("name") or ""
        for f in c.get("obtainable") or []:
            fid = int(f.get("formationId") or 0)
            if fid <= 0:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO manual_coach_obtainable
                (coach_id, coach_name, formation_id, formation_name, from_season, is_manual, source_file)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    coach_id,
                    coach_name,
                    fid,
                    f.get("formationName") or "",
                    int(f.get("fromSeason") or 1),
                    str(coaches_data_json),
                ),
            )


def player_truth_integrity(conn: sqlite3.Connection) -> dict[str, object]:
    core_ids = {
        int(row[0])
        for row in conn.execute("SELECT ZPLAYER_ID FROM ao__ZMOPLAYER WHERE ZPLAYER_ID > 0")
    }
    identity_ids = {
        int(row[0])
        for row in conn.execute("SELECT player_id FROM player_person_identity WHERE player_id > 0")
    }
    category_ids = {
        int(row[0])
        for row in conn.execute("SELECT player_id FROM manual_player_category WHERE player_id > 0")
    }
    missing_identity = sorted(core_ids - identity_ids)
    missing_category = sorted(core_ids - category_ids)
    return {
        "ok": not missing_identity and not missing_category,
        "corePlayers": len(core_ids),
        "personIdentity": len(identity_ids),
        "manualCategory": len(category_ids),
        "missingIdentity": missing_identity,
        "missingCategory": missing_category,
    }


def require_player_truth_integrity(conn: sqlite3.Connection) -> dict[str, object]:
    status = player_truth_integrity(conn)
    if status["ok"]:
        return status
    identity_preview = ", ".join(str(v) for v in status["missingIdentity"][:20])
    category_preview = ", ".join(str(v) for v in status["missingCategory"][:20])
    raise RuntimeError(
        "WSM player truth is incomplete: "
        f"core={status['corePlayers']} identity={status['personIdentity']} category={status['manualCategory']}; "
        f"missing identity={len(status['missingIdentity'])} [{identity_preview}]; "
        f"missing category={len(status['missingCategory'])} [{category_preview}]"
    )


def summarize(conn: sqlite3.Connection) -> List[str]:
    out: List[str] = []
    out.append(
        "cc_matches="
        + str(conn.execute("SELECT COUNT(*) FROM cc_matches").fetchone()[0])
        + " cc_teams="
        + str(conn.execute("SELECT COUNT(*) FROM cc_teams").fetchone()[0])
        + " cc_players="
        + str(conn.execute("SELECT COUNT(*) FROM cc_players").fetchone()[0])
        + " cc_goals="
        + str(conn.execute("SELECT COUNT(*) FROM cc_goals").fetchone()[0])
    )
    out.append(
        "app_original_tables="
        + str(conn.execute("SELECT COUNT(*) FROM app_original_tables").fetchone()[0])
        + " ao__ZMONATION="
        + str(conn.execute("SELECT COUNT(*) FROM ao__ZMONATION").fetchone()[0])
        + " ao__ZMOPLAYER="
        + str(conn.execute("SELECT COUNT(*) FROM ao__ZMOPLAYER").fetchone()[0])
        + " ao__ZMOPLAYERSPARAM="
        + str(conn.execute("SELECT COUNT(*) FROM ao__ZMOPLAYERSPARAM").fetchone()[0])
    )
    out.append(
        "updatefile_archives="
        + str(conn.execute("SELECT COUNT(*) FROM updatefile_archives").fetchone()[0])
        + " updatefile_files="
        + str(conn.execute("SELECT COUNT(*) FROM updatefile_files").fetchone()[0])
    )
    out.append(
        "manual_player_category="
        + str(conn.execute("SELECT COUNT(*) FROM manual_player_category").fetchone()[0])
        + " player_person_identity="
        + str(conn.execute("SELECT COUNT(*) FROM player_person_identity").fetchone()[0])
        + " manual_player_model="
        + str(conn.execute("SELECT COUNT(*) FROM manual_player_model").fetchone()[0])
        + " manual_scout_event="
        + str(conn.execute("SELECT COUNT(*) FROM manual_scout_event").fetchone()[0])
        + " manual_cm_event="
        + str(conn.execute("SELECT COUNT(*) FROM manual_cm_event").fetchone()[0])
        + " manual_coach_obtainable="
        + str(conn.execute("SELECT COUNT(*) FROM manual_coach_obtainable").fetchone()[0])
    )
    return out


def _main() -> int:
    args = parse_args()
    out_db = Path(args.out_db).expanduser().resolve()
    cc_db = Path(args.cc_db).expanduser().resolve()
    product = Path(args.product_sqlite).expanduser().resolve()
    update_dir = Path(args.updatefile_dir).expanduser().resolve()
    app_data = Path(args.app_data_json).expanduser().resolve()
    coaches_data = Path(args.coaches_data_json).expanduser().resolve()

    if out_db.exists():
        raise FileExistsError(out_db)
    from master_truth import inherit, ensure_player_truth, ingest_events
    if args.manual_source_db:
        manual_source = Path(args.manual_source_db).expanduser().resolve()
    else:
        from update_wsm_cc_from_json import latest_wsm
        manual_source = latest_wsm(WSC_DATA / "websoccer_master_db") if not args.bootstrap_site_json else None
    staging = out_db.with_suffix('.building')
    if staging.exists():
        raise FileExistsError(staging)
    conn = connect(staging)
    try:
        init_schema(conn)
        conn.commit()
        import_cc_db(conn, cc_db)
        put_source(conn, "cc_db", cc_db, "copied from incremental cc db")
        conn.commit()
        import_app_original(conn, product, verbose=args.verbose)
        from formation_core_data import import_into_master
        import_into_master(conn)
        put_source(conn, "app_original_product_sqlite", product, "all non-image app original tables copied as ao__*")
        restored_nations, restored_source = restore_historical_nations(conn, verbose=args.verbose)
        if restored_source is not None:
            put_source(
                conn,
                "historical_nation_restore",
                restored_source,
                f"restored missing ao__ZMONATION rows from known-good WSM; inserted={restored_nations}",
            )
        core_players, core_params, core_source = import_update_core_snapshots(conn, WSC_DATA, verbose=args.verbose)
        from master_truth import refresh_core_values
        refresh_core_values(conn, WSC_DATA)
        if core_source is not None:
            put_source(
                conn,
                "update_core_data_snapshots",
                core_source,
                f"imported missing ao__ player rows from saved update_core_data snapshots; players={core_players}; params={core_params}",
            )
        hist_players, hist_params, hist_source = restore_historical_player_rows(conn, verbose=args.verbose)
        if hist_source is not None and (hist_players or hist_params):
            put_source(
                conn,
                "historical_player_restore",
                hist_source,
                f"restored missing ao__ player rows from known-good WSM; players={hist_players}; params={hist_params}",
            )
        conn.commit()
        import_updatefiles(conn, update_dir, verbose=args.verbose)
        put_source(conn, "updatefile_archives", update_dir, "all non-image file entries in UpdateFile archives")
        conn.commit()
        if args.bootstrap_site_json:
            import_manual_truth(conn, app_data, coaches_data)
            from master_truth import init_extra
            init_extra(conn)
            put_source(conn, 'legacy_bootstrap', app_data, 'explicit one-time migration')
        else:
            inherit(conn, manual_source)
            put_source(conn, 'master_corrections', manual_source, 'master-owned correction tables inherited')
        ensure_player_truth(conn)
        ingest_events(conn, update_dir)
        integrity = require_player_truth_integrity(conn)
        conn.commit()
        print(f"[DONE] wrote unified db: {out_db}")
        print(f"[DONE] player truth integrity: {integrity}")
        for line in summarize(conn):
            print("[SUMMARY]", line)
    finally:
        conn.close()
    with sqlite3.connect(staging) as finalized:
        finalized.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finalized.execute("PRAGMA journal_mode=DELETE")
    finalized.close()
    staging.replace(out_db)
    return 0


def main() -> int:
    from master_truth import writer_lock
    with writer_lock(WSC_DATA / 'websoccer_master_db'):
        return _main()


if __name__ == "__main__":
    raise SystemExit(main())
