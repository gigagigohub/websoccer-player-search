#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional


JST = timezone(timedelta(hours=9))
DEFAULT_LOCAL_DIR = Path.home() / "work" / "coding" / "wsc_data" / "websoccer_master_db"
DEFAULT_JSON_ROOT = Path.home() / "work" / "coding" / "wsc_data" / "CC_match_result_json"
DEFAULT_DESKTOP_DIR = Path.home() / "Desktop" / "websoccer_master_db"
API_HOST = "api.app.websoccer.jp"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Create a new WSM DB by copying the latest WSM and directly inserting CC JSON data."
    )
    p.add_argument("--local-dir", default=str(DEFAULT_LOCAL_DIR))
    p.add_argument("--json-root", default=str(DEFAULT_JSON_ROOT))
    p.add_argument("--desktop-dir", default=str(DEFAULT_DESKTOP_DIR))
    p.add_argument("--source-wsm", default="", help="Source WSM. Default: latest wsm_*.sqlite3 in --local-dir")
    p.add_argument("--out-db", default="", help="Output WSM. Default: --local-dir/wsm_YYMMDDHHMM.sqlite3")
    p.add_argument(
        "--season",
        type=int,
        default=0,
        help="CC season to import. Default: latest season found in JSON.",
    )
    p.add_argument("--keep-local", type=int, default=3, help="How many local wsm_*.sqlite3 files to keep")
    p.add_argument("--keep-desktop", type=int, default=1, help="How many desktop wsm_*.sqlite3 files to keep")
    p.add_argument("--no-cleanup", action="store_true", help="Do not remove older WSM files")
    return p.parse_args()


def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def is_main_wsm(path: Path) -> bool:
    return bool(re.fullmatch(r"wsm_\d{10,14}\.sqlite3", path.name))


def wsm_sort_key(path: Path) -> tuple[str, float]:
    match = re.fullmatch(r"wsm_(\d{10,14})\.sqlite3", path.name)
    stamp = match.group(1) if match else ""
    return stamp, path.stat().st_mtime


def latest_wsm(local_dir: Path) -> Path:
    files = [p for p in local_dir.glob("wsm_*.sqlite3") if is_main_wsm(p)]
    if not files:
        raise FileNotFoundError(f"no wsm_*.sqlite3 found in {local_dir}")
    return sorted(files, key=wsm_sort_key)[-1]


def default_out_path(local_dir: Path) -> Path:
    stamp = datetime.now(JST).strftime("%y%m%d%H%M")
    out = local_dir / f"wsm_{stamp}.sqlite3"
    if not out.exists():
        return out
    stamp = datetime.now(JST).strftime("%y%m%d%H%M%S")
    return local_dir / f"wsm_{stamp}.sqlite3"


def cc_json_base(json_root: Path) -> Path:
    nested = json_root / API_HOST / "match" / "summary" / "cc"
    if nested.exists():
        return nested
    if json_root.name == "cc" and json_root.exists():
        return json_root
    raise FileNotFoundError(f"CC JSON base not found under {json_root}")


def iter_json_files(json_root: Path) -> Iterable[Path]:
    yield from cc_json_base(json_root).rglob("*.json")


def parse_match_payload(path: Path) -> Optional[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict) or obj.get("code") != "000":
        return None
    m = obj.get("m")
    return m if isinstance(m, dict) else None


def latest_season_in_json(json_root: Path) -> int:
    seasons: set[int] = set()
    for path in iter_json_files(json_root):
        m = parse_match_payload(path)
        if not m:
            continue
        season = to_int(m.get("szn"), 0)
        if season > 0:
            seasons.add(season)
    if not seasons:
        raise RuntimeError(f"no seasons found in JSON: {json_root}")
    return max(seasons)


