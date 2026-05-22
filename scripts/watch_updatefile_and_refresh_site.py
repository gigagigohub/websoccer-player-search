#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CODING_ROOT = REPO_ROOT.parent
WSC_DATA = CODING_ROOT / "wsc_data"
DEFAULT_WATCH_DIR = WSC_DATA / "updatefile_watch"
DEFAULT_PUSHOVER_CONFIG = Path.home() / ".websoccer_updatefile_watch" / "config.json"
DEFAULT_PUSHOVER_USER_KEY_CONFIG = Path.home() / ".yamato_pushover_watch" / "config.json"
DEFAULT_WSM_DIR = WSC_DATA / "websoccer_master_db"
DEFAULT_DESKTOP_WSM_DIR = Path.home() / "Desktop" / "websoccer_master_db"
DEFAULT_FILLED_CSV = WSC_DATA / "UpdateFile_inventory" / "updatefile_ss_events_filled.csv"
JST = timezone(timedelta(hours=9))

sys.path.insert(0, str(SCRIPT_DIR))
from fetch_updatefiles import (  # noqa: E402
    DEFAULT_BASE_URL,
    default_update_dir,
    fetch_one,
    iter_local_versions,
    maybe_rename_update_dir,
)


@dataclass
class CopiedImages:
    player_static: int = 0
    player_action: int = 0
    scout_buttons: int = 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Check for new UpdateFile archives and refresh WebSoccer DB/site when a new one appears."
    )
    p.add_argument("--update-dir", default=str(default_update_dir()))
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--watch-dir", default=str(DEFAULT_WATCH_DIR))
    p.add_argument("--pushover-config", default=str(DEFAULT_PUSHOVER_CONFIG))
    p.add_argument(
        "--pushover-user-key-config",
        default=str(DEFAULT_PUSHOVER_USER_KEY_CONFIG),
        help="Optional fallback config used only for the Pushover user key.",
    )
    p.add_argument("--wsm-dir", default=str(DEFAULT_WSM_DIR))
    p.add_argument("--desktop-wsm-dir", default=str(DEFAULT_DESKTOP_WSM_DIR))
    p.add_argument("--filled-csv", default=str(DEFAULT_FILLED_CSV))
    p.add_argument("--max-consecutive", type=int, default=5)
    p.add_argument("--commit-push", action="store_true", help="Commit and push regenerated site files after update.")
    p.add_argument("--no-notify", action="store_true", help="Do not send Pushover notifications.")
    p.add_argument("--dry-run", action="store_true", help="Check availability only. Do not download or update.")
    p.add_argument("--verify-tls", action="store_true", help="Enable TLS validation for the asset host.")
    return p.parse_args()


def log(message: str, log_path: Path) -> None:
    stamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S%z")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def acquire_lock(lock_path: Path) -> int | None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None


def release_lock(fd: int | None, lock_path: Path) -> None:
    if fd is not None:
        os.close(fd)
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def read_json_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_pushover_config(app_config_path: Path, user_key_config_path: Path | None = None) -> dict[str, str]:
    cfg = read_json_config(app_config_path)
    token = str(cfg.get("pushover_app_token") or cfg.get("token") or "").strip()
    user = str(cfg.get("pushover_user_key") or cfg.get("user") or "").strip()
    if not user and user_key_config_path and user_key_config_path.exists():
        user_cfg = read_json_config(user_key_config_path)
        user = str(user_cfg.get("pushover_user_key") or user_cfg.get("user") or "").strip()
    if not token or not user:
        raise ValueError(
            f"Pushover token/user key missing. app_config={app_config_path} user_key_config={user_key_config_path}"
        )
    return {"token": token, "user": user}


def notify(
    app_config_path: Path,
    user_key_config_path: Path | None,
    title: str,
    message: str,
    enabled: bool,
    log_path: Path,
) -> None:
    if not enabled:
        return
    try:
        cfg = load_pushover_config(app_config_path, user_key_config_path)
        payload = urllib.parse.urlencode(
            {
                "token": cfg["token"],
                "user": cfg["user"],
                "title": title,
                "message": message,
            }
        ).encode("utf-8")
        req = urllib.request.Request("https://api.pushover.net/1/messages.json", data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=15) as res:
            res.read()
        log(f"pushover sent: {title}", log_path)
    except Exception as exc:
        log(f"pushover failed: {type(exc).__name__}: {exc}", log_path)


def latest_local_version(update_dir: Path) -> int | None:
    versions = sorted(iter_local_versions(update_dir))
    return versions[-1] if versions else None


