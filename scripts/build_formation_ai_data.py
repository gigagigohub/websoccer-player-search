#!/usr/bin/env python3
import argparse
import json
import math
import shutil
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np

CORE_FEATURES = [
    ("spd", "Speed", "ZSPD", 10.0),
    ("tec", "Technique", "ZTEC", 10.0),
    ("pwr", "Power", "ZPWR", 10.0),
    ("individual", "Individual", "ZSTDP", 30.0),
    ("organization", "Organization", "ZTMP", 30.0),
    ("sense", "Sense", "ZSEN", 30.0),
    ("intelligence", "Intelligence", "ZINTE", 30.0),
]

POSITION_FEATURES = [(f"r{i}", f"R{i}", f"ZR{i}", 7.0) for i in range(1, 19)]
FEATURES = CORE_FEATURES + POSITION_FEATURES
FEATURE_KEYS = [x[0] for x in FEATURES]
CATEGORY_KEYS = ["CC", "SS", "CM", "NR"]
MIN_SAMPLES = 30
MIN_UNIQUE_PLAYERS = 8
RIDGE_LAMBDA = 2.5
TOP_N = 10
CORE_IDX = [0, 1, 2]
MENTAL_IDX = [3, 4, 5, 6]
FORMATION_IDX = list(range(7, 22))
LINE_IDX = [22, 23, 24]


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


def normalize_category(value):
    c = str(value or "").strip().upper()
    return c or "-"


def load_json_ids(raw):
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return set()
    return {to_int(x) for x in data if to_int(x) > 0}


def row_feature_vector(row):
    return np.array([to_float(row.get(col), 0.0) / scale for _, _, col, scale in FEATURES], dtype=float)


def display_params(row):
    return {key: to_int(row.get(col)) for key, _, col, _ in FEATURES}


def period_label(szn_no):
    n = to_int(szn_no)
    return f"{n + 1}期"


def load_player_index(conn):
    rows = conn.execute(
        """
        SELECT
          p.ZPLAYER_ID AS player_id,
          p.ZNAME AS player_name,
          p.ZFULLNAME AS player_fullname,
          p.ZNATION_ID AS nation_id,
          n.ZNAME AS nationality,
          p.ZRARITY AS rate,
          COALESCE(m.category, 'NR') AS category,
          COALESCE(m.retired, 0) AS retired
        FROM ao__ZMOPLAYER p
        LEFT JOIN ao__ZMONATION n ON n.ZNATION_ID = p.ZNATION_ID
        LEFT JOIN manual_player_category m ON m.player_id = p.ZPLAYER_ID
        WHERE p.ZPLAYER_ID IS NOT NULL
        """
    ).fetchall()
    index = {}
    for r in rows:
        pid = to_int(r["player_id"])
        if pid <= 0:
            continue
        index[pid] = {
            "id": pid,
            "name": r["player_name"] or r["player_fullname"] or str(pid),
            "fullName": r["player_fullname"] or r["player_name"] or str(pid),
            "nationId": to_int(r["nation_id"]),
            "nationality": r["nationality"] or "",
            "category": normalize_category(r["category"]),
            "rate": to_int(r["rate"]),
            "retired": bool(to_int(r["retired"])),
        }
    return index


def load_recent_ss_ids(conn, event_count=2):
    ids = set()
    rows = conn.execute(
        """
        SELECT player_ids_json
        FROM manual_scout_event
        WHERE player_ids_json IS NOT NULL AND TRIM(player_ids_json) != ''
        ORDER BY datetime(start) DESC, event_id DESC
        LIMIT ?
        """,
        (event_count,),
    ).fetchall()
    for r in rows:
        ids.update(load_json_ids(r["player_ids_json"]))
    return ids


