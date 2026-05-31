#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean


DEFAULT_DB = Path("/Users/gigagigo/Codex/WebSoccer/wsc_data/websoccer_master_db/wsm_2605251903.sqlite3")
DEFAULT_OUT = Path("app/prepared/local/cc_player_swap_analysis")
DEFAULT_TEAM_POWER = Path("app/prepared/cc_team_power_scores.csv")


@dataclass(frozen=True)
class Appearance:
    appearance_id: str
    season: int
    world_id: int
    match_id: int
    side: str
    team_id: int
    team_name: str
    formation_id: int
    formation_name: str
    headcoach_id: int
    headcoach_name: str
    goals_for: int
    goals_against: int
    result: str
    points: int
    starters_by_order: tuple[tuple[int, int, int, str, str], ...]
    cc_count: int
    opponent_team_power: float | None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze CC-player one-slot lineup swaps in CC match history.")
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--team-power-csv", default=str(DEFAULT_TEAM_POWER))
    return p.parse_args()


def dict_rows(con: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    con.row_factory = sqlite3.Row
    return [dict(row) for row in con.execute(sql, params)]


def point_value(result: str) -> int:
    return 3 if result == "W" else 1 if result == "D" else 0


def load_team_power(path: Path) -> dict[tuple[int, int, int], float]:
    out: dict[tuple[int, int, int], float] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                out[(int(row["season"]), int(row["worldId"]), int(row["teamId"]))] = float(row["teamPower"])
            except Exception:
                continue
    return out


def load_appearances(con: sqlite3.Connection, team_power: dict[tuple[int, int, int], float]) -> tuple[list[Appearance], dict[int, dict]]:
    cc_players = {
        int(row["player_id"])
        for row in dict_rows(
            con,
            """
            SELECT player_id
            FROM manual_player_category
            WHERE category = 'CC' OR category_membership_json LIKE '%"CC"%'
            """,
        )
    }
    name_rows = dict_rows(
        con,
        """
        SELECT c.player_id, c.category, p.ZFULLNAME AS fullname
        FROM manual_player_category c
        LEFT JOIN ao__ZMOPLAYER p ON p.ZPLAYER_ID = c.player_id
        WHERE c.category = 'CC' OR c.category_membership_json LIKE '%"CC"%'
        ORDER BY c.player_id
        """,
    )
    cc_meta = {int(row["player_id"]): row for row in name_rows}

    players_by_app: defaultdict[tuple[int, int, int, str], list[dict]] = defaultdict(list)
    for row in dict_rows(
        con,
        """
        SELECT
          p.season, p.world_id, p.match_id, p.side, p.member_order,
          p.player_id, p.player_fullname, p.player_name,
          COALESCE(i.canonical_person_id, p.player_id) AS canonical_person_id
        FROM cc_players p
        LEFT JOIN player_person_identity i ON i.player_id = p.player_id
        WHERE p.is_starting11 = 1
        """,
    ):
        key = (int(row["season"]), int(row["world_id"]), int(row["match_id"]), str(row["side"]))
        players_by_app[key].append(row)

    team_rows = dict_rows(
        con,
        """
        SELECT
          season, world_id, match_id, side, team_id, team_name,
          formation_id, formation_name, headcoach_id, headcoach_name,
          goals_for, goals_against, result
        FROM cc_teams
        """,
    )
    by_match: defaultdict[tuple[int, int, int], list[dict]] = defaultdict(list)
    for row in team_rows:
        by_match[(int(row["season"]), int(row["world_id"]), int(row["match_id"]))].append(row)
    opponent_team_by_app: dict[tuple[int, int, int, str], int] = {}
    for match_key, rows in by_match.items():
        if len(rows) < 2:
            continue
        for row in rows:
            side = str(row["side"])
            opponent = next((other for other in rows if str(other["side"]) != side), None)
            if opponent:
                opponent_team_by_app[(*match_key, side)] = int(opponent["team_id"] or 0)

    appearances: list[Appearance] = []
    for row in team_rows:
        key = (int(row["season"]), int(row["world_id"]), int(row["match_id"]), str(row["side"]))
        starters = sorted(players_by_app.get(key, []), key=lambda r: int(r["member_order"]))
        if len(starters) != 11:
            continue
        starter_tuple = tuple(
            (
                int(r["member_order"]),
                int(r["player_id"]),
                int(r["canonical_person_id"] or r["player_id"]),
                "CC" if int(r["player_id"]) in cc_players else "nonCC",
                str(r["player_fullname"] or r["player_name"] or r["player_id"]),
            )
            for r in starters
        )
        result = str(row["result"] or "")
        appearances.append(
            Appearance(
                appearance_id=f"{row['season']}-{row['world_id']}-{row['match_id']}-{row['side']}",
                season=int(row["season"]),
                world_id=int(row["world_id"]),
                match_id=int(row["match_id"]),
                side=str(row["side"]),
                team_id=int(row["team_id"] or 0),
                team_name=str(row["team_name"] or ""),
                formation_id=int(row["formation_id"] or 0),
                formation_name=str(row["formation_name"] or ""),
                headcoach_id=int(row["headcoach_id"] or 0),
                headcoach_name=str(row["headcoach_name"] or ""),
                goals_for=int(row["goals_for"] or 0),
                goals_against=int(row["goals_against"] or 0),
                result=result,
                points=point_value(result),
                starters_by_order=starter_tuple,
                cc_count=sum(1 for r in starters if int(r["player_id"]) in cc_players),
                opponent_team_power=team_power.get(
                    (
                        int(row["season"]),
                        int(row["world_id"]),
                        opponent_team_by_app.get(key, 0),
                    )
                ),
            )
        )
    return appearances, cc_meta


def build_pairs(appearances: list[Appearance], *, include_coach: bool) -> list[dict]:
    buckets: defaultdict[tuple, list[tuple[Appearance, tuple[int, int, str, str]]]] = defaultdict(list)
    for app in appearances:
        for omitted in app.starters_by_order:
            order = omitted[0]
            retained = tuple((o, canonical_pid) for o, _pid, canonical_pid, _cat, _name in app.starters_by_order if o != order)
            key = (app.formation_id, order, retained)
            if include_coach:
                key = (app.formation_id, app.headcoach_id, order, retained)
            buckets[key].append((app, omitted))

    seen: set[tuple[str, str, tuple]] = set()
    pairs: list[dict] = []
    for key, rows in buckets.items():
        if len(rows) < 2:
            continue
        for i in range(len(rows)):
            app_a, omitted_a = rows[i]
            for j in range(i + 1, len(rows)):
                app_b, omitted_b = rows[j]
                if app_a.appearance_id == app_b.appearance_id:
                    continue
                if omitted_a[2] == omitted_b[2]:
                    continue
                a_is_cc = omitted_a[3] == "CC"
                b_is_cc = omitted_b[3] == "CC"
                if a_is_cc == b_is_cc:
                    continue
                cc_app, cc_omitted, non_app, non_omitted = (
                    (app_a, omitted_a, app_b, omitted_b) if a_is_cc else (app_b, omitted_b, app_a, omitted_a)
                )
                pair_key = tuple(sorted([cc_app.appearance_id, non_app.appearance_id])) + (key,)
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                pairs.append(
                    {
                        "tier": "same_10_slots_same_coach" if include_coach else "same_10_slots",
                        "cc_app": cc_app,
                        "non_app": non_app,
                        "slot": cc_omitted[0],
                        "cc_player_id": cc_omitted[1],
                        "non_cc_player_id": non_omitted[1],
                        "cc_player": cc_omitted[4],
                        "non_cc_player": non_omitted[4],
                        "formation_name": cc_app.formation_name or non_app.formation_name,
                        "headcoach_name": cc_app.headcoach_name if include_coach else "",
                    }
                )
    return pairs


def build_swap_cells(appearances: list[Appearance], *, include_coach: bool) -> list[dict]:
    buckets: defaultdict[tuple, dict[int, list[tuple[Appearance, tuple[int, int, int, str, str]]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for app in appearances:
        for omitted in app.starters_by_order:
            order = omitted[0]
            retained = tuple((o, canonical_pid) for o, _pid, canonical_pid, _cat, _name in app.starters_by_order if o != order)
            key = (app.formation_id, order, retained)
            if include_coach:
                key = (app.formation_id, app.headcoach_id, order, retained)
            buckets[key][omitted[2]].append((app, omitted))

    cells: list[dict] = []
    for key, by_omitted_canonical in buckets.items():
        cc_groups = []
        non_groups = []
        for rows in by_omitted_canonical.values():
            omitted = rows[0][1]
            if omitted[3] == "CC":
                cc_groups.append(rows)
            else:
                non_groups.append(rows)
        for cc_rows in cc_groups:
            for non_rows in non_groups:
                cc_omitted = cc_rows[0][1]
                non_omitted = non_rows[0][1]
                cc_apps = [row[0] for row in cc_rows]
                non_apps = [row[0] for row in non_rows]
                cells.append(
                    {
                        "tier": "same_10_slots_same_coach" if include_coach else "same_10_slots",
                        "formation_name": cc_apps[0].formation_name or non_apps[0].formation_name,
                        "slot": cc_omitted[0],
                        "cc_player_id": cc_omitted[1],
                        "cc_player": cc_omitted[4],
                        "non_cc_player_id": non_omitted[1],
                        "non_cc_player": non_omitted[4],
                        "cc_appearances": len(cc_apps),
                        "non_cc_appearances": len(non_apps),
                        "cc_win_rate": mean([1 if app.result == "W" else 0 for app in cc_apps]),
                        "non_cc_win_rate": mean([1 if app.result == "W" else 0 for app in non_apps]),
                        "cc_avg_points": mean([app.points for app in cc_apps]),
                        "non_cc_avg_points": mean([app.points for app in non_apps]),
                        "avg_point_diff": mean([app.points for app in cc_apps])
                        - mean([app.points for app in non_apps]),
                        "cc_goal_diff": mean([app.goals_for - app.goals_against for app in cc_apps]),
                        "non_cc_goal_diff": mean([app.goals_for - app.goals_against for app in non_apps]),
                    }
                )
    return cells


def summarize_pairs(pairs: list[dict]) -> dict[str, object]:
    if not pairs:
        return {
            "pairs": 0,
            "cc_win_rate": "",
            "non_cc_win_rate": "",
            "cc_avg_points": "",
            "non_cc_avg_points": "",
            "avg_point_diff": "",
            "cc_goal_diff": "",
            "non_cc_goal_diff": "",
        }
    cc_points = [p["cc_app"].points for p in pairs]
    non_points = [p["non_app"].points for p in pairs]
    cc_wins = [1 if p["cc_app"].result == "W" else 0 for p in pairs]
    non_wins = [1 if p["non_app"].result == "W" else 0 for p in pairs]
    cc_gd = [p["cc_app"].goals_for - p["cc_app"].goals_against for p in pairs]
    non_gd = [p["non_app"].goals_for - p["non_app"].goals_against for p in pairs]
    return {
        "pairs": len(pairs),
        "cc_win_rate": mean(cc_wins),
        "non_cc_win_rate": mean(non_wins),
        "cc_avg_points": mean(cc_points),
        "non_cc_avg_points": mean(non_points),
        "avg_point_diff": mean([a - b for a, b in zip(cc_points, non_points)]),
        "cc_goal_diff": mean(cc_gd),
        "non_cc_goal_diff": mean(non_gd),
    }


def matched_appearances_from_pairs(pairs: list[dict]) -> tuple[list[Appearance], list[Appearance]]:
    cc_by_id: dict[str, Appearance] = {}
    non_by_id: dict[str, Appearance] = {}
    for pair in pairs:
        cc = pair["cc_app"]
        non = pair["non_app"]
        cc_by_id[cc.appearance_id] = cc
        non_by_id[non.appearance_id] = non
    return list(cc_by_id.values()), list(non_by_id.values())


def summarize_appearances(cc_apps: list[Appearance], non_apps: list[Appearance], *, comparison_pairs: int) -> dict[str, object]:
    if not cc_apps or not non_apps:
        return {
            "comparison_pairs": comparison_pairs,
            "cc_appearances": len(cc_apps),
            "non_cc_appearances": len(non_apps),
            "cc_win_rate": "",
            "non_cc_win_rate": "",
            "cc_avg_points": "",
            "non_cc_avg_points": "",
            "avg_point_diff": "",
            "cc_goal_diff": "",
            "non_cc_goal_diff": "",
        }
    cc_points = [app.points for app in cc_apps]
    non_points = [app.points for app in non_apps]
    cc_gd = [app.goals_for - app.goals_against for app in cc_apps]
    non_gd = [app.goals_for - app.goals_against for app in non_apps]
    cc_opp_power = [app.opponent_team_power for app in cc_apps if app.opponent_team_power is not None]
    non_opp_power = [app.opponent_team_power for app in non_apps if app.opponent_team_power is not None]
    return {
        "comparison_pairs": comparison_pairs,
        "cc_appearances": len(cc_apps),
        "non_cc_appearances": len(non_apps),
        "cc_win_rate": mean([1 if app.result == "W" else 0 for app in cc_apps]),
        "non_cc_win_rate": mean([1 if app.result == "W" else 0 for app in non_apps]),
        "cc_avg_points": mean(cc_points),
        "non_cc_avg_points": mean(non_points),
        "avg_point_diff": mean(cc_points) - mean(non_points),
        "cc_goal_diff": mean(cc_gd),
        "non_cc_goal_diff": mean(non_gd),
        "cc_avg_opp_power": mean(cc_opp_power) if cc_opp_power else "",
        "non_cc_avg_opp_power": mean(non_opp_power) if non_opp_power else "",
    }


def solve_linear_system(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    aug = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular matrix")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        aug[col] = [v / div for v in aug[col]]
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            if factor:
                aug[row] = [aug[row][i] - factor * aug[col][i] for i in range(n + 1)]
    return [aug[i][-1] for i in range(n)]


def ols_cc_coef(rows: list[dict], y_key: str) -> tuple[float | str, int]:
    clean = [row for row in rows if row["opponent_team_power"] is not None]
    if len(clean) < 10:
        return "", len(clean)
    formations = sorted({row["formation_id"] for row in clean})
    formation_cols = {formation: idx for idx, formation in enumerate(formations[1:], start=3)}
    opp_mean = mean([float(row["opponent_team_power"]) for row in clean])
    width = 3 + len(formation_cols)
    xtx = [[0.0] * width for _ in range(width)]
    xty = [0.0] * width
    for row in clean:
        x = [0.0] * width
        x[0] = 1.0
        x[1] = 1.0 if row["is_cc"] else 0.0
        x[2] = float(row["opponent_team_power"]) - opp_mean
        col = formation_cols.get(row["formation_id"])
        if col is not None:
            x[col] = 1.0
        y = float(row[y_key])
        for i in range(width):
            xty[i] += x[i] * y
            for j in range(width):
                xtx[i][j] += x[i] * x[j]
    try:
        beta = solve_linear_system(xtx, xty)
    except ValueError:
        return "", len(clean)
    return beta[1], len(clean)


def adjusted_summary_for_pairs(tier: str, pairs: list[dict]) -> dict[str, object]:
    cc_apps, non_apps = matched_appearances_from_pairs(pairs)
    rows = []
    for app in cc_apps:
        rows.append(
            {
                "is_cc": 1,
                "points": app.points,
                "win": 1 if app.result == "W" else 0,
                "opponent_team_power": app.opponent_team_power,
                "formation_id": app.formation_id,
            }
        )
    for app in non_apps:
        rows.append(
            {
                "is_cc": 0,
                "points": app.points,
                "win": 1 if app.result == "W" else 0,
                "opponent_team_power": app.opponent_team_power,
                "formation_id": app.formation_id,
            }
        )
    point_coef, point_n = ols_cc_coef(rows, "points")
    win_coef, win_n = ols_cc_coef(rows, "win")
    return {
        "tier": tier,
        "sample": min(point_n, win_n),
        "cc_adjusted_point_effect": point_coef,
        "cc_adjusted_win_rate_effect": win_coef,
        "controls": "opponent_team_power + formation_fixed_effect",
    }


def summarize_cells(cells: list[dict]) -> dict[str, object]:
    if not cells:
        return {
            "cells": 0,
            "cc_win_rate": "",
            "non_cc_win_rate": "",
            "cc_avg_points": "",
            "non_cc_avg_points": "",
            "avg_point_diff": "",
            "cc_goal_diff": "",
            "non_cc_goal_diff": "",
        }
    return {
        "cells": len(cells),
        "cc_win_rate": mean([c["cc_win_rate"] for c in cells]),
        "non_cc_win_rate": mean([c["non_cc_win_rate"] for c in cells]),
        "cc_avg_points": mean([c["cc_avg_points"] for c in cells]),
        "non_cc_avg_points": mean([c["non_cc_avg_points"] for c in cells]),
        "avg_point_diff": mean([c["avg_point_diff"] for c in cells]),
        "cc_goal_diff": mean([c["cc_goal_diff"] for c in cells]),
        "non_cc_goal_diff": mean([c["non_cc_goal_diff"] for c in cells]),
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize_by_formation(all_pairs: list[dict], coach_pairs: list[dict]) -> list[dict]:
    rows: list[dict] = []

    pair_groups: defaultdict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for aggregation, pairs in [
        ("raw_pair_weighted", all_pairs),
        ("raw_pair_weighted", coach_pairs),
    ]:
        for pair in pairs:
            pair_groups[(aggregation, pair["tier"], pair["formation_name"])].append(pair)

    for (aggregation, tier, formation), pairs in sorted(pair_groups.items(), key=lambda kv: (kv[0][0], kv[0][1], -len(kv[1]), kv[0][2])):
        cc_apps, non_apps = matched_appearances_from_pairs(pairs)
        summary = summarize_appearances(cc_apps, non_apps, comparison_pairs=len(pairs))
        rows.append(
            {
                "aggregation": aggregation,
                "tier": tier,
                "formation": formation,
                "comparison_pairs": summary["comparison_pairs"],
                "cc_appearances": summary["cc_appearances"],
                "non_cc_appearances": summary["non_cc_appearances"],
                "cc_win_rate": summary["cc_win_rate"],
                "non_cc_win_rate": summary["non_cc_win_rate"],
                "win_rate_diff": summary["cc_win_rate"] - summary["non_cc_win_rate"] if summary["cc_appearances"] and summary["non_cc_appearances"] else "",
                "cc_avg_points": summary["cc_avg_points"],
                "non_cc_avg_points": summary["non_cc_avg_points"],
                "avg_point_diff": summary["avg_point_diff"],
                "cc_goal_diff": summary["cc_goal_diff"],
                "non_cc_goal_diff": summary["non_cc_goal_diff"],
                "goal_diff_delta": summary["cc_goal_diff"] - summary["non_cc_goal_diff"] if summary["cc_appearances"] and summary["non_cc_appearances"] else "",
                "cc_avg_opp_power": summary.get("cc_avg_opp_power", ""),
                "non_cc_avg_opp_power": summary.get("non_cc_avg_opp_power", ""),
            }
        )

    return rows


def main() -> int:
    args = parse_args()
    db = Path(args.db).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    team_power_csv = Path(args.team_power_csv).expanduser().resolve()
    con = sqlite3.connect(db)
    appearances, cc_meta = load_appearances(con, load_team_power(team_power_csv))

    all_pairs = build_pairs(appearances, include_coach=False)
    coach_pairs = build_pairs(appearances, include_coach=True)
    summary_rows = []
    for tier, pairs in [("same_10_slots", all_pairs), ("same_10_slots_same_coach", coach_pairs)]:
        cc_apps, non_apps = matched_appearances_from_pairs(pairs)
        row = {"aggregation": "matched_appearance_weighted", "tier": tier}
        row.update(summarize_appearances(cc_apps, non_apps, comparison_pairs=len(pairs)))
        summary_rows.append(row)
    formation_summary_rows = summarize_by_formation(all_pairs, coach_pairs)
    adjusted_summary_rows = [
        adjusted_summary_for_pairs("same_10_slots", all_pairs),
        adjusted_summary_for_pairs("same_10_slots_same_coach", coach_pairs),
    ]

    pair_rows = []
    for p in all_pairs:
        cc = p["cc_app"]
        non = p["non_app"]
        pair_rows.append(
            {
                "tier": p["tier"],
                "formation": p["formation_name"],
                "slot": p["slot"],
                "cc_player_id": p["cc_player_id"],
                "cc_player": p["cc_player"],
                "non_cc_player_id": p["non_cc_player_id"],
                "non_cc_player": p["non_cc_player"],
                "cc_season": cc.season,
                "cc_world": cc.world_id,
                "cc_match": cc.match_id,
                "cc_team": cc.team_name,
                "cc_result": cc.result,
                "cc_points": cc.points,
                "cc_gf": cc.goals_for,
                "cc_ga": cc.goals_against,
                "non_cc_season": non.season,
                "non_cc_world": non.world_id,
                "non_cc_match": non.match_id,
                "non_cc_team": non.team_name,
                "non_cc_result": non.result,
                "non_cc_points": non.points,
                "non_cc_gf": non.goals_for,
                "non_cc_ga": non.goals_against,
                "point_diff_cc_minus_non": cc.points - non.points,
                "goal_diff_cc_minus_non": (cc.goals_for - cc.goals_against) - (non.goals_for - non.goals_against),
            }
        )

    cc_usage = []
    for pid, meta in cc_meta.items():
        starts = [app for app in appearances if any(pid == player_id for _o, player_id, _canonical_pid, cat, _name in app.starters_by_order if cat == "CC")]
        cc_usage.append(
            {
                "player_id": pid,
                "player": meta.get("fullname") or "",
                "starts": len(starts),
                "win_rate": mean([1 if a.result == "W" else 0 for a in starts]) if starts else "",
                "avg_points": mean([a.points for a in starts]) if starts else "",
                "avg_goal_diff": mean([a.goals_for - a.goals_against for a in starts]) if starts else "",
            }
        )

    write_csv(out_dir / "summary.csv", summary_rows, list(summary_rows[0].keys()))
    write_csv(out_dir / "formation_summary.csv", formation_summary_rows, list(formation_summary_rows[0].keys()))
    write_csv(out_dir / "adjusted_summary.csv", adjusted_summary_rows, list(adjusted_summary_rows[0].keys()))
    write_csv(
        out_dir / "one_slot_swap_pairs.csv",
        pair_rows,
        [
            "tier",
            "formation",
            "slot",
            "cc_player_id",
            "cc_player",
            "non_cc_player_id",
            "non_cc_player",
            "cc_season",
            "cc_world",
            "cc_match",
            "cc_team",
            "cc_result",
            "cc_points",
            "cc_gf",
            "cc_ga",
            "non_cc_season",
            "non_cc_world",
            "non_cc_match",
            "non_cc_team",
            "non_cc_result",
            "non_cc_points",
            "non_cc_gf",
            "non_cc_ga",
            "point_diff_cc_minus_non",
            "goal_diff_cc_minus_non",
        ],
    )
    write_csv(out_dir / "cc_player_usage.csv", cc_usage, list(cc_usage[0].keys()))

    report = [
        "# CC Player Swap Analysis",
        "",
        f"- DB: `{db}`",
        f"- Team power CSV: `{team_power_csv}`",
        f"- Team appearances with 11 starters: {len(appearances)}",
        f"- CC category players: {len(cc_meta)}",
        "",
        "## Pair Definition",
        "",
        "- `same_10_slots`: same formation, same 10 starters in the same member_order slots; the remaining one slot is CC vs non-CC.",
        "- `same_10_slots_same_coach`: same as above, also same headcoach id.",
        "",
        "## Summary",
        "",
        "| tier | comparison pairs | CC apps | non-CC apps | CC win% | non-CC win% | CC pts | non-CC pts | pts diff | CC GD | non-CC GD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        def fmt(v: object) -> str:
            return "" if v == "" else f"{float(v):.3f}" if isinstance(v, float) else str(v)
        report.append(
            f"| {row['tier']} | {row.get('comparison_pairs', '')} | {row.get('cc_appearances', '')} | {row.get('non_cc_appearances', '')} | {fmt(row['cc_win_rate'])} | {fmt(row['non_cc_win_rate'])} | "
            f"{fmt(row['cc_avg_points'])} | {fmt(row['non_cc_avg_points'])} | {fmt(row['avg_point_diff'])} | "
            f"{fmt(row['cc_goal_diff'])} | {fmt(row['non_cc_goal_diff'])} |"
        )
    report += [
        "",
        "## Files",
        "",
        f"- `{out_dir / 'summary.csv'}`",
        f"- `{out_dir / 'formation_summary.csv'}`",
        f"- `{out_dir / 'adjusted_summary.csv'}`",
        f"- `{out_dir / 'one_slot_swap_pairs.csv'}`",
        f"- `{out_dir / 'cc_player_usage.csv'}`",
        "",
        "## Caveats",
        "",
        "- This is an observational comparison, not a causal estimate.",
        "- `adjusted_summary.csv` controls opponent teamPower and formation fixed effects.",
        "- Home/away, tournament phase, and season/world strength are not yet controlled.",
        "- The strict one-slot definition favors cleaner comparisons but may produce sparse samples.",
        "- `comparison_pairs` can exceed match count because it is the number of eligible CC/non-CC combinations.",
        "- Use `cc_appearances` and `non_cc_appearances` as the actual sample sizes.",
        "- Formation-level rows with very small appearance counts should be treated as exploratory only.",
    ]
    (out_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"[DONE] appearances={len(appearances)} pairs={len(all_pairs)} coach_pairs={len(coach_pairs)}")
    print(f"[DONE] output={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
