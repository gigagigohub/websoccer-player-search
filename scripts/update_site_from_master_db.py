#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_WSM_DIR = Path.home() / "work" / "coding" / "wsc_data" / "websoccer_master_db"


def is_main_wsm(path: Path) -> bool:
    return bool(re.fullmatch(r"wsm_\d{10,14}\.sqlite3", path.name))


def latest_wsm(wsm_dir: Path) -> Path:
    files = [p for p in wsm_dir.glob("wsm_*.sqlite3") if is_main_wsm(p)]
    if not files:
        raise FileNotFoundError(f"no wsm_*.sqlite3 found in {wsm_dir}")
    return sorted(files, key=lambda p: (p.name, p.stat().st_mtime))[-1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Update site JSONs from master DB with fallback to legacy flow."
    )
    p.add_argument(
        "--master-db",
        default="",
        help="Master WSM DB path. Default: latest wsm_*.sqlite3 in --wsm-dir.",
    )
    p.add_argument(
        "--wsm-dir",
        default=str(DEFAULT_WSM_DIR),
        help="Directory used to find latest WSM when --master-db is omitted.",
    )
    p.add_argument(
        "--out-app-dir",
        default=str(Path.cwd() / "app"),
    )
    p.add_argument(
        "--out-docs-dir",
        default=str(Path.cwd() / "docs"),
    )
    p.add_argument(
        "--fallback-legacy",
        action="store_true",
        help="Run the previous legacy updater instead of master-db flow.",
    )

    # Legacy args (used only with --fallback-legacy)
    p.add_argument("--json-root", default=str(Path.home() / "Desktop" / "CC_match_result_json"))
    p.add_argument("--cc-db", default=str(Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3"))
    p.add_argument("--base-csv-dir", default="/Users/k.nishimura/Desktop/csv data")
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--require-best-team-season",
        type=int,
        default=0,
        help="Fail if generated formations_data.json has no Top Teams for this season.",
    )
    return p.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def validate_best_team_season(formations_json: Path, season: int) -> int:
    data = json.loads(formations_json.read_text(encoding="utf-8"))
    count = 0
    for formation in data.get("formations") or []:
        for team in formation.get("bestTeams") or []:
            if int(team.get("season") or 0) == season:
                count += 1
    if count <= 0:
        raise RuntimeError(f"Top Teams for season {season} were not generated in {formations_json}")
    return count


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parent.parent
    out_app_dir = Path(args.out_app_dir).expanduser().resolve()
    out_docs_dir = Path(args.out_docs_dir).expanduser().resolve()

    if args.fallback_legacy:
        legacy_cmd = [
            "python3",
            str(repo / "scripts" / "update_cc_site_data.py"),
            "--json-root",
            args.json_root,
            "--cc-db",
            args.cc_db,
            "--base-csv-dir",
            args.base_csv_dir,
            "--out-app",
            str(out_app_dir / "formations_data.json"),
            "--out-docs",
            str(out_docs_dir / "formations_data.json"),
        ]
        if args.verbose:
            legacy_cmd.append("--verbose")
        run(legacy_cmd)
        print("[DONE] fallback legacy flow completed.")
        return 0

    master_db = (
        Path(args.master_db).expanduser().resolve()
        if args.master_db
        else latest_wsm(Path(args.wsm_dir).expanduser().resolve())
    )

    run(
        [
            "python3",
            str(repo / "scripts" / "export_site_json_from_master_db.py"),
            "--master-db",
            str(master_db),
            "--fallback-data-json",
            str(out_app_dir / "data.json"),
            "--fallback-coaches-json",
            str(out_app_dir / "coaches_data.json"),
            "--out-app-dir",
            str(out_app_dir),
            "--out-docs-dir",
            str(out_docs_dir),
        ]
    )

    run(
        [
            "python3",
            str(repo / "scripts" / "prepare_formations_page_data.py"),
            "--master-db",
            str(master_db),
            "--out",
            str(out_app_dir / "formations_data.json"),
        ]
    )

    out_docs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_app_dir / "formations_data.json", out_docs_dir / "formations_data.json")
    if args.require_best_team_season:
        count = validate_best_team_season(out_app_dir / "formations_data.json", args.require_best_team_season)
        print(f"[DONE] verified Top Teams season {args.require_best_team_season}: {count} entries")
    print(f"[DONE] synced formations_data.json to {out_docs_dir / 'formations_data.json'}")
    print("[DONE] master-db flow completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
