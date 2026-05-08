#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import sqlite3
from collections import defaultdict
from pathlib import Path


DEFAULT_DB = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db/wsm_2605042226.sqlite3")
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "app" / "prepared"
MIN_SLOT_USES = 20


def to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def mean(values):
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def stdev(values):
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    mu = mean(vals)
    return math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))


def zscore(value, mu, sd):
    return 0.0 if sd <= 1e-9 else (value - mu) / sd


def sigmoid(value):
    if value > 30:
        return 1.0
    if value < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def rank_fit(rank):
    return 100.0 / (1.0 + 0.35 * (rank - 1)) if rank > 0 else 0.0


def points_from_result(result):
    value = str(result or "").strip().upper()
    if value == "W":
        return 3.0
    if value == "D":
        return 1.0
    if value == "L":
        return 0.0
    return None


def corr(xs, ys):
    xs = list(xs)
    ys = list(ys)
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mx = mean(xs)
    my = mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(vx * vy)


def load_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    teams = [dict(row) for row in conn.execute("SELECT * FROM cc_teams ORDER BY season, world_id, match_id, side")]
    players = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM cc_players WHERE is_starting11=1 ORDER BY season, world_id, match_id, side, member_order"
        )
    ]
    return teams, players


def build_maps(exclude_season, teams, players):
    by_slot_player = defaultdict(list)
    by_player = defaultdict(list)
    for row in players:
        if to_int(row.get("season")) == exclude_season:
            continue
        fid = to_int(row.get("formation_id"))
        slot = to_int(row.get("member_order"))
        pid = to_int(row.get("player_id"))
        pts = to_float(row.get("pts"), None)
        if fid <= 0 or slot <= 0 or pid <= 0 or pts is None:
            continue
        by_slot_player[(fid, slot, pid)].append(pts)
        by_player[pid].append(pts)

    slot_rank = {}
    slot_avg = {}
    items_by_slot = defaultdict(list)
    for (fid, slot, pid), pts_list in by_slot_player.items():
        uses = len(pts_list)
        if uses < MIN_SLOT_USES:
            continue
        items_by_slot[(fid, slot)].append((pid, uses, mean(pts_list)))

    for (fid, slot), items in items_by_slot.items():
        items.sort(key=lambda x: (-x[2], -x[1], x[0]))
        avg_values = [item[2] for item in items]
        avg_mu = mean(avg_values)
        avg_sd = stdev(avg_values)
        for rank, (pid, uses, avg_pts) in enumerate(items, start=1):
            slot_rank[(fid, slot, pid)] = rank_fit(rank)
            slot_avg[(fid, slot, pid)] = 50.0 + 10.0 * zscore(avg_pts, avg_mu, avg_sd)

    def result_stat_map(field):
        by_key = defaultdict(lambda: {"points": [], "gd": []})
        global_points = []
        global_gds = []
        for row in teams:
            if to_int(row.get("season")) == exclude_season:
                continue
            key = to_int(row.get(field))
            pts = points_from_result(row.get("result"))
            gf = to_float(row.get("goals_for"), None)
            ga = to_float(row.get("goals_against"), None)
            if key <= 0 or pts is None or gf is None or ga is None:
                continue
            gd = gf - ga
            by_key[key]["points"].append(pts)
            by_key[key]["gd"].append(gd)
            global_points.append(pts)
            global_gds.append(gd)

        global_ppg = mean(global_points)
        global_gd = mean(global_gds)
        rows = []
        prior = 80
        for key, stat in by_key.items():
            n = len(stat["points"])
            ppg = (mean(stat["points"]) * n + global_ppg * prior) / (n + prior)
            gd = (mean(stat["gd"]) * n + global_gd * prior) / (n + prior)
            rows.append((key, ppg, gd))
        ppg_mu = mean(row[1] for row in rows)
        ppg_sd = stdev(row[1] for row in rows)
        gd_mu = mean(row[2] for row in rows)
        gd_sd = stdev(row[2] for row in rows)
        return {key: 0.65 * zscore(ppg, ppg_mu, ppg_sd) + 0.35 * zscore(gd, gd_mu, gd_sd) for key, ppg, gd in rows}

    formation_score = result_stat_map("formation_id")
    coach_score = result_stat_map("headcoach_id")

    player_rows = []
    player_avgs = []
    prior = 30
    for pid, pts_list in by_player.items():
        if len(pts_list) < 10:
            continue
        avg = (mean(pts_list) * len(pts_list) + 3.0 * prior) / (len(pts_list) + prior)
        player_rows.append((pid, avg))
        player_avgs.append(avg)
    avg_mu = mean(player_avgs)
    avg_sd = stdev(player_avgs)
    player_overall = {pid: 50.0 + 10.0 * zscore(avg, avg_mu, avg_sd) for pid, avg in player_rows}

    return slot_rank, slot_avg, formation_score, coach_score, player_overall


