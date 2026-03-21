#!/usr/bin/env python3
import argparse
import csv
import json
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

        # Use current-era formations only (stride=1).
        # In this dataset, obtainable/depth4 sets are encoded as depth=2/4.
        stride = to_int(formation_by_id[fid].get("stride"))
        if stride != 1:
            continue

        if depth == 2:
            coach_to_formations[cid].append({"formationId": fid, "depth": depth})
            formation_to_coaches_all[fid].append({"coachId": cid, "depth": depth})
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
    parser.add_argument("--out", default="/Users/k.nishimura/work/coding/websoccer-player-search/app/formations_data.json")
    args = parser.parse_args()

    src = load_sources(Path(args.base_csv_dir), Path(args.cc_dir))
    out = build_data(src)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"formations={len(out['formations'])} coaches={len(out['coaches'])}")


if __name__ == "__main__":
    main()
