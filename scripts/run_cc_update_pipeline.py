#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Optional, Sequence

from fetch_cc_all_worlds_completed import (
    API_HOST,
    DEFAULT_MATCH_ROOT,
    extract_auth_from_session_files,
    request_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
PYTHON_EXE = str(PYTHON if PYTHON.exists() else Path(sys.executable))
SESSION_SUFFIXES = {".chlsx", ".chlsj", ".chlz"}
DEFAULT_SESSION_DIR = Path.home() / "charles_sessions"
SITE_GIT_PATHS = [
    "app/data.json",
    "app/coaches_data.json",
    "app/formations_data.json",
    "app/collections_data.json",
    "app/cc_range_data.json",
    "app/site_meta.json",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Refresh WebSoccer auth through Charles, fetch CC data, update WSM/site JSON, "
            "and optionally commit/push site changes."
        )
    )
    p.add_argument("--match-root", default=str(DEFAULT_MATCH_ROOT), help=f"CC JSON root (default: {DEFAULT_MATCH_ROOT})")
    p.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR), help="Directory for saved Charles sessions")
    p.add_argument("--session-file", default="", help="Use this saved Charles session")
    p.add_argument("--skip-capture", action="store_true", help="Do not launch apps; use --session-file or newest session")
    p.add_argument(
        "--reuse-valid-session",
        action="store_true",
        help="Before launching apps, reuse the newest/session-file Charles session if a lightweight CC API check passes.",
    )
    p.add_argument("--wait-sec", type=float, default=420.0, help="How long to wait for a saved Charles session")
    p.add_argument("--poll-sec", type=float, default=2.0, help="Polling interval while waiting for session save")
    p.add_argument("--websoccer-app", default="/Applications/Webサッカー.app")
    p.add_argument("--charles-app", default="/Applications/Charles.app")
    p.add_argument("--quit-first", action="store_true", help="Quit Charles/WebSoccer before launching them")
    p.add_argument("--keep-apps-open", action="store_true", help="Do not quit Charles/WebSoccer after the pipeline")
    p.add_argument("--skip-auto-start", action="store_true", help="Do not try to press START in WebSoccer")
    p.add_argument("--auto-navigate-websoccer", action="store_true", help="Try START -> OK -> Champions Cup UI navigation")
    p.add_argument("--capture-warmup-sec", type=float, default=8.0, help="Wait after WebSoccer auto navigation")
    p.add_argument("--capture-only", action="store_true", help="Only capture and validate a fresh Charles session")

    p.add_argument("--team-id", default="", help="Team ID (optional; inferred from gate-key if omitted)")
    p.add_argument("--worlds", default="1-21", help='World range/list, e.g. "1-21" or "1,2,20"')
    p.add_argument("--season", type=int, default=1, help="Fetch season selector: 0=current, 1=previous")
    p.add_argument("--groups", default="0-8", help='Group index range/list (default: "0-8")')
    p.add_argument("--round-max", type=int, default=12, help="Max tournament round index")
    p.add_argument("--delay-sec", type=float, default=0.08, help="Delay between summary requests")
    p.add_argument("--timeout-sec", type=float, default=10.0, help="HTTP timeout")
    p.add_argument("--summary-tail", default="", help='Summary tail override (e.g. "0" or "1")')
    p.add_argument("--progress-every", type=int, default=20)
    p.add_argument("--force", action="store_true", help="Refetch even if output exists")
    p.add_argument("--dry-run-fetch", action="store_true", help="Fetch target list only; skip WSM/site/git steps")

    p.add_argument("--wsm-season", type=int, default=0, help="WSM CC season to import. 0 means latest JSON season")
    p.add_argument("--skip-wsm-update", action="store_true", help="Only fetch CC JSON")
    p.add_argument("--commit-push", action="store_true", help="Commit and push generated site JSON changes")
    p.add_argument("--commit-message", default="Update CC data and site")
    p.add_argument("--skip-push", action="store_true", help="Commit only, without git push")
    p.add_argument("--notify-pushover", action="store_true", help="Send Pushover notification on success/failure")
    p.add_argument("--pushover-env-file", default=str(Path.home() / ".websoccer_pushover.env"))
    return p.parse_args()


