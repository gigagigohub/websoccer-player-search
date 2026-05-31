#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = [
    Path.home() / "Codex" / "WebSoccer" / "websoccer_local_backups" / "account_transfer",
    REPO_ROOT / "local" / "trade_chain" / "profiles",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a cross-team index from local WebSoccer profile snapshots.")
    p.add_argument("--root", action="append", default=[], help="Profile storage root. Can be repeated.")
    p.add_argument(
        "--out-dir",
        default=str(Path.home() / "Codex" / "WebSoccer" / "websoccer_local_backups" / "account_transfer" / "_index"),
    )
    return p.parse_args()


def iter_summary_paths(roots: list[Path]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if root.exists():
            candidates = [
                *root.glob("teams/*/current/profile_snapshot/summary.json"),
                *root.glob("*/profile_snapshot/summary.json"),
                *root.glob("*/Data/profile_snapshot/summary.json"),
            ]
            for path in candidates:
                rel_parts = path.relative_to(root).parts
                if rel_parts and (
                    rel_parts[0] == "safety_backups"
                    or rel_parts[0].startswith("active_before_restore_")
                ):
                    continue
                try:
                    key = path.resolve()
                except Exception:
                    key = path
                if key in seen:
                    continue
                seen.add(key)
                paths.append(path)
    return sorted(paths)


def main() -> int:
    args = parse_args()
    roots = [Path(p).expanduser().resolve() for p in args.root] if args.root else DEFAULT_ROOTS
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    skipped: list[dict] = []
    for summary_path in iter_summary_paths(roots):
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            skipped.append({"path": str(summary_path), "error": str(exc)})
            continue
        team = data.get("team") or {}
        profile_data = data.get("profileData") or str(summary_path.parents[1])
        for player in data.get("players") or []:
            rows.append(
                {
                    "name": player.get("name"),
                    "fullName": player.get("fullName"),
                    "playerId": player.get("playerId"),
                    "personId": player.get("personId"),
                    "termNo": player.get("termNo"),
                    "paramSeasonNo": player.get("paramSeasonNo"),
                    "rarity": player.get("rarity"),
                    "acquiredSeason": player.get("acquiredSeason"),
                    "power": player.get("power"),
                    "technique": player.get("technique"),
                    "speed": player.get("speed"),
                    "rosterNo": player.get("rosterNo"),
                    "teamName": team.get("teamName"),
                    "teamId": team.get("teamId"),
                    "ownerName": team.get("ownerName"),
                    "teamSeason": team.get("season"),
                    "worldName": team.get("worldName"),
                    "leagueGroupName": team.get("leagueGroupName"),
                    "profileData": profile_data,
                    "summaryPath": str(summary_path),
                }
            )

    rows.sort(key=lambda r: (str(r.get("name") or ""), str(r.get("teamName") or ""), int(r.get("termNo") or 0)))
    by_name: dict[str, list[dict]] = {}
    for row in rows:
        for key in {str(row.get("name") or ""), str(row.get("fullName") or "")}:
            if key:
                by_name.setdefault(key, []).append(row)

    (out_dir / "players_index.json").write_text(
        json.dumps({"roots": [str(r) for r in roots], "rows": rows, "byName": by_name, "skipped": skipped}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "players_index.csv").open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "name",
            "fullName",
            "playerId",
            "personId",
            "termNo",
            "paramSeasonNo",
            "rarity",
            "acquiredSeason",
            "power",
            "technique",
            "speed",
            "rosterNo",
            "teamName",
            "teamId",
            "ownerName",
            "teamSeason",
            "worldName",
            "leagueGroupName",
            "profileData",
            "summaryPath",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[DONE] indexed players: {len(rows)}")
    if skipped:
        print(f"[WARN] skipped summaries: {len(skipped)}")
    print(f"[DONE] wrote {out_dir / 'players_index.json'}")
    print(f"[DONE] wrote {out_dir / 'players_index.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
