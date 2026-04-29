#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sqlite3
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))


def now_jst_iso() -> str:
    return dt.datetime.now(JST).isoformat(timespec="seconds")


def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        try:
            return int(float(value))
        except Exception:
            return default


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Migrate player person IDs to player_person_identity canonical table."
    )
    p.add_argument("--master-db", required=True)
    p.add_argument(
        "--fallback-data-json",
        default=str(Path.cwd() / "app" / "data.json"),
        help="Existing site data used for player IDs not present in ao__ZMOPLAYER.",
    )
    p.add_argument(
        "--drop-old",
        action="store_true",
        help="Drop manual_player_person_id after successful migration.",
    )
    p.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a .bak copy before mutating the DB.",
    )
    return p.parse_args()


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def main() -> int:
    args = parse_args()
    db_path = Path(args.master_db).expanduser().resolve()
    fallback_path = Path(args.fallback_data_json).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"master db not found: {db_path}")
    if not fallback_path.exists():
        raise FileNotFoundError(f"fallback data json not found: {fallback_path}")

    if not args.no_backup:
        backup = db_path.with_suffix(db_path.suffix + f".pre_person_identity_{dt.datetime.now(JST).strftime('%Y%m%d%H%M%S')}.bak")
        shutil.copy2(db_path, backup)
        print(f"[BACKUP] {backup}")

    fallback = json.loads(fallback_path.read_text(encoding="utf-8"))
    fallback_players = {
        to_int(p.get("id"), 0): p
        for p in fallback.get("players", [])
        if to_int(p.get("id"), 0) > 0
    }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_person_identity (
              player_id INTEGER PRIMARY KEY,
              raw_person_id INTEGER,
              canonical_person_id INTEGER NOT NULL,
              is_override INTEGER NOT NULL DEFAULT 0,
              source_method TEXT NOT NULL DEFAULT 'canonical_from_raw',
              notes TEXT,
              source_file TEXT,
              updated_at TEXT NOT NULL
            )
            """
        )

        raw_by_player = {
            to_int(r["ZPLAYER_ID"]): to_int(r["ZPERSON_ID"])
            for r in conn.execute("SELECT ZPLAYER_ID, ZPERSON_ID FROM ao__ZMOPLAYER")
        }
        cat_ids = {
            to_int(r["player_id"])
            for r in conn.execute("SELECT player_id FROM manual_player_category")
        }

        legacy = {}
        if table_exists(conn, "manual_player_person_id"):
            for r in conn.execute(
                """
                SELECT player_id, manual_person_id, source_method, notes, updated_at
                FROM manual_player_person_id
                """
            ):
                pid = to_int(r["player_id"])
                if pid <= 0:
                    continue
                legacy[pid] = {
                    "canonical": to_int(r["manual_person_id"]),
                    "sourceMethod": str(r["source_method"] or ""),
                    "notes": str(r["notes"] or ""),
                    "updatedAt": str(r["updated_at"] or ""),
                }

        all_ids = sorted(set(raw_by_player) | cat_ids | set(fallback_players) | set(legacy))
        now = now_jst_iso()
        rows = []
        for pid in all_ids:
            fb = fallback_players.get(pid, {})
            legacy_row = legacy.get(pid, {})
            raw = raw_by_player.get(pid)
            if raw is None:
                raw = to_int(fb.get("personIdRaw") or fb.get("personId"), 0)
            canonical = to_int(legacy_row.get("canonical"), 0)
            if canonical <= 0:
                canonical = to_int(fb.get("personId") or raw, 0)
            if canonical <= 0:
                canonical = raw if raw and raw > 0 else pid

            legacy_method = str(legacy_row.get("sourceMethod") or "")
            is_override = 0
            if legacy_method and legacy_method != "baseline_raw_personid":
                is_override = 1
            if raw and raw > 0 and canonical != raw:
                is_override = 1

            if is_override:
                source_method = legacy_method or "manual_canonical_person_id"
            else:
                source_method = "canonical_from_raw"

            rows.append(
                (
                    pid,
                    raw if raw and raw > 0 else None,
                    canonical,
                    is_override,
                    source_method,
                    legacy_row.get("notes") or "canonicalized from raw person id",
                    str(fallback_path),
                    legacy_row.get("updatedAt") or now,
                )
            )

        conn.execute("DELETE FROM player_person_identity")
        conn.executemany(
            """
            INSERT INTO player_person_identity
              (player_id, raw_person_id, canonical_person_id, is_override, source_method, notes, source_file, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if args.drop_old and table_exists(conn, "manual_player_person_id"):
            conn.execute("DROP TABLE manual_player_person_id")
        conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM player_person_identity").fetchone()[0]
        overrides = conn.execute(
            "SELECT COUNT(*) FROM player_person_identity WHERE is_override=1"
        ).fetchone()[0]
        print(f"[DONE] player_person_identity rows={total} overrides={overrides} drop_old={args.drop_old}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