def load_param_rows(conn):
    rows = conn.execute(
        """
        SELECT
          ZPLAYER_ID,
          ZSZN_NO,
          ZSPD,
          ZTEC,
          ZPWR,
          ZSTDP,
          ZTMP,
          ZSEN,
          ZINTE,
          ZR1, ZR2, ZR3, ZR4, ZR5, ZR6, ZR7, ZR8, ZR9,
          ZR10, ZR11, ZR12, ZR13, ZR14, ZR15, ZR16, ZR17, ZR18
        FROM ao__ZMOPLAYERSPARAM
        WHERE ZPLAYER_ID IS NOT NULL
        """
    ).fetchall()
    by_player = defaultdict(list)
    for r in rows:
        pid = to_int(r["ZPLAYER_ID"])
        if pid <= 0:
            continue
        by_player[pid].append(dict(r))
    return by_player


def peak_row(rows):
    if not rows:
        return None
    def score(r):
        return (
            to_int(r.get("ZSPD")) + to_int(r.get("ZTEC")) + to_int(r.get("ZPWR")),
            to_int(r.get("ZSTDP")) + to_int(r.get("ZTMP")) + to_int(r.get("ZSEN")) + to_int(r.get("ZINTE")),
            -to_int(r.get("ZSZN_NO")),
        )
    return max(rows, key=score)


def build_candidates(player_index, params_by_player, recent_ss_ids):
    candidates = []
    for pid, player in player_index.items():
        category = normalize_category(player.get("category"))
        if player.get("retired"):
            continue
        if category == "CM":
            continue
        if category == "CM/SS":
            if pid not in recent_ss_ids:
                continue
            category = "SS"
        elif category == "SS":
            if pid not in recent_ss_ids:
                continue
        elif category not in {"NR", "CC"}:
            continue
        rows = params_by_player.get(pid) or []
        if not rows:
            continue
        period_rows = []
        for row in rows:
            period_rows.append({
                "vector": row_feature_vector(row),
                "score": 0.0,
                "season": period_label(row.get("ZSZN_NO")),
                "params": display_params(row),
            })
        candidates.append({**player, "category": category, "periodRows": period_rows})
    return candidates


def build_candidate_matrix(candidates):
    vectors = []
    owners = []
    for ci, candidate in enumerate(candidates):
        for pi, period in enumerate(candidate.get("periodRows") or []):
            vectors.append(period["vector"])
            owners.append((ci, pi))
    matrix = np.vstack(vectors) if vectors else np.zeros((0, len(FEATURES)), dtype=float)
    return matrix, owners


def ridge_fit(X, y):
    n, p = X.shape
    if n <= p:
        lam = RIDGE_LAMBDA * 2.0
    else:
        lam = RIDGE_LAMBDA
    xtx = X.T @ X
    reg = np.eye(p) * lam
    reg[0, 0] = 0.0
    try:
        return np.linalg.solve(xtx + reg, X.T @ y)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(xtx + reg) @ X.T @ y


def target_importance(target, reference=None, limit=6):
    ref = reference if reference is not None else np.zeros_like(target)
    deltas = np.maximum(target - ref, 0.0)
    rows = []
    for i, value in enumerate(deltas):
        if value < 0.015:
            continue
        key, label, _, _ = FEATURES[i]
        rows.append({"key": key, "label": label, "weight": round(float(value), 6)})
    rows.sort(key=lambda x: (-x["weight"], x["key"]))
    if rows:
        return rows[:limit]
    fallback = []
    for i, value in enumerate(target):
        if value < 0.015:
            continue
        key, label, _, _ = FEATURES[i]
        fallback.append({"key": key, "label": label, "weight": round(float(value), 6)})
    fallback.sort(key=lambda x: (-x["weight"], x["key"]))
    return fallback[:limit]


def confidence_label(n, unique_players):
    if n >= 120 and unique_players >= 20:
        return "High"
    if n >= 60 and unique_players >= 14:
        return "Mid"
    return "Low"


def candidate_best_score(candidate, period_scores):
    best = None
    for period, score in zip(candidate.get("periodRows") or [], period_scores):
        item = {
            "score": round(float(score) * 100.0, 3),
            "season": period["season"],
            "params": period["params"],
        }
        if best is None or item["score"] > best["score"]:
            best = item
    return best


