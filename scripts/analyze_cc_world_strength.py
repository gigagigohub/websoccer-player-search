#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_DB = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db/wsm_2605042226.sqlite3")
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "app" / "prepared"
MIN_SLOT_RANK_USES = 21


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


def points_from_result(result: str) -> float | None:
    r = (result or "").strip().upper()
    if r == "W":
        return 3.0
    if r == "D":
        return 1.0
    if r == "L":
        return 0.0
    return None


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
    if sd <= 1e-9:
        return 0.0
    return (value - mu) / sd


def clamp(value, lo=-3.0, hi=3.0):
    return max(lo, min(hi, value))


def percentile(values, p):
    vals = sorted(values)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def read_rows(conn, table, order_by):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}")]


def load_world_names(conn):
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT ZID, ZNAME FROM ao__ZMOWORLD ORDER BY ZID").fetchall()
    return {to_int(row["ZID"]): row["ZNAME"] for row in rows}


def build_formation_scores(team_rows):
    rows = []
    global_points = []
    global_gds = []
    by_formation = defaultdict(lambda: {"points": [], "gds": []})
    for row in team_rows:
        fid = to_int(row.get("formation_id"))
        pts = points_from_result(row.get("result"))
        gf = to_float(row.get("goals_for"), None)
        ga = to_float(row.get("goals_against"), None)
        if fid <= 0 or pts is None or gf is None or ga is None:
            continue
        gd = gf - ga
        by_formation[fid]["points"].append(pts)
        by_formation[fid]["gds"].append(gd)
        global_points.append(pts)
        global_gds.append(gd)

    global_ppg = mean(global_points)
    global_gd = mean(global_gds)
    prior = 80
    raw = {}
    ppg_values = []
    gd_values = []
    for fid, stat in by_formation.items():
        n = len(stat["points"])
        ppg = mean(stat["points"])
        gd = mean(stat["gds"])
        shrunk_ppg = ((ppg * n) + (global_ppg * prior)) / (n + prior)
        shrunk_gd = ((gd * n) + (global_gd * prior)) / (n + prior)
        raw[fid] = {"n": n, "ppg": shrunk_ppg, "gd": shrunk_gd}
        ppg_values.append(shrunk_ppg)
        gd_values.append(shrunk_gd)

    ppg_mu, ppg_sd = mean(ppg_values), stdev(ppg_values)
    gd_mu, gd_sd = mean(gd_values), stdev(gd_values)
    scores = {}
    for fid, stat in raw.items():
        ppg_z = zscore(stat["ppg"], ppg_mu, ppg_sd)
        gd_z = zscore(stat["gd"], gd_mu, gd_sd)
        scores[fid] = {
            "n": stat["n"],
            "score": clamp(0.65 * ppg_z + 0.35 * gd_z),
            "ppg": stat["ppg"],
            "gd": stat["gd"],
        }
    return scores


def rank_fit_score(rank):
    if rank <= 0:
        return 0.0
    return 100.0 / (1.0 + 0.35 * (rank - 1))


def build_slot_fit_scores(player_rows):
    by_player_slot = defaultdict(list)
    for row in player_rows:
        if str(row.get("is_starting11") or "") != "1":
            continue
        fid = to_int(row.get("formation_id"))
        slot = to_int(row.get("member_order"))
        pid = to_int(row.get("player_id"))
        pts = to_float(row.get("pts"), None)
        if fid <= 0 or slot <= 0 or pid <= 0 or pts is None:
            continue
        by_player_slot[(fid, slot, pid)].append(pts)

    candidates_by_slot = defaultdict(list)
    for (fid, slot, pid), pts_list in by_player_slot.items():
        uses = len(pts_list)
        if uses < MIN_SLOT_RANK_USES:
            continue
        avg = mean(pts_list)
        candidates_by_slot[(fid, slot)].append({"playerId": pid, "uses": uses, "avgPts": avg})

    scores = {}
    slot_rankings = {}
    for (fid, slot), items in candidates_by_slot.items():
        items.sort(key=lambda x: (-x["avgPts"], -x["uses"], x["playerId"]))
        ranking = []
        for rank, item in enumerate(items, start=1):
            score = rank_fit_score(rank)
            row = {
                "rank": rank,
                "playerId": item["playerId"],
                "uses": item["uses"],
                "avgPts": item["avgPts"],
                "score": score,
            }
            ranking.append(row)
            scores[(fid, slot, item["playerId"])] = row
        slot_rankings[(fid, slot)] = ranking
    return scores, slot_rankings


