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


def points_from_row(row):
    res = str(row.get("result") or "").strip().upper()
    if res == "W":
        return 3.0
    if res == "D":
        return 1.0
    if res == "L":
        return 0.0
    gf = to_float(row.get("goals_for"), None)
    ga = to_float(row.get("goals_against"), None)
    if gf is None or ga is None:
        return None
    if gf > ga:
        return 3.0
    if gf == ga:
        return 1.0
    return 0.0


def cc_round_rank(title):
    s = str(title or "")
    if "決勝" in s and "準決勝" not in s and "準々決勝" not in s:
        return 5
    if "準決勝" in s:
        return 4
    if "準々決勝" in s or "ベスト8" in s:
        return 3
    if "ベスト16" in s:
        return 2
    if "グループ" in s:
        return 1
    return 0


def finish_label_from_rank(rank, final_result=None, final_side=None, final_pk_winner_side=None):
    if rank >= 5:
        if str(final_result or "").strip().upper() == "W" or (
            final_pk_winner_side and str(final_pk_winner_side).strip().lower() == str(final_side or "").strip().lower()
        ):
            return "Champion"
        return "Runner-up"
    if rank == 4:
        return "Best 4"
    if rank == 3:
        return "Best 8"
    if rank == 2:
        return "Best 16"
    return "GL Exit"


