#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


API_HOST = "api.app.websoccer.jp"


@dataclass
class MatchBundle:
    file_path: Path
    mtime: float
    payload_m: dict


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build CC_match_result_csv normalized files from summary JSON")
    ap.add_argument(
        "--json-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_json"),
        help="Root directory containing match summary JSON (default: ~/Desktop/CC_match_result_json)",
    )
    ap.add_argument(
        "--csv-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_csv"),
        help="Output CSV root (default: ~/Desktop/CC_match_result_csv)",
    )
    return ap.parse_args()


def load_latest_match_payloads(json_root: Path) -> Dict[Tuple[int, int, int], MatchBundle]:
    base = json_root / API_HOST / "match" / "summary" / "cc"
    files: List[Path] = []
    if base.exists():
        for dirpath, _, filenames in os.walk(base):
            for name in filenames:
                if name.endswith(".json"):
                    files.append(Path(dirpath) / name)
    latest: Dict[Tuple[int, int, int], MatchBundle] = {}
    for fp in files:
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict) or obj.get("code") != "000":
            continue
        m = obj.get("m")
        if not isinstance(m, dict):
            continue
        try:
            mid = int(m.get("match_id"))
            wid = int(m.get("world_id"))
            szn = int(m.get("szn") or 0)
        except Exception:
            continue
        key = (szn, mid, wid)
        mt = fp.stat().st_mtime
        prev = latest.get(key)
        if (prev is None) or (mt >= prev.mtime):
            latest[key] = MatchBundle(file_path=fp, mtime=mt, payload_m=m)
    return latest