def build_team_entries(team_rows, player_rows, formation_scores, slot_scores, world_names):
    players_by_instance = defaultdict(list)
    for row in player_rows:
        if str(row.get("is_starting11") or "") != "1":
            continue
        key = (
            to_int(row.get("season")),
            to_int(row.get("world_id")),
            to_int(row.get("match_id")),
            str(row.get("side") or "").strip().lower(),
        )
        players_by_instance[key].append(row)

    teams = {}
    team_match_count = Counter()
    for row in team_rows:
        season = to_int(row.get("season"))
        world_id = to_int(row.get("world_id"))
        team_id = to_int(row.get("team_id"))
        if season <= 0 or world_id <= 0 or team_id <= 0:
            continue
        group_key = (season, world_id, team_id)
        team_match_count[group_key] += 1

        match_key = (
            season,
            world_id,
            to_int(row.get("match_id")),
            str(row.get("side") or "").strip().lower(),
        )
        members = players_by_instance.get(match_key, [])
        if len(members) < 11:
            continue
        fid = to_int(row.get("formation_id"))
        cid = to_int(row.get("headcoach_id"))
        member_scores = []
        for member in members:
            slot = to_int(member.get("member_order"))
            pid = to_int(member.get("player_id"))
            if slot <= 0 or pid <= 0:
                continue
            member_scores.append(slot_scores.get((fid, slot, pid), {}).get("score", 0.0))
        if len(member_scores) < 11:
            continue
        lineup_score = mean(member_scores)
        formation_score = formation_scores.get(fid, {}).get("score", 0.0)
        if group_key not in teams:
            teams[group_key] = {
                "season": season,
                "worldId": world_id,
                "worldName": world_names.get(world_id, f"World {world_id}"),
                "teamId": team_id,
                "teamName": row.get("team_name") or str(team_id),
                "lineupScores": [],
                "formationScores": [],
                "formations": Counter(),
                "coaches": Counter(),
            }
        entry = teams[group_key]
        entry["lineupScores"].append(lineup_score)
        entry["formationScores"].append(formation_score)
        entry["formations"][row.get("formation_name") or str(fid)] += 1
        entry["coaches"][row.get("headcoach_name") or str(cid)] += 1

    component_rows = []
    for key, entry in teams.items():
        if not entry["lineupScores"]:
            continue
        component_rows.append({
            "key": key,
            "lineup": mean(entry["lineupScores"]),
            "formation": mean(entry["formationScores"]),
        })

    lineup_mu, lineup_sd = mean(row["lineup"] for row in component_rows), stdev(row["lineup"] for row in component_rows)
    formation_mu, formation_sd = mean(row["formation"] for row in component_rows), stdev(row["formation"] for row in component_rows)

    raw_by_key = {}
    for row in component_rows:
        lineup_z = zscore(row["lineup"], lineup_mu, lineup_sd)
        formation_z = zscore(row["formation"], formation_mu, formation_sd)
        raw_by_key[row["key"]] = 0.70 * lineup_z + 0.30 * formation_z

    raw_values = list(raw_by_key.values())
    raw_mu, raw_sd = mean(raw_values), stdev(raw_values)

    results = []
    for key, entry in teams.items():
        if key not in raw_by_key:
            continue
        raw = raw_by_key[key]
        score = 50 + 10 * zscore(raw, raw_mu, raw_sd)
        formation_name = entry["formations"].most_common(1)[0][0] if entry["formations"] else ""
        coach_name = entry["coaches"].most_common(1)[0][0] if entry["coaches"] else ""
        results.append({
            "season": entry["season"],
            "worldId": entry["worldId"],
            "worldName": entry["worldName"],
            "teamId": entry["teamId"],
            "teamName": entry["teamName"],
            "score": score,
            "rawStrength": raw,
            "lineupComponent": mean(entry["lineupScores"]),
            "formationComponent": mean(entry["formationScores"]),
            "matches": team_match_count[key],
            "formation": formation_name,
            "coach": coach_name,
        })
    return results