def team_instance_key(row):
    return (
        to_int(row.get("season")),
        to_int(row.get("world_id")),
        to_int(row.get("match_id")),
        str(row.get("side") or "").strip().lower(),
        to_int(row.get("team_id")),
    )


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
        "match_level": read_csv(cc_dir / "normalized" / "match_level.csv"),
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
            "match_level": [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT
                      season,
                      world_id,
                      match_id,
                      title,
                      pk_winner_side
                    FROM cc_matches
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
        match_rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT
                  season,
                  world_id,
                  match_id,
                  title,
                  pk_winner_side
                FROM matches
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
        return {"match_level": match_rows, "team_level": team_rows, "player_level": player_rows}
    finally:
        conn.close()


def build_data(src):
    formation_rows = src["formation"]
    formation_info_rows = src["formation_info"]
    key_rows = src["formation_key"]
    pos_rows = src["formation_pos"]
    coach_rows = src["coach"]
    understanding_rows = src["coach_understanding"]
    match_rows = src.get("match_level", [])
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
    formation_goal_diff_sum = defaultdict(float)
    formation_goal_diff_sq_sum = defaultdict(float)
    formation_goal_diff_n = defaultdict(int)
    total_team_rows = 0
    coach_use_count = defaultdict(int)  # (formation, coach) -> use count
    coach_pts_sum = defaultdict(float)  # (formation, coach) -> sum pts
    coach_name_by_id = {}
    match_rows_by_key = defaultdict(list)
    team_row_by_instance = {}
    team_season_match_count = defaultdict(int)
    match_info_by_key = {}
    team_season_finish = {}

    for row in match_rows:
        mkey = (to_int(row.get("season")), to_int(row.get("world_id")), to_int(row.get("match_id")))
        match_info_by_key[mkey] = {
            "title": row.get("title") or "",
            "roundRank": cc_round_rank(row.get("title")),
            "pkWinnerSide": row.get("pk_winner_side") or "",
        }

    for row in team_rows:
        fid = to_int(row.get("formation_id"))
        if fid not in formation_by_id:
            continue
        total_team_rows += 1
        formation_team_counts[fid] += 1
        if (row.get("result") or "").strip().upper() == "W":
            formation_win_counts[fid] += 1
        gf = to_float(row.get("goals_for"), None)
        ga = to_float(row.get("goals_against"), None)
        if gf is not None and ga is not None:
            gd = gf - ga
            formation_goal_diff_sum[fid] += gd
            formation_goal_diff_sq_sum[fid] += gd * gd
            formation_goal_diff_n[fid] += 1
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
        team_row_by_instance[team_instance_key(row)] = row
        team_season_match_count[(to_int(row.get("season")), to_int(row.get("team_id")))] += 1
        finish_key = (to_int(row.get("season")), to_int(row.get("team_id")))
        match_info = match_info_by_key.get(mkey, {})
        round_rank = int(match_info.get("roundRank") or 0)
        prev = team_season_finish.get(finish_key)
        if not prev or round_rank > int(prev.get("roundRank") or 0):
            team_season_finish[finish_key] = {
                "roundRank": round_rank,
                "label": finish_label_from_rank(
                    round_rank,
                    row.get("result"),
                    row.get("side"),
                    match_info.get("pkWinnerSide"),
                ),
            }

    # Slot usage and pts by (formation, slot, player)
    formation_slot_total = defaultdict(int)
    slot_player_count = defaultdict(int)
    slot_player_pts_sum = defaultdict(float)
    slot_player_name = {}
    slot_player_fullname = {}
    starting_members_by_instance = defaultdict(list)

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
        slot_player_fullname[pid] = row.get("player_fullname") or row.get("player_name") or str(pid)
        starting_members_by_instance[team_instance_key(row)].append({
            "slot": slot,
            "playerId": pid,
            "playerName": row.get("player_name") or row.get("player_fullname") or str(pid),
            "playerFullName": row.get("player_fullname") or row.get("player_name") or str(pid),
            "pos": to_int(row.get("pos_code_1_4")),
            "ptsSum": to_float(row.get("pts"), 0.0),
        })

    slot_stats = defaultdict(lambda: defaultdict(list))
    slot_top = defaultdict(dict)

    for (fid, slot, pid), count in slot_player_count.items():
        denom = formation_slot_total[(fid, slot)] or 1
        rate = count / denom
        pts_avg = slot_player_pts_sum[(fid, slot, pid)] / count if count else 0.0
        pts_sum = slot_player_pts_sum[(fid, slot, pid)]
        item = {
            "playerId": pid,
            "playerName": slot_player_name.get(pid, str(pid)),
            "playerFullName": slot_player_fullname.get(pid, slot_player_name.get(pid, str(pid))),
            "uses": count,
            "usageRate": round(rate, 6),
            "ptsSum": round(pts_sum, 4),
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
            "ptsSum": round(coach_pts_sum[(fid, cid)], 4),
            "avgPts": round(avg_pts, 4),
        })
    for fid in coach_stats:
        coach_stats[fid].sort(key=lambda x: (-x["usageRate"], -x["uses"], -x["avgPts"], x["coachId"]))

    best_team_groups = {}
    for instance_key, members in starting_members_by_instance.items():
        team = team_row_by_instance.get(instance_key)
        if not team:
            continue
        fid = to_int(team.get("formation_id"))
        cid = to_int(team.get("headcoach_id"))
        season = to_int(team.get("season"))
        team_id = to_int(team.get("team_id"))
        if fid not in formation_by_id or cid <= 0 or season <= 0 or team_id <= 0:
            continue
        lineup = sorted(members, key=lambda x: x["slot"])
        if len(lineup) != 11 or len({m["slot"] for m in lineup}) != 11:
            continue
        lineup_signature = tuple((int(m["slot"]), int(m["playerId"])) for m in lineup)
        group_key = (season, team_id, fid, cid, lineup_signature)
        if group_key not in best_team_groups:
            team_season_matches = team_season_match_count[(season, team_id)]
            best_team_groups[group_key] = {
                "formationId": fid,
                "season": season,
                "teamId": team_id,
                "teamName": team.get("team_name") or "",
                "teamSeasonMatches": team_season_matches,
                "coach": {
                    "id": cid,
                    "name": team.get("headcoach_name") or coach_name_by_id.get(cid, str(cid)),
                    "ptsSum": 0.0,
                },
                "matches": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "points": 0.0,
                "goalsFor": 0,
                "goalsAgainst": 0,
                "goalDiff": 0,
                "playerPtsSum": 0.0,
                "membersBySlot": {int(m["slot"]): {**m} for m in lineup},
            }
        group = best_team_groups[group_key]
        group["matches"] += 1
        result = str(team.get("result") or "").strip().upper()
        if result == "W":
            group["wins"] += 1
        elif result == "D":
            group["draws"] += 1
        elif result == "L":
            group["losses"] += 1
        points = points_from_row(team) or 0.0
        gf = to_int(team.get("goals_for"))
        ga = to_int(team.get("goals_against"))
        group["points"] += points
        group["goalsFor"] += gf
        group["goalsAgainst"] += ga
        group["goalDiff"] += gf - ga
        coach_pts = to_float(team.get("headcoach_pts"), 0.0)
        group["coach"]["ptsSum"] += coach_pts
        for member in lineup:
            slot = int(member["slot"])
            pts = float(member.get("ptsSum") or 0.0)
            group["playerPtsSum"] += pts
            group["membersBySlot"][slot]["ptsSum"] = float(group["membersBySlot"][slot].get("ptsSum") or 0.0) + pts

    best_teams = defaultdict(list)
    for group in best_team_groups.values():
        matches = int(group["matches"] or 0)
        if matches <= 0:
            continue
        team_season_matches = int(group.get("teamSeasonMatches") or 0)
        if team_season_matches > 0 and matches != team_season_matches:
            continue
        members = []
        for slot in sorted(group["membersBySlot"]):
            member = group["membersBySlot"][slot]
            pts_sum = float(member.get("ptsSum") or 0.0)
            player_id = int(member.get("playerId") or 0)
            slot_usage_rate = 0
            for row in slot_stats[group["formationId"]].get(slot, []):
                if int(row.get("playerId") or 0) == player_id:
                    slot_usage_rate = row.get("usageRate", 0)
                    break
            members.append({
                "slot": slot,
                "playerId": player_id,
                "playerName": member.get("playerName") or "",
                "playerFullName": member.get("playerFullName") or member.get("playerName") or "",
                "pos": int(member.get("pos") or 0),
                "usageRate": slot_usage_rate,
                "ptsSum": round(pts_sum, 4),
                "avgPts": round(pts_sum / matches, 4),
            })
        coach_pts_sum = float(group["coach"].get("ptsSum") or 0.0)
        item = {
            "method": "season_team_same_coach_formation_lineup",
            "season": group["season"],
            "teamId": group["teamId"],
            "teamName": group["teamName"],
            "finish": team_season_finish.get((group["season"], group["teamId"]), {}).get("label", "GL Exit"),
            "matches": matches,
            "teamSeasonMatches": team_season_matches,
            "wins": int(group["wins"] or 0),
            "draws": int(group["draws"] or 0),
            "losses": int(group["losses"] or 0),
            "points": round(float(group["points"] or 0.0), 4),
            "goalsFor": int(group["goalsFor"] or 0),
            "goalsAgainst": int(group["goalsAgainst"] or 0),
            "goalDiff": int(group["goalDiff"] or 0),
            "score": int(group["wins"] or 0),
            "playerPtsSum": round(float(group["playerPtsSum"] or 0.0), 4),
            "avgPlayerPts": round(float(group["playerPtsSum"] or 0.0) / (matches * 11), 4),
            "coach": {
                "id": group["coach"]["id"],
                "name": group["coach"]["name"],
                "ptsSum": round(coach_pts_sum, 4),
                "avgPts": round(coach_pts_sum / matches, 4),
            },
            "members": members,
        }
        best_teams[group["formationId"]].append(item)

    for fid in best_teams:
        best_teams[fid].sort(
            key=lambda x: (
                -int(x.get("wins") or 0),
                -int(x.get("goalDiff") or 0),
                -int(x.get("goalsFor") or 0),
                -float(x.get("points") or 0.0),
                -int(x.get("matches") or 0),
                -int(x.get("season") or 0),
                str(x.get("teamName") or ""),
                int(x.get("teamId") or 0),
            )
        )
        for idx, team in enumerate(best_teams[fid][:5], start=1):
            team["rank"] = idx

    # Formation vs formation matchup stats (with significance filter).
    # Primary metric: strength-adjusted expected-points residual.
    # Why this metric:
    # - Handles draw-heavy formations better than pure win-rate.
    # - Avoids over-penalizing strong-but-low-margin styles from GD-only view.
    # - Controls for baseline formation strength on both sides.
    #
    # Points model:
    #   observedPts = 3/1/0 (W/D/L)
    #   expectedPts(fid vs opp) ~= global_mu + rating(fid) - rating(opp)
    # where rating(*) is fitted from all team-level rows by simple regularized
    # gradient updates.
    formation_mu_pts = {}
    formation_pts_sum = defaultdict(float)
    formation_pts_n = defaultdict(int)
    obs_rows = []
    total_pts = 0.0
    total_n = 0
    for rows in match_rows_by_key.values():
        if len(rows) != 2:
            continue
        a, b = rows[0], rows[1]
        fa = to_int(a.get("formation_id"))
        fb = to_int(b.get("formation_id"))
        if fa <= 0 or fb <= 0:
            continue
        pa = points_from_row(a)
        pb = points_from_row(b)
        if pa is None or pb is None:
            continue
        obs_rows.append((fa, fb, pa))
        obs_rows.append((fb, fa, pb))
        formation_pts_sum[fa] += pa
        formation_pts_sum[fb] += pb
        formation_pts_n[fa] += 1
        formation_pts_n[fb] += 1
        total_pts += pa + pb
        total_n += 2

    for fid, n in formation_pts_n.items():
        if n > 0:
            formation_mu_pts[fid] = formation_pts_sum[fid] / n

    global_mu_pts = (total_pts / total_n) if total_n else 1.0
    ratings = {fid: 0.0 for fid in formation_pts_n.keys()}
    if obs_rows:
        lr = 0.01
        l2 = 0.001
        for _ in range(120):
            for fa, fb, p_obs in obs_rows:
                ra = ratings.get(fa, 0.0)
                rb = ratings.get(fb, 0.0)
                pred = global_mu_pts + ra - rb
                err = p_obs - pred
                ratings[fa] = ra + lr * (err - l2 * ra)
                ratings[fb] = rb - lr * (err + l2 * rb)
            if ratings:
                mean_r = sum(ratings.values()) / len(ratings)
                for fid in ratings:
                    ratings[fid] -= mean_r

    matchup_raw = defaultdict(
        lambda: defaultdict(
            lambda: {
                "matches": 0,
                "goalDiffSum": 0.0,
                "pointsSum": 0.0,
                "expectedPointsSum": 0.0,
                "residualSum": 0.0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
            }
        )
    )
    formation_residual_sum = defaultdict(float)
    formation_residual_sq_sum = defaultdict(float)
    formation_residual_n = defaultdict(int)
    for rows in match_rows_by_key.values():
        if len(rows) != 2:
            continue
        a, b = rows[0], rows[1]
        fa = to_int(a.get("formation_id"))
        fb = to_int(b.get("formation_id"))
        if fa <= 0 or fb <= 0:
            continue
        gfa = to_float(a.get("goals_for"), None)
        gaa = to_float(a.get("goals_against"), None)
        gfb = to_float(b.get("goals_for"), None)
        gab = to_float(b.get("goals_against"), None)
        if gfa is None or gaa is None or gfb is None or gab is None:
            continue

        gd_a = gfa - gaa
        gd_b = gfb - gab
        p_a = points_from_row(a)
        p_b = points_from_row(b)
        if p_a is None or p_b is None:
            continue

        exp_a = global_mu_pts + ratings.get(fa, 0.0) - ratings.get(fb, 0.0)
        exp_b = global_mu_pts + ratings.get(fb, 0.0) - ratings.get(fa, 0.0)
        res_a = p_a - exp_a
        res_b = p_b - exp_b

        matchup_raw[fa][fb]["matches"] += 1
        matchup_raw[fb][fa]["matches"] += 1
        matchup_raw[fa][fb]["goalDiffSum"] += gd_a
        matchup_raw[fb][fa]["goalDiffSum"] += gd_b
        matchup_raw[fa][fb]["pointsSum"] += p_a
        matchup_raw[fb][fa]["pointsSum"] += p_b
        matchup_raw[fa][fb]["expectedPointsSum"] += exp_a
        matchup_raw[fb][fa]["expectedPointsSum"] += exp_b
        matchup_raw[fa][fb]["residualSum"] += res_a
        matchup_raw[fb][fa]["residualSum"] += res_b
        if p_a >= 2.5:
            matchup_raw[fa][fb]["wins"] += 1
            matchup_raw[fb][fa]["losses"] += 1
        elif p_a >= 0.5:
            matchup_raw[fa][fb]["draws"] += 1
            matchup_raw[fb][fa]["draws"] += 1
        else:
            matchup_raw[fa][fb]["losses"] += 1
            matchup_raw[fb][fa]["wins"] += 1

        formation_residual_sum[fa] += res_a
        formation_residual_sum[fb] += res_b
        formation_residual_sq_sum[fa] += res_a * res_a
        formation_residual_sq_sum[fb] += res_b * res_b
        formation_residual_n[fa] += 1
        formation_residual_n[fb] += 1

    # Matchup ranking tuned for practical comparison:
    # - primary metric: strength-adjusted points residual (AdjPts)
    # - guardrail: minimum sample, then show the strongest/weakest ranked deltas.
    min_matchups = 15
    matchup_stats = defaultdict(lambda: {"strongAgainst": [], "weakAgainst": []})

    for fid, opp_map in matchup_raw.items():
        rn = formation_residual_n[fid]
        if rn <= 0:
            continue
        var0 = (formation_residual_sq_sum[fid] / rn) - ((formation_residual_sum[fid] / rn) ** 2)
        if var0 <= 1e-9:
            continue
        strong = []
        weak = []
        for opp_id, stat in opp_map.items():
            if int(opp_id) == int(fid):
                continue
            n = int(stat["matches"] or 0)
            if n < min_matchups:
                continue
            gd_sum = float(stat["goalDiffSum"] or 0.0)
            pts_sum = float(stat["pointsSum"] or 0.0)
            exp_pts_sum = float(stat["expectedPointsSum"] or 0.0)
            residual_sum = float(stat["residualSum"] or 0.0)
            mu_hat = gd_sum / n if n else 0.0
            pts_hat = pts_sum / n if n else 0.0
            exp_pts_hat = exp_pts_sum / n if n else 0.0
            delta = residual_sum / n if n else 0.0
            z = delta / math.sqrt(var0 / n)
            row = {
                "formationId": int(opp_id),
                "matches": n,
                "wins": int(stat["wins"] or 0),
                "draws": int(stat["draws"] or 0),
                "losses": int(stat["losses"] or 0),
                "goalDiffSum": round(gd_sum, 4),
                "goalDiffPerMatch": round(mu_hat, 6),
                "pointsPerMatch": round(pts_hat, 6),
                "expectedPointsPerMatch": round(exp_pts_hat, 6),
                "overallPointsPerMatch": round(formation_mu_pts.get(fid, global_mu_pts), 6),
                "residualPointsPerMatch": round(delta, 6),
                "delta": round(delta, 6),
                "zScore": round(z, 4),
            }
            if n >= 40:
                row["confidence"] = "High"
            elif n >= 25:
                row["confidence"] = "Mid"
            else:
                row["confidence"] = "Low"
            if delta > 0:
                strong.append(row)
            elif delta < 0:
                weak.append(row)

        strong.sort(key=lambda x: (-x["delta"], -x["matches"], x["formationId"]))
        weak.sort(key=lambda x: (x["delta"], -x["matches"], x["formationId"]))
        matchup_stats[fid] = {
            "strongAgainst": strong[:5],
            "weakAgainst": weak[:5],
            "criteria": {
                "minMatches": min_matchups,
                "method": "ranked_strength_adjusted_points_residual",
                "ranking": "top_bottom_delta_adj_pts",
                "confidenceBands": {
                    "low": [15, 24],
                    "mid": [25, 39],
                    "high": [40, None],
                },
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
            "bestTeams": best_teams[fid][:5],
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