def ratio_similarity(candidate_part, target_part):
    cand_sum = candidate_part.sum(axis=1, keepdims=True)
    target_sum = float(target_part.sum())
    cand_ratio = np.divide(candidate_part, np.maximum(cand_sum, 1e-9))
    target_ratio = target_part / max(target_sum, 1e-9)
    dist = np.sqrt(np.mean((cand_ratio - target_ratio) ** 2, axis=1))
    return np.clip(1.0 - dist / 0.42, 0.0, 1.0)


def level_similarity(candidate_part, target_part, scale=0.45):
    dist = np.sqrt(np.mean((candidate_part - target_part) ** 2, axis=1))
    return np.clip(1.0 - dist / scale, 0.0, 1.0)


def formation_similarity(candidate_matrix, target):
    cand = candidate_matrix[:, FORMATION_IDX]
    tgt = target[FORMATION_IDX]
    level = level_similarity(cand, tgt, scale=0.31)
    distribution = ratio_similarity(cand, tgt)
    cand_centered = cand - cand.mean(axis=1, keepdims=True)
    tgt_centered = tgt - tgt.mean()
    contour_dist = np.sqrt(np.mean((cand_centered - tgt_centered) ** 2, axis=1))
    contour = np.clip(1.0 - contour_dist / 0.30, 0.0, 1.0)
    return 0.45 * level + 0.35 * distribution + 0.20 * contour


def core_pattern(target_core):
    labels = ["Speed", "Technique", "Power"]
    order = np.argsort(-target_core)
    sorted_vals = target_core[order]
    gap1 = float(sorted_vals[0] - sorted_vals[1])
    gap2 = float(sorted_vals[1] - sorted_vals[2])
    if gap1 < 0.08 and gap2 < 0.08:
        kind = "balanced"
    elif gap1 >= 0.12:
        kind = "single_specialist"
    elif gap2 >= 0.12:
        kind = "double_specialist"
    else:
        kind = "specialist_plus_support"
    return {
        "kind": kind,
        "primary": labels[int(order[0])],
        "secondary": labels[int(order[1])],
        "gaps": [round(gap1, 4), round(gap2, 4)],
    }


def core_similarity(candidate_matrix, target):
    cand = candidate_matrix[:, CORE_IDX]
    tgt = target[CORE_IDX]
    pattern = core_pattern(tgt)
    target_order = np.argsort(-tgt)
    cand_order = np.argsort(-cand, axis=1)
    sorted_cand = np.take_along_axis(cand, cand_order, axis=1)
    sorted_tgt = tgt[target_order]

    gap_tgt = np.array([sorted_tgt[0] - sorted_tgt[1], sorted_tgt[1] - sorted_tgt[2]])
    gap_cand = np.column_stack([
        sorted_cand[:, 0] - sorted_cand[:, 1],
        sorted_cand[:, 1] - sorted_cand[:, 2],
    ])
    gap_fit = np.clip(1.0 - np.mean(np.abs(gap_cand - gap_tgt), axis=1) / 0.18, 0.0, 1.0)

    level = level_similarity(cand, tgt, scale=0.36)
    ratio = ratio_similarity(cand, tgt)

    if pattern["kind"] == "single_specialist":
        top_fit = (cand_order[:, 0] == target_order[0]).astype(float)
        support = np.minimum(cand[:, target_order[1]], tgt[target_order[1]] + 0.08)
        support_fit = np.clip(support / max(float(tgt[target_order[1]]), 0.08), 0.0, 1.0)
        pattern_fit = 0.62 * top_fit + 0.38 * support_fit
    elif pattern["kind"] == "double_specialist":
        target_top2 = set(int(i) for i in target_order[:2])
        top2_fit = np.array([
            1.0 if set(int(i) for i in row[:2]) == target_top2 else 0.35 if int(row[0]) in target_top2 else 0.0
            for row in cand_order
        ])
        third_not_too_high = np.clip(1.0 - np.maximum(cand[:, target_order[2]] - tgt[target_order[2]] - 0.08, 0.0) / 0.22, 0.0, 1.0)
        pattern_fit = 0.70 * top2_fit + 0.30 * third_not_too_high
    elif pattern["kind"] == "balanced":
        spread = cand.max(axis=1) - cand.min(axis=1)
        target_spread = float(tgt.max() - tgt.min())
        pattern_fit = np.clip(1.0 - np.abs(spread - target_spread) / 0.16, 0.0, 1.0)
    else:
        top_fit = (cand_order[:, 0] == target_order[0]).astype(float)
        gap_shape = gap_fit
        pattern_fit = 0.50 * top_fit + 0.50 * gap_shape

    return 0.48 * pattern_fit + 0.34 * gap_fit + 0.12 * level + 0.06 * ratio


