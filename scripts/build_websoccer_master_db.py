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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build unified WebSoccer master SQLite DB from CC DB + Product.sqlite + UpdateFile zips + manual truth."
    )
    p.add_argument(
        "--out-db",
        default=str(
            Path.home()
            / "Desktop"
            / "websoccer_master_db"
            / f"wsm_{datetime.now(JST).strftime('%y%m%d%H%M')}.sqlite3"
        ),
    )
    p.add_argument(
        "--cc-db",
        default=str(Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3"),
    )
    p.add_argument(
        "--product-sqlite",
        default=str(Path.home() / "Desktop" / "app original" / "Payload" / "Webサッカー.app" / "Product.sqlite"),
    )
    p.add_argument(
        "--updatefile-dir",
        default=str(Path.home() / "Desktop" / "UpdateFile_p40_320"),
    )
    p.add_argument(
        "--app-data-json",
        default=str(Path.home() / "work" / "coding" / "websoccer-player-search" / "app" / "data.json"),
    )
    p.add_argument(
        "--coaches-data-json",
        default=str(Path.home() / "work" / "coding" / "websoccer-player-search" / "app" / "coaches_data.json"),
    )
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
        path.unlink()
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

        CREATE TABLE IF NOT EXISTS manual_player_model_player (
          player_id INTEGER PRIMARY KEY,
          model_name TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_method TEXT NOT NULL DEFAULT 'manual_update',
          is_manual INTEGER NOT NULL DEFAULT 1,
          notes TEXT,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS manual_player_person_id (
          player_id INTEGER PRIMARY KEY,
          manual_person_id INTEGER NOT NULL,
          source_method TEXT NOT NULL DEFAULT 'manual_fix',
          is_manual INTEGER NOT NULL DEFAULT 1,
          notes TEXT,
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
        conn.execute(
            """
            INSERT INTO cc_matches
            SELECT season, world_id, match_id, datetime, title, referee,
                   stadium_id, stadium_name, stadium_capacity, audience,
                   home_score, away_score, access_datetime, file_path
            FROM ccsrc.matches
            """
        )
        conn.execute(
            """
            INSERT INTO cc_teams
            SELECT season, world_id, match_id, side, team_id, team_name,
                   uniform_id, formation_id, formation_name, headcoach_id,
                   headcoach_name, headcoach_pts, goals_for, goals_against, result
            FROM ccsrc.teams
            """
        )
        conn.execute(
            """
            INSERT INTO cc_players
            SELECT season, world_id, match_id, side, member_order, is_starting11,
                   player_id, player_fullname, player_name, pos_code_1_4, pts,
                   team_id, team_name, formation_id, formation_name
            FROM ccsrc.players
            """
        )
        conn.execute(
            """
            INSERT INTO cc_goals
            SELECT season, world_id, match_id, goal_index, side, minute, scorer_player_id
            FROM ccsrc.goals
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
    for p in players:
        pid = int(p.get("id") or 0)
        if pid <= 0:
            continue
        cat = str(p.get("category") or "NR")
        membership = p.get("categoryMembership") or [cat]
        conn.execute(
            """
            INSERT INTO manual_player_category
            (player_id, category, category_membership_json, is_manual, source_file, source_note)
            VALUES (?, ?, ?, 1, ?, 'category treated as manual truth')
            """,
            (pid, cat, _to_json(membership), str(app_data_json)),
        )

    for s in app.get("scouts") or []:
        event_id = int(s.get("eventId") or 0)
        if event_id <= 0:
            continue
        name_source = str(s.get("nameSource") or "")
        is_manual = 1 if name_source == "manual_fill" else 0
        conn.execute(
            """
            INSERT INTO manual_scout_event
            (event_id, name, start, end, type, version, notes, name_raw, name_source,
             player_count, player_ids_json, is_manual, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                s.get("name"),
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


def main() -> int:
    args = parse_args()
    out_db = Path(args.out_db).expanduser().resolve()
    cc_db = Path(args.cc_db).expanduser().resolve()
    product = Path(args.product_sqlite).expanduser().resolve()
    update_dir = Path(args.updatefile_dir).expanduser().resolve()
    app_data = Path(args.app_data_json).expanduser().resolve()
    coaches_data = Path(args.coaches_data_json).expanduser().resolve()

    conn = connect(out_db)
    try:
        init_schema(conn)
        conn.commit()
        import_cc_db(conn, cc_db)
        put_source(conn, "cc_db", cc_db, "copied from incremental cc db")
        conn.commit()
        import_app_original(conn, product, verbose=args.verbose)
        put_source(conn, "app_original_product_sqlite", product, "all non-image app original tables copied as ao__*")
        conn.commit()
        import_updatefiles(conn, update_dir, verbose=args.verbose)
        put_source(conn, "updatefile_p40_320", update_dir, "all non-image file entries in p40-320 archives")
        conn.commit()
        import_manual_truth(conn, app_data, coaches_data)
        put_source(conn, "manual_truth_app_data_json", app_data, "manual truth overlay from current site data")
        put_source(conn, "manual_truth_coaches_data_json", coaches_data, "manual coach obtainable truth")
        conn.commit()
        print(f"[DONE] wrote unified db: {out_db}")
        for line in summarize(conn):
            print("[SUMMARY]", line)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