def summarize_worlds(team_entries):
    scores = [row["score"] for row in team_entries]
    strong_cutoff = percentile(scores, 0.80)
    elite_cutoff = percentile(scores, 0.90)

    by_world = defaultdict(list)
    by_world_season = defaultdict(list)
    for row in team_entries:
        by_world[row["worldId"]].append(row)
        by_world_season[(row["season"], row["worldId"])].append(row)

    def summarize(rows, extra=None):
        vals = [row["score"] for row in rows]
        strong = [row for row in rows if row["score"] >= strong_cutoff]
        elite = [row for row in rows if row["score"] >= elite_cutoff]
        top_rows = sorted(rows, key=lambda x: (-x["score"], -x["matches"], x["teamName"]))[:5]
        strong_formations = Counter(row["formation"] for row in strong if row.get("formation"))
        out = {
            "teams": len(rows),
            "strongTeams": len(strong),
            "eliteTeams": len(elite),
            "strongShare": len(strong) / len(rows) if rows else 0.0,
            "eliteShare": len(elite) / len(rows) if rows else 0.0,
            "gachiIndex": (len(strong) / len(rows) / 0.20 * 100) if rows else 0.0,
            "avgScore": mean(vals),
            "medianScore": percentile(vals, 0.50),
            "p90Score": percentile(vals, 0.90),
            "avgLineupComponent": mean(row["lineupComponent"] for row in rows),
            "avgFormationComponent": mean(row["formationComponent"] for row in rows),
            "topTeams": "; ".join(f"{r['teamName']}({r['season']}, {r['score']:.1f})" for r in top_rows),
            "strongFormations": "; ".join(f"{name}({count})" for name, count in strong_formations.most_common(5)),
        }
        if extra:
            out.update(extra)
        return out

    world_rows = []
    for world_id, rows in by_world.items():
        seasons = sorted({row["season"] for row in rows})
        world_name = rows[0].get("worldName") or f"World {world_id}"
        item = summarize(rows, {"worldId": world_id, "worldName": world_name, "seasons": f"{seasons[0]}-{seasons[-1]}", "seasonCount": len(seasons)})
        world_rows.append(item)
    world_rows.sort(key=lambda x: (-x["strongShare"], -x["eliteShare"], -x["p90Score"], x["worldId"]))
    for idx, row in enumerate(world_rows, start=1):
        row["rank"] = idx

    world_season_rows = []
    for (season, world_id), rows in by_world_season.items():
        world_name = rows[0].get("worldName") or f"World {world_id}"
        item = summarize(rows, {"season": season, "worldId": world_id, "worldName": world_name})
        world_season_rows.append(item)
    world_season_rows.sort(key=lambda x: (-x["strongShare"], -x["eliteShare"], -x["p90Score"], x["season"], x["worldId"]))
    for idx, row in enumerate(world_season_rows, start=1):
        row["rank"] = idx

    return world_rows, world_season_rows, strong_cutoff, elite_cutoff


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def fmt_pct(value):
    return f"{value * 100:.1f}%"


