#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Ingest CC PK data from raw JSON into master DB.")
    ap.add_argument(
        "--json-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_json"),
        help="Root containing CC match summary JSON files.",
    )
    ap.add_argument(
        "--master-db",
        default=str(Path.home() / "Desktop" / "websoccer_master_db" / "websoccer_master.sqlite3"),
        help="Master DB path.",
    )
    return ap.parse_args()


def to_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return default


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE cc_matches ADD COLUMN pk_home_goals INTEGER")
    conn.execute("ALTER TABLE cc_matches ADD COLUMN pk_away_goals INTEGER")
    conn.execute("ALTER TABLE cc_matches ADD COLUMN pk_home_attempts INTEGER")
    conn.execute("ALTER TABLE cc_matches ADD COLUMN pk_away_attempts INTEGER")
    conn.execute("ALTER TABLE cc_matches ADD COLUMN pk_winner_side TEXT")


def ensure_schema_safe(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cc_matches)").fetchall()}
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
          side TEXT NOT NULL, -- home | away
          pk_order INTEGER NOT NULL,
          minute INTEGER NOT NULL,
          player_id INTEGER,
          goal INTEGER NOT NULL, -- 1 success, 0 miss
          PRIMARY KEY (season, world_id, match_id, side, pk_order)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cc_pk_events_match ON cc_pk_events(season, world_id, match_id)"
    )


def main() -> int:
    args = parse_args()
    json_root = Path(args.json_root).expanduser().resolve()
    master_db = Path(args.master_db).expanduser().resolve()
    if not json_root.exists():
        raise FileNotFoundError(f"json root not found: {json_root}")
    if not master_db.exists():
        raise FileNotFoundError(f"master db not found: {master_db}")

    conn = sqlite3.connect(str(master_db))
    try:
        ensure_schema_safe(conn)
        conn.execute("BEGIN")

        pk_match_count = 0
        pk_event_count = 0
        scanned = 0

        for f in json_root.rglob("*.json"):
            scanned += 1
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            m = obj.get("m")
            if not isinstance(m, dict):
                continue

            season = to_int(m.get("szn"), 0)
            world_id = to_int(m.get("world_id"), 0)
            match_id = to_int(m.get("match_id"), 0)
            if season <= 0 or world_id <= 0 or match_id <= 0:
                continue

            pk = m.get("pk")
            if not isinstance(pk, list) or not pk:
                continue

            home_list = pk[0] if len(pk) >= 1 and isinstance(pk[0], list) else []
            away_list = pk[1] if len(pk) >= 2 and isinstance(pk[1], list) else []
            home_goals = sum(1 for x in home_list if isinstance(x, dict) and to_int(x.get("goal"), 0) == 1)
            away_goals = sum(1 for x in away_list if isinstance(x, dict) and to_int(x.get("goal"), 0) == 1)
            home_attempts = len(home_list)
            away_attempts = len(away_list)
            winner = "home" if home_goals > away_goals else ("away" if away_goals > home_goals else "draw")

            conn.execute(
                """
                UPDATE cc_matches
                SET pk_home_goals=?, pk_away_goals=?, pk_home_attempts=?, pk_away_attempts=?, pk_winner_side=?
                WHERE season=? AND world_id=? AND match_id=?
                """,
                (home_goals, away_goals, home_attempts, away_attempts, winner, season, world_id, match_id),
            )
            # upsert per event
            for side, arr in [("home", home_list), ("away", away_list)]:
                for idx, ev in enumerate(arr, start=1):
                    minute = to_int((ev or {}).get("min"), 0) if isinstance(ev, dict) else 0
                    player_id = to_int((ev or {}).get("player_id"), 0) if isinstance(ev, dict) else 0
                    goal = 1 if to_int((ev or {}).get("goal"), 0) == 1 else 0
                    conn.execute(
                        """
                        INSERT INTO cc_pk_events
                        (season, world_id, match_id, side, pk_order, minute, player_id, goal)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(season, world_id, match_id, side, pk_order)
                        DO UPDATE SET minute=excluded.minute, player_id=excluded.player_id, goal=excluded.goal
                        """,
                        (season, world_id, match_id, side, idx, minute, player_id if player_id > 0 else None, goal),
                    )
                    pk_event_count += 1
            pk_match_count += 1

        conn.commit()
        distinct_pk_matches = conn.execute(
            "SELECT COUNT(DISTINCT season||':'||world_id||':'||match_id) FROM cc_pk_events"
        ).fetchone()[0]
        print(f"[DONE] scanned_json={scanned} pk_matches_seen={pk_match_count} pk_events_upserted={pk_event_count}")
        print(f"[DONE] cc_pk_events distinct matches={distinct_pk_matches}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