def ensure_pk_schema(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(cc_matches)").fetchall()}
    for col, typ in [
        ("pk_home_goals", "INTEGER"),
        ("pk_away_goals", "INTEGER"),
        ("pk_home_attempts", "INTEGER"),
        ("pk_away_attempts", "INTEGER"),
        ("pk_winner_side", "TEXT"),
    ]:
        if col not in cols:
            conn.execute(f"ALTER TABLE cc_matches ADD COLUMN {col} {typ}")

    conn.execute(
        """
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
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cc_pk_events_match ON cc_pk_events(season, world_id, match_id)"
    )


def delete_cc_season(conn: sqlite3.Connection, season: int) -> None:
    for table in ["cc_pk_events", "cc_goals", "cc_players", "cc_teams", "cc_matches"]:
        conn.execute(f"DELETE FROM {table} WHERE season=?", (season,))


def pk_summary(pk) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int], Optional[str]]:
    if not isinstance(pk, list) or not pk:
        return None, None, None, None, None
    home = pk[0] if len(pk) >= 1 and isinstance(pk[0], list) else []
    away = pk[1] if len(pk) >= 2 and isinstance(pk[1], list) else []
    home_goals = sum(1 for x in home if isinstance(x, dict) and to_int(x.get("goal"), 0) == 1)
    away_goals = sum(1 for x in away if isinstance(x, dict) and to_int(x.get("goal"), 0) == 1)
    winner = "home" if home_goals > away_goals else ("away" if away_goals > home_goals else "draw")
    return home_goals, away_goals, len(home), len(away), winner


def insert_pk_events(conn: sqlite3.Connection, season: int, world_id: int, match_id: int, pk) -> int:
    if not isinstance(pk, list) or not pk:
        return 0
    inserted = 0
    home = pk[0] if len(pk) >= 1 and isinstance(pk[0], list) else []
    away = pk[1] if len(pk) >= 2 and isinstance(pk[1], list) else []
    for side, events in [("home", home), ("away", away)]:
        for pk_order, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                continue
            player_id = to_int(event.get("player_id"), 0)
            conn.execute(
                """
                INSERT INTO cc_pk_events
                (season, world_id, match_id, side, pk_order, minute, player_id, goal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    season,
                    world_id,
                    match_id,
                    side,
                    pk_order,
                    to_int(event.get("min"), 0),
                    player_id if player_id > 0 else None,
                    1 if to_int(event.get("goal"), 0) == 1 else 0,
                ),
            )
            inserted += 1
    return inserted


def insert_match(conn: sqlite3.Connection, path: Path, m: dict) -> tuple[int, int]:
    season = to_int(m.get("szn"), 0)
    world_id = to_int(m.get("world_id"), 0)
    match_id = to_int(m.get("match_id"), 0)
    teams = m.get("team") if isinstance(m.get("team"), list) else []
    if season <= 0 or world_id <= 0 or match_id <= 0 or len(teams) < 2:
        raise ValueError(f"invalid match payload: {path}")

    goals = m.get("goal") if isinstance(m.get("goal"), list) else []
    flat_goals: list[tuple[str, int, int]] = []
    home_score = 0
    away_score = 0
    for goal_side_index, goal_dict in enumerate(goals):
        if not isinstance(goal_dict, dict):
            continue
        side = "home" if goal_side_index == 0 else ("away" if goal_side_index == 1 else "unknown")
        for minute_raw, scorer_raw in goal_dict.items():
            scorer_id = to_int(scorer_raw, 0)
            if scorer_id <= 0:
                continue
            if side == "home":
                home_score += 1
            elif side == "away":
                away_score += 1
            flat_goals.append((side, to_int(minute_raw, 0), scorer_id))

    stadium = m.get("stadium") if isinstance(m.get("stadium"), dict) else {}
    pk_home_goals, pk_away_goals, pk_home_attempts, pk_away_attempts, pk_winner_side = pk_summary(m.get("pk"))
    conn.execute(
        """
        INSERT INTO cc_matches (
          season, world_id, match_id, datetime, title, referee, stadium_id, stadium_name,
          stadium_capacity, audience, home_score, away_score, access_datetime, file_path,
          pk_home_goals, pk_away_goals, pk_home_attempts, pk_away_attempts, pk_winner_side
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            str(path),
            pk_home_goals,
            pk_away_goals,
            pk_home_attempts,
            pk_away_attempts,
            pk_winner_side,
        ),
    )

    for team_index, team in enumerate(teams[:2]):
        side = "home" if team_index == 0 else "away"
        team_id = to_int(team.get("id"), 0)
        team_name = str(team.get("name") or "")
        formation_id = to_int(team.get("formation"), 0)
        formation_name = str(team.get("formation_name") or "")
        headcoach = team.get("headcoach") if isinstance(team.get("headcoach"), dict) else {}
        goals_for = home_score if side == "home" else away_score
        goals_against = away_score if side == "home" else home_score
        result = "W" if goals_for > goals_against else ("L" if goals_for < goals_against else "D")
        conn.execute(
            """
            INSERT INTO cc_teams (
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
                to_int(team.get("uniform"), 0),
                formation_id,
                formation_name,
                to_int(headcoach.get("id"), 0),
                str(headcoach.get("name") or ""),
                to_float(headcoach.get("pts"), 0.0),
                goals_for,
                goals_against,
                result,
            ),
        )

        members = team.get("members") if isinstance(team.get("members"), list) else []
        for member_order, member in enumerate(members, start=1):
            conn.execute(
                """
                INSERT INTO cc_players (
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
                    1 if member_order <= 11 else 0,
                    to_int(member.get("id"), 0),
                    str(member.get("fullname") or ""),
                    str(member.get("name") or ""),
                    to_int(member.get("pos"), 0),
                    to_float(member.get("pts"), 0.0),
                    team_id,
                    team_name,
                    formation_id,
                    formation_name,
                ),
            )

    for goal_index, (side, minute, scorer_id) in enumerate(flat_goals, start=1):
        conn.execute(
            """
            INSERT INTO cc_goals
            (season, world_id, match_id, goal_index, side, minute, scorer_player_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (season, world_id, match_id, goal_index, side, minute, scorer_id),
        )

    pk_events = insert_pk_events(conn, season, world_id, match_id, m.get("pk"))
    return len(flat_goals), pk_events


def import_cc_season_from_json(conn: sqlite3.Connection, json_root: Path, season: int) -> dict[str, int]:
    ensure_pk_schema(conn)
    delete_cc_season(conn, season)

    scanned = 0
    matched = 0
    inserted = 0
    invalid = 0
    goals = 0
    pk_events = 0
    for path in iter_json_files(json_root):
        scanned += 1
        m = parse_match_payload(path)
        if not m:
            invalid += 1
            continue
        if to_int(m.get("szn"), 0) != season:
            continue
        matched += 1
        try:
            goal_count, pk_count = insert_match(conn, path, m)
        except Exception:
            invalid += 1
            raise
        inserted += 1
        goals += goal_count
        pk_events += pk_count

    return {
        "scanned": scanned,
        "matched": matched,
        "inserted": inserted,
        "invalid": invalid,
        "goals": goals,
        "pk_events": pk_events,
    }


def summarize(conn: sqlite3.Connection, season: int) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS matches,
               COUNT(DISTINCT world_id) AS worlds,
               MIN(match_id) AS min_match_id,
               MAX(match_id) AS max_match_id
        FROM cc_matches
        WHERE season=?
        """,
        (season,),
    ).fetchone()
    complete_worlds = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
          SELECT world_id, COUNT(*) AS c
          FROM cc_matches
          WHERE season=?
          GROUP BY world_id
          HAVING c=63
        )
        """,
        (season,),
    ).fetchone()[0]
    return {
        "matches": int(row[0] or 0),
        "worlds": int(row[1] or 0),
        "min_match_id": int(row[2] or 0),
        "max_match_id": int(row[3] or 0),
        "complete_worlds": int(complete_worlds or 0),
        "teams": int(conn.execute("SELECT COUNT(*) FROM cc_teams WHERE season=?", (season,)).fetchone()[0]),
        "players": int(conn.execute("SELECT COUNT(*) FROM cc_players WHERE season=?", (season,)).fetchone()[0]),
        "goals": int(conn.execute("SELECT COUNT(*) FROM cc_goals WHERE season=?", (season,)).fetchone()[0]),
        "pk_events": int(conn.execute("SELECT COUNT(*) FROM cc_pk_events WHERE season=?", (season,)).fetchone()[0]),
    }


def put_meta_source(conn: sqlite3.Connection, key: str, path: Path, note: str) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta_sources'"
    ).fetchone()
    if not exists:
        return
    conn.execute(
        """
        INSERT INTO meta_sources (source_key, source_path, loaded_at, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
          source_path=excluded.source_path,
          loaded_at=excluded.loaded_at,
          note=excluded.note
        """,
        (key, str(path), datetime.now(JST).isoformat(timespec="seconds"), note),
    )


