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
    DEFAULT_WEBSOCCER_CONTAINER,
    DEFAULT_MATCH_ROOT,
    extract_auth_from_session_files,
    local_auth_from_container,
    request_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
PYTHON_EXE = str(PYTHON if PYTHON.exists() else Path(sys.executable))
SESSION_SUFFIXES = {".chlsx", ".chlsj", ".chlz"}
DEFAULT_SESSION_DIR = Path.home() / "charles_sessions"
DEFAULT_OPENAI_AUTH_PROFILE = Path("/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current")
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
            "Use local WebSoccer profile auth, fetch CC data, update WSM/site JSON, "
            "and optionally commit/push site changes. This command does not launch apps."
        )
    )
    p.add_argument("--match-root", default=str(DEFAULT_MATCH_ROOT), help=f"CC JSON root (default: {DEFAULT_MATCH_ROOT})")
    p.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR), help="Directory for saved Charles sessions")
    p.add_argument("--session-file", default="", help="Use this saved Charles session")
    p.add_argument(
        "--auth-source",
        choices=("auto", "local", "session"),
        default="local",
        help="API auth source. Default is local OpenAI profile auth; use session explicitly for Charles fallback.",
    )
    p.add_argument(
        "--websoccer-container",
        default=str(DEFAULT_OPENAI_AUTH_PROFILE if DEFAULT_OPENAI_AUTH_PROFILE.exists() else DEFAULT_WEBSOCCER_CONTAINER),
        help="Profile Data directory used for local API auth. Default is the stored OpenAI profile.",
    )
    p.add_argument("--skip-capture", action="store_true", help="Deprecated no-op; app/Charles capture is disabled.")
    p.add_argument(
        "--reuse-valid-session",
        action="store_true",
        help="Before launching apps, reuse the newest/session-file Charles session if a lightweight CC API check passes.",
    )
    p.add_argument("--wait-sec", type=float, default=420.0, help="Deprecated no-op; app/Charles capture is disabled.")
    p.add_argument("--poll-sec", type=float, default=2.0, help="Deprecated no-op; app/Charles capture is disabled.")
    p.add_argument("--capture-only", action="store_true", help="Validate local/session auth only; never launches apps.")

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


def local_auth_passes_cc_api_check(args: argparse.Namespace) -> bool:
    auth = local_auth_from_container(Path(args.websoccer_container).expanduser())
    if not auth:
        return False
    team_id = (args.team_id or auth.local_team_id or auth.gate_key.split(":", 1)[0]).strip()
    if not team_id.isdigit():
        return False
    world_id = first_int_from_spec(args.worlds, 1)
    group_idx = first_int_from_spec(args.groups, 0)
    path = f"/cc/preliminary/{team_id}/{world_id}/{group_idx}/{args.season}.json"
    ok, data = request_json(path, auth, args.timeout_sec)
    if not ok:
        print("[INFO] Generated local gate-key failed the CC API check.", flush=True)
        return False
    obj = data if isinstance(data, dict) else {}
    code = str(obj.get("code") or "")
    if code == "000":
        print("[INFO] Generated local gate-key passed the CC API check.", flush=True)
        return True
    print(f"[INFO] Generated local gate-key did not pass the CC API check: code={code or 'missing'}", flush=True)
    return False


def resolve_session(args: argparse.Namespace) -> Optional[Path]:
    if args.auth_source in {"auto", "local"}:
        if local_auth_passes_cc_api_check(args):
            return None
        if args.auth_source == "local":
            raise RuntimeError("could not use generated local WebSoccer gate-key")

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
        raise RuntimeError("Charles/Webサッカー capture is disabled. Use --auth-source local, or pass --auth-source session with --session-file/--skip-capture for an existing saved session.")
    if args.session_file:
        fp = Path(args.session_file).expanduser().resolve()
    else:
        fp = newest_session_file(Path(args.session_dir).expanduser().resolve()) or Path()
    if not fp.exists():
        raise FileNotFoundError("No Charles session file found. Remove --skip-capture or pass --session-file.")
    if not session_has_auth(fp):
        raise RuntimeError(f"Charles session does not contain Websoccer-gate-key: {fp}")
    return fp


def fetch_cc(args: argparse.Namespace, session_file: Optional[Path]) -> None:
    auth_source = "session" if session_file and args.auth_source == "auto" else args.auth_source
    cmd = [
        PYTHON_EXE,
        str(REPO_ROOT / "scripts" / "fetch_cc_completed_season.py"),
        "--match-root",
        str(Path(args.match_root).expanduser()),
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
        "--auth-source",
        auth_source,
        "--websoccer-container",
        str(Path(args.websoccer_container).expanduser()),
    ]
    if session_file:
        cmd += ["--session-file", str(session_file)]
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


def git_commit_push(args: argparse.Namespace, progress: dict[str, bool] | None = None) -> None:
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
    if progress is not None:
        progress["committed"] = True
    if not args.skip_push:
        run(["git", "push"])
        if progress is not None:
            progress["pushed"] = True


def cc_season_label(args: argparse.Namespace) -> str:
    if args.season == 0:
        return "現シーズン"
    if args.season == 1:
        return "昨シーズン"
    return f"{args.season}シーズン前"


def notify_pushover(
    args: argparse.Namespace,
    *,
    success: bool,
    detail: str,
    site_updated: bool = False,
) -> None:
    if not args.notify_pushover:
        return
    season_label = cc_season_label(args)
    if success:
        title = "WebSoccer CC Update Complete"
        message = f"{season_label}CCデータ取得とサイト更新が完了しました。{detail}"
        priority = "0"
    elif site_updated:
        title = "WebSoccer CC Publish Failed"
        message = f"{season_label}CCデータ取得とサイト更新は完了しましたが、commit/push段階で失敗しました。{detail}"
        priority = "1"
    else:
        title = "WebSoccer CC Update Failed"
        message = f"{season_label}CC更新に失敗しました。{detail}"
        priority = "1"
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
            priority,
        ],
        check=False,
    )
    if cp.returncode != 0:
        print("[WARN] Pushover notification was not delivered.", flush=True)


def main() -> int:
    args = parse_args()
    rc = 0
    error_detail = ""
    session_file: Optional[Path] = None
    progress = {
        "fetched": False,
        "site_updated": False,
        "committed": False,
        "pushed": False,
    }
    try:
        session_file = resolve_session(args)
        if args.capture_only:
            if session_file is None:
                print("[DONE] capture-only local generated gate-key validated")
                notify_pushover(args, success=True, detail="capture-only ローカル生成gate-key検証のみ完了。")
                return 0
            print(f"[DONE] capture-only session validated: {session_file}")
            notify_pushover(args, success=True, detail="capture-only セッション検証のみ完了。")
            return 0
        fetch_cc(args, session_file)
        progress["fetched"] = True
        if args.dry_run_fetch:
            print("[DONE] dry-run fetch completed; WSM/site/git steps skipped.")
        else:
            if not args.skip_wsm_update:
                update_wsm_and_site(args)
                progress["site_updated"] = True
            if args.commit_push:
                git_commit_push(args, progress)
    except Exception as exc:  # noqa: BLE001
        error_detail = str(exc)
        print(f"[ERROR] {exc}", file=sys.stderr, flush=True)
        rc = 1
    finally:
        pass
    if rc == 0:
        notify_pushover(args, success=True, detail="commit/push 実行オプションに従って処理済み。")
        print("[DONE] CC update pipeline completed.")
    else:
        notify_pushover(args, success=False, detail=error_detail[:500], site_updated=progress["site_updated"])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