def mental_similarity(candidate_matrix, target):
    cand = candidate_matrix[:, MENTAL_IDX]
    tgt = target[MENTAL_IDX]
    level = level_similarity(cand, tgt, scale=0.42)
    tgt_dom = int(np.argmax(tgt))
    tgt_sorted = np.sort(tgt)
    tgt_gap = float(tgt_sorted[-1] - tgt_sorted[-2]) if len(tgt_sorted) >= 2 else 0.0
    cand_dom = np.argmax(cand, axis=1)
    same_dom = (cand_dom == tgt_dom).astype(float)
    dom_bonus = same_dom * min(1.0, tgt_gap / 0.12)
    return 0.72 * level + 0.28 * dom_bonus


def line_similarity(candidate_matrix, target):
    return level_similarity(candidate_matrix[:, LINE_IDX], target[LINE_IDX], scale=0.45)


def score_candidate_periods(candidate_matrix, target, global_mean):
    if candidate_matrix.size == 0:
        return np.zeros(0, dtype=float)
    formation = formation_similarity(candidate_matrix, target)
    core = core_similarity(candidate_matrix, target)
    mental = mental_similarity(candidate_matrix, target)
    line = line_similarity(candidate_matrix, target)

    excess_all = np.maximum(candidate_matrix.mean(axis=1) - target.mean() - 0.05, 0.0)
    excess_irrelevant = np.maximum(candidate_matrix[:, FORMATION_IDX] - target[FORMATION_IDX] - 0.10, 0.0).mean(axis=1)
    low_floor = np.maximum(global_mean - candidate_matrix, 0.0).mean(axis=1)
    return (
        0.56 * formation
        + 0.22 * core
        + 0.17 * mental
        + 0.05 * line
        - 0.10 * excess_all
        - 0.10 * excess_irrelevant
        - 0.06 * low_floor
    )


