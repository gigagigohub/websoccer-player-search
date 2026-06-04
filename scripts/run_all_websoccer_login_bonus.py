#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from manage_websoccer_present_box import (  # noqa: E402
    LOGIN_BONUS_SERVICE_MENU_ID,
    LOGIN_PATH,
    PRESENT_BOX_ACCEPT,
    PRESENT_BOX_INDEX,
    present_info,
    profile_world_id,
)
from sync_all_websoccer_profiles import collect_numbered_trade_profiles, collect_profiles  # noqa: E402
from websoccer_trade_api import profile_metadata, request_json  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_pushover.py"
SHOP_PLAYER_INQUIRY = "/shop_player/inquiry/{team_id}/{world_id}.json"
DEFAULT_TICKET_INVENTORY_DIR = REPO_ROOT / "local" / "shop_player_ticket_inventory"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Trigger daily login and accept every unaccepted present-box item for stored WebSoccer profiles."
    )
    p.add_argument(
        "--profile-data",
        action="append",
        help="Run only this profile Data directory. May be passed multiple times. Defaults to all collected profiles.",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="Call /login/login and accept all unaccepted present-box items. Without this, the command is read-only.",
    )
    p.add_argument("--timeout-sec", type=float, default=30.0)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--retry-delay-sec", type=int, default=5)
    p.add_argument("--login-app-version", type=int, default=325)
    p.add_argument("--login-arg", type=int, default=0)
    p.add_argument(
        "--skip-shop-player-inquiry",
        action="store_true",
        help="Skip read-only /shop_player/inquiry ticket inventory collection.",
    )
    p.add_argument(
        "--ticket-inventory-dir",
        default=str(DEFAULT_TICKET_INVENTORY_DIR),
        help=f"Directory for saved ticket inventory JSON. Default: {DEFAULT_TICKET_INVENTORY_DIR}",
    )
    p.add_argument(
        "--numbered-trade-profiles-only",
        action="store_true",
        help="Run only trade-chain profiles referenced by local/trade_chain/profiles_by_no.",
    )
    p.add_argument("--notify-pushover", action="store_true")
    return p.parse_args()


def selected_profiles(args: argparse.Namespace) -> list[Path]:
    if args.profile_data:
        return [Path(item).expanduser().resolve() for item in args.profile_data]
    if args.numbered_trade_profiles_only:
        return collect_numbered_trade_profiles()
    return collect_profiles()


def get_json_with_retries(
    path: str,
    profile: Path,
    *,
    timeout_sec: float,
    retries: int,
    retry_delay_sec: int,
) -> tuple[bool, dict[str, Any] | str, int]:
    attempts = 1 + max(0, int(retries))
    last_ok = False
    last_payload: dict[str, Any] | str = ""
    for attempt in range(1, attempts + 1):
        last_ok, last_payload = request_json("GET", path, profile, timeout_sec=timeout_sec)
        if last_ok or attempt == attempts:
            return last_ok, last_payload, attempt
        time.sleep(max(1, int(retry_delay_sec)))
    return last_ok, last_payload, attempts


def unaccepted_targets(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if int(item.get("status") or 0) == 1]