def extract_features(team, players_by_side, maps):
    slot_rank, slot_avg, formation_score, coach_score, player_overall = maps
    fid = to_int(team.get("formation_id"))
    members = players_by_side.get(
        (to_int(team.get("season")), to_int(team.get("world_id")), to_int(team.get("match_id")), team.get("side")),
        [],
    )
    rank_scores = []
    avg_scores = []
    overall_scores = []
    for member in members:
        slot = to_int(member.get("member_order"))
        pid = to_int(member.get("player_id"))
        rank_scores.append(slot_rank.get((fid, slot, pid), 0.0))
        avg_scores.append(slot_avg.get((fid, slot, pid), 50.0))
        overall_scores.append(player_overall.get(pid, 50.0))
    if len(rank_scores) < 11:
        return None

    rank_sorted = sorted(rank_scores)
    return {
        "slotRank": mean(rank_scores),
        "slotFloor": mean(rank_sorted[:3]),
        "slotTop": mean(rank_sorted[-5:]),
        "slotAvg": mean(avg_scores),
        "playerOverall": mean(overall_scores),
        "formation": formation_score.get(fid, 0.0),
        "coach": coach_score.get(to_int(team.get("headcoach_id")), 0.0),
    }


def build_examples(teams, players):
    players_by_side = defaultdict(list)
    for row in players:
        players_by_side[
            (to_int(row.get("season")), to_int(row.get("world_id")), to_int(row.get("match_id")), row.get("side"))
        ].append(row)

    match_sides = defaultdict(dict)
    for row in teams:
        match_sides[(to_int(row.get("season")), to_int(row.get("world_id")), to_int(row.get("match_id")))][row.get("side")] = row

    seasons = sorted({to_int(row.get("season")) for row in teams})
    examples = []
    team_feature_rows = []
    for season in seasons:
        maps = build_maps(season, teams, players)
        for (match_season, world_id, match_id), sides in match_sides.items():
            if match_season != season or "home" not in sides or "away" not in sides:
                continue
            home = sides["home"]
            away = sides["away"]
            home_features = extract_features(home, players_by_side, maps)
            away_features = extract_features(away, players_by_side, maps)
            if not home_features or not away_features:
                continue

            home_result = str(home.get("result") or "").upper()
            away_result = str(away.get("result") or "").upper()
            y = None
            if home_result == "W" and away_result == "L":
                y = 1
            elif home_result == "L" and away_result == "W":
                y = 0
            gd = to_float(home.get("goals_for")) - to_float(home.get("goals_against"))
            diff = {key: home_features[key] - away_features[key] for key in home_features}
            examples.append({"y": y, "gd": gd, "diff": diff, "season": season})

            for team, features in ((home, home_features), (away, away_features)):
                team_feature_rows.append(
                    {
                        "season": season,
                        "worldId": to_int(team.get("world_id")),
                        "teamId": to_int(team.get("team_id")),
                        "teamName": team.get("team_name") or "",
                        "formationName": team.get("formation_name") or "",
                        "side": team.get("side") or "",
                        **features,
                    }
                )
    return examples, team_feature_rows