def write_html(path, world_rows, season_rows, team_entries, strong_cutoff, elite_cutoff, db_path):
    top_worlds = world_rows[:21]
    top_seasons = season_rows[:50]
    season_by_world = defaultdict(list)
    teams_by_world = defaultdict(list)
    for row in season_rows:
        season_by_world[row["worldId"]].append(row)
    for row in team_entries:
        teams_by_world[row["worldId"]].append(row)

    def world_label(row):
        return f"{row['worldId']} {row.get('worldName') or ''}".strip()

    def table_world(rows):
        body = []
        for row in rows:
            body.append(
                "<tr>"
                f"<td>{row['rank']}</td>"
                f"<td>{html.escape(world_label(row))}</td>"
                f"<td>{html.escape(str(row['seasons']))}</td>"
                f"<td>{row['teams']}</td>"
                f"<td class='strong'>{fmt_pct(row['strongShare'])}</td>"
                f"<td>{fmt_pct(row['eliteShare'])}</td>"
                f"<td>{row['gachiIndex']:.0f}</td>"
                f"<td>{row['p90Score']:.1f}</td>"
                f"<td>{row['medianScore']:.1f}</td>"
                f"<td>{row['avgLineupComponent']:.1f}</td>"
                f"<td>{row['avgFormationComponent']:.3f}</td>"
                f"<td class='top'>{html.escape(row['strongFormations'])}</td>"
                "</tr>"
            )
        return "\n".join(body)

    def table_season(rows):
        body = []
        for row in rows:
            body.append(
                "<tr>"
                f"<td>{row['rank']}</td>"
                f"<td>{row['season']}</td>"
                f"<td>{html.escape(world_label(row))}</td>"
                f"<td>{row['teams']}</td>"
                f"<td class='strong'>{fmt_pct(row['strongShare'])}</td>"
                f"<td>{fmt_pct(row['eliteShare'])}</td>"
                f"<td>{row['gachiIndex']:.0f}</td>"
                f"<td>{row['p90Score']:.1f}</td>"
                f"<td class='top'>{html.escape(row['topTeams'])}</td>"
                "</tr>"
            )
        return "\n".join(body)

    def detail_sections(rows):
        sections = []
        for row in rows:
            wid = row["worldId"]
            team_rows = sorted(teams_by_world.get(wid, []), key=lambda x: (-x["score"], -x["matches"], x["teamName"]))
            strong_rows = [team for team in team_rows if team["score"] >= strong_cutoff]
            season_rows_for_world = sorted(season_by_world.get(wid, []), key=lambda x: x["season"])
            formation_mix = Counter(team["formation"] for team in strong_rows if team.get("formation"))

            season_body = "\n".join(
                "<tr>"
                f"<td>{season['season']}</td>"
                f"<td>{fmt_pct(season['strongShare'])}</td>"
                f"<td>{fmt_pct(season['eliteShare'])}</td>"
                f"<td>{season['p90Score']:.1f}</td>"
                f"<td>{season['medianScore']:.1f}</td>"
                f"<td>{html.escape(season['topTeams'])}</td>"
                "</tr>"
                for season in season_rows_for_world
            )
            team_body = "\n".join(
                "<tr>"
                f"<td>{idx}</td>"
                f"<td>{team['season']}</td>"
                f"<td>{html.escape(team['teamName'])}</td>"
                f"<td class='strong'>{team['score']:.1f}</td>"
                f"<td>{team['matches']}</td>"
                f"<td>{html.escape(team['formation'])}</td>"
                f"<td>{html.escape(team['coach'])}</td>"
                f"<td>{team['lineupComponent']:.1f}</td>"
                f"<td>{team['formationComponent']:.3f}</td>"
                "</tr>"
                for idx, team in enumerate(team_rows[:15], start=1)
            )
            mix_html = "".join(
                f"<span class='pill'>{html.escape(name)} <b>{count}</b></span>"
                for name, count in formation_mix.most_common(8)
            ) or "<span class='muted'>No strong teams</span>"
            sections.append(
                f"""
    <section class="world-detail" id="world-{wid}">
      <div class="detail-head">
        <div>
          <h2>{row['rank']}. {html.escape(world_label(row))}</h2>
          <div class="meta-line">Teams {row['teams']} / Strong {row['strongTeams']} / Elite {row['eliteTeams']}</div>
        </div>
        <div class="score-card">
          <span>Strong Share</span>
          <b>{fmt_pct(row['strongShare'])}</b>
        </div>
      </div>
      <div class="metric-grid">
        <div><span>Gachi Index</span><b>{row['gachiIndex']:.0f}</b></div>
        <div><span>Elite Share</span><b>{fmt_pct(row['eliteShare'])}</b></div>
        <div><span>P90</span><b>{row['p90Score']:.1f}</b></div>
        <div><span>Median</span><b>{row['medianScore']:.1f}</b></div>
        <div><span>Avg Rank Fit</span><b>{row['avgLineupComponent']:.1f}</b></div>
        <div><span>Avg Formation</span><b>{row['avgFormationComponent']:.3f}</b></div>
      </div>
      <div class="mix">{mix_html}</div>
      <div class="split">
        <div>
          <h3>Season Trend</h3>
          <div class="table-wrap compact">
            <table>
              <thead><tr><th>Season</th><th>Strong</th><th>Elite</th><th>P90</th><th>Median</th><th>Top Samples</th></tr></thead>
              <tbody>{season_body}</tbody>
            </table>
          </div>
        </div>
        <div>
          <h3>Top Team Samples</h3>
          <div class="table-wrap compact">
            <table>
              <thead><tr><th>#</th><th>Season</th><th>Team</th><th>Score</th><th>Matches</th><th>Formation</th><th>Coach</th><th>RankFit</th><th>Form</th></tr></thead>
              <tbody>{team_body}</tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
"""
            )
        return "\n".join(sections)

    details_html = detail_sections(top_worlds).lstrip()
    content = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>CC World Strength Ranking</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --panel:#0e1a2c; --line:#243653; --text:#eaf1ff; --muted:#92a5c5; --accent:#67d3ff; --strong:#ffe27a; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); }}
    header {{ position:sticky; top:0; z-index:5; padding:14px 16px; background:rgba(7,17,31,.95); border-bottom:1px solid var(--line); backdrop-filter:blur(10px); }}
    h1 {{ margin:0; font-size:18px; }}
    .meta {{ margin-top:6px; color:var(--muted); font-size:12px; line-height:1.45; }}
    main {{ padding:16px; max-width:1180px; margin:0 auto; }}
    section {{ margin:0 0 20px; }}
    h2 {{ font-size:15px; margin:0 0 10px; }}
    h3 {{ font-size:13px; margin:14px 0 8px; color:#cfe1ff; }}
    .note {{ color:var(--muted); font-size:13px; line-height:1.6; margin-bottom:14px; }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    .table-wrap.compact {{ max-height:360px; }}
    table {{ border-collapse:collapse; width:100%; min-width:900px; }}
    .compact table {{ min-width:760px; }}
    th,td {{ padding:9px 10px; border-bottom:1px solid rgba(255,255,255,.07); font-size:13px; text-align:left; vertical-align:top; }}
    th {{ position:sticky; top:0; background:#13213a; color:#cfe1ff; font-size:12px; white-space:nowrap; }}
    tr:last-child td {{ border-bottom:0; }}
    .strong {{ color:var(--strong); font-weight:800; }}
    .top {{ color:#c8d5ed; min-width:260px; }}
    .pill {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:3px 8px; margin:2px 4px 2px 0; color:#cfe1ff; background:#0b1525; font-size:12px; }}
    .muted {{ color:var(--muted); }}
    .detail-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:10px; }}
    .meta-line {{ color:var(--muted); font-size:12px; }}
    .score-card {{ min-width:116px; border:1px solid rgba(255,255,255,.12); border-radius:10px; padding:8px 10px; background:#101f36; text-align:right; }}
    .score-card span,.metric-grid span {{ display:block; color:var(--muted); font-size:11px; }}
    .score-card b {{ display:block; color:var(--strong); font-size:20px; }}
    .metric-grid {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:8px; margin:10px 0; }}
    .metric-grid div {{ border:1px solid rgba(255,255,255,.1); border-radius:10px; background:#0b1728; padding:8px; }}
    .metric-grid b {{ display:block; font-size:15px; margin-top:3px; }}
    .mix {{ margin:8px 0 10px; }}
    .split {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .world-detail {{ border:1px solid var(--line); border-radius:12px; padding:14px; background:rgba(14,26,44,.58); }}
    @media (max-width: 860px) {{
      .metric-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .split {{ grid-template-columns:1fr; }}
      table {{ min-width:780px; }}
      .detail-head {{ align-items:stretch; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>CC World Strength Ranking</h1>
    <div class="meta">Source: {html.escape(str(db_path))}<br>
    Strong cutoff: {strong_cutoff:.2f} / Elite cutoff: {elite_cutoff:.2f}</div>
  </header>
  <main>
    <section>
      <div class="note">
        チーム力は、過去CCデータから算出した slot別評価点ランキング適合度とフォーメーション実績を合成した簡易スコアです。
        slot適合度は、同じフォーメーション・同じslotの評価点ランキングで、使用数20以下を除外した上位選手を使っているかで判定します。
        各slotは1位=100点で、順位が下がるほど減点され、全slotが1位ならチームのslot適合度は100になります。
        監督評価はフォーメーションとセットになりやすいため、今回のスコア計算から外しています。
        ランキングは平均値ではなく、全チーム中上位20%に入るチームの割合を主指標にしています。
        Gachi Indexは「全体平均の上位20%比率」を100とした指数です。
      </div>
      <div>
        <span class="pill">Unit: season + world + team</span>
        <span class="pill">Primary: top 20% share</span>
        <span class="pill">Score: rank fit 70% / formation 30%</span>
        <span class="pill">Slot ranking: uses &gt; 20</span>
        <span class="pill">Tie-break: elite share / p90</span>
      </div>
    </section>
    <section>
      <h2>World Ranking</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>#</th><th>World</th><th>Seasons</th><th>Teams</th><th>Strong Share</th><th>Elite Share</th><th>Gachi Index</th><th>P90</th><th>Median</th><th>Avg RankFit</th><th>Avg Form</th><th>Strong Formation Mix</th></tr>
          </thead>
          <tbody>{table_world(top_worlds)}</tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>World Season Ranking</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>#</th><th>Season</th><th>World</th><th>Teams</th><th>Strong Share</th><th>Elite Share</th><th>Gachi Index</th><th>P90</th><th>Top Team Samples</th></tr>
          </thead>
          <tbody>{table_season(top_seasons)}</tbody>
        </table>
      </div>
    </section>
    <section>
      <h2>World Details</h2>
    </section>
{details_html}
  </main>
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    world_names = load_world_names(conn)
    team_rows = read_rows(conn, "cc_teams", "season, world_id, match_id, side")
    player_rows = read_rows(conn, "cc_players", "season, world_id, match_id, side, member_order")

    formation_scores = build_formation_scores(team_rows)
    slot_scores, _slot_baseline = build_slot_fit_scores(player_rows)
    team_entries = build_team_entries(team_rows, player_rows, formation_scores, slot_scores, world_names)
    world_rows, season_rows, strong_cutoff, elite_cutoff = summarize_worlds(team_entries)

    write_csv(
        out_dir / "cc_world_strength_ranking.csv",
        world_rows,
        ["rank", "worldId", "worldName", "seasons", "seasonCount", "teams", "strongTeams", "eliteTeams", "strongShare", "eliteShare", "gachiIndex", "avgScore", "medianScore", "p90Score", "avgLineupComponent", "avgFormationComponent", "strongFormations", "topTeams"],
    )
    write_csv(
        out_dir / "cc_world_season_strength_ranking.csv",
        season_rows,
        ["rank", "season", "worldId", "worldName", "teams", "strongTeams", "eliteTeams", "strongShare", "eliteShare", "gachiIndex", "avgScore", "medianScore", "p90Score", "avgLineupComponent", "avgFormationComponent", "strongFormations", "topTeams"],
    )
    write_csv(
        out_dir / "cc_team_strength_scores.csv",
        sorted(team_entries, key=lambda x: (-x["score"], x["season"], x["worldId"], x["teamName"])),
        ["season", "worldId", "worldName", "teamId", "teamName", "score", "rawStrength", "lineupComponent", "formationComponent", "matches", "formation", "coach"],
    )
    write_html(out_dir / "cc_world_strength_ranking.html", world_rows, season_rows, team_entries, strong_cutoff, elite_cutoff, db_path)

    print(f"[DONE] teams={len(team_entries)} worlds={len(world_rows)} strong_cutoff={strong_cutoff:.2f} elite_cutoff={elite_cutoff:.2f}")
    print(f"[OUT] {out_dir / 'cc_world_strength_ranking.html'}")
    for row in world_rows[:10]:
        print(
            f"#{row['rank']:02d} world={row['worldId']:>2} strong={row['strongShare']*100:>4.1f}% "
            f"{row.get('worldName') or ''} elite={row['eliteShare']*100:>4.1f}% index={row['gachiIndex']:>5.0f} p90={row['p90Score']:.1f}"
        )


if __name__ == "__main__":
    main()
