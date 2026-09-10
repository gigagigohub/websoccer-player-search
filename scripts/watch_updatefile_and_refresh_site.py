#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import ssl
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
DEFAULT_PUSHOVER_ENV_FILE = Path.home() / ".websoccer_ordinary_pushover.env"
DEFAULT_WSM_DIR = WSC_DATA / "websoccer_master_db"
DEFAULT_FILLED_CSV = WSC_DATA / "UpdateFile_inventory" / "updatefile_ss_events_filled.csv"
DEFAULT_CC_JSON_ROOT = WSC_DATA / "CC_match_result_json"
DEFAULT_PRODUCT_SQLITE = WSC_DATA / "app original" / "Payload" / "Webサッカー.app" / "Product.sqlite"
JST = timezone(timedelta(hours=9))

sys.path.insert(0, str(SCRIPT_DIR))
from build_websoccer_master_db import default_cc_db as default_master_cc_db  # noqa: E402
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
    formations: int = 0


@dataclass
class UpdateFileInspection:
    versions: list[int]
    has_data_plist: bool = False
    has_ss_plist: bool = False
    challenge_plist_count: int = 0
    cm_asset_count: int = 0
    normal_player_image_ids: set[int] | None = None
    scout_button_count: int = 0
    challenge_names: list[str] | None = None
    unknown_player_image_ids: list[int] | None = None

    def __post_init__(self) -> None:
        if self.normal_player_image_ids is None:
            self.normal_player_image_ids = set()
        if self.challenge_names is None:
            self.challenge_names = []
        if self.unknown_player_image_ids is None:
            self.unknown_player_image_ids = []

    def labels(self) -> list[str]:
        labels: list[str] = []
        if self.challenge_plist_count or self.cm_asset_count:
            labels.append("CM更新")
        if self.has_ss_plist:
            labels.append("SSリスト更新")
        if self.has_data_plist:
            labels.append("data.plistあり")
        if self.normal_player_image_ids:
            if self.unknown_player_image_ids:
                labels.append(f"未登録選手画像ID {len(self.unknown_player_image_ids)}件")
            else:
                labels.append(f"既知選手画像 {len(self.normal_player_image_ids)}件")
        if self.scout_button_count:
            labels.append(f"Scoutボタン {self.scout_button_count}件")
        return labels or ["分類対象なし"]

    def one_line(self) -> str:
        names = ""
        if self.challenge_names:
            shown = self.challenge_names[:8]
            suffix = "..." if len(self.challenge_names) > len(shown) else ""
            names = f"; CM名={','.join(shown)}{suffix}"
        unknown = ""
        if self.unknown_player_image_ids:
            shown_ids = ",".join(str(v) for v in self.unknown_player_image_ids[:20])
            suffix = "..." if len(self.unknown_player_image_ids) > 20 else ""
            unknown = f"; 未登録画像ID={shown_ids}{suffix}"
        return (
            f"種別={','.join(self.labels())}; "
            f"通常選手画像={len(self.normal_player_image_ids or [])}; "
            f"CMアセット={self.cm_asset_count}; "
            f"ChallengeMatchList={self.challenge_plist_count}; "
            f"ss.plist={'yes' if self.has_ss_plist else 'no'}; "
            f"data.plist={'yes' if self.has_data_plist else 'no'}"
            f"{unknown}{names}"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Check for new UpdateFile archives and refresh WebSoccer DB/site when a new one appears."
    )
    p.add_argument("--update-dir", default=str(default_update_dir()))
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--watch-dir", default=str(DEFAULT_WATCH_DIR))
    p.add_argument("--pushover-config", default=str(DEFAULT_PUSHOVER_CONFIG))
    p.add_argument("--pushover-env-file", default=str(DEFAULT_PUSHOVER_ENV_FILE))
    p.add_argument(
        "--pushover-user-key-config",
        default=str(DEFAULT_PUSHOVER_USER_KEY_CONFIG),
        help="Optional fallback config used only for the Pushover user key.",
    )
    p.add_argument("--wsm-dir", default=str(DEFAULT_WSM_DIR))
    p.add_argument("--filled-csv", default=str(DEFAULT_FILLED_CSV))
    p.add_argument("--cc-db", default=str(default_master_cc_db()))
    p.add_argument("--cc-json-root", default=str(DEFAULT_CC_JSON_ROOT))
    p.add_argument("--product-sqlite", default=str(DEFAULT_PRODUCT_SQLITE))
    p.add_argument(
        "--master-builder-script",
        default="",
        help="build_websoccer_master_db.py to run. Default prefers the local-ops worktree copy when available.",
    )
    p.add_argument("--max-consecutive", type=int, default=5)
    p.add_argument("--commit-push", action="store_true", help="Commit and push regenerated site files after update.")
    p.add_argument("--no-notify", action="store_true", help="Do not send Pushover notifications.")
    p.add_argument("--dry-run", action="store_true", help="Check availability only. Do not download or update.")
    p.add_argument("--verify-tls", action="store_true", help="Enable TLS validation for the asset host.")
    p.add_argument(
        "--verify-pushover-tls",
        action="store_true",
        help="Enable TLS validation for Pushover. Disabled by default to avoid local Python CA issues.",
    )
    return p.parse_args()