def component_stats(examples, feature_names):
    decisive = [row for row in examples if row["y"] is not None]
    return {
        name: {
            "mu": mean(row["diff"][name] for row in decisive),
            "sd": stdev(row["diff"][name] for row in decisive) or 1.0,
        }
        for name in feature_names
    }


def normalized_diff(row, name, stats):
    stat = stats[name]
    return (row["diff"][name] - stat["mu"]) / stat["sd"]


def evaluate_formula(examples, weights, stats):
    decisive = [row for row in examples if row["y"] is not None]
    all_scores = [sum(weight * normalized_diff(row, name, stats) for name, weight in weights.items()) for row in examples]
    decisive_scores = [sum(weight * normalized_diff(row, name, stats) for name, weight in weights.items()) for row in decisive]
    goal_diffs = [row["gd"] for row in examples]
    best = {"logLoss": 999.0, "accuracy": 0.0, "scale": 0.0}
    for scale in (0.2, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0):
        losses = []
        correct = 0
        for score, row in zip(decisive_scores, decisive):
            p = min(max(sigmoid(scale * score), 1e-6), 1 - 1e-6)
            y = row["y"]
            losses.append(-(y * math.log(p) + (1 - y) * math.log(1 - p)))
            correct += int((p >= 0.5) == bool(y))
        log_loss = mean(losses)
        accuracy = correct / len(decisive) if decisive else 0.0
        if log_loss < best["logLoss"]:
            best = {"logLoss": log_loss, "accuracy": accuracy, "scale": scale}
    best["goalDiffCorr"] = corr(all_scores, goal_diffs)
    return best


def evaluate_single_features(examples, feature_names):
    decisive = [row for row in examples if row["y"] is not None]
    rows = []
    for name in feature_names:
        comparable = [row for row in decisive if abs(row["diff"][name]) > 1e-9]
        accuracy = (
            sum(int((row["diff"][name] > 0) == bool(row["y"])) for row in comparable) / len(comparable)
            if comparable
            else 0.0
        )
        rows.append(
            {
                "feature": name,
                "accuracy": accuracy,
                "goalDiffCorr": corr([row["diff"][name] for row in examples], [row["gd"] for row in examples]),
                "meanAbsDiff": mean(abs(row["diff"][name]) for row in examples),
            }
        )
    return rows


