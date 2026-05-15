#!/usr/bin/env python3
from __future__ import annotations

import csv
import argparse
import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_DIR = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db")
FORMATIONS_JSON = ROOT / "app" / "formations_data.json"
OUTPUT_JSON = ROOT / "app" / "v4_clean_uniform_data.json"
REPORT_HTML = ROOT / "app" / "prepared" / "team_power_index_reestimate.html"
REPORT_CSV = ROOT / "app" / "prepared" / "team_power_index_reestimate_metrics.csv"

PLAYER_EFFECT_PRIOR = 35.0
FORMATION_SLOT_EFFECT_PRIOR = 70.0
FORMATION_POWER_PRIOR = 45.0
COACH_POWER_PRIOR = 60.0
ITERATIONS = 32


@dataclass(frozen=True)
class TeamRow:
    season: int
    world_id: int
    match_id: int
    side: str
    formation_id: int
    formation_name: str
    headcoach_id: int
    headcoach_name: str
    headcoach_pts: Optional[float]
    goals_for: int
    goals_against: int


@dataclass(frozen=True)
class PlayerRow:
    season: int
    world_id: int
    match_id: int
    side: str
    slot: int
    player_id: int
    pts: float


@dataclass(frozen=True)
class FixedEffects:
    global_avg: float
    player_effect: Dict[int, float]
    formation_slot_effect: Dict[Tuple[int, int], float]
    player_counts: Dict[int, int]
    formation_slot_counts: Dict[Tuple[int, int], int]


def as_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def find_latest_master_db(db_dir: Path = DEFAULT_DB_DIR) -> Path:
    candidates = sorted(
        db_dir.glob("wsm_*.sqlite3"),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No master DB found under {db_dir}")
    return candidates[0]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Re-estimate Team Power Index data from the current websoccer master DB. "
            "By default, the newest wsm_*.sqlite3 under the local master DB directory is used."
        )
    )
    parser.add_argument("--db", type=Path, default=None, help="Master DB path. Defaults to the newest local wsm_*.sqlite3.")
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR, help="Directory used when --db is omitted.")
    parser.add_argument("--formations-json", type=Path, default=FORMATIONS_JSON, help="formations_data.json path.")
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON, help="Output JSON consumed by MyTeam.")
    parser.add_argument("--report-html", type=Path, default=REPORT_HTML, help="Analysis report HTML output.")
    parser.add_argument("--report-csv", type=Path, default=REPORT_CSV, help="Season holdout metrics CSV output.")
    return parser.parse_args(argv)


def load_formations(formations_json: Path = FORMATIONS_JSON) -> Dict[int, Dict[int, int]]:
    with formations_json.open(encoding="utf-8") as f:
        raw = json.load(f)
    result: Dict[int, Dict[int, int]] = {}
    for formation in raw.get("formations", []):
        fid = int(formation.get("id") or 0)
        if fid <= 0:
            continue
        keys: Dict[int, int] = {}
        for row in formation.get("keyPositions") or []:
            key_no = int(row.get("rank") or 0)
            slot_no = int(row.get("slot") or 0)
            if 1 <= key_no <= 4 and 1 <= slot_no <= 11:
                keys[key_no] = slot_no
        result[fid] = keys
    return result