def fetch_new_updatefiles(args: argparse.Namespace, update_dir: Path, log_path: Path) -> tuple[Path, list[int]]:
    downloaded_versions: list[int] = []
    results = []
    current = latest_local_version(update_dir)
    if current is None:
        raise FileNotFoundError(f"No local UpdateFile versions found in {update_dir}")

    for _ in range(max(1, args.max_consecutive)):
        next_version = current + 1
        result = fetch_one(
            version=next_version,
            base_url=args.base_url,
            update_dir=update_dir,
            timeout=args.timeout,
            verify_tls=args.verify_tls,
            dry_run=args.dry_run,
        )
        results.append(result)
        log(f"p{next_version}: {result.status} {result.note}", log_path)
        if result.status in {"available", "downloaded", "exists_ok"}:
            downloaded_versions.append(next_version)
            current = next_version
            if args.dry_run:
                break
            continue
        if result.status == "missing":
            break
        raise RuntimeError(f"UpdateFile p{next_version} check failed: {result.status} {result.note}")

    if downloaded_versions and not args.dry_run:
        update_dir = maybe_rename_update_dir(update_dir, results)
    return update_dir, downloaded_versions


PLAYER_RE = re.compile(
    r"(?:^|/)Resources/img/chara/players/(static|action)/(\d+)(?:@2x)?\.gif$",
    re.IGNORECASE,
)
SCOUT_BUTTON_RE = re.compile(
    r"(?:^|/)Resources/img/Shop/btn/(ss_btn_\d+)\.png$",
    re.IGNORECASE,
)


def copy_updatefile_images(zip_paths: list[Path], app_dir: Path) -> CopiedImages:
    copied = CopiedImages()
    static_dir = app_dir / "images" / "chara" / "players" / "static"
    action_dir = app_dir / "images" / "chara" / "players" / "action"
    scout_btn_dir = app_dir / "images" / "Shop" / "btn"
    static_dir.mkdir(parents=True, exist_ok=True)
    action_dir.mkdir(parents=True, exist_ok=True)
    scout_btn_dir.mkdir(parents=True, exist_ok=True)

    for zip_path in zip_paths:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                player_match = PLAYER_RE.search(name)
                if player_match:
                    kind, player_id = player_match.groups()
                    dest_dir = static_dir if kind.lower() == "static" else action_dir
                    dest = dest_dir / f"{player_id}.gif"
                    dest.write_bytes(zf.read(info.filename))
                    if kind.lower() == "static":
                        copied.player_static += 1
                    else:
                        copied.player_action += 1
                    continue

                scout_match = SCOUT_BUTTON_RE.search(name)
                if scout_match:
                    dest = scout_btn_dir / f"{scout_match.group(1)}.png"
                    dest.write_bytes(zf.read(info.filename))
                    copied.scout_buttons += 1
    return copied


def run(cmd: list[str], cwd: Path = REPO_ROOT) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def build_master_db(update_dir: Path, wsm_dir: Path) -> Path:
    stamp = datetime.now(JST).strftime("%y%m%d%H%M")
    wsm_dir.mkdir(parents=True, exist_ok=True)
    out_db = wsm_dir / f"wsm_{stamp}.sqlite3"
    run(
        [
            sys.executable,
            str(SCRIPT_DIR / "build_websoccer_master_db.py"),
            "--out-db",
            str(out_db),
            "--updatefile-dir",
            str(update_dir),
        ]
    )
    return out_db


def copy_latest_wsm_to_desktop(out_db: Path, desktop_wsm_dir: Path) -> Path:
    desktop_wsm_dir.mkdir(parents=True, exist_ok=True)
    dest = desktop_wsm_dir / out_db.name
    shutil.copy2(out_db, dest)
    return dest


def cleanup_wsm_files(local_dir: Path, desktop_dir: Path) -> None:
    local_files = sorted(local_dir.glob("wsm_*.sqlite3"), key=lambda p: (p.name, p.stat().st_mtime))
    for old in local_files[:-3]:
        old.unlink()
    desktop_files = sorted(desktop_dir.glob("wsm_*.sqlite3"), key=lambda p: (p.name, p.stat().st_mtime))
    for old in desktop_files[:-1]:
        old.unlink()


