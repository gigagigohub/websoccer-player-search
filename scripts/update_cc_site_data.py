#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Incremental CC ingest (SQLite) + app/formations_data.json generation."
    )
    ap.add_argument(
        "--json-root",
        default=str(Path.home() / "Desktop" / "CC_match_result_json"),
        help="Raw JSON root",
    )
    ap.add_argument(
        "--cc-db",
        default=str(Path.home() / "Desktop" / "CC_match_result_db" / "cc_match_result.sqlite3"),
        help="SQLite path",
    )
    ap.add_argument(
        "--base-csv-dir",
        default="/Users/k.nishimura/Desktop/csv data",
        help="Base csv data dir for formation/coach master tables",
    )
    ap.add_argument(
        "--out-app",
        default="/Users/k.nishimura/work/coding/websoccer-player-search/app/formations_data.json",
        help="Output app formations_data.json",
    )
    ap.add_argument("--verbose", action="store_true", help="Verbose ingest progress")
    return ap.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parent.parent

    ingest_cmd = [
        "python3",
        str(repo / "scripts" / "ingest_cc_match_result_db.py"),
        "--json-root",
        args.json_root,
        "--db-path",
        args.cc_db,
    ]
    if args.verbose:
        ingest_cmd.append("--verbose")
    run(ingest_cmd)

    run(
        [
            "python3",
            str(repo / "scripts" / "prepare_formations_page_data.py"),
            "--base-csv-dir",
            args.base_csv_dir,
            "--cc-db",
            args.cc_db,
            "--out",
            args.out_app,
        ]
    )

    print(f"[DONE] wrote app formations data: {Path(args.out_app).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
