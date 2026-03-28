#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


API_HOST = "api.app.websoccer.jp"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Incrementally ingest CC match summary JSON into SQLite."
    )
    ap.add_argument(
        "--json-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_json"),
        help="Root containing raw JSON (default: ~/Desktop/CC_match_result_json)",
    )
    ap.add_argument(
        "--db-path",
        default=str(Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3"),
        help="SQLite DB path (default: ~/Desktop/CC_match_result_db/cc_match_result.sqlite3)",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file progress every 500 files.",
    )
    ap.add_argument(
        "--force-reingest",
        action="store_true",
        help="Ignore source_files cache and re-ingest all JSON files.",
    )
    return ap.parse_args()


def iter_json_files(base: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(base):
        for name in filenames:
            if name.endswith(".json"):
                yield Path(dirpath) / name


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_files (
          path TEXT PRIMARY KEY,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          season INTEGER,
          world_id INTEGER,
          match_id INTEGER,
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS matches (
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
          home_score INTEGER NOT NULL DEFAULT 0,
          away_score INTEGER NOT NULL DEFAULT 0,
          access_datetime TEXT,
          file_path TEXT,
          PRIMARY KEY (season, world_id, match_id)
        );

        CREATE TABLE IF NOT EXISTS teams (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          side TEXT NOT NULL, -- home | away
          team_id INTEGER,
          team_name TEXT,
          uniform_id INTEGER,
          formation_id INTEGER,
          formation_name TEXT,
          headcoach_id INTEGER,
          headcoach_name TEXT,
          headcoach_pts REAL,
          goals_for INTEGER NOT NULL DEFAULT 0,
          goals_against INTEGER NOT NULL DEFAULT 0,
          result TEXT NOT NULL DEFAULT 'D', -- W/L/D
          PRIMARY KEY (season, world_id, match_id, side)
        );

        CREATE TABLE IF NOT EXISTS players (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          side TEXT NOT NULL, -- home | away
          member_order INTEGER NOT NULL,
          is_starting11 INTEGER NOT NULL DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS goals (
          season INTEGER NOT NULL,
          world_id INTEGER NOT NULL,
          match_id INTEGER NOT NULL,
          goal_index INTEGER NOT NULL,
          side TEXT NOT NULL, -- home | away | unknown
          minute INTEGER NOT NULL,
          scorer_player_id INTEGER,
          PRIMARY KEY (season, world_id, match_id, goal_index)
        );

        CREATE INDEX IF NOT EXISTS idx_teams_formation ON teams(formation_id);
        CREATE INDEX IF NOT EXISTS idx_teams_headcoach ON teams(headcoach_id);
        CREATE INDEX IF NOT EXISTS idx_players_formation ON players(formation_id);
        CREATE INDEX IF NOT EXISTS idx_players_player ON players(player_id);
        CREATE INDEX IF NOT EXISTS idx_matches_world ON matches(world_id);
        CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season);
        """
    )
    ensure_column(conn, "matches", "stadium_id", "INTEGER")
    ensure_column(conn, "matches", "stadium_capacity", "INTEGER")
    ensure_column(conn, "teams", "uniform_id", "INTEGER")


def ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, col_type: str) -> None:
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    cols = {str(r[1]) for r in cur.fetchall()}  # r[1] = column name
    if column_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type}")


def read_source_file_row(conn: sqlite3.Connection, path: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT path, mtime, size, season, world_id, match_id FROM source_files WHERE path = ?",
        (path,),
    )
    return cur.fetchone()


def remove_match(conn: sqlite3.Connection, season: int, world_id: int, match_id: int) -> None:
    params = (season, world_id, match_id)
    conn.execute("DELETE FROM goals WHERE season=? AND world_id=? AND match_id=?", params)
    conn.execute("DELETE FROM players WHERE season=? AND world_id=? AND match_id=?", params)
    conn.execute("DELETE FROM teams WHERE season=? AND world_id=? AND match_id=?", params)
    conn.execute("DELETE FROM matches WHERE season=? AND world_id=? AND match_id=?", params)


def parse_payload(path: Path) -> Optional[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict) or obj.get("code") != "000":
        return None
    m = obj.get("m")
    if not isinstance(m, dict):
        return None
    return m


def to_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def to_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def ingest_one(conn: sqlite3.Connection, file_path: Path, m: dict) -> Tuple[int, int, int]:
    season = to_int(m.get("szn"), 0)
    world_id = to_int(m.get("world_id"), 0)
    match_id = to_int(m.get("match_id"), 0)
    if season <= 0 or world_id <= 0 or match_id <= 0:
        raise ValueError("invalid match key")

    teams = m.get("team") if isinstance(m.get("team"), list) else []
    if len(teams) < 2:
        raise ValueError("invalid team list")

    team_member_side: Dict[str, str] = {}
    for idx, t in enumerate(teams[:2]):
        side = "home" if idx == 0 else "away"
        members = t.get("members") if isinstance(t.get("members"), list) else []
        for mem in members:
            pid = to_int(mem.get("id"), 0)
            if pid > 0:
                team_member_side[str(pid)] = side

    goals_raw = m.get("goal") if isinstance(m.get("goal"), list) else []
    goals_flat: List[Tuple[str, int, int]] = []  # (side, minute, scorer_id)
    home_score = 0
    away_score = 0
    for ge in goals_raw:
        if not isinstance(ge, dict):
            continue
        for minute_raw, scorer_raw in ge.items():
            scorer_id = to_int(scorer_raw, 0)
            if scorer_id <= 0:
                continue
            minute = to_int(minute_raw, 0)
            side = team_member_side.get(str(scorer_id), "unknown")
            if side == "home":
                home_score += 1
            elif side == "away":
                away_score += 1
            goals_flat.append((side, minute, scorer_id))

    # Replace full match payload atomically
    remove_match(conn, season, world_id, match_id)

    stadium = m.get("stadium") if isinstance(m.get("stadium"), dict) else {}
    conn.execute(
        """
        INSERT INTO matches (
          season, world_id, match_id, datetime, title, referee, stadium_id, stadium_name, stadium_capacity, audience,
          home_score, away_score, access_datetime, file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            season,
            world_id,
            match_id,
            str(m.get("datetime") or ""),
            str(m.get("title") or ""),
            str(m.get("referee") or ""),
            to_int(stadium.get("id"), 0),
            str(stadium.get("name") or ""),
            to_int(stadium.get("capacity"), 0),
            to_int(m.get("audience"), 0),
            home_score,
            away_score,
            str(m.get("access_datetime") or ""),
            str(file_path),
        ),
    )

    for idx, t in enumerate(teams[:2]):
        side = "home" if idx == 0 else "away"
        team_id = to_int(t.get("id"), 0)
        team_name = str(t.get("name") or "")
        uniform_id = to_int(t.get("uniform"), 0)
        formation_id = to_int(t.get("formation"), 0)
        formation_name = str(t.get("formation_name") or "")
        hc = t.get("headcoach") if isinstance(t.get("headcoach"), dict) else {}
        headcoach_id = to_int(hc.get("id"), 0)
        headcoach_name = str(hc.get("name") or "")
        headcoach_pts = to_float(hc.get("pts"), 0.0)
        goals_for = home_score if side == "home" else away_score
        goals_against = away_score if side == "home" else home_score
        if goals_for > goals_against:
            result = "W"
        elif goals_for < goals_against:
            result = "L"
        else:
            result = "D"

        conn.execute(
            """
                INSERT INTO teams (
              season, world_id, match_id, side, team_id, team_name, uniform_id,
              formation_id, formation_name, headcoach_id, headcoach_name, headcoach_pts,
              goals_for, goals_against, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                season,
                world_id,
                match_id,
                side,
                team_id,
                team_name,
                uniform_id,
                formation_id,
                formation_name,
                headcoach_id,
                headcoach_name,
                headcoach_pts,
                goals_for,
                goals_against,
                result,
            ),
        )

        members = t.get("members") if isinstance(t.get("members"), list) else []
        for member_order, mem in enumerate(members, start=1):
            player_id = to_int(mem.get("id"), 0)
            player_fullname = str(mem.get("fullname") or "")
            player_name = str(mem.get("name") or "")
            pos_code = to_int(mem.get("pos"), 0)
            pts = to_float(mem.get("pts"), 0.0)
            is_starting11 = 1 if member_order <= 11 else 0
            conn.execute(
                """
                INSERT INTO players (
                  season, world_id, match_id, side, member_order, is_starting11,
                  player_id, player_fullname, player_name, pos_code_1_4, pts,
                  team_id, team_name, formation_id, formation_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    season,
                    world_id,
                    match_id,
                    side,
                    member_order,
                    is_starting11,
                    player_id,
                    player_fullname,
                    player_name,
                    pos_code,
                    pts,
                    team_id,
                    team_name,
                    formation_id,
                    formation_name,
                ),
            )

    for idx, (side, minute, scorer_id) in enumerate(goals_flat, start=1):
        conn.execute(
            """
            INSERT INTO goals (
              season, world_id, match_id, goal_index, side, minute, scorer_player_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (season, world_id, match_id, idx, side, minute, scorer_id),
        )

    return season, world_id, match_id


def update_source_file(
    conn: sqlite3.Connection,
    path: str,
    mtime: float,
    size: int,
    season: Optional[int],
    world_id: Optional[int],
    match_id: Optional[int],
) -> None:
    conn.execute(
        """
        INSERT INTO source_files (path, mtime, size, season, world_id, match_id, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(path) DO UPDATE SET
          mtime=excluded.mtime,
          size=excluded.size,
          season=excluded.season,
          world_id=excluded.world_id,
          match_id=excluded.match_id,
          updated_at=datetime('now')
        """,
        (path, mtime, size, season, world_id, match_id),
    )


def summarize(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        """
        SELECT season, world_id, COUNT(*) AS match_count
        FROM matches
        GROUP BY season, world_id
        ORDER BY season, world_id
        """
    )
    rows = cur.fetchall()
    print(f"[SUMMARY] season/world rows: {len(rows)}")
    if rows:
        print("[SUMMARY] tail:")
        for r in rows[-25:]:
            print(f"  season={r['season']} world={r['world_id']} matches={r['match_count']}")


def main() -> int:
    args = parse_args()
    json_root = Path(args.json_root).expanduser().resolve()
    db_path = Path(args.db_path).expanduser().resolve()
    base = json_root / API_HOST / "match" / "summary" / "cc"
    if not base.exists():
        print(f"[ERROR] JSON base not found: {base}")
        return 2

    conn = connect_db(db_path)
    init_schema(conn)

    scanned = 0
    changed = 0
    ingested = 0
    skipped = 0
    invalid = 0
    failed = 0

    try:
        with conn:
            for fp in iter_json_files(base):
                scanned += 1
                st = fp.stat()
                path_s = str(fp)
                prev = None if args.force_reingest else read_source_file_row(conn, path_s)
                if prev and float(prev["mtime"]) == float(st.st_mtime) and int(prev["size"]) == int(st.st_size):
                    skipped += 1
                    if args.verbose and scanned % 500 == 0:
                        print(
                            f"[PROGRESS] scanned={scanned} changed={changed} ingested={ingested} "
                            f"skipped={skipped} invalid={invalid} failed={failed}"
                        )
                    continue

                changed += 1
                m = parse_payload(fp)
                if m is None:
                    # If file became invalid, clean previously mapped match.
                    if prev and prev["season"] and prev["world_id"] and prev["match_id"]:
                        remove_match(conn, int(prev["season"]), int(prev["world_id"]), int(prev["match_id"]))
                    update_source_file(conn, path_s, float(st.st_mtime), int(st.st_size), None, None, None)
                    invalid += 1
                    continue

                try:
                    season, world_id, match_id = ingest_one(conn, fp, m)
                    update_source_file(
                        conn,
                        path_s,
                        float(st.st_mtime),
                        int(st.st_size),
                        season,
                        world_id,
                        match_id,
                    )
                    ingested += 1
                except Exception:
                    failed += 1
                    # Keep source file stamp to avoid infinite retries on broken file unless file changes.
                    update_source_file(conn, path_s, float(st.st_mtime), int(st.st_size), None, None, None)

                if args.verbose and scanned % 500 == 0:
                    print(
                        f"[PROGRESS] scanned={scanned} changed={changed} ingested={ingested} "
                        f"skipped={skipped} invalid={invalid} failed={failed}"
                    )
    finally:
        summarize(conn)
        conn.close()

    print(
        f"[DONE] scanned={scanned} changed={changed} ingested={ingested} "
        f"skipped={skipped} invalid={invalid} failed={failed}"
    )
    print(f"[DONE] db={db_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