def run(cmd: Sequence[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(
        list(cmd),
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=capture,
        check=check,
    )


def run_osascript(script: str, timeout_sec: float = 8.0) -> bool:
    try:
        cp = subprocess.run(
            ["osascript"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_sec,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if cp.returncode != 0 and cp.stderr.strip():
        print(f"[WARN] AppleScript failed: {cp.stderr.strip()}", flush=True)
    return cp.returncode == 0


def run_osascript_stdout(script: str, timeout_sec: float = 8.0) -> str:
    try:
        cp = subprocess.run(
            ["osascript"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_sec,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if cp.returncode != 0 and cp.stderr.strip():
        print(f"[WARN] AppleScript failed: {cp.stderr.strip()}", flush=True)
    return cp.stdout.strip()


def open_app(app_path: str, fallback_name: str) -> None:
    path = Path(app_path)
    cmd = ["open", str(path)] if path.exists() else ["open", "-a", fallback_name]
    run(cmd, check=False)


def quit_apps() -> None:
    run_osascript('tell application "Webサッカー" to quit', timeout_sec=3)
    run_osascript('tell application "Charles" to quit', timeout_sec=3)
    time.sleep(2)


def start_charles_recording() -> None:
    script = """
tell application "Charles" to activate
delay 0.5
tell application "System Events"
  tell process "Charles"
    if exists menu item "Start Recording" of menu "Proxy" of menu bar 1 then
      click menu item "Start Recording" of menu "Proxy" of menu bar 1
    end if
  end tell
end tell
"""
    run_osascript(script, timeout_sec=8)


def try_press_websoccer_start() -> None:
    script = """
tell application "Webサッカー" to activate
delay 2
tell application "System Events"
  tell process "Webサッカー"
    try
      click button "スタート" of window 1
      return
    end try
    try
      click button "START" of window 1
      return
    end try
    try
      click button "Start" of window 1
      return
    end try
    key code 36
  end tell
end tell
"""
    if not run_osascript(script, timeout_sec=8):
        print("[WARN] START automation failed. Press START manually.", flush=True)


def try_click_websoccer_sequence() -> None:
    def click_description(description_part: str) -> bool:
        script = f"""
tell application "Webサッカー" to activate
delay 0.2
tell application "System Events"
  tell process "Webサッカー"
    set elems to entire contents of window 1
    repeat with e in elems
      try
        if description of e contains "{description_part}" then
          try
            perform action "AXPress" of e
          end try
          try
            click e
          end try
          return "clicked"
        end if
      end try
    end repeat
  end tell
end tell
return "missing"
"""
        result = run_osascript_stdout(script, timeout_sec=8)
        if result:
            print(f"[AUTO] WebSoccer click {description_part}: {result}", flush=True)
        return result == "clicked"

    def description_exists(description_part: str) -> bool:
        script = f"""
tell application "System Events"
  tell process "Webサッカー"
    set elems to entire contents of window 1
    repeat with e in elems
      try
        if description of e contains "{description_part}" then
          return "exists"
        end if
      end try
    end repeat
  end tell
end tell
return "missing"
"""
        return run_osascript_stdout(script, timeout_sec=5) == "exists"

    def wait_click(description_part: str, retries: int, interval_sec: float = 0.5) -> bool:
        for _ in range(max(1, retries)):
            if click_description(description_part):
                return True
            time.sleep(interval_sec)
        return False

    did_start = False
    for _ in range(3):
        if click_description("top btn"):
            time.sleep(3.0)
            if not description_exists("top btn"):
                did_start = True
                break
        else:
            time.sleep(0.4)
    if not did_start:
        run_osascript('tell application "System Events" to tell process "Webサッカー" to key code 36')
        time.sleep(3.0)
    wait_click("others header btn close", 30, 1.0)
    time.sleep(1.0)
    wait_click("league results menu btn cc", 45, 1.0)
    time.sleep(2)
    click_description("others header btn close")


def iter_session_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in SESSION_SUFFIXES)


def newest_session_file(root: Path, after_mtime: float = 0.0) -> Optional[Path]:
    files = [p for p in iter_session_files(root) if p.stat().st_mtime >= after_mtime]
    if not files:
        return None
    return sorted(files, key=lambda p: (p.stat().st_mtime, p.name))[-1]


def new_session_files(root: Path, after_mtime: float = 0.0) -> list[Path]:
    files = [p for p in iter_session_files(root) if p.stat().st_mtime >= after_mtime]
    return sorted(files, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def session_has_auth(fp: Path) -> bool:
    try:
        return extract_auth_from_session_files([fp]) is not None
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] could not inspect {fp}: {exc}", flush=True)
        return False


def first_int_from_spec(raw: str, default: int) -> int:
    raw = (raw or "").strip()
    if not raw:
        return default
    first = raw.split(",", 1)[0].strip()
    if "-" in first:
        first = first.split("-", 1)[0].strip()
    try:
        return int(first)
    except ValueError:
        return default


def session_passes_cc_api_check(args: argparse.Namespace, fp: Path) -> bool:
    auth = extract_auth_from_session_files([fp])
    if not auth:
        return False
    team_id = (args.team_id or auth.gate_key.split(":", 1)[0]).strip()
    if not team_id.isdigit():
        return False
    world_id = first_int_from_spec(args.worlds, 1)
    group_idx = first_int_from_spec(args.groups, 0)
    path = f"/cc/preliminary/{team_id}/{world_id}/{group_idx}/{args.season}.json"
    ok, data = request_json(path, auth, args.timeout_sec)
    if not ok:
        print("[INFO] Existing Charles session failed the CC API check.", flush=True)
        return False
    obj = data if isinstance(data, dict) else {}
    code = str(obj.get("code") or "")
    if code == "000":
        return True
    print(f"[INFO] Existing Charles session did not pass the CC API check: code={code or 'missing'}", flush=True)
    return False


def wait_for_auth_session(root: Path, after_mtime: float, timeout_sec: float, poll_sec: float) -> Path:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        for fp in new_session_files(root, after_mtime):
            if session_has_auth(fp):
                print(f"[INFO] Charles session with gate-key: {fp}", flush=True)
                return fp
        time.sleep(max(0.5, poll_sec))
    raise RuntimeError(f"Timed out waiting for a saved Charles session with Websoccer-gate-key in {root}")


def capture_session(args: argparse.Namespace) -> Path:
    session_dir = Path(args.session_dir).expanduser().resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    newest_before = newest_session_file(session_dir)
    after_mtime = newest_before.stat().st_mtime + 0.0001 if newest_before else time.time()

    if args.quit_first:
        print("[STEP] Quit existing Charles/WebSoccer processes")
        quit_apps()

    print("[STEP] Open Charles and start recording")
    open_app(args.charles_app, "Charles")
    time.sleep(1)
    start_charles_recording()

    print("[STEP] Open WebSoccer and try START")
    open_app(args.websoccer_app, "Webサッカー")
    if args.auto_navigate_websoccer:
        try_click_websoccer_sequence()
        if args.capture_warmup_sec > 0:
            time.sleep(args.capture_warmup_sec)
    elif not args.skip_auto_start:
        try_press_websoccer_start()

    if args.auto_navigate_websoccer:
        print(
            "\n[ACTION]\n"
            "  Webサッカー操作は自動化を試行済みです。\n"
            "  Charles Auto Save / Web Interface 保存が有効なら、このまま保存ファイルを待ちます。\n"
            "  保存が無効な場合は Charles のセッションを手動で .chlz 保存してください。\n",
            flush=True,
        )
    else:
        print(
            "\n[ACTION]\n"
            "  1. Webサッカーで START を押す\n"
            "  2. お知らせが出たら OK で閉じる\n"
            "  3. チャンピオンズカップを開く\n"
            "  4. CC画面が読み込めたら Charles の Recording を止める\n"
            f"  5. Charles のセッションを {session_dir} に .chlz で保存する\n",
            flush=True,
        )
    print(f"[WAIT] Looking for Websoccer-gate-key from {API_HOST}...", flush=True)
    return wait_for_auth_session(session_dir, after_mtime, args.wait_sec, args.poll_sec)


def resolve_session(args: argparse.Namespace) -> Path:
    if not args.skip_capture:
        if args.reuse_valid_session and not args.capture_only:
            if args.session_file:
                fp = Path(args.session_file).expanduser().resolve()
            else:
                fp = newest_session_file(Path(args.session_dir).expanduser().resolve()) or Path()
            if fp.exists() and session_has_auth(fp):
                if session_passes_cc_api_check(args, fp):
                    print(f"[INFO] Reusing valid Charles session: {fp}", flush=True)
                    return fp
                print("[INFO] Existing Charles session appears stale; capturing a fresh one.", flush=True)
        return capture_session(args)
    if args.session_file:
        fp = Path(args.session_file).expanduser().resolve()
    else:
        fp = newest_session_file(Path(args.session_dir).expanduser().resolve()) or Path()
    if not fp.exists():
        raise FileNotFoundError("No Charles session file found. Remove --skip-capture or pass --session-file.")
    if not session_has_auth(fp):
        raise RuntimeError(f"Charles session does not contain Websoccer-gate-key: {fp}")
    return fp


def fetch_cc(args: argparse.Namespace, session_file: Path) -> None:
    cmd = [
        PYTHON_EXE,
        str(REPO_ROOT / "scripts" / "fetch_cc_completed_season.py"),
        "--match-root",
        str(Path(args.match_root).expanduser()),
        "--session-file",
        str(session_file),
        "--worlds",
        args.worlds,
        "--season",
        str(args.season),
        "--groups",
        args.groups,
        "--round-max",
        str(args.round_max),
        "--delay-sec",
        str(args.delay_sec),
        "--timeout-sec",
        str(args.timeout_sec),
        "--progress-every",
        str(args.progress_every),
    ]
    if args.team_id:
        cmd += ["--team-id", args.team_id]
    if args.summary_tail:
        cmd += ["--summary-tail", args.summary_tail]
    if args.force:
        cmd.append("--force")
    if args.dry_run_fetch:
        cmd.append("--dry-run")
    run(cmd)


def update_wsm_and_site(args: argparse.Namespace) -> None:
    cmd = [
        PYTHON_EXE,
        str(REPO_ROOT / "scripts" / "update_wsm_cc_from_json.py"),
        "--json-root",
        str(Path(args.match_root).expanduser()),
        "--repo-dir",
        str(REPO_ROOT),
    ]
    if args.wsm_season:
        cmd += ["--season", str(args.wsm_season)]
    run(cmd)


def git_commit_push(args: argparse.Namespace) -> None:
    tracked = run(["git", "ls-files", *SITE_GIT_PATHS], capture=True).stdout.splitlines()
    paths = [p for p in tracked if (REPO_ROOT / p).exists()]
    if not paths:
        print("[INFO] No tracked site JSON paths found for commit.", flush=True)
        return

    status = run(["git", "status", "--porcelain", "--", *paths], capture=True).stdout.strip()
    if not status:
        print("[INFO] No site JSON changes to commit.", flush=True)
        return

    run(["git", "add", "--", *paths])
    run(["git", "commit", "-m", args.commit_message])
    if not args.skip_push:
        run(["git", "push"])


def notify_pushover(args: argparse.Namespace, *, success: bool, detail: str) -> None:
    if not args.notify_pushover:
        return
    title = "WebSoccer CC Update Complete" if success else "WebSoccer CC Update Failed"
    message = (
        f"現シーズンCCデータ取得とサイト更新が完了しました。{detail}"
        if success
        else f"現シーズンCC更新に失敗しました。{detail}"
    )
    cp = run(
        [
            PYTHON_EXE,
            str(REPO_ROOT / "scripts" / "notify_pushover.py"),
            "--env-file",
            args.pushover_env_file,
            "--title",
            title,
            "--message",
            message,
            "--priority",
            "0" if success else "1",
        ],
        check=False,
    )
    if cp.returncode != 0:
        print("[WARN] Pushover notification was not delivered.", flush=True)


def main() -> int:
    args = parse_args()
    rc = 0
    error_detail = ""
    try:
        session_file = resolve_session(args)
        if args.capture_only:
            print(f"[DONE] capture-only session validated: {session_file}")
            notify_pushover(args, success=True, detail="capture-only セッション検証のみ完了。")
            return 0
        fetch_cc(args, session_file)
        if args.dry_run_fetch:
            print("[DONE] dry-run fetch completed; WSM/site/git steps skipped.")
        else:
            if not args.skip_wsm_update:
                update_wsm_and_site(args)
            if args.commit_push:
                git_commit_push(args)
    except Exception as exc:  # noqa: BLE001
        error_detail = str(exc)
        print(f"[ERROR] {exc}", file=sys.stderr, flush=True)
        rc = 1
    finally:
        if not args.skip_capture and not args.keep_apps_open:
            print("[STEP] Quit Charles and WebSoccer")
            quit_apps()
    if rc == 0:
        notify_pushover(args, success=True, detail="commit/push 実行オプションに従って処理済み。")
        print("[DONE] CC update pipeline completed.")
    else:
        notify_pushover(args, success=False, detail=error_detail[:500])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