def refresh_site(update_dir: Path, wsm_dir: Path, desktop_wsm_dir: Path, filled_csv: Path) -> Path:
    app_dir = REPO_ROOT / "app"
    # First reflect the latest ss.plist into app/data.json so the master DB imports new SS events.
    run(
        [
            sys.executable,
            str(SCRIPT_DIR / "link_scout_history.py"),
            "--zip-dir",
            str(update_dir),
            "--filled-csv",
            str(filled_csv),
            "--app-data",
            str(app_dir / "data.json"),
            "--blank-missing-title",
        ]
    )
    out_db = build_master_db(update_dir, wsm_dir)
    copy_latest_wsm_to_desktop(out_db, desktop_wsm_dir)
    run(
        [
            sys.executable,
            str(SCRIPT_DIR / "update_site_from_master_db.py"),
            "--master-db",
            str(out_db),
        ]
    )
    # Re-attach per-player scoutHistory after the exporter rewrites app/data.json.
    run(
        [
            sys.executable,
            str(SCRIPT_DIR / "link_scout_history.py"),
            "--zip-dir",
            str(update_dir),
            "--filled-csv",
            str(filled_csv),
            "--app-data",
            str(app_dir / "data.json"),
            "--blank-missing-title",
        ]
    )
    run([sys.executable, str(SCRIPT_DIR / "write_site_meta.py"), "--app-dir", str(app_dir)])
    cleanup_wsm_files(wsm_dir, desktop_wsm_dir)
    return out_db


def git_commit_push(versions: list[int]) -> None:
    paths = [
        "app/data.json",
        "app/coaches_data.json",
        "app/formations_data.json",
        "app/site_meta.json",
        "app/images/chara/players/static",
        "app/images/chara/players/action",
        "app/images/Shop/btn",
    ]
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *paths],
        cwd=str(REPO_ROOT),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    if not status:
        return
    run(["git", "add", *paths])
    if len(versions) == 1:
        msg = f"Update site for UpdateFile p{versions[0]}"
    else:
        msg = f"Update site for UpdateFile p{versions[0]}-p{versions[-1]}"
    run(["git", "commit", "-m", msg])
    run(["git", "push"])


def main() -> int:
    args = parse_args()
    watch_dir = Path(args.watch_dir).expanduser().resolve()
    log_path = watch_dir / "logs" / "updatefile_watch.log"
    lock_path = watch_dir / "updatefile_watch.lock"
    update_dir = Path(args.update_dir).expanduser().resolve()
    pushover_config = Path(args.pushover_config).expanduser().resolve()
    pushover_user_key_config = Path(args.pushover_user_key_config).expanduser().resolve()
    wsm_dir = Path(args.wsm_dir).expanduser().resolve()
    desktop_wsm_dir = Path(args.desktop_wsm_dir).expanduser().resolve()
    filled_csv = Path(args.filled_csv).expanduser().resolve()
    notify_enabled = not args.no_notify

    fd = acquire_lock(lock_path)
    if fd is None:
        log("another updatefile watch run is active; skipping", log_path)
        return 0

    found_versions: list[int] = []
    try:
        log(f"checking UpdateFile from {update_dir}", log_path)
        update_dir, found_versions = fetch_new_updatefiles(args, update_dir, log_path)
        if not found_versions:
            log("no new UpdateFile", log_path)
            return 0
        if args.dry_run:
            log(f"dry-run found UpdateFile versions: {found_versions}", log_path)
            return 0

        version_label = (
            f"p{found_versions[0]}" if len(found_versions) == 1 else f"p{found_versions[0]}-p{found_versions[-1]}"
        )
        notify(
            pushover_config,
            pushover_user_key_config,
            "WebSoccer UpdateFile",
            f"{version_label} が見つかりました。DBとサイト更新を開始します。",
            notify_enabled,
            log_path,
        )

        zip_paths = [update_dir / f"p{v}.zip" for v in found_versions]
        copied = copy_updatefile_images(zip_paths, REPO_ROOT / "app")
        log(
            "copied images: "
            f"static={copied.player_static} action={copied.player_action} scoutButtons={copied.scout_buttons}",
            log_path,
        )
        out_db = refresh_site(update_dir, wsm_dir, desktop_wsm_dir, filled_csv)
        if args.commit_push:
            git_commit_push(found_versions)

        notify(
            pushover_config,
            pushover_user_key_config,
            "WebSoccer Update Complete",
            f"{version_label} のDB/サイト更新が完了しました。WSM: {out_db.name}",
            notify_enabled,
            log_path,
        )
        log(f"update complete: versions={found_versions} db={out_db}", log_path)
        return 0
    except Exception as exc:
        log(f"update failed: {type(exc).__name__}: {exc}", log_path)
        log(traceback.format_exc(), log_path)
        if found_versions:
            notify(
                pushover_config,
                pushover_user_key_config,
                "WebSoccer Update Failed",
                f"UpdateFile {found_versions} の更新処理に失敗しました: {type(exc).__name__}: {exc}",
                notify_enabled,
                log_path,
            )
        return 1
    finally:
        release_lock(fd, lock_path)


if __name__ == "__main__":
    raise SystemExit(main())