def write_csv(path: Path, header: List[str], rows: List[List[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    args = parse_args()
    json_root = Path(args.json_root).expanduser().resolve()
    csv_root = Path(args.csv_root).expanduser().resolve()
    norm_dir = csv_root / "normalized"
    reports_dir = csv_root / "reports"

    bundles = load_latest_match_payloads(json_root)
    if not bundles:
        print("[ERROR] no valid summary JSON found.")
        return 2

    match_rows: List[List[object]] = []
    team_rows: List[List[object]] = []
    player_rows: List[List[object]] = []
    goal_rows: List[List[object]] = []
    coverage: defaultdict[Tuple[int, int], int] = defaultdict(int)

    for (_szn, mid, wid), bundle in sorted(bundles.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][1])):
        m = bundle.payload_m
        szn = int(m.get("szn") or 0)
        dt = str(m.get("datetime") or "")
        title = str(m.get("title") or "")
        referee = str(m.get("referee") or "")
        stadium = str((m.get("stadium") or {}).get("name") or "")
        audience = int(m.get("audience") or 0)
        teams = m.get("team") if isinstance(m.get("team"), list) else []
        if len(teams) < 2:
            continue

        # build quick member->side map
        team_member_ids: Dict[str, str] = {}
        for idx, t in enumerate(teams[:2]):
            side = "home" if idx == 0 else "away"
            members = t.get("members") if isinstance(t.get("members"), list) else []
            for mem in members:
                try:
                    pid = str(int(mem.get("id")))
                    team_member_ids[pid] = side
                except Exception:
                    continue

        home_score = 0
        away_score = 0
        goals = m.get("goal") if isinstance(m.get("goal"), list) else []
        for ge in goals:
            if not isinstance(ge, dict):
                continue
            for minute_raw, scorer_raw in ge.items():
                try:
                    scorer_id = int(scorer_raw)
                except Exception:
                    continue
                side = team_member_ids.get(str(scorer_id), "unknown")
                if side == "home":
                    home_score += 1
                elif side == "away":
                    away_score += 1
                try:
                    minute = int(minute_raw)
                except Exception:
                    minute = 0
                goal_rows.append([mid, wid, szn, side, minute, scorer_id])

        match_rows.append(
            [mid, wid, szn, dt, title, referee, stadium, audience, home_score, away_score]
        )

        for idx, t in enumerate(teams[:2]):
            side = "home" if idx == 0 else "away"
            team_id = int(t.get("id") or 0)
            team_name = str(t.get("name") or "")
            formation_id = int(t.get("formation") or 0)
            formation_name = str(t.get("formation_name") or "")
            hc = t.get("headcoach") if isinstance(t.get("headcoach"), dict) else {}
            hc_id = int(hc.get("id") or 0)
            hc_name = str(hc.get("name") or "")
            try:
                hc_pts = float(hc.get("pts") or 0)
            except Exception:
                hc_pts = 0.0

            gf = home_score if side == "home" else away_score
            ga = away_score if side == "home" else home_score
            if gf > ga:
                result = "W"
            elif gf < ga:
                result = "L"
            else:
                result = "D"

            team_rows.append(
                [
                    mid,
                    wid,
                    szn,
                    dt,
                    side,
                    team_id,
                    team_name,
                    formation_id,
                    formation_name,
                    hc_id,
                    hc_name,
                    hc_pts,
                    gf,
                    ga,
                    result,
                ]
            )

            members = t.get("members") if isinstance(t.get("members"), list) else []
            for member_order, mem in enumerate(members, start=1):
                try:
                    pid = int(mem.get("id") or 0)
                except Exception:
                    pid = 0
                fullname = str(mem.get("fullname") or "")
                pname = str(mem.get("name") or "")
                try:
                    pos = int(mem.get("pos") or 0)
                except Exception:
                    pos = 0
                try:
                    pts = float(mem.get("pts") or 0)
                except Exception:
                    pts = 0.0
                player_rows.append(
                    [
                        mid,
                        wid,
                        szn,
                        dt,
                        side,
                        team_id,
                        team_name,
                        formation_id,
                        formation_name,
                        member_order,
                        1 if member_order <= 11 else 0,
                        pid,
                        fullname,
                        pname,
                        pos,
                        pts,
                    ]
                )

        coverage[(szn, wid)] += 1

    # Sort outputs
    match_rows.sort(key=lambda r: (int(r[2]), int(r[1]), int(r[0])))
    team_rows.sort(key=lambda r: (int(r[2]), int(r[1]), int(r[0]), 0 if r[4] == "home" else 1))
    player_rows.sort(key=lambda r: (int(r[2]), int(r[1]), int(r[0]), 0 if r[4] == "home" else 1, int(r[9])))
    goal_rows.sort(key=lambda r: (int(r[2]), int(r[1]), int(r[0]), int(r[4]), 0 if r[3] == "home" else 1))

    write_csv(
        norm_dir / "match_level.csv",
        ["match_id", "world_id", "season", "datetime", "title", "referee", "stadium", "audience", "home_score", "away_score"],
        match_rows,
    )
    write_csv(
        norm_dir / "team_level.csv",
        ["match_id", "world_id", "season", "datetime", "side", "team_id", "team_name", "formation_id", "formation_name", "headcoach_id", "headcoach_name", "headcoach_pts", "goals_for", "goals_against", "result"],
        team_rows,
    )
    write_csv(
        norm_dir / "player_level.csv",
        ["match_id", "world_id", "season", "datetime", "side", "team_id", "team_name", "formation_id", "formation_name", "member_order", "is_starting11", "player_id", "player_fullname", "player_name", "pos_code_1_4", "pts"],
        player_rows,
    )
    write_csv(
        norm_dir / "goal_events.csv",
        ["match_id", "world_id", "season", "side", "minute", "scorer_player_id"],
        goal_rows,
    )

    coverage_rows = [[szn, wid, cnt] for (szn, wid), cnt in sorted(coverage.items(), key=lambda kv: (kv[0][0], kv[0][1]))]
    write_csv(reports_dir / "coverage_season_world.csv", ["season", "world_id", "match_count"], coverage_rows)

    print(f"[DONE] matches={len(match_rows)} teams={len(team_rows)} players={len(player_rows)} goals={len(goal_rows)}")
    print(f"[DONE] coverage rows={len(coverage_rows)} -> {reports_dir / 'coverage_season_world.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