def default_master_builder_script() -> Path:
    explicit = os.environ.get("WEBSOCCER_MASTER_BUILDER_SCRIPT")
    if explicit:
        return Path(explicit).expanduser()
    local_ops = CODING_ROOT / "websoccer-player-search" / "scripts" / "build_websoccer_master_db.py"
    current = SCRIPT_DIR / "build_websoccer_master_db.py"
    if local_ops.exists():
        try:
            if local_ops.resolve() != current.resolve():
                return local_ops
        except FileNotFoundError:
            return local_ops
    return current


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


def read_env_config(path: Path) -> dict:
    cfg = {}
    if not path.exists():
        return cfg
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cfg[key.strip()] = value.strip().strip('"').strip("'")
    return cfg


def load_pushover_config(
    app_config_path: Path,
    user_key_config_path: Path | None = None,
    env_file_path: Path | None = None,
) -> dict[str, str]:
    cfg = read_json_config(app_config_path) if app_config_path.exists() else {}
    token = str(cfg.get("pushover_app_token") or cfg.get("token") or "").strip()
    user = str(cfg.get("pushover_user_key") or cfg.get("user") or "").strip()
    if (not token or not user) and env_file_path:
        env_cfg = read_env_config(env_file_path)
        token = token or str(env_cfg.get("PUSHOVER_APP_TOKEN") or "").strip()
        user = user or str(env_cfg.get("PUSHOVER_USER_KEY") or "").strip()
    if not user and user_key_config_path and user_key_config_path.exists():
        user_cfg = read_json_config(user_key_config_path)
        user = str(user_cfg.get("pushover_user_key") or user_cfg.get("user") or "").strip()
    if not token or not user:
        raise ValueError(
            "Pushover token/user key missing. "
            f"app_config={app_config_path} user_key_config={user_key_config_path} env_file={env_file_path}"
        )
    return {"token": token, "user": user}


def notify(
    app_config_path: Path,
    user_key_config_path: Path | None,
    env_file_path: Path | None,
    title: str,
    message: str,
    enabled: bool,
    log_path: Path,
    verify_tls: bool,
) -> None:
    if not enabled:
        return
    try:
        cfg = load_pushover_config(app_config_path, user_key_config_path, env_file_path)
        payload = urllib.parse.urlencode(
            {
                "token": cfg["token"],
                "user": cfg["user"],
                "title": title,
                "message": message,
            }
        ).encode("utf-8")
        req = urllib.request.Request("https://api.pushover.net/1/messages.json", data=payload, method="POST")
        ctx = None if verify_tls else ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as res:
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
CHALLENGE_PLIST_NAMES = {
    "ChallengeMatchList.plist",
    "ChallengeMatchListTounament.plist",
    "ChallengeMatchListByWday.plist",
}


def load_site_player_ids(app_data: Path) -> set[int]:
    if not app_data.exists():
        return set()
    try:
        data = json.loads(app_data.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out: set[int] = set()
    for row in data.get("players") or []:
        try:
            player_id = int(row.get("id") or 0)
        except Exception:
            continue
        if player_id > 0:
            out.add(player_id)
    return out


def _plist_challenge_names(raw: bytes) -> list[str]:
    try:
        data = plistlib.loads(raw)
    except Exception:
        return []
    rows = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def inspect_updatefiles(zip_paths: list[Path], app_data: Path) -> UpdateFileInspection:
    versions: list[int] = []
    normal_player_image_ids: set[int] = set()
    challenge_names: list[str] = []
    result = UpdateFileInspection(versions=versions, normal_player_image_ids=normal_player_image_ids)

    for zip_path in zip_paths:
        match = re.search(r"p(\d+)\.zip$", zip_path.name)
        if match:
            versions.append(int(match.group(1)))
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                base = Path(name).name
                if re.search(r"/data/data\.plist$", name):
                    result.has_data_plist = True
                if base == "ss.plist":
                    result.has_ss_plist = True
                if base in CHALLENGE_PLIST_NAMES:
                    result.challenge_plist_count += 1
                    for challenge_name in _plist_challenge_names(zf.read(info.filename)):
                        if challenge_name not in challenge_names:
                            challenge_names.append(challenge_name)
                if "/Resources/img/SpecialMatch/CM/" in name:
                    result.cm_asset_count += 1
                player_match = PLAYER_RE.search(name)
                if player_match:
                    normal_player_image_ids.add(int(player_match.group(2)))
                scout_match = SCOUT_BUTTON_RE.search(name)
                if scout_match:
                    result.scout_button_count += 1

    known_ids = load_site_player_ids(app_data)
    result.challenge_names = challenge_names
    result.unknown_player_image_ids = sorted(normal_player_image_ids - known_ids)
    return result


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

                formation_match = re.search(r"/Resources/img/formation/(\d+@2x\.png)$", name)
                if formation_match:
                    dest = app_dir / "images" / "formation" / formation_match.group(1)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(info.filename))
                    copied.formations += 1
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


