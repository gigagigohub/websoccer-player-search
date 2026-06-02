#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILES_ROOT = REPO_ROOT / "local" / "trade_chain" / "profiles"
DEFAULT_OUT_JSON = REPO_ROOT / "local" / "trade_chain" / "profile_registry.json"
DEFAULT_OUT_MD = REPO_ROOT / "local" / "trade_chain" / "profile_registry.md"
DEFAULT_ALIAS_ROOT = REPO_ROOT / "local" / "trade_chain" / "profiles_by_no"
STAMP_RE = re.compile(r"_(\d{8})_(\d{6})(?:_(\d{1,6}))?$")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build management numbering for trade-chain profiles.")
    p.add_argument("--profiles-root", default=str(DEFAULT_PROFILES_ROOT))
    p.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    p.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    p.add_argument("--alias-root", default=str(DEFAULT_ALIAS_ROOT))
    p.add_argument("--no-aliases", action="store_true", help="Do not create/update profiles_by_no symlinks.")
    return p.parse_args()


def db_path(profile_dir: Path) -> Path:
    return profile_dir / "Data" / "Documents" / "Model" / "Model.sqlite"


def parse_folder_stamp(profile_dir: Path) -> tuple[str, str]:
    match = STAMP_RE.search(profile_dir.name)
    if not match:
        return "", ""
    date_part, time_part, micro_part = match.groups()
    micro = (micro_part or "0").ljust(6, "0")[:6]
    key = f"{date_part}{time_part}{micro}"
    display = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}.{micro}"
    return key, display


def read_team(profile_dir: Path) -> dict[str, object]:
    db = db_path(profile_dir)
    if not db.exists():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "select ZTEAM_ID,ZNAME,ZOWNER_NAME,ZSZN,ZWORLD_ID,ZLEAGUE from ZMOTEAMDATA limit 1"
        ).fetchone()
        return dict(row) if row else {}
    finally:
        con.close()


def wanted_from_folder(profile_dir: Path) -> tuple[str, int | None]:
    stem = profile_dir.name
    match = STAMP_RE.search(stem)
    if match:
        stem = stem[: match.start()]
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0], int(parts[1])
    return stem, None


def build_entries(profiles_root: Path, alias_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for profile_dir in sorted(profiles_root.glob("*")):
        if not profile_dir.is_dir() or not db_path(profile_dir).exists():
            continue
        key, created_at = parse_folder_stamp(profile_dir)
        team = read_team(profile_dir)
        wanted_name, wanted_player_id = wanted_from_folder(profile_dir)
        entries.append(
            {
                "sortKey": key or profile_dir.name,
                "createdAtFromFolder": created_at,
                "createdAtSource": "folder_name_timestamp" if key else "folder_name_sort_fallback",
                "folderName": profile_dir.name,
                "profileData": str((profile_dir / "Data").resolve()),
                "wantedPlayerName": wanted_name,
                "wantedPlayerId": wanted_player_id,
                "teamId": team.get("ZTEAM_ID"),
                "teamName": team.get("ZNAME"),
                "ownerName": team.get("ZOWNER_NAME"),
                "season": team.get("ZSZN"),
                "worldId": team.get("ZWORLD_ID"),
                "leagueField": team.get("ZLEAGUE"),
            }
        )
    entries.sort(key=lambda item: (str(item["sortKey"]), int(item.get("teamId") or 0), str(item["folderName"])))
    for idx, item in enumerate(entries, start=1):
        number = f"{idx:03d}"
        item["managementNo"] = number
        item["aliasPath"] = str(alias_root / number)
        item.pop("sortKey", None)
    return entries


def write_json(path: Path, entries: list[dict[str, object]], profiles_root: Path, alias_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
        "profilesRoot": str(profiles_root.resolve()),
        "aliasRoot": str(alias_root.resolve()),
        "count": len(entries),
        "numbering": "001-based creation order from profile folder timestamps; ties sorted by teamId and folderName",
        "entries": entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Trade Chain Profile Registry",
        "",
        "Management numbers are separate from in-game team names.",
        "Order is based on the creation timestamp embedded in each profile folder name.",
        "",
        "| No | createdAt | teamId | teamName | wanted | folder |",
        "|---:|---|---:|---|---|---|",
    ]
    for item in entries:
        wanted = item.get("wantedPlayerName") or ""
        wanted_id = item.get("wantedPlayerId")
        if wanted_id:
            wanted = f"{wanted} ({wanted_id})"
        lines.append(
            "| {managementNo} | {createdAtFromFolder} | {teamId} | {teamName} | {wanted} | `{folderName}` |".format(
                managementNo=item.get("managementNo") or "",
                createdAtFromFolder=item.get("createdAtFromFolder") or "",
                teamId=item.get("teamId") or "",
                teamName=item.get("teamName") or "",
                wanted=wanted,
                folderName=item.get("folderName") or "",
            )
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def update_aliases(alias_root: Path, entries: list[dict[str, object]]) -> None:
    alias_root.mkdir(parents=True, exist_ok=True)
    for existing in alias_root.iterdir():
        if existing.name.isdigit() and existing.is_symlink():
            existing.unlink()
    for item in entries:
        number = str(item["managementNo"])
        link = alias_root / number
        if link.exists() or link.is_symlink():
            raise RuntimeError(f"alias path already exists and is not a managed symlink: {link}")
        target = Path(str(item["profileData"])).resolve().parent
        relative_target = os.path.relpath(target, start=alias_root)
        link.symlink_to(relative_target)
        item["aliasPath"] = str(link)


def main() -> int:
    args = parse_args()
    profiles_root = Path(args.profiles_root).expanduser().resolve()
    out_json = Path(args.out_json).expanduser().resolve()
    out_md = Path(args.out_md).expanduser().resolve()
    alias_root = Path(args.alias_root).expanduser().resolve()
    entries = build_entries(profiles_root, alias_root)
    if not args.no_aliases:
        update_aliases(alias_root, entries)
    write_json(out_json, entries, profiles_root, alias_root)
    write_markdown(out_md, entries)
    print(f"[DONE] numbered profiles: {len(entries)}")
    print(f"[DONE] wrote {out_json}")
    print(f"[DONE] wrote {out_md}")
    if not args.no_aliases:
        print(f"[DONE] updated aliases under {alias_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
