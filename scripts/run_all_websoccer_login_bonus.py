#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

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
from sync_all_websoccer_profiles import collect_profiles  # noqa: E402
from websoccer_trade_api import profile_metadata, request_json  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_pushover.py"


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
    p.add_argument("--notify-pushover", action="store_true")
    return p.parse_args()


def selected_profiles(args: argparse.Namespace) -> list[Path]:
    if args.profile_data:
        return [Path(item).expanduser().resolve() for item in args.profile_data]
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
    return result


def notify(summary: dict[str, Any]) -> None:
    failed_count = len(summary.get("failed") or [])
    accepted_count = int(summary.get("acceptedCount") or 0)
    breakdown = summary.get("targetBreakdownByServiceMenuId") or {}
    breakdown_text = ", ".join(f"{key}:{value}" for key, value in sorted(breakdown.items())) or "none"
    message = (
        f"プレゼント回収完了: {accepted_count}件 / {summary.get('profileCount')}チーム / 内訳 {breakdown_text}"
        if failed_count == 0
        else f"プレゼント回収 要確認: {failed_count}失敗 / {summary.get('profileCount')}チーム / 回収{accepted_count}件 / 内訳 {breakdown_text}"
    )
    subprocess.run(
        [sys.executable, str(NOTIFY_SCRIPT), "--title", "WebSoccer Present Box", "--message", message],
        check=False,
    )


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
    summary = {
        "execute": bool(args.execute),
        "profileCount": len(profiles),
        "okCount": len(results) - len(failed),
        "targetCount": target_count,
        "loginBonusTargetCount": login_bonus_target_count,
        "targetBreakdownByServiceMenuId": dict(sorted(target_breakdown.items(), key=lambda kv: kv[0])),
        "acceptedCount": accepted_count,
        "failed": failed,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.notify_pushover:
        notify(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
