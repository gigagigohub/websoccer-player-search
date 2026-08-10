#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_WSM_DIR = Path("/Users/gigagigo/Codex/websoccer/wsc_data/websoccer_master_db")
WSC_DATA = Path("/Users/gigagigo/Codex/websoccer/wsc_data")


def is_main_wsm(path: Path) -> bool:
    return bool(re.fullmatch(r"wsm_\d{10,14}\.sqlite3", path.name))


def latest_wsm(wsm_dir: Path) -> Path:
    files = [p for p in wsm_dir.glob("wsm_*.sqlite3") if is_main_wsm(p)]
    if not files:
        raise FileNotFoundError(f"no wsm_*.sqlite3 found in {wsm_dir}")
    return sorted(files, key=lambda p: (p.name, p.stat().st_mtime))[-1]


def latest_updatefile_dir() -> Path:
    def key(path: Path) -> tuple[int, str]:
        nums = [int(x) for x in re.findall(r"\d+", path.name)]
        return (nums[-1] if nums else -1, path.name)

    dirs = sorted(WSC_DATA.glob("UpdateFile_p*"), key=key)
    if not dirs:
        raise FileNotFoundError(f"no UpdateFile_p* directory found in {WSC_DATA}")
    return dirs[-1]


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
        "--fallback-legacy",
        action="store_true",
        help="Run the previous legacy updater instead of master-db flow.",
    )
    p.add_argument(
        "--skip-scout-history",
        action="store_true",
        help="Do not re-attach per-player scoutHistory after exporting master DB data.",
    )
    p.add_argument(
        "--skip-challenge-history",
        action="store_true",
        help="Do not re-attach Challenge Match events and per-player cmHistory after exporting master DB data.",
    )
    p.add_argument(
        "--skip-tpi-update",
        action="store_true",
        help="Do not regenerate v4_clean_uniform_data.json and cc_range_data.json from the master DB.",
    )
    p.add_argument(
        "--update-zip-dir",
        default="",
        help="UpdateFile_p* directory used to rebuild scoutHistory and cmHistory. Default: latest under wsc_data.",
    )
    p.add_argument(
        "--filled-csv",
        default=str(WSC_DATA / "UpdateFile_inventory" / "updatefile_ss_events_filled.csv"),
        help="Manual scout-event title CSV used by link_scout_history.py.",
    )
    p.add_argument(
        "--blank-missing-title",
        action="store_true",
        help="Keep scout event names blank when they are absent from metadata.",
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


def load_preserved_scout_metadata(data_json: Path) -> dict[int, dict[str, object]]:
    if not data_json.exists():
        return {}
    try:
        payload = json.loads(data_json.read_text(encoding="utf-8"))
    except Exception:
        return {}
    preserved: dict[int, dict[str, object]] = {}
    for row in payload.get("scouts") or []:
        event_id = int(row.get("eventId") or 0)
        if event_id <= 0:
            continue
        metadata = {
            key: row.get(key)
            for key in ("name", "nameRaw", "nameSource", "shopButtonImage")
            if row.get(key) not in (None, "")
        }
        if metadata:
            preserved[event_id] = metadata
    return preserved


def restore_scout_metadata(data_json: Path, preserved: dict[int, dict[str, object]]) -> int:
    if not preserved or not data_json.exists():
        return 0
    payload = json.loads(data_json.read_text(encoding="utf-8"))
    restored = 0
    for row in payload.get("scouts") or []:
        metadata = preserved.get(int(row.get("eventId") or 0))
        if not metadata:
            continue
        changed = False
        for key, value in metadata.items():
            if row.get(key) != value:
                row[key] = value
                changed = True
        restored += int(changed)
    if restored:
        data_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return restored


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parent.parent
    out_app_dir = Path(args.out_app_dir).expanduser().resolve()
    preserved_scout_metadata = load_preserved_scout_metadata(out_app_dir / "data.json")

    if args.fallback_legacy:
        legacy_cmd = [
            sys.executable,
            str(repo / "scripts" / "update_cc_site_data.py"),
            "--json-root",
            args.json_root,
            "--cc-db",
            args.cc_db,
            "--base-csv-dir",
            args.base_csv_dir,
            "--out-app",
            str(out_app_dir / "formations_data.json"),
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
            sys.executable,
            str(repo / "scripts" / "export_site_json_from_master_db.py"),
            "--master-db",
            str(master_db),
            "--fallback-data-json",
            str(out_app_dir / "data.json"),
            "--fallback-coaches-json",
            str(out_app_dir / "coaches_data.json"),
            "--out-app-dir",
            str(out_app_dir),
        ]
    )

    run(
        [
            sys.executable,
            str(repo / "scripts" / "prepare_formations_page_data.py"),
            "--master-db",
            str(master_db),
            "--out",
            str(out_app_dir / "formations_data.json"),
        ]
    )
    if not args.skip_tpi_update:
        prepared_dir = out_app_dir / "prepared"
        prepared_dir.mkdir(parents=True, exist_ok=True)
        run(
            [
                sys.executable,
                str(repo / "scripts" / "build_v4_slot_adjusted_team_power.py"),
                "--db",
                str(master_db),
                "--formations-json",
                str(out_app_dir / "formations_data.json"),
                "--output-json",
                str(out_app_dir / "v4_clean_uniform_data.json"),
                "--report-html",
                str(prepared_dir / "team_power_index_reestimate.html"),
                "--report-csv",
                str(prepared_dir / "team_power_index_reestimate_metrics.csv"),
            ]
        )
        run(
            [
                sys.executable,
                str(repo / "scripts" / "build_cc_range_data.py"),
                "--source",
                str(out_app_dir / "v4_clean_uniform_data.json"),
                "--dest",
                str(out_app_dir / "cc_range_data.json"),
            ]
        )
    update_zip_dir = None
    restored_scout_events = restore_scout_metadata(
        out_app_dir / "data.json", preserved_scout_metadata
    )
    if restored_scout_events:
        print(f"[DONE] restored scout metadata: {restored_scout_events} events")
    if not args.skip_scout_history or not args.skip_challenge_history:
        update_zip_dir = (
            Path(args.update_zip_dir).expanduser().resolve()
            if args.update_zip_dir
            else latest_updatefile_dir()
        )
    if not args.skip_scout_history:
        assert update_zip_dir is not None
        link_cmd = [
            sys.executable,
            str(repo / "scripts" / "link_scout_history.py"),
            "--zip-dir",
            str(update_zip_dir),
            "--filled-csv",
            str(Path(args.filled_csv).expanduser().resolve()),
            "--app-data",
            str(out_app_dir / "data.json"),
        ]
        if args.blank_missing_title:
            link_cmd.append("--blank-missing-title")
        run(link_cmd)
    if not args.skip_challenge_history:
        assert update_zip_dir is not None
        run(
            [
                sys.executable,
                str(repo / "scripts" / "link_challenge_history.py"),
                "--zip-dir",
                str(update_zip_dir),
                "--app-data",
                str(out_app_dir / "data.json"),
            ]
        )
    run(
        [
            sys.executable,
            str(repo / "scripts" / "write_site_meta.py"),
            "--app-dir",
            str(out_app_dir),
        ]
    )

    if args.require_best_team_season:
        count = validate_best_team_season(out_app_dir / "formations_data.json", args.require_best_team_season)
        print(f"[DONE] verified Top Teams season {args.require_best_team_season}: {count} entries")
    print("[DONE] master-db flow completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