def build_team_scores(team_feature_rows, weights):
    grouped = defaultdict(list)
    for row in team_feature_rows:
        grouped[(row["season"], row["worldId"], row["teamId"], row["teamName"])].append(row)
    team_rows = []
    for (season, world_id, team_id, team_name), rows in grouped.items():
        out = {
            "season": season,
            "worldId": world_id,
            "teamId": team_id,
            "teamName": team_name,
            "formationName": max(
                (row["formationName"] for row in rows),
                key=[row["formationName"] for row in rows].count,
            ),
            "matches": len(rows),
        }
        for name in ("slotRank", "slotFloor", "slotTop", "slotAvg", "playerOverall", "formation", "coach"):
            out[name] = mean(row[name] for row in rows)
        team_rows.append(out)

    norm = {}
    for name in weights:
        vals = [row[name] for row in team_rows]
        norm[name] = {"mu": mean(vals), "sd": stdev(vals) or 1.0}
    raw_values = []
    for row in team_rows:
        raw = sum(weight * zscore(row[name], norm[name]["mu"], norm[name]["sd"]) for name, weight in weights.items())
        row["rawPower"] = raw
        raw_values.append(raw)
    raw_mu = mean(raw_values)
    raw_sd = stdev(raw_values) or 1.0
    for row in team_rows:
        row["teamPower"] = 50.0 + 10.0 * zscore(row["rawPower"], raw_mu, raw_sd)
    team_rows.sort(key=lambda row: (-row["teamPower"], row["season"], row["worldId"], row["teamName"]))
    return team_rows


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_html(path, examples, single_rows, formula_rows, team_rows):
    def pct(value):
        return f"{value * 100:.1f}%"

    single_html = "\n".join(
        f"<tr><td>{html.escape(row['feature'])}</td><td>{pct(row['accuracy'])}</td>"
        f"<td>{row['goalDiffCorr']:.3f}</td><td>{row['meanAbsDiff']:.2f}</td></tr>"
        for row in single_rows
    )
    formula_html = "\n".join(
        f"<tr><td>{html.escape(row['name'])}</td><td>{html.escape(row['weightsText'])}</td>"
        f"<td>{row['logLoss']:.4f}</td><td>{pct(row['accuracy'])}</td>"
        f"<td>{row['goalDiffCorr']:.3f}</td><td>{row['scale']:.2f}</td></tr>"
        for row in formula_rows
    )
    team_html = "\n".join(
        f"<tr><td>{idx}</td><td>{row['season']}</td><td>{row['worldId']}</td><td>{html.escape(str(row['teamName']))}</td>"
        f"<td class='strong'>{row['teamPower']:.1f}</td><td>{row['matches']}</td>"
        f"<td>{html.escape(str(row['formationName']))}</td><td>{row['playerOverall']:.1f}</td>"
        f"<td>{row['slotRank']:.1f}</td><td>{row['slotFloor']:.1f}</td><td>{row['formationScore']:.3f}</td></tr>"
        for idx, row in enumerate(team_rows[:50], start=1)
    )

    decisive = sum(1 for row in examples if row["y"] is not None)
    draws = len(examples) - decisive
    path.write_text(
        f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>CC Team Power Logic</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --panel:#0e1a2c; --line:#243653; --text:#eaf1ff; --muted:#91a5c4; --accent:#67d3ff; --strong:#ffe27a; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:16px; border-bottom:1px solid var(--line); background:#091525; }}
    main {{ padding:16px; max-width:1160px; margin:0 auto; }}
    h1 {{ font-size:20px; margin:0 0 6px; }}
    h2 {{ font-size:16px; margin:22px 0 10px; }}
    p, li {{ color:#c9d7ec; line-height:1.65; }}
    .muted {{ color:var(--muted); font-size:12px; }}
    .panel {{ border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:12px; margin:12px 0; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; min-width:760px; }}
    th, td {{ padding:8px 9px; border-bottom:1px solid rgba(255,255,255,.08); text-align:right; white-space:nowrap; }}
    th:first-child, td:first-child, th:nth-child(4), td:nth-child(4) {{ text-align:left; }}
    th {{ position:sticky; top:0; background:#13213a; color:#d7e6ff; }}
    .strong {{ color:var(--strong); font-weight:800; }}
    code {{ color:#d9ecff; }}
  </style>
</head>
<body>
  <header>
    <h1>CC Team Power Logic</h1>
    <div class="muted">Matches {len(examples)} / decisive {decisive} / draws {draws} / validation: leave-one-season-out feature build</div>
  </header>
  <main>
    <section class="panel">
      <h2>Recommended Logic</h2>
      <p>勝敗に一番近い単独要素は、slotランキングではなく <b>PlayerOverall</b> でした。slot適合は単独でも効きますが、選手カード自体の評価点の出やすさを主軸にした方が実勝敗に近いです。</p>
      <p>実装用の解釈しやすい指数は以下です。</p>
      <p><code>TeamPowerRaw = 1.00 * PlayerOverallZ + 0.50 * SlotRankZ + 0.20 * SlotFloorZ + 0.30 * FormationZ</code></p>
      <p><code>TeamPower = 50 + 10 * z(TeamPowerRaw)</code></p>
      <ul>
        <li><b>PlayerOverall</b>: 選手IDごとの過去平均評価点。slotやフォメを問わず、そのカードが評価点を出しやすいか。</li>
        <li><b>SlotRank</b>: 同一フォーメーション・同一slotで、過去Avg上位に載る選手が使われているか。使用数20以下は除外。</li>
        <li><b>SlotFloor</b>: 下位3slotのSlotRank平均。穴の大きさをペナルティ的に拾う。</li>
        <li><b>Formation</b>: 過去のフォーメーション勝点/GD成績。監督は寄与が小さいため指数からは外す。</li>
      </ul>
    </section>

    <h2>Formula Backtest</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Formula</th><th>Weights</th><th>LogLoss</th><th>Win Acc</th><th>GD Corr</th><th>Scale</th></tr></thead>
        <tbody>{formula_html}</tbody>
      </table>
    </div>

    <h2>Single Component Backtest</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Component</th><th>Win Acc</th><th>GD Corr</th><th>Mean Abs Diff</th></tr></thead>
        <tbody>{single_html}</tbody>
      </table>
    </div>

    <h2>Top TeamPower Samples</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Season</th><th>World</th><th>Team</th><th>Power</th><th>Matches</th><th>Formation</th><th>Player</th><th>Slot</th><th>Floor</th><th>Form</th></tr></thead>
        <tbody>{team_html}</tbody>
      </table>
    </div>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    teams, players = load_db(args.db)
    examples, team_feature_rows = build_examples(teams, players)
    feature_names = ["slotRank", "slotFloor", "slotTop", "slotAvg", "playerOverall", "formation", "coach"]
    stats = component_stats(examples, feature_names)
    single_rows = evaluate_single_features(examples, feature_names)

    formulas = [
        ("Player only", {"playerOverall": 1.0}),
        ("Slot only", {"slotRank": 1.0}),
        ("Player + Formation", {"playerOverall": 1.0, "formation": 0.3}),
        ("Player + Slot + Formation", {"playerOverall": 1.0, "slotRank": 0.3, "formation": 0.3}),
        ("Recommended TeamPower", {"playerOverall": 1.0, "slotRank": 0.5, "slotFloor": 0.2, "formation": 0.3}),
        ("Recommended + Coach", {"playerOverall": 1.0, "slotRank": 0.5, "formation": 0.3, "coach": 0.1}),
    ]
    formula_rows = []
    for name, weights in formulas:
        metrics = evaluate_formula(examples, weights, stats)
        formula_rows.append(
            {
                "name": name,
                "weightsText": " + ".join(f"{weight:g}*{component}" for component, weight in weights.items()),
                **metrics,
            }
        )

    recommended = formulas[4][1]
    team_rows = build_team_scores(team_feature_rows, recommended)
    for row in team_rows:
        row["formationScore"] = row.pop("formation")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.out_dir / "cc_team_power_logic_metrics.csv",
        formula_rows,
        ["name", "weightsText", "logLoss", "accuracy", "goalDiffCorr", "scale"],
    )
    write_csv(
        args.out_dir / "cc_team_power_scores.csv",
        team_rows,
        [
            "season",
            "worldId",
            "teamId",
            "teamName",
            "teamPower",
            "matches",
            "formationName",
            "playerOverall",
            "slotRank",
            "slotFloor",
            "slotTop",
            "slotAvg",
            "formationScore",
            "coach",
        ],
    )
    write_html(args.out_dir / "cc_team_power_logic.html", examples, single_rows, formula_rows, team_rows)
    print(f"[DONE] examples={len(examples)} metrics={args.out_dir / 'cc_team_power_logic_metrics.csv'}")
    for row in formula_rows:
        print(
            f"{row['name']}: acc={row['accuracy']*100:.2f}% "
            f"corr={row['goalDiffCorr']:.3f} logLoss={row['logLoss']:.4f}"
        )


if __name__ == "__main__":
    main()