def service_menu_breakdown(items: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        key = str(item.get("serviceMenuId") or "unknown")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def normalize_ticket_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for key, count in value.items():
        try:
            normalized_count = int(count or 0)
        except (TypeError, ValueError):
            continue
        out[str(key)] = normalized_count
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def compact_shop_player_inquiry(payload: dict[str, Any]) -> dict[str, Any]:
    listup = payload.get("listup") if isinstance(payload.get("listup"), dict) else None
    return {
        "code": payload.get("code"),
        "ticket": normalize_ticket_counts(payload.get("ticket")),
        "used": payload.get("used") if isinstance(payload.get("used"), dict) else {},
        "hasListup": bool(listup),
        "listupId": listup.get("id") if listup else None,
    }


def ticket_total(ticket_counts: dict[str, int]) -> int:
    return sum(int(value or 0) for value in ticket_counts.values())


def run_one(profile: Path, args: argparse.Namespace) -> dict[str, Any]:
    try:
        meta = profile_metadata(profile)
        world_id = profile_world_id(profile)
    except Exception as exc:  # noqa: BLE001
        return {"profileData": str(profile), "ok": False, "error": f"metadata failed: {exc}"}

    result: dict[str, Any] = {
        "profileData": str(profile),
        "teamId": meta["teamId"],
        "teamName": meta["teamName"],
        "ownerName": meta["ownerName"],
        "season": meta["season"],
        "worldId": world_id,
        "execute": bool(args.execute),
        "ok": True,
    }

    if args.execute:
        login_path = LOGIN_PATH.format(
            team_id=meta["teamId"],
            world_id=world_id,
            app_version=args.login_app_version,
            login_arg=args.login_arg,
        )
        ok, login_payload, attempt = get_json_with_retries(
            login_path,
            profile,
            timeout_sec=args.timeout_sec,
            retries=args.retries,
            retry_delay_sec=args.retry_delay_sec,
        )
        result["login"] = {"ok": ok, "attempt": attempt, "path": login_path, "response": login_payload}
        if not ok or not isinstance(login_payload, dict) or str(login_payload.get("code") or "") != "000":
            result["ok"] = False
            result["error"] = "login_failed"
            return result

    box_path = PRESENT_BOX_INDEX.format(team_id=meta["teamId"], world_id=world_id)
    ok, box_payload, attempt = get_json_with_retries(
        box_path,
        profile,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
        retry_delay_sec=args.retry_delay_sec,
    )
    result["presentBox"] = {"ok": ok, "attempt": attempt, "path": box_path}
    if not ok or not isinstance(box_payload, dict) or str(box_payload.get("code") or "") != "000":
        result["ok"] = False
        result["error"] = "present_box_failed"
        result["presentBox"]["response"] = box_payload
        return result

    all_items = [present_info(item) for item in box_payload.get("list") or [] if isinstance(item, dict)]
    targets = unaccepted_targets(all_items)
    login_bonus_targets = [item for item in targets if item.get("serviceMenuId") == LOGIN_BONUS_SERVICE_MENU_ID]
    result["presentBox"].update(
        {
            "totalItems": len(all_items),
            "loginBonusTotal": sum(1 for item in all_items if item.get("serviceMenuId") == LOGIN_BONUS_SERVICE_MENU_ID),
            "loginBonusTargets": len(login_bonus_targets),
            "targetCount": len(targets),
            "targetBreakdownByServiceMenuId": service_menu_breakdown(targets),
            "targetItems": targets,
        }
    )

    accepted: list[dict[str, Any]] = []
    accept_errors: list[dict[str, Any]] = []
    if args.execute:
        for item in targets:
            present_id = int(item["presentId"])
            ok, accept_payload = request_json(
                "POST",
                PRESENT_BOX_ACCEPT.format(team_id=meta["teamId"], world_id=world_id),
                profile,
                payload={"present_id": present_id},
                timeout_sec=args.timeout_sec,
            )
            row = {
                "presentId": present_id,
                "serviceMenuId": item.get("serviceMenuId"),
                "title": item.get("title"),
                "ok": ok,
                "response": accept_payload,
            }
            if ok and isinstance(accept_payload, dict) and str(accept_payload.get("code") or "") == "000":
                accepted.append(row)
            else:
                accept_errors.append(row)

    result["acceptedCount"] = len(accepted)
    result["accepted"] = accepted
    result["acceptErrors"] = accept_errors
    if accept_errors:
        result["ok"] = False
        result["error"] = "accept_failed"

    if not args.skip_shop_player_inquiry:
        inquiry_path = SHOP_PLAYER_INQUIRY.format(team_id=meta["teamId"], world_id=world_id)
        ok, inquiry_payload, attempt = get_json_with_retries(
            inquiry_path,
            profile,
            timeout_sec=args.timeout_sec,
            retries=args.retries,
            retry_delay_sec=args.retry_delay_sec,
        )
        inquiry: dict[str, Any] = {"ok": ok, "attempt": attempt, "path": inquiry_path}
        if ok and isinstance(inquiry_payload, dict) and str(inquiry_payload.get("code") or "") == "000":
            inquiry.update(compact_shop_player_inquiry(inquiry_payload))
            inquiry["ticketTotal"] = ticket_total(inquiry["ticket"])
        else:
            inquiry["response"] = inquiry_payload
        result["shopPlayerInquiry"] = inquiry
    return result


def notify(summary: dict[str, Any]) -> None:
    failed_count = len(summary.get("failed") or [])
    ticket_failed_count = len(summary.get("ticketInquiryFailed") or [])
    needs_attention = failed_count > 0 or ticket_failed_count > 0
    accepted_count = int(summary.get("acceptedCount") or 0)
    breakdown = summary.get("targetBreakdownByServiceMenuId") or {}
    breakdown_text = ", ".join(f"{key}:{value}" for key, value in sorted(breakdown.items())) or "none"
    ticket_totals = summary.get("ticketTotalsByType") or {}
    ticket_total_text = ", ".join(f"{key}:{value}" for key, value in sorted(ticket_totals.items())) or "none"
    ticket_suffix = f" / チケット合計 {summary.get('ticketTotalCount', 0)}枚 ({ticket_total_text})"
    if ticket_failed_count:
        ticket_suffix = f"{ticket_suffix} / チケット確認失敗{ticket_failed_count}件"
    message = (
        f"プレゼント回収完了: {accepted_count}件 / {summary.get('profileCount')}チーム / 内訳 {breakdown_text}{ticket_suffix}"
        if not needs_attention
        else f"プレゼント回収 要確認: {failed_count}失敗 / {summary.get('profileCount')}チーム / 回収{accepted_count}件 / 内訳 {breakdown_text}{ticket_suffix}"
    )
    subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "--title", "WebSoccer Present Box", "--message", message],
        check=False,
    )


