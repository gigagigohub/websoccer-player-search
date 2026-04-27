#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import ssl
import sqlite3
import time
import urllib.request
import zipfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path


API_HOST = "api.app.websoccer.jp"
DEFAULT_TEAMDATA_SESSION = Path.home() / "Desktop" / "teamdata.chlz"
DEFAULT_CC_DB = Path.home() / "work/coding/wsc_data/cc_match_result.sqlite3"
DEFAULT_OUT_DIR = Path.home() / "Desktop" / "nr_implementation_probe"


@dataclass
class Auth:
    gate_key: str
    user_agent: str


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe current NR implementation status from team data API.")
    p.add_argument("--session-file", default=str(DEFAULT_TEAMDATA_SESSION))
    p.add_argument("--data-json", default=str(Path.cwd() / "app/data.json"))
    p.add_argument("--cc-db", default=str(DEFAULT_CC_DB))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--max-teams", type=int, default=2500)
    p.add_argument("--delay-sec", type=float, default=0.04)
    p.add_argument("--timeout-sec", type=float, default=10.0)
    p.add_argument("--progress-every", type=int, default=50)
    p.add_argument("--shallow-season-max", type=int, default=10)
    return p.parse_args()


def extract_auth(session_file: Path) -> Auth:
    best: dict[str, str] | None = None
    with zipfile.ZipFile(session_file) as zf:
        for name in sorted(n for n in zf.namelist() if n.endswith("-meta.json")):
            meta = json.loads(zf.read(name))
            if meta.get("host") != API_HOST:
                continue
            hdrs = {
                str(h.get("name") or "").lower(): str(h.get("value") or "")
                for h in (((meta.get("request") or {}).get("header") or {}).get("headers") or [])
                if h.get("name")
            }
            if hdrs.get("websoccer-gate-key"):
                best = hdrs
    if not best:
        raise RuntimeError(f"Websoccer-gate-key not found in {session_file}")
    return Auth(
        gate_key=best["websoccer-gate-key"],
        user_agent=best.get("user-agent") or "WebSoccer/1.3.28 CFNetwork/1335.0.3.4 Darwin/21.6.0",
    )


