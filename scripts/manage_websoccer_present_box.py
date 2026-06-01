#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from websoccer_trade_api import db_path, profile_metadata, request_json  # noqa: E402


ACTIVE_PROFILE = Path.home() / "Library" / "Containers" / "jp.novelapproach.WebSoccer" / "Data"
PRESENT_BOX_INDEX = "/present_box/index/{team_id}/{world_id}.json"
PRESENT_BOX_ACCEPT = "/present_box/accept/{team_id}/{world_id}.json"
LOGIN_BONUS_SERVICE_MENU_ID = 6001
CM_REWARD_SERVICE_MENU_ID = 3110


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="List or accept WebSoccer present-box items using local profile auth."
    )
    p.add_argument(
        "--profile-data",
        default=str(ACTIVE_PROFILE),
        help=f"Profile Data directory used for auth and team_id lookup. Default: active app profile {ACTIVE_PROFILE}",
    )
    p.add_argument(
        "--kind",
        choices=("login-bonus", "cm", "all"),
        default="login-bonus",
        help="Which unaccepted presents to target. Default: login-bonus only.",
    )
    p.add_argument(
        "--include-accepted",
        action="store_true",
        help="Show already accepted present-box items in the output.",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Accept matching unaccepted presents. Without this, the command is read-only.",
    )
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument("--world-id", type=int, help="Override world id. Defaults to ZWORLD_ID from Model.sqlite, then 1.")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return p.parse_args()


def present_info(item: dict[str, Any]) -> dict[str, Any]:
    present = item.get("present") if isinstance(item.get("present"), dict) else {}
    return {
        "presentId": item.get("id"),
        "created": item.get("created"),
        "expireTermId": item.get("expire_term_id"),
        "status": item.get("status"),
        "serviceMenuId": present.get("service_menu_id"),
        "title": present.get("title"),
        "description": present.get("description"),
        "items": present.get("items") if isinstance(present.get("items"), list) else [],
    }


def matches_kind(info: dict[str, Any], kind: str) -> bool:
    if kind == "all":
        return True
    if kind == "login-bonus":
        return info.get("serviceMenuId") == LOGIN_BONUS_SERVICE_MENU_ID
    if kind == "cm":
        return info.get("serviceMenuId") == CM_REWARD_SERVICE_MENU_ID
    return False


def compact_items(items: list[Any]) -> str:
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parts.append(f"type={item.get('type')} detail={item.get('detail')} id={item.get('id')}")
    return ", ".join(parts)


def profile_world_id(profile: Path) -> int:
    import sqlite3

    db = db_path(profile)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("select ZWORLD_ID from ZMOTEAMDATA limit 1").fetchone()
        if row and row["ZWORLD_ID"] is not None:
            return int(row["ZWORLD_ID"])
    finally:
        con.close()
    return 1


def main() -> int:
    args = parse_args()
    profile = Path(args.profile_data).expanduser().resolve()
    meta = profile_metadata(profile)
    world_id = int(args.world_id or profile_world_id(profile))

    ok, payload = request_json(
        "GET",
        PRESENT_BOX_INDEX.format(team_id=meta["teamId"], world_id=world_id),
        profile,
        timeout_sec=args.timeout_sec,
    )
    if not ok or not isinstance(payload, dict):
        print(f"[ERROR] present_box/index failed: {payload}", file=sys.stderr)
        return 1
    if str(payload.get("code") or "") != "000":
        print(f"[ERROR] present_box/index returned code={payload.get('code')}: {payload}", file=sys.stderr)
        return 1

    all_items = [present_info(item) for item in payload.get("list") or [] if isinstance(item, dict)]
    visible = [
        item
        for item in all_items
        if matches_kind(item, args.kind) and (args.include_accepted or int(item.get("status") or 0) == 1)
    ]
    targets = [item for item in visible if int(item.get("status") or 0) == 1]

    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if args.execute:
        for item in targets:
            present_id = int(item["presentId"])
            ok, res = request_json(
                "POST",
                PRESENT_BOX_ACCEPT.format(team_id=meta["teamId"], world_id=world_id),
                profile,
                payload={"present_id": present_id},
                timeout_sec=args.timeout_sec,
            )
            row = {"presentId": present_id, "ok": ok, "response": res}
            if ok and isinstance(res, dict) and str(res.get("code") or "") == "000":
                accepted.append(row)
            else:
                errors.append(row)

    result = {
        "execute": bool(args.execute),
        "kind": args.kind,
        "profile": str(profile),
        "team": {
            "teamId": meta["teamId"],
            "teamName": meta["teamName"],
            "ownerName": meta["ownerName"],
            "season": meta["season"],
            "worldId": world_id,
        },
        "totalPresentBoxItems": len(all_items),
        "visibleCount": len(visible),
        "targetCount": len(targets),
        "items": visible,
        "accepted": accepted,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"team: {meta['teamId']} {meta['teamName']} / {meta['ownerName']} season={meta['season']} world={world_id}")
        print(f"kind={args.kind} execute={args.execute} targets={len(targets)} visible={len(visible)} total={len(all_items)}")
        for item in visible:
            status = "unaccepted" if int(item.get("status") or 0) == 1 else "accepted"
            print(
                f"- {item['presentId']} [{status}] service={item.get('serviceMenuId')} "
                f"{item.get('title') or ''}: {item.get('description') or ''} ({compact_items(item.get('items') or [])})"
            )
        if args.execute:
            print(f"accepted={len(accepted)} errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