def analyze_slot(rows, params_by_player, player_index, candidates, candidate_period_owners, candidate_matrix):
    usable = []
    for r in rows:
        pid = to_int(r["player_id"])
        pr = peak_row(params_by_player.get(pid) or [])
        if not pr:
            continue
        player = player_index.get(pid, {})
        cat = normalize_category(player.get("category"))
        usable.append((r, pr, cat))

    n = len(usable)
    unique_players = len({to_int(r["player_id"]) for r, _, _ in usable})
    if n < MIN_SAMPLES or unique_players < MIN_UNIQUE_PLAYERS:
        return {
            "status": "insufficient",
            "sampleSize": n,
            "uniquePlayers": unique_players,
            "minSamples": MIN_SAMPLES,
            "minUniquePlayers": MIN_UNIQUE_PLAYERS,
            "top": [],
            "requirements": [],
        }

    feature_matrix = np.vstack([row_feature_vector(pr) for _, pr, _ in usable])
    means = feature_matrix.mean(axis=0)
    stds = feature_matrix.std(axis=0)
    stds[stds < 1e-6] = 1.0
    z = (feature_matrix - means) / stds
    cat_matrix = np.zeros((n, len(CATEGORY_KEYS)), dtype=float)
    for idx, (_, _, cat) in enumerate(usable):
        if cat in CATEGORY_KEYS:
            cat_matrix[idx, CATEGORY_KEYS.index(cat)] = 1.0
    X = np.column_stack([np.ones(n), z, cat_matrix])
    y = np.array([to_float(r["pts"]) for r, _, _ in usable], dtype=float)
    coefs = ridge_fit(X, y)

    category_effects = {
        CATEGORY_KEYS[i]: float(coefs[1 + len(FEATURES) + i])
        for i in range(len(CATEGORY_KEYS))
    }
    adjusted_y = np.array([
        to_float(r["pts"]) - category_effects.get(cat, 0.0)
        for r, _, cat in usable
    ], dtype=float)

    player_perf = {}
    for idx, (r, pr, cat) in enumerate(usable):
        pid = to_int(r["player_id"])
        if pid not in player_perf:
            player_perf[pid] = {
                "count": 0,
                "pts": 0.0,
                "vector": row_feature_vector(pr),
                "name": player_index.get(pid, {}).get("name", str(pid)),
            }
        player_perf[pid]["count"] += 1
        player_perf[pid]["pts"] += float(adjusted_y[idx])

    perf_rows = []
    for pid, stat in player_perf.items():
        count = int(stat["count"])
        avg_pts = float(stat["pts"] / count) if count else 0.0
        reliability = min(1.0, math.sqrt(count / 8.0))
        perf_rows.append({
            "playerId": pid,
            "playerName": stat["name"],
            "count": count,
            "avgPts": avg_pts,
            "reliability": reliability,
            "vector": stat["vector"],
            "score": avg_pts * (0.65 + 0.35 * reliability),
        })
    perf_rows.sort(key=lambda x: (-x["score"], -x["count"], x["playerId"]))
    top_k = max(5, min(14, math.ceil(unique_players * 0.28)))
    reference_players = perf_rows[:top_k]
    ref_scores = np.array([p["score"] for p in reference_players], dtype=float)
    cutoff = float(np.quantile(ref_scores, 0.35)) if len(ref_scores) else 0.0
    ref_weights = np.array([
        max(0.05, (p["score"] - cutoff) + 0.05) * math.sqrt(max(1, p["count"]))
        for p in reference_players
    ], dtype=float)
    ref_matrix = np.vstack([p["vector"] for p in reference_players])
    target = np.average(ref_matrix, axis=0, weights=ref_weights)
    target = np.clip(target, 0.0, 1.0)
    global_mean = np.mean(feature_matrix, axis=0)

    all_period_scores = score_candidate_periods(candidate_matrix, target, global_mean)
    scores_by_candidate = defaultdict(list)
    for idx, (ci, _) in enumerate(candidate_period_owners):
        scores_by_candidate[ci].append(float(all_period_scores[idx]))

    top = []
    for ci, candidate in enumerate(candidates):
        best = candidate_best_score(candidate, scores_by_candidate.get(ci, []))
        if not best:
            continue
        top.append({
            "playerId": candidate["id"],
            "playerName": candidate["name"],
            "playerFullName": candidate["fullName"],
            "category": candidate["category"],
            "rate": candidate["rate"],
            "score": best["score"],
            "bestSeason": best["season"],
            "params": best["params"],
        })
    top.sort(key=lambda x: (-float(x["score"]), x["category"] != "NR", x["playerName"], x["playerId"]))

    return {
        "status": "ok",
        "sampleSize": n,
        "uniquePlayers": unique_players,
        "confidence": confidence_label(n, unique_players),
        "method": "top_performer_profile_similarity",
        "categoryEffects": {
            key: round(value, 4)
            for key, value in category_effects.items()
        },
        "target": {
            FEATURES[i][0]: round(float(target[i]), 4)
            for i in range(len(FEATURES))
            if abs(float(target[i] - global_mean[i])) >= 0.015
        },
        "corePattern": core_pattern(target[CORE_IDX]),
        "referencePlayers": [
            {
                "playerId": int(p["playerId"]),
                "playerName": p["playerName"],
                "uses": int(p["count"]),
                "avgPts": round(float(p["avgPts"]), 4),
            }
            for p in reference_players[:8]
        ],
        "requirements": target_importance(target, global_mean),
        "top": top[:TOP_N],
    }


