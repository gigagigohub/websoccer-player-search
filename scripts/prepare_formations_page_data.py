#!/usr/bin/env python3
import argparse
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

PARAM_KEYS = [
    ("spd", "ZSPD"),
    ("tec", "ZTEC"),
    ("pwr", "ZPWR"),
    ("off", "ZOFF"),
    ("def", "ZDEF"),
    ("mid", "ZMID"),
    ("ttl", "ZTTL"),
    ("stm", "ZSTM"),
    ("dif", "ZDIF"),
]


def to_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_sources(base_csv_dir, cc_dir):
    sqlite_dir = base_csv_dir / "csv" / "sqlite_tables"
    return {
        "formation": read_csv(sqlite_dir / "ZMOFORMATION.csv"),
        "formation_info": read_csv(sqlite_dir / "ZMOFORMATIONSINFO.csv"),
        "formation_key": read_csv(sqlite_dir / "ZMOFORMATIONSKEYPOSITION.csv"),
        "formation_pos": read_csv(sqlite_dir / "ZMOFORMATIONSPOSITION.csv"),
        "coach": read_csv(sqlite_dir / "ZMOHEADCOACH.csv"),
        "coach_understanding": read_csv(sqlite_dir / "ZMOHEADCOACHESUNDERSTANDING.csv"),
        "team_level": read_csv(cc_dir / "normalized" / "team_level.csv"),
        "player_level": read_csv(cc_dir / "normalized" / "player_level.csv"),
    }


def load_sources_from_master_db(master_db_path):
    conn = sqlite3.connect(str(master_db_path))
    conn.row_factory = sqlite3.Row
    try:
        src = {
            "formation": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZNAME,
                      ZSYSTEM,
                      ZSTRIDE,
                      ZYEAR
                    FROM ao__ZMOFORMATION
                    """
                ).fetchall()
            ],
            "formation_info": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZSPD,
                      ZTEC,
                      ZPWR,
                      ZOFF,
                      ZDEF,
                      ZMID,
                      ZTTL,
                      ZSTM,
                      ZDIF,
                      ZDESCRIPTION_TEXT,
                      ZSUBTITLE
                    FROM ao__ZMOFORMATIONSINFO
                    """
                ).fetchall()
            ],
            "formation_key": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZKEYPOS,
                      ZPOS,
                      ZSUBTITLE,
                      ZDESCRIPTION_TEXT
                    FROM ao__ZMOFORMATIONSKEYPOSITION
                    """
                ).fetchall()
            ],
            "formation_pos": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZFORMATION_ID,
                      ZPOS,
                      ZX,
                      ZY
                    FROM ao__ZMOFORMATIONSPOSITION
                    """
                ).fetchall()
            ],
            "coach": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZHEADCOACH_ID,
                      ZNAME,
                      ZFULLNAME,
                      ZHEADCOACH_TYPE,
                      ZNATION_ID,
                      ZAGE,
                      ZACT_SZN,
                      ZRARITY
                    FROM ao__ZMOHEADCOACH
                    """
                ).fetchall()
            ],
            "coach_understanding": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      ZHEADCOACH_ID,
                      ZFORMATION_ID,
                      ZDEPTH
                    FROM ao__ZMOHEADCOACHESUNDERSTANDING
                    """
                ).fetchall()
            ],
            "team_level": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      season,
                      world_id,
                      match_id,
                      side,
                      team_id,
                      team_name,
                      formation_id,
                      formation_name,
                      headcoach_id,
                      headcoach_name,
                      headcoach_pts,
                      goals_for,
                      goals_against,
                      result
                    FROM cc_teams
                    """
                ).fetchall()
            ],
            "player_level": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      season,
                      world_id,
                      match_id,
                      side,
                      team_id,
                      team_name,
                      formation_id,
                      formation_name,
                      member_order,
                      is_starting11,
                      player_id,
                      player_fullname,
                      player_name,
                      pos_code_1_4,
                      pts
                    FROM cc_players
                    """
                ).fetchall()
            ],
        }
        return src
    finally:
        conn.close()


def load_cc_from_db(cc_db_path):
    conn = sqlite3.connect(str(cc_db_path))
    conn.row_factory = sqlite3.Row
    try:
        team_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                  season,
                  world_id,
                  match_id,
                  side,
                  team_id,
                  team_name,
                  formation_id,
                  formation_name,
                  headcoach_id,
                  headcoach_name,
                  headcoach_pts,
                  goals_for,
                  goals_against,
                  result
                FROM teams
                """
            ).fetchall()
        ]
        player_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                  season,
                  world_id,
                  match_id,
                  side,
                  team_id,
                  team_name,
                  formation_id,
                  formation_name,
                  member_order,
                  is_starting11,
                  player_id,
                  player_fullname,
                  player_name,
                  pos_code_1_4,
                  pts
                FROM players
                """
            ).fetchall()
        ]
        return {"team_level": team_rows, "player_level": player_rows}
    finally:
        conn.close()