def build_master_db(
    update_dir: Path,
    wsm_dir: Path,
    cc_db: Path,
    cc_json_root: Path,
    product_sqlite: Path,
    master_builder_script: Path,
) -> Path:
    stamp = datetime.now(JST).strftime("%y%m%d%H%M")
    wsm_dir.mkdir(parents=True, exist_ok=True)
    out_db = wsm_dir / f"wsm_{stamp}.sqlite3"
    if out_db.exists():
        stamp = datetime.now(JST).strftime("%y%m%d%H%M%S")
        out_db = wsm_dir / f"wsm_{stamp}.sqlite3"
    if out_db.exists():
        raise FileExistsError(f"output WSM already exists: {out_db}")
    run(
        [
            sys.executable,
            str(master_builder_script),
            "--out-db",
            str(out_db),
            "--updatefile-dir",
            str(update_dir),
            "--cc-db",
            str(cc_db),
            "--product-sqlite",
            str(product_sqlite),
        ]
    )
    if cc_json_root.exists():
        run(
            [
                sys.executable,
                str(SCRIPT_DIR / "ingest_cc_pk_into_master_db.py"),
                "--json-root",
                str(cc_json_root),
                "--master-db",
                str(out_db),
            ]
        )
    return out_db


def cleanup_wsm_files(local_dir: Path) -> None:
    # WSM files are immutable backups. Keep every dated wsm_*.sqlite3 unless
    # the user explicitly requests manual cleanup outside this automation.
    return None


def refresh_site(
    update_dir: Path,
    wsm_dir: Path,
    filled_csv: Path,
    cc_db: Path,
    cc_json_root: Path,
    product_sqlite: Path,
    master_builder_script: Path,
) -> Path:
    app_dir = REPO_ROOT / "app"
    out_db = build_master_db(update_dir, wsm_dir, cc_db, cc_json_root, product_sqlite, master_builder_script)
    run(
        [
            sys.executable,
            str(SCRIPT_DIR / "update_site_from_master_db.py"),
            "--master-db",
            str(out_db),
        ]
    )
    run([sys.executable, str(SCRIPT_DIR / "write_site_meta.py"), "--app-dir", str(app_dir)])
    cleanup_wsm_files(wsm_dir)
    return out_db


def git_commit_push(versions: list[int]) -> None:
    from validate_site_master import validate
    from paths import latest_wsm_file
    validate(REPO_ROOT / "app", latest_wsm_file())
    paths = [
        "app/data.json",
        "app/coaches_data.json",
        "app/formations_data.json",
        "app/site_meta.json",
        "app/images/chara/players/static",
        "app/images/chara/players/action",
        "app/images/Shop/btn",
        "app/images/formation",
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
    pushover_env_file = Path(args.pushover_env_file).expanduser().resolve()
    wsm_dir = Path(args.wsm_dir).expanduser().resolve()
    filled_csv = Path(args.filled_csv).expanduser().resolve()
    cc_db = Path(args.cc_db).expanduser().resolve()
    cc_json_root = Path(args.cc_json_root).expanduser().resolve()
    product_sqlite = Path(args.product_sqlite).expanduser().resolve()
    master_builder_script = (
        Path(args.master_builder_script).expanduser().resolve()
        if args.master_builder_script
        else default_master_builder_script().resolve()
    )
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
        zip_paths = [update_dir / f"p{v}.zip" for v in found_versions]
        inspection = inspect_updatefiles(zip_paths, REPO_ROOT / "app" / "data.json")
        log(f"updatefile classification: {inspection.one_line()}", log_path)

        notify(
            pushover_config,
            pushover_user_key_config,
            pushover_env_file,
            "WebSoccer UpdateFile",
            f"{version_label} が見つかりました。\n内容: {inspection.one_line()}\nDBとサイト更新を開始します。",
            notify_enabled,
            log_path,
            args.verify_pushover_tls,
        )

        copied = copy_updatefile_images(zip_paths, REPO_ROOT / "app")
        log(
            "copied images: "
            f"static={copied.player_static} action={copied.player_action} scoutButtons={copied.scout_buttons}",
            log_path,
        )
        out_db = refresh_site(update_dir, wsm_dir, filled_csv, cc_db, cc_json_root, product_sqlite, master_builder_script)
        if args.commit_push:
            git_commit_push(found_versions)

        notify(
            pushover_config,
            pushover_user_key_config,
            pushover_env_file,
            "WebSoccer Update Complete",
            f"{version_label} のDB/サイト更新が完了しました。WSM: {out_db.name}",
            notify_enabled,
            log_path,
            args.verify_pushover_tls,
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
                pushover_env_file,
                "WebSoccer Update Failed",
                f"UpdateFile {found_versions} の更新処理に失敗しました: {type(exc).__name__}: {exc}",
                notify_enabled,
                log_path,
                args.verify_pushover_tls,
            )
        return 1
    finally:
        release_lock(fd, lock_path)


if __name__ == "__main__":
    raise SystemExit(main())
