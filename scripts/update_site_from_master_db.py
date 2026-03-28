#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Update site JSONs from master DB with fallback to legacy flow."
    )
    p.add_argument(
        "--master-db",
        default=str(Path.home() / "Desktop" / "websoccer_master_db" / "websoccer_master.sqlite3"),
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
    return p.parse_args()


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


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

    run(
        [
            "python3",
            str(repo / "scripts" / "export_site_json_from_master_db.py"),
            "--master-db",
            args.master_db,
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
            args.master_db,
            "--out",
            str(out_app_dir / "formations_data.json"),
        ]
    )

    out_docs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_app_dir / "formations_data.json", out_docs_dir / "formations_data.json")
    print(f"[DONE] synced formations_data.json to {out_docs_dir / 'formations_data.json'}")
    print("[DONE] master-db flow completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