def ticket_inventory_result(summary: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in summary.get("results") or []:
        inquiry = item.get("shopPlayerInquiry") or {}
        if not inquiry:
            continue
        ticket = normalize_ticket_counts(inquiry.get("ticket"))
        rows.append(
            {
                "profileData": item.get("profileData"),
                "teamId": item.get("teamId"),
                "teamName": item.get("teamName"),
                "ownerName": item.get("ownerName"),
                "season": item.get("season"),
                "worldId": item.get("worldId"),
                "ok": bool(inquiry.get("ok") and str(inquiry.get("code") or "") == "000"),
                "ticket": ticket,
                "ticketTotal": ticket_total(ticket),
                "used": inquiry.get("used") or {},
                "hasListup": bool(inquiry.get("hasListup")),
                "listupId": inquiry.get("listupId"),
                "error": inquiry.get("response")
                if not inquiry.get("ok") or str(inquiry.get("code") or "") != "000"
                else None,
            }
        )
    totals_by_type: dict[str, int] = {}
    for row in rows:
        if not row.get("ok"):
            continue
        for key, value in (row.get("ticket") or {}).items():
            totals_by_type[str(key)] = totals_by_type.get(str(key), 0) + int(value or 0)
    return {
        "generatedAt": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
        "source": "run_all_websoccer_login_bonus.py /shop_player/inquiry",
        "profileCount": len(rows),
        "okCount": sum(1 for row in rows if row.get("ok")),
        "failedCount": sum(1 for row in rows if not row.get("ok")),
        "ticketTotalsByType": dict(sorted(totals_by_type.items(), key=lambda kv: kv[0])),
        "ticketTotalCount": sum(totals_by_type.values()),
        "results": rows,
    }


def save_ticket_inventory(summary: dict[str, Any], out_dir: Path) -> dict[str, Any] | None:
    inventory = ticket_inventory_result(summary)
    if inventory["profileCount"] == 0:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d_%H%M%S")
    dated_path = out_dir / f"ticket_inventory_{stamp}.json"
    latest_path = out_dir / "latest.json"
    text = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    dated_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    return {
        "path": str(dated_path),
        "latestPath": str(latest_path),
        "okCount": inventory["okCount"],
        "failedCount": inventory["failedCount"],
        "ticketTotalsByType": inventory["ticketTotalsByType"],
        "ticketTotalCount": inventory["ticketTotalCount"],
    }


def main() -> int:
    args = parse_args()
    profiles = selected_profiles(args)
    results = [run_one(profile, args) for profile in profiles]
    failed = [item for item in results if not item.get("ok")]
    accepted_count = sum(int(item.get("acceptedCount") or 0) for item in results)
    target_count = sum(int(((item.get("presentBox") or {}).get("targetCount")) or 0) for item in results)
    login_bonus_target_count = sum(int(((item.get("presentBox") or {}).get("loginBonusTargets")) or 0) for item in results)
    target_breakdown: dict[str, int] = {}
    for item in results:
        for key, value in ((item.get("presentBox") or {}).get("targetBreakdownByServiceMenuId") or {}).items():
            target_breakdown[str(key)] = target_breakdown.get(str(key), 0) + int(value or 0)
    ticket_totals: dict[str, int] = {}
    ticket_inquiry_failed: list[dict[str, Any]] = []
    for item in results:
        inquiry = item.get("shopPlayerInquiry") or {}
        if not inquiry:
            continue
        if not inquiry.get("ok") or str(inquiry.get("code") or "") != "000":
            ticket_inquiry_failed.append(
                {
                    "profileData": item.get("profileData"),
                    "teamId": item.get("teamId"),
                    "teamName": item.get("teamName"),
                    "worldId": item.get("worldId"),
                    "shopPlayerInquiry": inquiry,
                }
            )
            continue
        for key, value in normalize_ticket_counts(inquiry.get("ticket")).items():
            ticket_totals[str(key)] = ticket_totals.get(str(key), 0) + int(value or 0)
    summary = {
        "execute": bool(args.execute),
        "profileCount": len(profiles),
        "okCount": len(results) - len(failed),
        "targetCount": target_count,
        "loginBonusTargetCount": login_bonus_target_count,
        "targetBreakdownByServiceMenuId": dict(sorted(target_breakdown.items(), key=lambda kv: kv[0])),
        "acceptedCount": accepted_count,
        "ticketTotalsByType": dict(sorted(ticket_totals.items(), key=lambda kv: kv[0])),
        "ticketTotalCount": sum(ticket_totals.values()),
        "ticketInquiryFailed": ticket_inquiry_failed,
        "failed": failed,
        "results": results,
    }
    ticket_inventory = None
    if not args.skip_shop_player_inquiry:
        ticket_inventory = save_ticket_inventory(summary, Path(args.ticket_inventory_dir).expanduser().resolve())
        summary["ticketInventory"] = ticket_inventory
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.notify_pushover:
        notify(summary)
    return 1 if failed or ticket_inquiry_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