def request_json(path: str, auth: Auth, timeout_sec: float) -> dict:
    req = urllib.request.Request(
        f"https://{API_HOST}{path}",
        headers={
            "Accept": "*/*",
            "Websoccer-gate-key": auth.gate_key,
            "User-Agent": auth.user_agent,
            "Accept-Language": "ja",
            "Connection": "keep-alive",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl._create_unverified_context()) as res:
        return json.loads(res.read().decode("utf-8", errors="replace"))


def load_nr_players(data_json: Path) -> dict[int, dict]:
    data = json.loads(data_json.read_text(encoding="utf-8"))
    out: dict[int, dict] = {}
    for p in data.get("players", []):
        if (p.get("category") or "NR") != "NR":
            continue
        pid = int(p.get("id") or 0)
        if pid <= 0:
            continue
        out[pid] = {
            "id": pid,
            "name": p.get("name") or "",
            "position": p.get("position") or "",
            "rate": p.get("rate"),
        }
    return out


def load_seed_teams(cc_db: Path) -> list[tuple[int, int]]:
    con = sqlite3.connect(cc_db)
    try:
        rows = con.execute(
            """
            select distinct cast(team_id as integer), cast(world_id as integer)
            from teams
            where team_id is not null and team_id > 0 and world_id is not null
            order by world_id, team_id
            """
        ).fetchall()
    finally:
        con.close()
    return [(int(team_id), int(world_id)) for team_id, world_id in rows]


def parse_team_players(rows: list[str]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for raw in rows or []:
        parts = str(raw).split(",")
        if len(parts) < 2:
            continue
        try:
            out.append((int(parts[0]), int(parts[1])))
        except ValueError:
            continue
    return out


def write_outputs(out_dir: Path, nr_players: dict[int, dict], stats: dict[int, dict], summary: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "nr_player_observations.json").write_text(
        json.dumps({"players": stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (out_dir / "nr_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["player_id", "name", "position", "rate", "hits", "min_age", "latest_szn", "teams"])
        for pid, p in sorted(nr_players.items()):
            s = stats.get(pid, {})
            if s.get("has_shallow"):
                continue
            teams = sorted(s.get("teams", []))
            w.writerow([
                pid,
                p.get("name", ""),
                p.get("position", ""),
                p.get("rate", ""),
                s.get("hits", 0),
                s.get("min_age", ""),
                s.get("latest_szn", ""),
                " ".join(map(str, teams[:20])),
            ])


def main() -> None:
    args = parse_args()
    auth = extract_auth(Path(args.session_file).expanduser())
    nr_players = load_nr_players(Path(args.data_json).expanduser())
    nr_ids = set(nr_players)
    seed_teams = load_seed_teams(Path(args.cc_db).expanduser())
    out_dir = Path(args.out_dir).expanduser()
    sync_data = request_json("/sync/all.json", auth, args.timeout_sec)
    current_season = int(sync_data.get("season") or 0)

    q: deque[tuple[int, int]] = deque(seed_teams)
    queued = set(seed_teams)
    official_done: set[tuple[int, int]] = set()
    away_done: set[int] = set()
    team_world: dict[int, int] = {team_id: world_id for team_id, world_id in seed_teams}
    stats: dict[int, dict] = defaultdict(lambda: {
        "hits": 0,
        "teams": set(),
        "szns": [],
        "min_age": None,
        "latest_szn": None,
        "has_shallow": False,
    })
    errors: list[dict] = []
    started = time.time()

    while q and len(away_done) < args.max_teams:
        team_id, world_id = q.popleft()
        if (team_id, world_id) in official_done and team_id in away_done:
            continue

        if (team_id, world_id) not in official_done:
            try:
                data = request_json(f"/official_match/index/{team_id}/{world_id}/0.json", auth, args.timeout_sec)
                if data.get("code") == "000":
                    for row in data.get("list") or []:
                        for team in row.get("team") or []:
                            try:
                                tid = int(team.get("id") or 0)
                                wid = int(team.get("world_id") or world_id)
                            except (TypeError, ValueError):
                                continue
                            if tid <= 0 or wid <= 0:
                                continue
                            team_world.setdefault(tid, wid)
                            key = (tid, wid)
                            if key not in queued and key not in official_done:
                                queued.add(key)
                                q.append(key)
                else:
                    errors.append({"endpoint": "official", "team_id": team_id, "world_id": world_id, "code": data.get("code")})
            except Exception as e:  # noqa: BLE001
                errors.append({"endpoint": "official", "team_id": team_id, "world_id": world_id, "error": str(e)[:200]})
            official_done.add((team_id, world_id))
            time.sleep(args.delay_sec)

        if team_id not in away_done:
            try:
                data = request_json(f"/away_team/index/9725201/{team_id}.json", auth, args.timeout_sec)
                if data.get("code") == "000":
                    if data.get("world_id"):
                        try:
                            team_world[team_id] = int(data.get("world_id"))
                        except (TypeError, ValueError):
                            pass
                    for pid, szn in parse_team_players(data.get("players") or []):
                        if pid not in nr_ids:
                            continue
                        age = max(1, current_season - szn + 1) if current_season else None
                        s = stats[pid]
                        s["hits"] += 1
                        s["teams"].add(team_id)
                        s["szns"].append(szn)
                        s["latest_szn"] = max(s["latest_szn"] or szn, szn)
                        if age is not None:
                            s["min_age"] = age if s["min_age"] is None else min(s["min_age"], age)
                            if age <= args.shallow_season_max:
                                s["has_shallow"] = True
                else:
                    errors.append({"endpoint": "away", "team_id": team_id, "code": data.get("code")})
            except Exception as e:  # noqa: BLE001
                errors.append({"endpoint": "away", "team_id": team_id, "error": str(e)[:200]})
            away_done.add(team_id)
            time.sleep(args.delay_sec)

        if len(away_done) % args.progress_every == 0:
            shallow = sum(1 for s in stats.values() if s.get("has_shallow"))
            observed = len(stats)
            print(
                f"[PROGRESS] teams={len(away_done)} queue={len(q)} discovered={len(team_world)} "
                f"nr_observed={observed}/{len(nr_ids)} shallow={shallow} errors={len(errors)}",
                flush=True,
            )
            summary = {
                "teamsFetched": len(away_done),
                "officialFetched": len(official_done),
                "queue": len(q),
                "discoveredTeams": len(team_world),
                "currentSeason": current_season,
                "nrTotal": len(nr_ids),
                "nrObserved": observed,
                "nrShallowImplemented": shallow,
                "errors": errors[-20:],
                "elapsedSec": round(time.time() - started, 1),
            }
            serializable_stats = {
                pid: {**s, "teams": sorted(s["teams"])}
                for pid, s in stats.items()
            }
            write_outputs(out_dir, nr_players, serializable_stats, summary)

    shallow = sum(1 for s in stats.values() if s.get("has_shallow"))
    serializable_stats = {
        pid: {**s, "teams": sorted(s["teams"])}
        for pid, s in stats.items()
    }
    summary = {
        "teamsFetched": len(away_done),
        "officialFetched": len(official_done),
        "queue": len(q),
        "discoveredTeams": len(team_world),
        "currentSeason": current_season,
        "nrTotal": len(nr_ids),
        "nrObserved": len(stats),
        "nrShallowImplemented": shallow,
        "unobservedNr": len(nr_ids) - len(stats),
        "errors": errors[-100:],
        "elapsedSec": round(time.time() - started, 1),
        "outputDir": str(out_dir),
    }
    write_outputs(out_dir, nr_players, serializable_stats, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
