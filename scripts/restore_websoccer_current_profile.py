#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path


APP_DOMAIN = "jp.novelapproach.WebSoccer"
ACTIVE_DATA = Path.home() / "Library/Containers" / APP_DOMAIN / "Data"
BACKUP_ROOT = Path.home() / "Codex/WebSoccer/websoccer_local_backups/account_transfer"
TEAMS_ROOT = BACKUP_ROOT / "teams"
SAFETY_ROOT = BACKUP_ROOT / "safety_backups"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Restore a WebSoccer team current profile to ACTIVE, saving the current ACTIVE profile first."
    )
    p.add_argument("--team-id", required=True, help="Team id to restore, e.g. 9710901.")
    p.add_argument(
        "--skip-save-active-current",
        action="store_true",
        help="Do not update the active team's teams/<slug>/current before switching.",
    )
    return p.parse_args()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_team(data_dir: Path) -> dict | None:
    db = data_dir / "Documents/Model/Model.sqlite"
    if not db.exists():
        return None
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "select ZTEAM_ID,ZNAME,ZOWNER_NAME,ZSZN,ZLEAGUE from ZMOTEAMDATA limit 1"
        ).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def find_team_dir(team_id: str) -> Path:
    matches = sorted(TEAMS_ROOT.glob(f"{team_id}_*"))
    if len(matches) != 1:
        raise SystemExit(f"[ERROR] expected one team dir for {team_id}, found {len(matches)}")
    current = matches[0] / "current"
    if not (current / "Documents/Model/Model.sqlite").exists():
        raise SystemExit(f"[ERROR] current profile missing Model.sqlite: {current}")
    return matches[0]


def quit_app() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "Webサッカー" to quit'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def kill_cfprefsd() -> None:
    subprocess.run(["killall", "cfprefsd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def replace_dir(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        raise SystemExit(f"[ERROR] destination already exists: {dst}")
    shutil.copytree(src, dst, symlinks=True)


def save_active_current() -> None:
    active = read_team(ACTIVE_DATA)
    if not active:
        print("[SAVE_ACTIVE] skipped: active Model.sqlite not found")
        return
    team_id = str(active["ZTEAM_ID"])
    team_dir = find_team_dir(team_id)
    current = team_dir / "current"
    old = SAFETY_ROOT / f"{team_dir.name}_previous_current_{stamp()}"
    print(f"[SAVE_ACTIVE] {active['ZNAME']} ({team_id}) -> {current}")
    if current.exists() or current.is_symlink():
        shutil.move(str(current), str(old))
        print(f"[SAFETY] previous current -> {old}")
    replace_dir(ACTIVE_DATA, current)


def restore_target(team_id: str) -> None:
    target_dir = find_team_dir(team_id)
    target_current = target_dir / "current"
    target = read_team(target_current)
    active = read_team(ACTIVE_DATA)
    if active and str(active["ZTEAM_ID"]) == team_id:
        print(f"[RESTORE] already active: {active['ZNAME']} ({team_id})")
        return
    save = SAFETY_ROOT / f"active_before_restore_{target_dir.name}_{stamp()}"
    shutil.move(str(ACTIVE_DATA), str(save))
    print(f"[SAFETY] active before restore -> {save}")
    replace_dir(target_current, ACTIVE_DATA)
    if target:
        print(f"[RESTORE] active is now {target['ZNAME']} ({team_id})")


def main() -> int:
    args = parse_args()
    SAFETY_ROOT.mkdir(parents=True, exist_ok=True)
    quit_app()
    if not args.skip_save_active_current:
        save_active_current()
    restore_target(str(args.team_id))
    kill_cfprefsd()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