def build_data(src):
    formation_rows = src["formation"]
    formation_info_rows = src["formation_info"]
    key_rows = src["formation_key"]
    pos_rows = src["formation_pos"]
    coach_rows = src["coach"]
    understanding_rows = src["coach_understanding"]
    team_rows = src["team_level"]
    player_rows = src["player_level"]

    formation_by_id = {}
    for row in formation_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        formation_by_id[fid] = {
            "id": fid,
            "name": row.get("ZNAME") or f"Formation {fid}",
            "system": row.get("ZSYSTEM") or "",
            "stride": to_int(row.get("ZSTRIDE")),
            "year": to_int(row.get("ZYEAR")),
            "params": {k: 0 for k, _ in PARAM_KEYS},
            "description": "",
            "subtitle": "",
            "positions": [],
            "keyPositions": [],
        }

    for row in formation_info_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        f = formation_by_id.get(fid)
        if not f:
            continue
        for out_key, col in PARAM_KEYS:
            f["params"][out_key] = to_int(row.get(col))
        f["description"] = row.get("ZDESCRIPTION_TEXT") or ""
        f["subtitle"] = row.get("ZSUBTITLE") or ""

    for row in pos_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        f = formation_by_id.get(fid)
        if not f:
            continue
        f["positions"].append({
            "slot": to_int(row.get("ZPOS")),
            "x": to_float(row.get("ZX")),
            "y": to_float(row.get("ZY")),
        })

    for f in formation_by_id.values():
        f["positions"].sort(key=lambda p: p["slot"])

    for row in key_rows:
        fid = to_int(row.get("ZFORMATION_ID"))
        f = formation_by_id.get(fid)
        if not f:
            continue
        f["keyPositions"].append({
            "rank": to_int(row.get("ZKEYPOS")),
            "slot": to_int(row.get("ZPOS")),
            "subtitle": row.get("ZSUBTITLE") or "",
            "description": row.get("ZDESCRIPTION_TEXT") or "",
        })

    for f in formation_by_id.values():
        f["keyPositions"].sort(key=lambda p: (p["rank"], p["slot"]))

    coach_by_id = {}
    for row in coach_rows:
        cid = to_int(row.get("ZHEADCOACH_ID"))
        coach_by_id[cid] = {
            "id": cid,
            "name": row.get("ZNAME") or "",
            "fullName": row.get("ZFULLNAME") or "",
            "type": to_int(row.get("ZHEADCOACH_TYPE")),
            "nationId": to_int(row.get("ZNATION_ID")),
            "age": to_int(row.get("ZAGE")),
            "actSzn": to_int(row.get("ZACT_SZN")),
            "rarity": to_int(row.get("ZRARITY")),
        }

    coach_to_formations = defaultdict(list)
    coach_to_formations_depth4 = defaultdict(list)
    formation_to_coaches_all = defaultdict(list)
    formation_to_coaches_depth4 = defaultdict(list)

    for row in understanding_rows:
        cid = to_int(row.get("ZHEADCOACH_ID"))
        fid = to_int(row.get("ZFORMATION_ID"))
        depth = to_int(row.get("ZDEPTH"))
        if cid not in coach_by_id or fid not in formation_by_id:
            continue

        # Obtainable: keep original understanding-linked set (all depth rows).
        coach_to_formations[cid].append({"formationId": fid, "depth": depth})
        formation_to_coaches_all[fid].append({"coachId": cid, "depth": depth})

        # Depth4: use raw understanding depth as-is.
        if depth == 4:
            coach_to_formations_depth4[cid].append({"formationId": fid, "depth": depth})
            formation_to_coaches_depth4[fid].append({"coachId": cid, "depth": depth})

    for cid in coach_to_formations:
        coach_to_formations[cid].sort(key=lambda x: x["formationId"])
    for cid in coach_to_formations_depth4:
        coach_to_formations_depth4[cid].sort(key=lambda x: x["formationId"])

    # Team-level aggregate for usage/win rate and coach usage.
    formation_team_counts = defaultdict(int)
    formation_win_counts = defaultdict(int)
    total_team_rows = 0
    coach_use_count = defaultdict(int)  # (formation, coach) -> use count
    coach_pts_sum = defaultdict(float)  # (formation, coach) -> sum pts
    coach_name_by_id = {}
    match_rows_by_key = defaultdict(list)

    for row in team_rows:
        fid = to_int(row.get("formation_id"))
        if fid not in formation_by_id:
            continue
        total_team_rows += 1
        formation_team_counts[fid] += 1
        if (row.get("result") or "").strip().upper() == "W":
            formation_win_counts[fid] += 1
        cid = to_int(row.get("headcoach_id"))
        if cid > 0:
            key = (fid, cid)
            coach_use_count[key] += 1
            pts = to_float(row.get("headcoach_pts"), None)
            if pts is not None:
                coach_pts_sum[key] += pts
            coach_name_by_id[cid] = row.get("headcoach_name") or coach_by_id.get(cid, {}).get("name") or str(cid)
        mkey = (to_int(row.get("season")), to_int(row.get("world_id")), to_int(row.get("match_id")))
        match_rows_by_key[mkey].append(row)

    # Slot usage and pts by (formation, slot, player)
    formation_slot_total = defaultdict(int)
    slot_player_count = defaultdict(int)
    slot_player_pts_sum = defaultdict(float)
    slot_player_name = {}

    for row in player_rows:
        if str(row.get("is_starting11") or "") != "1":
            continue
        fid = to_int(row.get("formation_id"))
        slot = to_int(row.get("member_order"))
        pid = to_int(row.get("player_id"))
        if fid not in formation_by_id or slot < 1 or slot > 11 or pid <= 0:
            continue
        key = (fid, slot, pid)
        formation_slot_total[(fid, slot)] += 1
        slot_player_count[key] += 1
        pts = to_float(row.get("pts"), None)
        if pts is not None:
            slot_player_pts_sum[key] += pts
        slot_player_name[pid] = row.get("player_name") or row.get("player_fullname") or str(pid)

    slot_stats = defaultdict(lambda: defaultdict(list))
    slot_top = defaultdict(dict)

    for (fid, slot, pid), count in slot_player_count.items():
        denom = formation_slot_total[(fid, slot)] or 1
        rate = count / denom
        pts_avg = slot_player_pts_sum[(fid, slot, pid)] / count if count else 0.0
        item = {
            "playerId": pid,
            "playerName": slot_player_name.get(pid, str(pid)),
            "uses": count,
            "usageRate": round(rate, 6),
            "avgPts": round(pts_avg, 4),
        }
        slot_stats[fid][slot].append(item)

    for fid, slots in slot_stats.items():
        for slot, items in slots.items():
            items.sort(key=lambda x: (-x["usageRate"], -x["uses"], -x["avgPts"], x["playerId"]))
            slot_top[fid][slot] = items[0]

    coach_stats = defaultdict(list)
    for (fid, cid), count in coach_use_count.items():
        denom = formation_team_counts[fid] or 1
        usage = count / denom
        avg_pts = coach_pts_sum[(fid, cid)] / count if count else 0.0
        coach_stats[fid].append({
            "coachId": cid,
            "coachName": coach_name_by_id.get(cid, str(cid)),
            "uses": count,
            "usageRate": round(usage, 6),
            "avgPts": round(avg_pts, 4),
        })
    for fid in coach_stats:
        coach_stats[fid].sort(key=lambda x: (-x["usageRate"], -x["uses"], -x["avgPts"], x["coachId"]))

    # Formation vs formation matchup stats (with significance filter).
    # We test uplift/downlift of formation win rate against each opponent
    # vs the formation's global win rate.
    matchup_raw = defaultdict(lambda: defaultdict(lambda: {"matches": 0, "wins": 0}))
    for rows in match_rows_by_key.values():
        if len(rows) != 2:
            continue
        a, b = rows[0], rows[1]
        fa = to_int(a.get("formation_id"))
        fb = to_int(b.get("formation_id"))
        if fa <= 0 or fb <= 0:
            continue
        ra = (a.get("result") or "").strip().upper()
        rb = (b.get("result") or "").strip().upper()

        matchup_raw[fa][fb]["matches"] += 1
        matchup_raw[fb][fa]["matches"] += 1
        if ra == "W":
            matchup_raw[fa][fb]["wins"] += 1
        if rb == "W":
            matchup_raw[fb][fa]["wins"] += 1

    # Relaxed thresholds so matchup lists are populated more often while
    # keeping a minimum sample size and effect-size guardrail.
    min_matchups = 8
    min_abs_delta = 0.04
    min_abs_z = 1.28  # approx 80% two-sided z-threshold
    matchup_stats = defaultdict(lambda: {"strongAgainst": [], "weakAgainst": []})

    for fid, opp_map in matchup_raw.items():
        uses = formation_team_counts[fid]
        if uses <= 0:
            continue
        p0 = formation_win_counts[fid] / uses
        strong = []
        weak = []
        for opp_id, stat in opp_map.items():
            n = int(stat["matches"] or 0)
            if n < min_matchups:
                continue
            wins = int(stat["wins"] or 0)
            p_hat = wins / n if n else 0.0
            delta = p_hat - p0
            variance = (p0 * (1.0 - p0) / n) if n > 0 else 0.0
            if variance <= 0:
                continue
            z = delta / math.sqrt(variance)
            if abs(delta) < min_abs_delta or abs(z) < min_abs_z:
                continue
            row = {
                "formationId": int(opp_id),
                "matches": n,
                "wins": wins,
                "winRate": round(p_hat, 6),
                "overallWinRate": round(p0, 6),
                "delta": round(delta, 6),
                "zScore": round(z, 4),
            }
            if delta > 0:
                strong.append(row)
            else:
                weak.append(row)

        strong.sort(key=lambda x: (-x["delta"], -x["matches"], x["formationId"]))
        weak.sort(key=lambda x: (x["delta"], -x["matches"], x["formationId"]))
        matchup_stats[fid] = {
            "strongAgainst": strong[:5],
            "weakAgainst": weak[:5],
            "criteria": {
                "minMatches": min_matchups,
                "minAbsDelta": min_abs_delta,
                "minAbsZScore": min_abs_z,
            },
        }

    formations = []
    for fid in sorted(formation_by_id):
        f = formation_by_id[fid]
        uses = formation_team_counts[fid]
        wins = formation_win_counts[fid]
        usage_rate = (uses / total_team_rows) if total_team_rows else 0.0
        win_rate = (wins / uses) if uses else 0.0

        obtainables = sorted(formation_to_coaches_all[fid], key=lambda x: (-x["depth"], x["coachId"]))
        depth4 = sorted(formation_to_coaches_depth4[fid], key=lambda x: x["coachId"])

        f_item = {
            **f,
            "cc": {
                "uses": uses,
                "wins": wins,
                "usageRate": round(usage_rate, 6),
                "winRate": round(win_rate, 6),
            },
            "coaches": {
                "obtainable": [
                    {
                        "id": row["coachId"],
                        "name": coach_by_id[row["coachId"]]["name"],
                        "depth": row["depth"],
                    }
                    for row in obtainables
                ],
                "depth4": [
                    {
                        "id": row["coachId"],
                        "name": coach_by_id[row["coachId"]]["name"],
                        "depth": row["depth"],
                    }
                    for row in depth4
                ],
            },
            "slotTop": {
                str(slot): slot_top[fid][slot]
                for slot in sorted(slot_top[fid])
            },
            "slotStats": {
                str(slot): slot_stats[fid][slot]
                for slot in sorted(slot_stats[fid])
            },
            "coachStats": coach_stats[fid],
            "matchups": matchup_stats[fid],
        }
        formations.append(f_item)

    coaches = []
    for cid in sorted(coach_by_id):
        c = coach_by_id[cid]
        rel = coach_to_formations[cid]
        rel4 = coach_to_formations_depth4[cid]
        coaches.append({
            **c,
            "formationDepth4": [x["formationId"] for x in rel4],
            "formationObtainable": [x["formationId"] for x in rel],
        })

    return {
        "meta": {
            "generatedFrom": {
                "ccTeamRows": len(team_rows),
                "ccPlayerRows": len(player_rows),
                "formationCount": len(formations),
                "coachCount": len(coaches),
                "totalTeamRowsForUsage": total_team_rows,
            }
        },
        "formations": formations,
        "coaches": coaches,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-csv-dir", default="/Users/k.nishimura/Desktop/csv data")
    parser.add_argument("--cc-dir", default="/Users/k.nishimura/Desktop/CC_match_result_csv")
    parser.add_argument(
        "--cc-db",
        default=str(Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3"),
        help="SQLite DB path for CC match data (if exists, this is used instead of --cc-dir CSV)",
    )
    parser.add_argument(
        "--master-db",
        default="",
        help="Unified master SQLite DB path (if set and exists, this is used as full source)",
    )
    parser.add_argument("--out", default="/Users/k.nishimura/work/coding/websoccer-player-search/app/formations_data.json")
    args = parser.parse_args()

    master_db_path = Path(args.master_db).expanduser().resolve() if args.master_db else None
    if master_db_path and master_db_path.exists():
        src = load_sources_from_master_db(master_db_path)
        print(f"using master db: {master_db_path}")
    else:
        src = load_sources(Path(args.base_csv_dir), Path(args.cc_dir))
        cc_db_path = Path(args.cc_db).expanduser().resolve()
        if cc_db_path.exists():
            src.update(load_cc_from_db(cc_db_path))
            print(f"using cc db: {cc_db_path}")
        else:
            print(f"cc db not found, fallback csv: {Path(args.cc_dir).expanduser().resolve()}")
    out = build_data(src)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"formations={len(out['formations'])} coaches={len(out['coaches'])}")


if __name__ == "__main__":
    main()