def load_db(db_path: Path) -> Tuple[Dict[Tuple[int, int, int, str], TeamRow], Dict[Tuple[int, int, int, str], List[PlayerRow]]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        teams: Dict[Tuple[int, int, int, str], TeamRow] = {}
        for row in conn.execute(
            """
            SELECT season, world_id, match_id, side, formation_id, formation_name,
                   headcoach_id, headcoach_name, headcoach_pts,
                   goals_for, goals_against
            FROM cc_teams
            """
        ):
            key = (int(row["season"]), int(row["world_id"]), int(row["match_id"]), str(row["side"]))
            teams[key] = TeamRow(
                season=key[0],
                world_id=key[1],
                match_id=key[2],
                side=key[3],
                formation_id=int(row["formation_id"] or 0),
                formation_name=str(row["formation_name"] or ""),
                headcoach_id=int(row["headcoach_id"] or 0),
                headcoach_name=str(row["headcoach_name"] or ""),
                headcoach_pts=as_float(row["headcoach_pts"]),
                goals_for=int(row["goals_for"] or 0),
                goals_against=int(row["goals_against"] or 0),
            )

        players: Dict[Tuple[int, int, int, str], List[PlayerRow]] = defaultdict(list)
        for row in conn.execute(
            """
            SELECT season, world_id, match_id, side, member_order, player_id, pts
            FROM cc_players
            WHERE is_starting11 = 1
              AND pts IS NOT NULL
              AND player_id IS NOT NULL
              AND member_order BETWEEN 1 AND 11
            """
        ):
            pts = as_float(row["pts"])
            if pts is None:
                continue
            key = (int(row["season"]), int(row["world_id"]), int(row["match_id"]), str(row["side"]))
            players[key].append(
                PlayerRow(
                    season=key[0],
                    world_id=key[1],
                    match_id=key[2],
                    side=key[3],
                    slot=int(row["member_order"]),
                    player_id=int(row["player_id"]),
                    pts=pts,
                )
            )
        return teams, players
    finally:
        conn.close()


def estimate_rating_fixed_effects(
    teams: Mapping[Tuple[int, int, int, str], TeamRow],
    players_by_team: Mapping[Tuple[int, int, int, str], Sequence[PlayerRow]],
    seasons: Optional[set[int]] = None,
) -> FixedEffects:
    cells: Dict[Tuple[int, Tuple[int, int]], List[float]] = defaultdict(lambda: [0.0, 0.0])
    player_counts: Dict[int, int] = defaultdict(int)
    fs_counts: Dict[Tuple[int, int], int] = defaultdict(int)
    total_sum = 0.0
    total_n = 0

    for key, rows in players_by_team.items():
        team = teams.get(key)
        if team is None or (seasons is not None and team.season not in seasons):
            continue
        for row in rows:
            fs = (team.formation_id, row.slot)
            cell = cells[(row.player_id, fs)]
            cell[0] += row.pts
            cell[1] += 1.0
            player_counts[row.player_id] += 1
            fs_counts[fs] += 1
            total_sum += row.pts
            total_n += 1

    if total_n == 0:
        return FixedEffects(3.0, {}, {}, {}, {})

    global_avg = total_sum / total_n
    cell_means = [(player_id, fs, values[0] / values[1], values[1]) for (player_id, fs), values in cells.items()]
    player_effect = {player_id: 0.0 for player_id in player_counts}
    fs_effect = {fs: 0.0 for fs in fs_counts}

    for _ in range(ITERATIONS):
        accum: Dict[int, List[float]] = defaultdict(lambda: [0.0, 0.0])
        for player_id, fs, mean_pts, weight in cell_means:
            accum[player_id][0] += (mean_pts - global_avg - fs_effect.get(fs, 0.0)) * weight
            accum[player_id][1] += weight
        player_effect = {
            player_id: values[0] / (values[1] + PLAYER_EFFECT_PRIOR)
            for player_id, values in accum.items()
        }
        weighted_mean = sum(player_effect[p] * player_counts[p] for p in player_effect) / max(1, sum(player_counts[p] for p in player_effect))
        player_effect = {p: v - weighted_mean for p, v in player_effect.items()}

        fs_accum: Dict[Tuple[int, int], List[float]] = defaultdict(lambda: [0.0, 0.0])
        for player_id, fs, mean_pts, weight in cell_means:
            fs_accum[fs][0] += (mean_pts - global_avg - player_effect.get(player_id, 0.0)) * weight
            fs_accum[fs][1] += weight
        fs_effect = {
            fs: values[0] / (values[1] + FORMATION_SLOT_EFFECT_PRIOR)
            for fs, values in fs_accum.items()
        }
        fs_mean = sum(fs_effect[fs] * fs_counts[fs] for fs in fs_effect) / max(1, sum(fs_counts[fs] for fs in fs_effect))
        fs_effect = {fs: v - fs_mean for fs, v in fs_effect.items()}

    return FixedEffects(
        global_avg=global_avg,
        player_effect=player_effect,
        formation_slot_effect=fs_effect,
        player_counts=dict(player_counts),
        formation_slot_counts=dict(fs_counts),
    )


def solve_linear_regression(rows: Sequence[Tuple[List[float], float]], ridge: float = 1e-6) -> List[float]:
    if not rows:
        return []
    dim = len(rows[0][0]) + 1
    xtx = [[0.0 for _ in range(dim)] for _ in range(dim)]
    xty = [0.0 for _ in range(dim)]
    for features, target in rows:
        x = [1.0] + [float(v) for v in features]
        for i in range(dim):
            xty[i] += x[i] * target
            for j in range(dim):
                xtx[i][j] += x[i] * x[j]
    for i in range(dim):
        xtx[i][i] += ridge

    # Gaussian elimination with partial pivoting.
    a = [row[:] + [xty[i]] for i, row in enumerate(xtx)]
    for col in range(dim):
        pivot = max(range(col, dim), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            continue
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        div = a[col][col]
        for j in range(col, dim + 1):
            a[col][j] /= div
        for r in range(dim):
            if r == col:
                continue
            factor = a[r][col]
            if factor == 0:
                continue
            for j in range(col, dim + 1):
                a[r][j] -= factor * a[col][j]
    return [a[i][dim] for i in range(dim)]


def predict(coef: Sequence[float], features: Sequence[float]) -> float:
    if not coef:
        return 0.0
    return coef[0] + sum(coef[i + 1] * features[i] for i in range(min(len(features), len(coef) - 1)))


def rmse(pairs: Sequence[Tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return math.sqrt(sum((actual - pred) ** 2 for actual, pred in pairs) / len(pairs))


def mae(pairs: Sequence[Tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    return sum(abs(actual - pred) for actual, pred in pairs) / len(pairs)


def corr(pairs: Sequence[Tuple[float, float]]) -> float:
    if len(pairs) < 2:
        return 0.0
    actuals = [a for a, _ in pairs]
    preds = [p for _, p in pairs]
    ma = sum(actuals) / len(actuals)
    mp = sum(preds) / len(preds)
    cov = sum((a - ma) * (p - mp) for a, p in pairs)
    va = sum((a - ma) ** 2 for a in actuals)
    vp = sum((p - mp) ** 2 for p in preds)
    return cov / math.sqrt(va * vp) if va > 0 and vp > 0 else 0.0


def side_features(
    team_key: Tuple[int, int, int, str],
    teams: Mapping[Tuple[int, int, int, str], TeamRow],
    players_by_team: Mapping[Tuple[int, int, int, str], Sequence[PlayerRow]],
    effects: FixedEffects,
    key_slots_by_formation: Mapping[int, Mapping[int, int]],
    formation_power: Optional[Mapping[int, float]] = None,
    coach_power: Optional[Mapping[int, float]] = None,
) -> Optional[Dict[str, float]]:
    team = teams.get(team_key)
    rows = players_by_team.get(team_key) or []
    if team is None or len(rows) != 11:
        return None
    row_by_slot = {row.slot: row for row in rows}
    if any(slot not in row_by_slot for slot in range(1, 12)):
        return None
    start = sum(effects.player_effect.get(row_by_slot[slot].player_id, 0.0) for slot in range(1, 12))
    key_sum = 0.0
    for key_no, slot in (key_slots_by_formation.get(team.formation_id) or {}).items():
        if 1 <= int(key_no) <= 4 and 1 <= int(slot) <= 11:
            key_sum += effects.player_effect.get(row_by_slot[int(slot)].player_id, 0.0)
    return {
        "start": start,
        "key": key_sum,
        "formation": float((formation_power or {}).get(team.formation_id, 0.0)),
        "coach": float((coach_power or {}).get(team.headcoach_id, 0.0)),
    }


def pair_rows(
    teams: Mapping[Tuple[int, int, int, str], TeamRow],
    players_by_team: Mapping[Tuple[int, int, int, str], Sequence[PlayerRow]],
    effects: FixedEffects,
    key_slots_by_formation: Mapping[int, Mapping[int, int]],
    seasons: Optional[set[int]] = None,
    formation_power: Optional[Mapping[int, float]] = None,
    coach_power: Optional[Mapping[int, float]] = None,
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    seen = {(season, world, match) for season, world, match, _side in teams}
    for season, world_id, match_id in sorted(seen):
        if seasons is not None and season not in seasons:
            continue
        home_key = (season, world_id, match_id, "home")
        away_key = (season, world_id, match_id, "away")
        home = teams.get(home_key)
        away = teams.get(away_key)
        if home is None or away is None:
            continue
        hf = side_features(home_key, teams, players_by_team, effects, key_slots_by_formation, formation_power, coach_power)
        af = side_features(away_key, teams, players_by_team, effects, key_slots_by_formation, formation_power, coach_power)
        if hf is None or af is None:
            continue
        rows.append(
            {
                "season": season,
                "home": home,
                "away": away,
                "features": [
                    float(hf["start"] - af["start"]),
                    float(hf["key"] - af["key"]),
                    float(hf["formation"] - af["formation"]),
                    float(hf["coach"] - af["coach"]),
                ],
                "goal_diff": float(home.goals_for - away.goals_for),
                "coach_pts_diff": float((home.headcoach_pts or 0.0) - (away.headcoach_pts or 0.0)),
            }
        )
    return rows


def estimate_side_power_from_residuals(
    rows: Sequence[Dict[str, object]],
    residuals: Sequence[float],
    attr: str,
    prior: float,
) -> Dict[int, float]:
    accum: Dict[int, List[float]] = defaultdict(lambda: [0.0, 0.0])
    for row, residual in zip(rows, residuals):
        home: TeamRow = row["home"]  # type: ignore[assignment]
        away: TeamRow = row["away"]  # type: ignore[assignment]
        home_id = int(getattr(home, attr) or 0)
        away_id = int(getattr(away, attr) or 0)
        if home_id > 0:
            accum[home_id][0] += residual
            accum[home_id][1] += 1.0
        if away_id > 0:
            accum[away_id][0] -= residual
            accum[away_id][1] += 1.0
    power = {key: values[0] / (values[1] + prior) for key, values in accum.items()}
    if not power:
        return {}
    mean_value = sum(power.values()) / len(power)
    return {key: value - mean_value for key, value in power.items()}


def fit_model(
    teams: Mapping[Tuple[int, int, int, str], TeamRow],
    players_by_team: Mapping[Tuple[int, int, int, str], Sequence[PlayerRow]],
    key_slots_by_formation: Mapping[int, Mapping[int, int]],
    train_seasons: Optional[set[int]] = None,
) -> Dict[str, object]:
    effects = estimate_rating_fixed_effects(teams, players_by_team, train_seasons)

    base_rows = pair_rows(teams, players_by_team, effects, key_slots_by_formation, train_seasons)
    start_key_coef = solve_linear_regression(
        [([row["features"][0], row["features"][1]], float(row["goal_diff"])) for row in base_rows],
        ridge=1e-5,
    )
    base_pred = [predict(start_key_coef, [row["features"][0], row["features"][1]]) for row in base_rows]
    base_residuals = [float(row["goal_diff"]) - pred for row, pred in zip(base_rows, base_pred)]
    formation_raw = estimate_side_power_from_residuals(base_rows, base_residuals, "formation_id", FORMATION_POWER_PRIOR)

    rows_with_form = pair_rows(
        teams,
        players_by_team,
        effects,
        key_slots_by_formation,
        train_seasons,
        formation_power=formation_raw,
    )
    form_coef = solve_linear_regression(
        [([row["features"][0], row["features"][1], row["features"][2]], float(row["goal_diff"])) for row in rows_with_form],
        ridge=1e-5,
    )
    base_goal_pred = [predict(form_coef, [row["features"][0], row["features"][1], row["features"][2]]) for row in rows_with_form]
    coach_pts_coef = solve_linear_regression(
        [([pred], float(row["coach_pts_diff"])) for row, pred in zip(rows_with_form, base_goal_pred)],
        ridge=1e-5,
    )
    coach_surprise = [float(row["coach_pts_diff"]) - predict(coach_pts_coef, [pred]) for row, pred in zip(rows_with_form, base_goal_pred)]
    goal_resid = [float(row["goal_diff"]) - pred for row, pred in zip(rows_with_form, base_goal_pred)]
    surprise_coef = solve_linear_regression([([surprise], resid) for surprise, resid in zip(coach_surprise, goal_resid)], ridge=1e-5)
    clean_goal_diff = [
        float(row["goal_diff"]) - predict(surprise_coef, [surprise])
        for row, surprise in zip(rows_with_form, coach_surprise)
    ]

    clean_coef_no_coach = solve_linear_regression(
        [([row["features"][0], row["features"][1], row["features"][2]], y) for row, y in zip(rows_with_form, clean_goal_diff)],
        ridge=1e-5,
    )
    clean_pred_no_coach = [
        predict(clean_coef_no_coach, [row["features"][0], row["features"][1], row["features"][2]])
        for row in rows_with_form
    ]
    clean_residuals = [y - pred for y, pred in zip(clean_goal_diff, clean_pred_no_coach)]
    coach_raw = estimate_side_power_from_residuals(rows_with_form, clean_residuals, "headcoach_id", COACH_POWER_PRIOR)

    final_rows = pair_rows(
        teams,
        players_by_team,
        effects,
        key_slots_by_formation,
        train_seasons,
        formation_power=formation_raw,
        coach_power=coach_raw,
    )
    final_clean_goal_diff = []
    for row in final_rows:
        base_pred_for_coach = predict(form_coef, [row["features"][0], row["features"][1], row["features"][2]])
        surprise = float(row["coach_pts_diff"]) - predict(coach_pts_coef, [base_pred_for_coach])
        final_clean_goal_diff.append(float(row["goal_diff"]) - predict(surprise_coef, [surprise]))

    final_coef = solve_linear_regression(
        [(row["features"], y) for row, y in zip(final_rows, final_clean_goal_diff)],  # type: ignore[arg-type]
        ridge=1e-5,
    )
    # Store already-scaled powers so the runtime index can add them directly.
    beta_formation = final_coef[3] if len(final_coef) > 3 else 0.0
    beta_coach = final_coef[4] if len(final_coef) > 4 else 0.0
    formation_power = {fid: beta_formation * value for fid, value in formation_raw.items()}
    coach_power = {cid: beta_coach * value for cid, value in coach_raw.items()}

    return {
        "effects": effects,
        "weights": {
            "intercept": final_coef[0] if final_coef else 0.0,
            "slotAdjusted": final_coef[1] if len(final_coef) > 1 else 0.0,
            "keyAdjusted": final_coef[2] if len(final_coef) > 2 else 0.0,
            "formationRaw": beta_formation,
            "coachRaw": beta_coach,
        },
        "formationPower": formation_power,
        "coachPower": coach_power,
        "diagnostics": {
            "coachPtsVsBaseGoalDiffIntercept": coach_pts_coef[0] if coach_pts_coef else 0.0,
            "coachPtsVsBaseGoalDiffSlope": coach_pts_coef[1] if len(coach_pts_coef) > 1 else 0.0,
            "coachSurpriseGoalDiffIntercept": surprise_coef[0] if surprise_coef else 0.0,
            "coachSurpriseGoalDiffSlope": surprise_coef[1] if len(surprise_coef) > 1 else 0.0,
        },
        "trainRows": final_rows,
        "cleanGoalDiff": final_clean_goal_diff,
    }


def evaluate_model(model: Mapping[str, object]) -> Dict[str, float]:
    rows: Sequence[Dict[str, object]] = model["trainRows"]  # type: ignore[assignment]
    clean_goal_diff: Sequence[float] = model["cleanGoalDiff"]  # type: ignore[assignment]
    weights: Mapping[str, float] = model["weights"]  # type: ignore[assignment]
    coef = [
        weights.get("intercept", 0.0),
        weights.get("slotAdjusted", 0.0),
        weights.get("keyAdjusted", 0.0),
        1.0,
        1.0,
    ]
    predictions = []
    clean_predictions = []
    for row, clean_y in zip(rows, clean_goal_diff):
        pred = predict(coef, row["features"])  # type: ignore[arg-type]
        predictions.append((float(row["goal_diff"]), pred))
        clean_predictions.append((float(clean_y), pred))
    return {
        "matches": float(len(rows)),
        "actualGoalDiffRmse": rmse(predictions),
        "actualGoalDiffMae": mae(predictions),
        "actualGoalDiffCorr": corr(predictions),
        "cleanGoalDiffRmse": rmse(clean_predictions),
        "cleanGoalDiffMae": mae(clean_predictions),
        "cleanGoalDiffCorr": corr(clean_predictions),
    }


def season_holdout_metrics(
    teams: Mapping[Tuple[int, int, int, str], TeamRow],
    players_by_team: Mapping[Tuple[int, int, int, str], Sequence[PlayerRow]],
    key_slots_by_formation: Mapping[int, Mapping[int, int]],
) -> List[Dict[str, float]]:
    seasons = sorted({key[0] for key in teams})
    output: List[Dict[str, float]] = []
    for season in seasons:
        train_seasons = set(seasons) - {season}
        model = fit_model(teams, players_by_team, key_slots_by_formation, train_seasons)
        effects: FixedEffects = model["effects"]  # type: ignore[assignment]
        rows = pair_rows(
            teams,
            players_by_team,
            effects,
            key_slots_by_formation,
            {season},
            formation_power=model["formationPower"],  # type: ignore[arg-type]
            coach_power=model["coachPower"],  # type: ignore[arg-type]
        )
        weights: Mapping[str, float] = model["weights"]  # type: ignore[assignment]
        coef = [
            weights.get("intercept", 0.0),
            weights.get("slotAdjusted", 0.0),
            weights.get("keyAdjusted", 0.0),
            1.0,
            1.0,
        ]
        pairs = [(float(row["goal_diff"]), predict(coef, row["features"])) for row in rows]  # type: ignore[arg-type]
        output.append(
            {
                "season": float(season),
                "matches": float(len(rows)),
                "rmse": rmse(pairs),
                "mae": mae(pairs),
                "corr": corr(pairs),
            }
        )
    return output


def rounded_mapping(mapping: Mapping[object, float], digits: int = 6) -> Dict[str, float]:
    return {str(key): round(float(value), digits) for key, value in sorted(mapping.items(), key=lambda kv: str(kv[0]))}


def render_report(metrics: Mapping[str, float], holdout: Sequence[Mapping[str, float]], model: Mapping[str, object]) -> str:
    weights: Mapping[str, float] = model["weights"]  # type: ignore[assignment]
    diagnostics: Mapping[str, float] = model["diagnostics"]  # type: ignore[assignment]
    holdout_rows = "\n".join(
        f"<tr><td>{int(row['season'])}</td><td>{int(row['matches'])}</td><td>{row['rmse']:.3f}</td><td>{row['mae']:.3f}</td><td>{row['corr']:.3f}</td></tr>"
        for row in holdout
    )
    return f"""<!doctype html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>Team Power Index Re-estimation</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; margin: 20px; background: #f6f7f9; color: #17202a; }}
    main {{ max-width: 980px; margin: 0 auto; }}
    section {{ background: #fff; border: 1px solid #d9dee6; border-radius: 10px; padding: 16px; margin: 14px 0; }}
    h1 {{ font-size: 22px; }}
    h2 {{ font-size: 16px; margin: 0 0 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 7px 8px; border-bottom: 1px solid #e8ebf0; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 10px; }}
    .metric {{ border: 1px solid #e1e5ea; border-radius: 8px; padding: 10px; }}
    .metric span {{ display: block; font-size: 11px; color: #667085; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 18px; }}
    code {{ background: #eef1f5; border-radius: 4px; padding: 1px 4px; }}
  </style>
</head>
<body>
<main>
  <h1>Team Power Index Re-estimation</h1>
  <section>
    <h2>Final Weights</h2>
    <div class=\"grid\">
      <div class=\"metric\"><span>Starting Member adjusted</span><strong>{weights.get('slotAdjusted', 0):.6f}</strong></div>
      <div class=\"metric\"><span>Key Slots adjusted</span><strong>{weights.get('keyAdjusted', 0):.6f}</strong></div>
      <div class=\"metric\"><span>Formation raw scale</span><strong>{weights.get('formationRaw', 0):.6f}</strong></div>
      <div class=\"metric\"><span>Coach raw scale</span><strong>{weights.get('coachRaw', 0):.6f}</strong></div>
    </div>
  </section>
  <section>
    <h2>In-sample Fit</h2>
    <div class=\"grid\">
      <div class=\"metric\"><span>Matches</span><strong>{int(metrics.get('matches', 0))}</strong></div>
      <div class=\"metric\"><span>Actual GD RMSE</span><strong>{metrics.get('actualGoalDiffRmse', 0):.3f}</strong></div>
      <div class=\"metric\"><span>Actual GD Corr</span><strong>{metrics.get('actualGoalDiffCorr', 0):.3f}</strong></div>
      <div class=\"metric\"><span>Clean GD Corr</span><strong>{metrics.get('cleanGoalDiffCorr', 0):.3f}</strong></div>
    </div>
  </section>
  <section>
    <h2>Coach Rating Diagnostics</h2>
    <p>監督評価差は試合後評価なのでTeam Power Index本体には直接入れず、係数推計時に得失点差の上振れ/下振れを分離するためだけに使っています。</p>
    <table>
      <tr><th>Item</th><th>Value</th></tr>
      <tr><td>Expected coach rating diff slope vs base index</td><td>{diagnostics.get('coachPtsVsBaseGoalDiffSlope', 0):.6f}</td></tr>
      <tr><td>Goal diff residual slope vs coach surprise</td><td>{diagnostics.get('coachSurpriseGoalDiffSlope', 0):.6f}</td></tr>
    </table>
  </section>
  <section>
    <h2>Season Holdout</h2>
    <table>
      <thead><tr><th>Season</th><th>Matches</th><th>RMSE</th><th>MAE</th><th>Corr</th></tr></thead>
      <tbody>{holdout_rows}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    db_path = args.db if args.db is not None else find_latest_master_db(args.db_dir)
    key_slots = load_formations(args.formations_json)
    teams, players_by_team = load_db(db_path)
    model = fit_model(teams, players_by_team, key_slots)
    metrics = evaluate_model(model)
    holdout = season_holdout_metrics(teams, players_by_team, key_slots)

    effects: FixedEffects = model["effects"]  # type: ignore[assignment]
    formation_slot_expected = {
        f"{fid}:{slot}": effects.global_avg + value
        for (fid, slot), value in effects.formation_slot_effect.items()
    }
    output = {
        "meta": {
            "model": "team_power_index_slot_adjusted",
            "generatedFrom": str(db_path),
            "ratingDecomposition": "pts = global + player_effect + formation_slot_effect + residual",
            "playerEffectPrior": PLAYER_EFFECT_PRIOR,
            "formationSlotEffectPrior": FORMATION_SLOT_EFFECT_PRIOR,
            "formationPowerPrior": FORMATION_POWER_PRIOR,
            "coachPowerPrior": COACH_POWER_PRIOR,
            "seasons": [min(key[0] for key in teams), max(key[0] for key in teams)],
            "teamRows": len(teams),
            "matchRows": int(metrics.get("matches", 0)),
        },
        "weights": {key: round(float(value), 8) for key, value in model["weights"].items()},  # type: ignore[union-attr]
        "diagnostics": {key: round(float(value), 8) for key, value in model["diagnostics"].items()},  # type: ignore[union-attr]
        "metrics": {key: round(float(value), 6) for key, value in metrics.items()},
        "globalAvg": round(effects.global_avg, 6),
        "formationSlotExpectedPts": rounded_mapping(formation_slot_expected, 6),
        "formationSlotSourceCounts": rounded_mapping({f"{fid}:{slot}": count for (fid, slot), count in effects.formation_slot_counts.items()}, 0),
        "formationPower": rounded_mapping(model["formationPower"], 6),  # type: ignore[arg-type]
        "coachPower": rounded_mapping(model["coachPower"], 6),  # type: ignore[arg-type]
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_html.parent.mkdir(parents=True, exist_ok=True)
    args.report_html.write_text(render_report(metrics, holdout, model), encoding="utf-8")
    args.report_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.report_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["season", "matches", "rmse", "mae", "corr"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(holdout)

    print(f"using {db_path}")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.report_html}")
    print(f"matches={int(metrics.get('matches', 0))} corr={metrics.get('actualGoalDiffCorr', 0):.3f} rmse={metrics.get('actualGoalDiffRmse', 0):.3f}")
    print(
        "weights",
        "slot=", f"{model['weights']['slotAdjusted']:.6f}",  # type: ignore[index]
        "key=", f"{model['weights']['keyAdjusted']:.6f}",  # type: ignore[index]
        "formation=", f"{model['weights']['formationRaw']:.6f}",  # type: ignore[index]
        "coach=", f"{model['weights']['coachRaw']:.6f}",  # type: ignore[index]
    )


if __name__ == "__main__":
    main()
