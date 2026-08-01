#!/usr/bin/env python3
"""Bias-aware formation matchup estimates from historical CC matches.

The primary analysis deliberately uses regulation-time group-stage outcomes.
It first fits a regularized additive baseline for formation strength,
team-season strength, coach strength, and home advantage.  Matchup effects are
then estimated from the remaining signed residuals, with repeated team pairs
down-weighted, empirical-Bayes shrinkage, clustered uncertainty, and FDR.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


MatchKey = tuple[int, int, int]


DEFAULT_GUARD_ARTIFACTS_DIR = Path(
    "/Users/gigagigo/Codex/websoccer/websoccer-player-search/"
    "local/team_agent_analysis/team_agent_match_guard"
)


@dataclass(frozen=True)
class MatchupConfig:
    formation_prior: float = 45.0
    team_season_prior: float = 8.0
    coach_prior: float = 70.0
    matchup_prior: float = 12.0
    repeated_team_pair_cap: float = 3.0
    min_matches: int = 15
    min_effective_matches: float = 8.0
    min_unique_team_pairs: int = 6
    min_unique_teams_each: int = 3
    min_seasons: int = 3
    min_worlds: int = 3
    max_fdr: float = 0.20
    recent_seasons: int = 6
    max_rows_each_side: int = 5
    coordinate_iterations: int = 40
    convergence_tolerance: float = 1e-7


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_group_stage(title: Any) -> bool:
    value = str(title or "")
    return "グループステージ" in value


def _outcome_power(row: Mapping[str, Any]) -> float | None:
    result = str(row.get("result") or "").strip().upper()
    if result == "W":
        return 1.0
    if result == "D":
        return 0.0
    if result == "L":
        return -1.0
    goals_for = row.get("goals_for")
    goals_against = row.get("goals_against")
    if goals_for is None or goals_against is None:
        return None
    gf = _to_float(goals_for)
    ga = _to_float(goals_against)
    if gf > ga:
        return 1.0
    if gf < ga:
        return -1.0
    return 0.0


def load_guard_exclusions(
    artifacts_dir: Path | str | None = DEFAULT_GUARD_ARTIFACTS_DIR,
) -> tuple[set[MatchKey], dict[str, Any]]:
    """Return CC matches where an executed guard actually hid fixed reserves."""

    root = Path(artifacts_dir).expanduser() if artifacts_dir else None
    exclusions: set[MatchKey] = set()
    reasons: Counter[str] = Counter()
    files_read = 0
    evidence_rows = 0
    if root is None or not root.exists():
        return exclusions, {
            "artifactsDir": str(root) if root else "",
            "available": False,
            "filesRead": 0,
            "evidenceRows": 0,
            "uniqueMatches": 0,
            "reasons": {},
        }

    for path in sorted(root.glob("team_agent_match_guard_*.json")):
        if path.name.endswith("_latest.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        files_read += 1
        if not payload.get("execute"):
            continue
        for team in payload.get("teams") or []:
            if str(team.get("desiredLineupMode") or "") != "hide_fixed":
                continue
            lineup = team.get("lineup") or {}
            update = lineup.get("update") or {}
            if str(update.get("status") or "") not in {"updated", "already_ok"}:
                continue
            season = _to_int(team.get("season"))
            world_id = _to_int(team.get("worldId"))
            if season <= 0 or world_id <= 0:
                continue
            reason = str((team.get("lineupModeDecision") or {}).get("reason") or "unspecified")
            for match in team.get("targetSlotMatches") or []:
                if str(match.get("prefix") or "").strip().lower() != "cc":
                    continue
                match_id = _to_int(match.get("matchId"))
                if match_id <= 0:
                    continue
                evidence_rows += 1
                exclusions.add((season, world_id, match_id))
                reasons[reason] += 1

    return exclusions, {
        "artifactsDir": str(root),
        "available": True,
        "filesRead": files_read,
        "evidenceRows": evidence_rows,
        "uniqueMatches": len(exclusions),
        "reasons": dict(sorted(reasons.items())),
    }


def build_match_rows(
    team_rows: Sequence[Mapping[str, Any]],
    match_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    match_info = {
        (
            _to_int(row.get("season")),
            _to_int(row.get("world_id")),
            _to_int(row.get("match_id")),
        ): row
        for row in match_rows
    }
    grouped: MutableMapping[MatchKey, list[Mapping[str, Any]]] = defaultdict(list)
    for row in team_rows:
        key = (
            _to_int(row.get("season")),
            _to_int(row.get("world_id")),
            _to_int(row.get("match_id")),
        )
        grouped[key].append(row)

    built: list[dict[str, Any]] = []
    skipped = Counter()
    for key, rows in grouped.items():
        if len(rows) != 2:
            skipped["not_two_team_rows"] += 1
            continue
        by_side = {str(row.get("side") or "").lower(): row for row in rows}
        home = by_side.get("home")
        away = by_side.get("away")
        if home is None or away is None:
            skipped["missing_home_away"] += 1
            continue
        home_form = _to_int(home.get("formation_id"))
        away_form = _to_int(away.get("formation_id"))
        home_team = _to_int(home.get("team_id"))
        away_team = _to_int(away.get("team_id"))
        if min(home_form, away_form, home_team, away_team) <= 0:
            skipped["missing_identity"] += 1
            continue
        y = _outcome_power(home)
        if y is None:
            skipped["missing_outcome"] += 1
            continue
        info = match_info.get(key) or {}
        built.append(
            {
                "key": key,
                "season": key[0],
                "world": key[1],
                "matchId": key[2],
                "title": str(info.get("title") or ""),
                "stage": "group" if _is_group_stage(info.get("title")) else "knockout",
                "y": float(y),
                "homeFormation": home_form,
                "awayFormation": away_form,
                "homeTeam": home_team,
                "awayTeam": away_team,
                "homeCoach": _to_int(home.get("headcoach_id")),
                "awayCoach": _to_int(away.get("headcoach_id")),
                "homeResult": str(home.get("result") or "").upper(),
                "awayResult": str(away.get("result") or "").upper(),
            }
        )
    built.sort(key=lambda row: row["key"])
    return built, dict(sorted(skipped.items()))


def assign_capped_weights(
    matches: Sequence[Mapping[str, Any]], cap: float = 3.0
) -> list[dict[str, Any]]:
    counts: Counter[tuple[int, int, int, int]] = Counter()
    for match in matches:
        key = (
            min(_to_int(match.get("homeTeam")), _to_int(match.get("awayTeam"))),
            max(_to_int(match.get("homeTeam")), _to_int(match.get("awayTeam"))),
            min(_to_int(match.get("homeFormation")), _to_int(match.get("awayFormation"))),
            max(_to_int(match.get("homeFormation")), _to_int(match.get("awayFormation"))),
        )
        counts[key] += 1
    weighted = []
    for match in matches:
        row = dict(match)
        key = (
            min(_to_int(row.get("homeTeam")), _to_int(row.get("awayTeam"))),
            max(_to_int(row.get("homeTeam")), _to_int(row.get("awayTeam"))),
            min(_to_int(row.get("homeFormation")), _to_int(row.get("awayFormation"))),
            max(_to_int(row.get("homeFormation")), _to_int(row.get("awayFormation"))),
        )
        row["weight"] = min(1.0, float(cap) / max(1, counts[key]))
        row["repeatCount"] = counts[key]
        weighted.append(row)
    return weighted


def _entity_ids(match: Mapping[str, Any], kind: str) -> tuple[Any, Any]:
    if kind == "formation":
        return match["homeFormation"], match["awayFormation"]
    if kind == "coach":
        return match["homeCoach"], match["awayCoach"]
    if kind == "teamSeason":
        season = match["season"]
        return (season, match["homeTeam"]), (season, match["awayTeam"])
    raise KeyError(kind)


def _effect_difference(
    match: Mapping[str, Any], effects: Mapping[str, Mapping[Any, float]]
) -> float:
    total = 0.0
    for kind, values in effects.items():
        home_id, away_id = _entity_ids(match, kind)
        if not home_id or not away_id or home_id == away_id:
            continue
        total += values.get(home_id, 0.0) - values.get(away_id, 0.0)
    return total


def fit_regularized_baseline(
    matches: Sequence[Mapping[str, Any]], config: MatchupConfig
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    effects: dict[str, dict[Any, float]] = {
        "formation": {},
        "coach": {},
        "teamSeason": {},
    }
    priors = {
        "formation": config.formation_prior,
        "coach": config.coach_prior,
        "teamSeason": config.team_season_prior,
    }
    intercept = 0.0
    converged_at = config.coordinate_iterations

    for iteration in range(config.coordinate_iterations):
        previous = intercept
        total_weight = sum(_to_float(row.get("weight"), 1.0) for row in matches)
        if total_weight:
            intercept = sum(
                _to_float(row.get("weight"), 1.0)
                * (float(row["y"]) - _effect_difference(row, effects))
                for row in matches
            ) / total_weight

        max_change = abs(intercept - previous)
        for kind in ("formation", "coach", "teamSeason"):
            old = effects[kind]
            numerator: MutableMapping[Any, float] = defaultdict(float)
            denominator: MutableMapping[Any, float] = defaultdict(float)
            for row in matches:
                home_id, away_id = _entity_ids(row, kind)
                if not home_id or not away_id or home_id == away_id:
                    continue
                weight = _to_float(row.get("weight"), 1.0)
                prediction = intercept + _effect_difference(row, effects)
                residual_without = float(row["y"]) - (
                    prediction - old.get(home_id, 0.0) + old.get(away_id, 0.0)
                )
                numerator[home_id] += weight * residual_without
                denominator[home_id] += weight
                numerator[away_id] -= weight * residual_without
                denominator[away_id] += weight
            new = {
                entity: numerator[entity] / (denominator[entity] + priors[kind])
                for entity in denominator
            }
            denom_sum = sum(denominator.values())
            if denom_sum:
                center = sum(new[e] * denominator[e] for e in new) / denom_sum
                new = {entity: value - center for entity, value in new.items()}
            for entity in set(old) | set(new):
                max_change = max(
                    max_change, abs(new.get(entity, 0.0) - old.get(entity, 0.0))
                )
            effects[kind] = new

        if max_change < config.convergence_tolerance:
            converged_at = iteration + 1
            break

    scored: list[dict[str, Any]] = []
    squared_error = 0.0
    total_weight = 0.0
    for match in matches:
        row = dict(match)
        prediction = intercept + _effect_difference(row, effects)
        residual = float(row["y"]) - prediction
        weight = _to_float(row.get("weight"), 1.0)
        row["baselinePrediction"] = prediction
        row["residual"] = residual
        scored.append(row)
        squared_error += weight * residual * residual
        total_weight += weight

    return {
        "homeAdvantage": intercept,
        "weightedRmse": math.sqrt(squared_error / total_weight) if total_weight else 0.0,
        "iterations": converged_at,
        "effectCounts": {kind: len(values) for kind, values in effects.items()},
        "priors": {
            "formation": config.formation_prior,
            "teamSeason": config.team_season_prior,
            "coach": config.coach_prior,
        },
    }, scored


def _effective_n(weights: Iterable[float]) -> float:
    values = [float(value) for value in weights if value > 0]
    total = sum(values)
    squares = sum(value * value for value in values)
    return (total * total / squares) if squares else 0.0


def _clustered_standard_error(
    observations: Sequence[tuple[float, float, tuple[int, int]]], mean: float
) -> tuple[float, float]:
    clusters: MutableMapping[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for value, weight, cluster in observations:
        clusters[cluster].append((value, weight))
    cluster_rows = []
    for rows in clusters.values():
        weight = sum(row[1] for row in rows)
        if weight <= 0:
            continue
        cluster_rows.append((sum(value * w for value, w in rows) / weight, weight))
    if len(cluster_rows) < 2:
        return float("inf"), float(len(cluster_rows))
    total_weight = sum(weight for _, weight in cluster_rows)
    squared_weights = sum(weight * weight for _, weight in cluster_rows)
    effective_clusters = (
        total_weight * total_weight / squared_weights if squared_weights else 0.0
    )
    variance_denom = total_weight - squared_weights / total_weight
    if variance_denom <= 0 or effective_clusters <= 1:
        return float("inf"), effective_clusters
    variance = (
        sum(weight * (value - mean) ** 2 for value, weight in cluster_rows)
        / variance_denom
    )
    return math.sqrt(max(0.0, variance) / effective_clusters), effective_clusters


def _normal_p_value(value: float, standard_error: float) -> float:
    if not math.isfinite(standard_error) or standard_error <= 0:
        return 1.0
    z = abs(value / standard_error)
    return math.erfc(z / math.sqrt(2.0))


def _apply_bh_fdr(rows: list[dict[str, Any]]) -> None:
    ranked = sorted(enumerate(rows), key=lambda item: float(item[1]["pValue"]))
    total = len(ranked)
    running = 1.0
    for reverse_index in range(total - 1, -1, -1):
        original_index, row = ranked[reverse_index]
        rank = reverse_index + 1
        running = min(running, float(row["pValue"]) * total / rank)
        rows[original_index]["qValue"] = min(1.0, running)


def _aggregate_pair_stats(
    scored: Sequence[Mapping[str, Any]], config: MatchupConfig
) -> dict[tuple[int, int], dict[str, Any]]:
    buckets: MutableMapping[tuple[int, int], dict[str, Any]] = defaultdict(
        lambda: {
            "observations": [],
            "matches": 0,
            "winsLow": 0,
            "draws": 0,
            "lossesLow": 0,
            "weights": [],
            "teamPairs": set(),
            "teamSeasons": set(),
            "lowTeams": set(),
            "highTeams": set(),
            "seasons": set(),
            "worlds": set(),
        }
    )
    for row in scored:
        home_form = _to_int(row.get("homeFormation"))
        away_form = _to_int(row.get("awayFormation"))
        if home_form == away_form:
            continue
        low_form, high_form = sorted((home_form, away_form))
        sign = 1.0 if home_form == low_form else -1.0
        value = sign * _to_float(row.get("residual"))
        outcome = sign * _to_float(row.get("y"))
        weight = _to_float(row.get("weight"), 1.0)
        low_team = _to_int(row.get("homeTeam")) if sign > 0 else _to_int(row.get("awayTeam"))
        high_team = _to_int(row.get("awayTeam")) if sign > 0 else _to_int(row.get("homeTeam"))
        team_pair = tuple(sorted((low_team, high_team)))
        season = _to_int(row.get("season"))
        bucket = buckets[(low_form, high_form)]
        bucket["observations"].append((value, weight, team_pair))
        bucket["matches"] += 1
        bucket["weights"].append(weight)
        bucket["teamPairs"].add(team_pair)
        bucket["teamSeasons"].update(((season, low_team), (season, high_team)))
        bucket["lowTeams"].add(low_team)
        bucket["highTeams"].add(high_team)
        bucket["seasons"].add(season)
        bucket["worlds"].add(_to_int(row.get("world")))
        if outcome > 0.5:
            bucket["winsLow"] += 1
        elif outcome < -0.5:
            bucket["lossesLow"] += 1
        else:
            bucket["draws"] += 1

    results: dict[tuple[int, int], dict[str, Any]] = {}
    tested: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        observations = bucket["observations"]
        total_weight = sum(weight for _, weight, _ in observations)
        if total_weight <= 0:
            continue
        raw = sum(value * weight for value, weight, _ in observations) / total_weight
        raw_se, effective_clusters = _clustered_standard_error(observations, raw)
        shrink = total_weight / (total_weight + config.matchup_prior)
        shrunk = raw * shrink
        shrunk_se = raw_se * shrink if math.isfinite(raw_se) else raw_se
        effective_matches = _effective_n(bucket["weights"])
        eligible = (
            bucket["matches"] >= config.min_matches
            and effective_matches >= config.min_effective_matches
            and len(bucket["teamPairs"]) >= config.min_unique_team_pairs
            and len(bucket["lowTeams"]) >= config.min_unique_teams_each
            and len(bucket["highTeams"]) >= config.min_unique_teams_each
            and len(bucket["seasons"]) >= config.min_seasons
            and len(bucket["worlds"]) >= config.min_worlds
            and math.isfinite(shrunk_se)
        )
        row = {
            "formationLow": key[0],
            "formationHigh": key[1],
            "matches": bucket["matches"],
            "weightedMatches": total_weight,
            "effectiveMatches": effective_matches,
            "effectiveTeamPairClusters": effective_clusters,
            "uniqueTeamPairs": len(bucket["teamPairs"]),
            "uniqueTeamSeasons": len(bucket["teamSeasons"]),
            "uniqueTeamsLow": len(bucket["lowTeams"]),
            "uniqueTeamsHigh": len(bucket["highTeams"]),
            "seasonCount": len(bucket["seasons"]),
            "worldCount": len(bucket["worlds"]),
            "winsLow": bucket["winsLow"],
            "draws": bucket["draws"],
            "lossesLow": bucket["lossesLow"],
            "rawEdge": raw,
            "edge": shrunk,
            "standardError": shrunk_se,
            "ciLow": shrunk - 1.96 * shrunk_se if math.isfinite(shrunk_se) else -1.0,
            "ciHigh": shrunk + 1.96 * shrunk_se if math.isfinite(shrunk_se) else 1.0,
            "pValue": _normal_p_value(raw, raw_se),
            "qValue": 1.0,
            "eligible": eligible,
        }
        results[key] = row
        if eligible:
            tested.append(row)

    _apply_bh_fdr(tested)
    return results


def _analyze_subset(
    matches: Sequence[Mapping[str, Any]], config: MatchupConfig
) -> tuple[dict[tuple[int, int], dict[str, Any]], dict[str, Any]]:
    weighted = assign_capped_weights(matches, config.repeated_team_pair_cap)
    baseline, scored = fit_regularized_baseline(weighted, config)
    pairs = _aggregate_pair_stats(scored, config)
    return pairs, {
        "matches": len(matches),
        "weightedMatches": sum(_to_float(row.get("weight"), 1.0) for row in weighted),
        "baseline": baseline,
        "pairCount": len(pairs),
        "eligiblePairCount": sum(1 for row in pairs.values() if row["eligible"]),
    }


def _directional_row(
    pair: Mapping[str, Any], own_is_low: bool, secondary: Mapping[str, Any] | None,
    recent: Mapping[str, Any] | None, config: MatchupConfig,
) -> dict[str, Any]:
    sign = 1.0 if own_is_low else -1.0
    wins = int(pair["winsLow"] if own_is_low else pair["lossesLow"])
    losses = int(pair["lossesLow"] if own_is_low else pair["winsLow"])
    draws = int(pair["draws"])
    matches = int(pair["matches"])
    delta = sign * float(pair["edge"]) * 3.0
    ci_low = (
        float(pair["ciLow"]) * 3.0 if own_is_low else -float(pair["ciHigh"]) * 3.0
    )
    ci_high = (
        float(pair["ciHigh"]) * 3.0 if own_is_low else -float(pair["ciLow"]) * 3.0
    )
    secondary_delta = sign * float(secondary["edge"]) * 3.0 if secondary else None
    recent_delta = sign * float(recent["edge"]) * 3.0 if recent else None
    stable_all = secondary_delta is None or delta == 0 or secondary_delta == 0 or delta * secondary_delta > 0
    stable_recent = recent_delta is None or delta == 0 or recent_delta == 0 or delta * recent_delta > 0
    q_value = float(pair["qValue"])
    interval_excludes_zero = ci_low > 0 or ci_high < 0
    supported = bool(
        pair["eligible"]
        and interval_excludes_zero
        and q_value <= config.max_fdr
        and stable_all
    )
    if supported and q_value <= 0.05 and int(pair["uniqueTeamPairs"]) >= 12:
        evidence = "High"
    elif supported and q_value <= 0.10:
        evidence = "Mid"
    elif supported:
        evidence = "Low"
    else:
        evidence = "Exploratory"
    return {
        "formationId": int(pair["formationHigh"] if own_is_low else pair["formationLow"]),
        "matches": matches,
        "effectiveMatches": round(float(pair["effectiveMatches"]), 3),
        "uniqueTeamPairs": int(pair["uniqueTeamPairs"]),
        "uniqueTeamSeasons": int(pair["uniqueTeamSeasons"]),
        "uniqueTeamsOwn": int(pair["uniqueTeamsLow"] if own_is_low else pair["uniqueTeamsHigh"]),
        "uniqueTeamsOpponent": int(pair["uniqueTeamsHigh"] if own_is_low else pair["uniqueTeamsLow"]),
        "seasonCount": int(pair["seasonCount"]),
        "worldCount": int(pair["worldCount"]),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "pointsPerMatch": round((3.0 * wins + draws) / matches, 6) if matches else 0.0,
        "delta": round(delta, 6),
        "ciLow": round(ci_low, 6),
        "ciHigh": round(ci_high, 6),
        "pValue": round(float(pair["pValue"]), 8),
        "qValue": round(q_value, 8),
        "evidence": evidence,
        "supported": supported,
        "allStageDelta": round(secondary_delta, 6) if secondary_delta is not None else None,
        "recentDelta": round(recent_delta, 6) if recent_delta is not None else None,
        "stableAllStages": stable_all,
        "stableRecent": stable_recent,
    }


def build_bias_aware_matchups(
    team_rows: Sequence[Mapping[str, Any]],
    match_rows: Sequence[Mapping[str, Any]],
    guard_exclusions: set[MatchKey] | None = None,
    guard_meta: Mapping[str, Any] | None = None,
    config: MatchupConfig | None = None,
) -> dict[str, Any]:
    config = config or MatchupConfig()
    guard_exclusions = guard_exclusions or set()
    built, skipped = build_match_rows(team_rows, match_rows)
    guard_matched = [row for row in built if row["key"] in guard_exclusions]
    clean = [row for row in built if row["key"] not in guard_exclusions]
    primary = [row for row in clean if row["stage"] == "group"]
    all_stage = clean

    primary_pairs, primary_meta = _analyze_subset(primary, config)
    all_pairs, all_meta = _analyze_subset(all_stage, config)
    max_season = max((_to_int(row.get("season")) for row in primary), default=0)
    recent_start = max_season - config.recent_seasons + 1 if max_season else 0
    recent_matches = [row for row in primary if _to_int(row.get("season")) >= recent_start]
    recent_pairs, recent_meta = _analyze_subset(recent_matches, config)

    by_formation: MutableMapping[int, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"strongAgainst": [], "weakAgainst": []}
    )
    supported_pair_count = 0
    for key, pair in primary_pairs.items():
        secondary = all_pairs.get(key)
        if secondary is not None and not secondary.get("eligible"):
            secondary = None
        recent = recent_pairs.get(key)
        if recent is not None and not recent.get("eligible"):
            recent = None
        low_row = _directional_row(pair, True, secondary, recent, config)
        high_row = _directional_row(pair, False, secondary, recent, config)
        if low_row["supported"]:
            supported_pair_count += 1
            by_formation[key[0]]["strongAgainst" if low_row["delta"] > 0 else "weakAgainst"].append(low_row)
            by_formation[key[1]]["strongAgainst" if high_row["delta"] > 0 else "weakAgainst"].append(high_row)

    criteria = {
        "method": "bias_aware_group_stage_residual_v1",
        "primaryScope": "CC group stage regulation-time results",
        "outcome": "signed 3-point result differential",
        "baselineAdjustments": [
            "formation overall strength",
            "team-season latent strength",
            "headcoach identity",
            "home advantage",
        ],
        "repeatedTeamPairCap": config.repeated_team_pair_cap,
        "matchupPrior": config.matchup_prior,
        "minMatches": config.min_matches,
        "minEffectiveMatches": config.min_effective_matches,
        "minUniqueTeamPairs": config.min_unique_team_pairs,
        "minUniqueTeamsEach": config.min_unique_teams_each,
        "minSeasons": config.min_seasons,
        "minWorlds": config.min_worlds,
        "maxFdr": config.max_fdr,
        "recentSeasons": config.recent_seasons,
        "confidenceBands": {
            "high": "q<=0.05 and at least 12 unique team pairs",
            "mid": "q<=0.10",
            "low": "q<=0.20",
        },
    }
    for formation_id, rows in by_formation.items():
        rows["strongAgainst"].sort(
            key=lambda row: (-float(row["delta"]), float(row["qValue"]), -int(row["uniqueTeamPairs"]))
        )
        rows["weakAgainst"].sort(
            key=lambda row: (float(row["delta"]), float(row["qValue"]), -int(row["uniqueTeamPairs"]))
        )
        rows["strongAgainst"] = rows["strongAgainst"][: config.max_rows_each_side]
        rows["weakAgainst"] = rows["weakAgainst"][: config.max_rows_each_side]
        rows["criteria"] = criteria

    return {
        "byFormation": dict(by_formation),
        "meta": {
            "method": criteria["method"],
            "builtMatches": len(built),
            "skipped": skipped,
            "guardEvidence": dict(guard_meta or {}),
            "guardExcludedMatches": len(guard_matched),
            "guardExcludedMatchIds": [row["matchId"] for row in guard_matched],
            "primary": primary_meta,
            "allStagesSensitivity": all_meta,
            "recentSensitivity": {**recent_meta, "seasonStart": recent_start, "seasonEnd": max_season},
            "supportedPairCount": supported_pair_count,
            "criteria": criteria,
            "caveats": [
                "Observational adjusted association, not a causal formation effect.",
                "Primary estimates exclude knockout rounds to avoid advancement selection.",
                "Only guard activations with successful hide_fixed evidence are excluded.",
                "Sparse and team-dominated pairs are suppressed rather than ranked.",
            ],
        },
    }