def copy_to_desktop(out_db: Path, desktop_dir: Path) -> Path:
    desktop_dir.mkdir(parents=True, exist_ok=True)
    dest = desktop_dir / out_db.name
    shutil.copy2(out_db, dest)
    return dest


def cleanup_wsm_files(directory: Path, keep: int) -> list[Path]:
    if keep <= 0 or not directory.exists():
        return []
    files = [p for p in directory.glob("wsm_*.sqlite3") if is_main_wsm(p)]
    files = sorted(files, key=wsm_sort_key, reverse=True)
    kept_names = {p.name for p in files[:keep]}
    removed: list[Path] = []
    for path in files[keep:]:
        path.unlink()
        removed.append(path)
    for sidecar in list(directory.glob("wsm_*.sqlite3-wal")) + list(directory.glob("wsm_*.sqlite3-shm")):
        base_name = sidecar.name.rsplit("-", 1)[0]
        if base_name not in kept_names:
            sidecar.unlink()
            removed.append(sidecar)
    return removed


def main() -> int:
    args = parse_args()
    local_dir = Path(args.local_dir).expanduser().resolve()
    json_root = Path(args.json_root).expanduser().resolve()
    desktop_dir = Path(args.desktop_dir).expanduser().resolve()
    source = Path(args.source_wsm).expanduser().resolve() if args.source_wsm else latest_wsm(local_dir)
    out_db = Path(args.out_db).expanduser().resolve() if args.out_db else default_out_path(local_dir).resolve()
    season = args.season or latest_season_in_json(json_root)

    if not source.exists():
        raise FileNotFoundError(f"source WSM not found: {source}")
    if out_db.exists():
        raise FileExistsError(f"output DB already exists: {out_db}")
    out_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out_db)

    conn = sqlite3.connect(str(out_db))
    try:
        with conn:
            stats = import_cc_season_from_json(conn, json_root, season)
            put_meta_source(
                conn,
                f"cc_match_result_json_season_{season}",
                json_root,
                "direct CC JSON import into WSM",
            )
        summary = summarize(conn, season)
    finally:
        conn.close()

    desktop_copy = copy_to_desktop(out_db, desktop_dir)
    removed_local: list[Path] = []
    removed_desktop: list[Path] = []
    if not args.no_cleanup:
        removed_local = cleanup_wsm_files(local_dir, args.keep_local)
        removed_desktop = cleanup_wsm_files(desktop_dir, args.keep_desktop)

    print(f"[DONE] source_wsm={source}")
    print(f"[DONE] out_wsm={out_db}")
    print(f"[DONE] desktop_copy={desktop_copy}")
    print(f"[DONE] season={season} import_stats={stats}")
    print(f"[DONE] season={season} summary={summary}")
    print(f"[DONE] removed_local={len(removed_local)}")
    for path in removed_local:
        print(f"  removed local {path}")
    print(f"[DONE] removed_desktop={len(removed_desktop)}")
    for path in removed_desktop:
        print(f"  removed desktop {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
