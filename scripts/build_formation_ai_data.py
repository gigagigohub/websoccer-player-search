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


def coefficient_weights(coefs):
    raw = np.maximum(coefs[: len(FEATURES)], 0.0)
    if raw.sum() <= 1e-9:
        raw = np.abs(coefs[: len(FEATURES)])
    if raw.sum() <= 1e-9:
        raw = np.ones(len(FEATURES), dtype=float)
    weights = raw / raw.sum()
    return weights


def feature_importance(weights, limit=6):
    rows = []
    for i, w in enumerate(weights):
        if w < 0.005:
            continue
        key, label, _, _ = FEATURES[i]
        rows.append({"key": key, "label": label, "weight": round(float(w), 6)})
    rows.sort(key=lambda x: (-x["weight"], x["key"]))
    return rows[:limit]


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


def score_candidate_periods(candidate_matrix, weights, concentration):
    weighted_idx = np.argsort(weights)[::-1]
    top_k = max(3, min(8, int(math.ceil(len(weights) * 0.25))))
    relevant = set(int(i) for i in weighted_idx[:top_k] if weights[i] > 0)
    if candidate_matrix.size == 0:
        return np.zeros(0, dtype=float)
    base = candidate_matrix @ weights
    if relevant:
        non_relevant = [i for i in range(len(weights)) if i not in relevant]
        excess = candidate_matrix[:, non_relevant].mean(axis=1) if non_relevant else 0.0
    else:
        excess = 0.0
    return base - (0.12 * concentration * excess)


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
    weights = coefficient_weights(coefs[1 : 1 + len(FEATURES)])
    concentration = float(np.sum(weights * weights))

    all_period_scores = score_candidate_periods(candidate_matrix, weights, concentration)
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
        "method": "category_adjusted_ridge_slot_fit",
        "categoryEffects": {
            CATEGORY_KEYS[i]: round(float(coefs[1 + len(FEATURES) + i]), 4)
            for i in range(len(CATEGORY_KEYS))
        },
        "concentration": round(concentration, 6),
        "requirements": feature_importance(weights),
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
                "method": "CC match slot rating regression with category-effect adjustment",
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