def build_ai(master_db):
    conn = sqlite3.connect(str(master_db))
    conn.row_factory = sqlite3.Row
    try:
        player_index = load_player_index(conn)
        recent_ss_ids = load_recent_ss_ids(conn)
        params_by_player = load_param_rows(conn)
        candidates = build_candidates(player_index, params_by_player, recent_ss_ids)
        candidate_matrix, candidate_period_owners = build_candidate_matrix(candidates)
        formation_ids_all = [
            to_int(r["ZFORMATION_ID"])
            for r in conn.execute("SELECT ZFORMATION_ID FROM ao__ZMOFORMATION WHERE ZFORMATION_ID IS NOT NULL").fetchall()
        ]
        cc_rows = conn.execute(
            """
            SELECT formation_id, member_order, player_id, pts
            FROM cc_players
            WHERE is_starting11 = 1
              AND pts IS NOT NULL
              AND formation_id IS NOT NULL
              AND member_order BETWEEN 1 AND 11
              AND player_id IS NOT NULL
            """
        ).fetchall()
    finally:
        conn.close()

    rows_by_slot = defaultdict(list)
    for r in cc_rows:
        rows_by_slot[(to_int(r["formation_id"]), to_int(r["member_order"]))].append(dict(r))

    formation_ids = sorted({fid for fid in formation_ids_all if fid > 0})
    outputs = {}
    for fid in formation_ids:
        slots = {}
        for slot in range(1, 12):
            slots[str(slot)] = analyze_slot(
                rows_by_slot.get((fid, slot), []),
                params_by_player,
                player_index,
                candidates,
                candidate_period_owners,
                candidate_matrix,
            )
        outputs[fid] = {
            "formationId": fid,
            "criteria": {
                "minSamples": MIN_SAMPLES,
                "minUniquePlayers": MIN_UNIQUE_PLAYERS,
                "candidatePool": {
                    "nr": "active NR players",
                    "cc": "active CC players",
                    "ss": "players in latest two scout events",
                    "cm": "excluded",
                    "retired": "excluded",
                },
                "features": [{"key": key, "label": label} for key, label, _, _ in FEATURES],
                "method": "high-sample top performer profile similarity with category-effect adjustment",
            },
            "slots": slots,
        }
    player_index_rows = sorted(
        (
            {
                "id": p["id"],
                "name": p["name"],
                "fullName": p["fullName"],
                "nationId": p["nationId"],
                "nationality": p["nationality"],
                "category": p["category"],
                "rate": p["rate"],
                "retired": p["retired"],
            }
            for p in player_index.values()
        ),
        key=lambda x: x["id"],
    )
    return outputs, {
        "meta": {
            "playerCount": len(player_index_rows),
            "recentScoutPlayerCount": len(recent_ss_ids),
            "candidateCount": len(candidates),
        },
        "players": player_index_rows,
    }


def write_outputs(outputs, player_index, app_dir, docs_dir):
    for root in [app_dir, docs_dir]:
        ai_dir = root / "formation_ai"
        if ai_dir.exists():
            shutil.rmtree(ai_dir)
        ai_dir.mkdir(parents=True, exist_ok=True)
        for fid, payload in outputs.items():
            (ai_dir / f"{fid}.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (root / "player_index.json").write_text(json.dumps(player_index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build per-formation AI slot fit data.")
    parser.add_argument("--master-db", default="/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db/wsm_2604261329.sqlite3")
    parser.add_argument("--app-dir", default="/Users/k.nishimura/work/coding/websoccer-player-search/app")
    parser.add_argument("--docs-dir", default="/Users/k.nishimura/work/coding/websoccer-player-search/docs")
    args = parser.parse_args()

    outputs, player_index = build_ai(Path(args.master_db).expanduser())
    write_outputs(outputs, player_index, Path(args.app_dir), Path(args.docs_dir))
    ok_slots = sum(1 for payload in outputs.values() for s in payload["slots"].values() if s.get("status") == "ok")
    print(f"formations={len(outputs)} ok_slots={ok_slots} players={player_index['meta']['playerCount']} candidates={player_index['meta']['candidateCount']}")


if __name__ == "__main__":
    main()
