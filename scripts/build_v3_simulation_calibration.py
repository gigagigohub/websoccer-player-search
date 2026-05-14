#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path


DEFAULT_DB_DIR = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "app" / "simulation_v3_calibration.json"


def latest_wsm_db() -> Path:
    files = sorted(DEFAULT_DB_DIR.glob("wsm_*.sqlite3"))
    if not files:
        raise FileNotFoundError(f"No wsm_*.sqlite3 found in {DEFAULT_DB_DIR}")
    return files[-1]


def to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def bucket_for(diff: float, width: float) -> float:
    return math.floor(diff / width) * width


def build_calibration(db_path: Path, bin_width: float = 2.0, alpha: float = 1.0, min_sample_size: int = 30):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        WITH team_agg AS (
          SELECT
            t.season,
            t.world_id,
            t.match_id,
            t.side,
            COALESCE(t.headcoach_pts, 0) AS headcoach_pts,
            t.goals_for,
            t.goals_against,
            SUM(CASE WHEN p.is_starting11 = 1 THEN COALESCE(p.pts, 0) ELSE 0 END) AS starter_pts_sum,
            COUNT(CASE WHEN p.is_starting11 = 1 THEN 1 END) AS starter_count,
            SUM(CASE WHEN p.is_starting11 = 1 AND p.pos_code_1_4 = 1 THEN COALESCE(p.pts, 0) ELSE 0 END) AS fw_pts,
            SUM(CASE WHEN p.is_starting11 = 1 AND p.pos_code_1_4 = 2 THEN COALESCE(p.pts, 0) ELSE 0 END) AS mf_pts,
            SUM(CASE WHEN p.is_starting11 = 1 AND p.pos_code_1_4 = 3 THEN COALESCE(p.pts, 0) ELSE 0 END) AS df_pts,
            SUM(CASE WHEN p.is_starting11 = 1 AND p.pos_code_1_4 = 4 THEN COALESCE(p.pts, 0) ELSE 0 END) AS gk_pts
          FROM cc_teams t
          JOIN cc_players p
            ON t.season = p.season
           AND t.world_id = p.world_id
           AND t.match_id = p.match_id
           AND t.side = p.side
          GROUP BY
            t.season,
            t.world_id,
            t.match_id,
            t.side
        ),
        pairs AS (
          SELECT
            h.season,
            h.world_id,
            h.match_id,
            h.starter_pts_sum + h.headcoach_pts AS home_index,
            a.starter_pts_sum + a.headcoach_pts AS away_index,
            h.goals_for AS home_goals,
            a.goals_for AS away_goals,
            CASE
              WHEN h.goals_for > a.goals_for THEN 'W'
              WHEN h.goals_for = a.goals_for THEN 'D'
              ELSE 'L'
            END AS home_result
          FROM team_agg h
          JOIN team_agg a
            ON h.season = a.season
           AND h.world_id = a.world_id
           AND h.match_id = a.match_id
           AND h.side = 'home'
           AND a.side = 'away'
          WHERE h.starter_count = 11
            AND a.starter_count = 11
        )
        SELECT * FROM pairs
        """
    ).fetchall()

    buckets = defaultdict(lambda: {"n": 0, "wins": 0, "draws": 0, "losses": 0, "homeGoals": 0.0, "awayGoals": 0.0})
    seasons = set()
    for row in rows:
        seasons.add(int(row["season"]))
        diff = to_float(row["home_index"]) - to_float(row["away_index"])
        bucket = bucket_for(diff, bin_width)
        stat = buckets[bucket]
        stat["n"] += 1
        result = row["home_result"]
        if result == "W":
            stat["wins"] += 1
        elif result == "D":
            stat["draws"] += 1
        else:
            stat["losses"] += 1
        stat["homeGoals"] += to_float(row["home_goals"])
        stat["awayGoals"] += to_float(row["away_goals"])

    bucket_rows = []
    for bucket, stat in sorted(buckets.items()):
        n = stat["n"]
        bucket_rows.append(
            {
                "bucket": bucket,
                "n": n,
                "wins": stat["wins"],
                "draws": stat["draws"],
                "losses": stat["losses"],
                "avgHomeGoals": stat["homeGoals"] / n if n else 0.0,
                "avgAwayGoals": stat["awayGoals"] / n if n else 0.0,
                "avgGoalDiff": (stat["homeGoals"] - stat["awayGoals"]) / n if n else 0.0,
            }
        )

    jst = timezone(timedelta(hours=9))
    return {
        "generatedAt": datetime.now(jst).isoformat(timespec="seconds"),
        "source": db_path.name,
        "model": "v3",
        "binWidth": bin_width,
        "alpha": alpha,
        "minSampleSize": min_sample_size,
        "pairCount": len(rows),
        "seasonStart": min(seasons) if seasons else None,
        "seasonEnd": max(seasons) if seasons else None,
        "buckets": bucket_rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--bin-width", type=float, default=2.0)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--min-sample-size", type=int, default=30)
    args = parser.parse_args()

    db_path = args.db or latest_wsm_db()
    data = build_calibration(db_path, args.bin_width, args.alpha, args.min_sample_size)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {args.out} buckets={len(data['buckets'])} pairs={data['pairCount']}")


if __name__ == "__main__":
    main()
