#!/usr/bin/env python3
from __future__ import annotations

import plistlib
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT.parent / "wsc_data"
HANDOFF_PATH = REPO_ROOT / "docs" / "daily_handoff.md"
HANDOFF_NOTES_PATH = REPO_ROOT / "docs" / "daily_handoff_notes.md"
LOG_DIR = Path.home() / "Library" / "Logs" / "websoccer-player-search"
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
AUTOMATIONS = Path.home() / ".codex" / "automations"


def run(cmd: list[str], cwd: Path = REPO_ROOT) -> str:
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).stdout.rstrip()
    except OSError as exc:
        return f"[error] {exc}"


def automation_status(automation_id: str) -> str:
    path = AUTOMATIONS / automation_id / "automation.toml"
    if not path.exists():
        return "missing"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("status = "):
            return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def plist_value(plist_name: str, key: str) -> str:
    path = LAUNCH_AGENTS / plist_name
    if not path.exists():
        return "missing"
    try:
        data = plistlib.loads(path.read_bytes())
    except Exception as exc:
        return f"invalid plist: {exc}"
    value = data.get(key, "missing")
    return str(value)


def latest_matching(root: Path, pattern: str) -> str:
    matches = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return str(matches[-1]) if matches else "none found"


def last_log_lines(path: Path, markers: tuple[str, ...], limit: int = 8) -> list[str]:
    if not path.exists():
        return ["log not found"]
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = [line for line in lines if any(marker in line for marker in markers)]
    return selected[-limit:] if selected else ["no matching recent log lines"]


def fenced_or_none(text: str) -> str:
    return text if text else "(clean)"


def handoff_notes() -> str:
    if not HANDOFF_NOTES_PATH.exists():
        return "- No persistent chat notes yet."
    text = HANDOFF_NOTES_PATH.read_text(encoding="utf-8").strip()
    return text if text else "- No persistent chat notes yet."


def main() -> int:
    now = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M JST")
    git_status = run(["git", "status", "--short"])
    stash_list = run(["git", "stash", "list"])

    cc_plist = "com.gigagigo.websoccer.cc-current-season-update.plist"
    update_plist = "com.gigagigo.websoccer.updatefile-core-watch.plist"
    handoff_plist = "com.gigagigo.websoccer.daily-handoff-refresh.plist"
    login_bonus_plist = "com.gigagigo.websoccer.daily-login-bonus-sync.plist"

    update_log = last_log_lines(
        LOG_DIR / "updatefile-core-watch.out.log",
        (
            "updatefile/core-data watch start",
            "p326:",
            "no new UpdateFile",
            "validating latest local core-data id",
            "[FOUND]",
            "no new core-data rows found",
            "updatefile/core-data watch done",
        ),
    )
    cc_log = last_log_lines(
        LOG_DIR / "weekly-cc-update.out.log",
        ("weekly current-season CC update", "[DONE]", "[ERROR]", "[WARN]"),
    )

    content = f"""# Daily Handoff

Last reviewed: {now}

## Start Here

Use `docs/new_chat_prompt.md` when opening a fresh Codex chat.

Always start in:

```bash
cd {REPO_ROOT}
git status --short
```

## Current Operating Notes

- Do not print Websoccer-gate-key, Cookie, User-Agent, Pushover token, or Pushover user key values.
- Avoid `git add .`; stage only intentional files.
- Existing local scratch should go under `app/prepared/local/`, `local/`, `tmp/`, or `artifacts/`.
- Follow `docs/git_hygiene.md` when deciding whether to commit or keep local.
- Unattended LaunchAgent runs use `{REPO_ROOT}`.

## Dirty Tree Summary

```text
{fenced_or_none(git_status)}
```

## Active Schedulers

- Codex cron:
  - `websoccer-daily-handoff-refresh`: {automation_status("websoccer-daily-handoff-refresh")}
  - `websoccer-current-season-cc-weekly-update`: {automation_status("websoccer-current-season-cc-weekly-update")}
  - `websoccer-updatefile-and-core-data-watch`: {automation_status("websoccer-updatefile-and-core-data-watch")}
- LaunchAgent `com.gigagigo.websoccer.daily-handoff-refresh`
  - Schedule: daily 05:00 JST
  - Workdir: {plist_value(handoff_plist, "WorkingDirectory")}
  - Logs: `~/Library/Logs/websoccer-player-search/daily-handoff-refresh.out.log` and `.err.log`
  - Pushover: failure-only via `~/.handoff_pushover.env`
- LaunchAgent `com.gigagigo.websoccer.cc-current-season-update`
  - Schedule: Sunday 02:00 JST
  - Workdir: {plist_value(cc_plist, "WorkingDirectory")}
  - Logs: `~/Library/Logs/websoccer-player-search/weekly-cc-update.out.log` and `.err.log`
- LaunchAgent `com.gigagigo.websoccer.updatefile-core-watch`
  - Schedule: hourly at minute `00`, excluding 04:00, 05:00, and 06:00 JST
  - Workdir: {plist_value(update_plist, "WorkingDirectory")}
  - Logs: `~/Library/Logs/websoccer-player-search/updatefile-core-watch.out.log` and `.err.log`
- LaunchAgent `com.gigagigo.websoccer.daily-login-bonus-sync`
  - Schedule: daily 07:00 JST
  - Workdir: {plist_value(login_bonus_plist, "WorkingDirectory")}
  - Logs: `~/Library/Logs/websoccer-player-search/daily-login-bonus-sync.out.log` and `.err.log`
  - Scope: login bonus trigger/accept for collected profiles, then full profile sync

## Important Commands

```bash
python3 scripts/run_cc_update_pipeline.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-source local --skip-capture --season 0 --commit-push --notify-pushover
python3 scripts/run_cc_update_pipeline.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-source local --skip-capture --season 0 --worlds 10 --groups 0 --round-max 1 --dry-run-fetch --skip-wsm-update
python3 scripts/watch_updatefile_and_refresh_site.py --commit-push
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --auth-check
python3 scripts/fetch_update_core_data.py --websoccer-container /Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current --dry-run
python3 scripts/install_daily_handoff_refresh_launch_agent.py
python3 scripts/install_weekly_cc_update_launch_agent.py
python3 scripts/install_updatefile_and_core_data_launch_agent.py
python3 scripts/install_daily_login_bonus_and_profile_sync_launch_agent.py
```

## Recent Status

- CC:
  - Latest weekly log signals:
```text
{chr(10).join(cc_log)}
```
- UpdateFile:
  - Latest local UpdateFile directory: `{latest_matching(DATA_ROOT, "UpdateFile_p*_*")}`.
  - Latest watcher log signals:
```text
{chr(10).join(update_log)}
```
- Update_core_data:
  - Latest local snapshot: `{latest_matching(DATA_ROOT, "update_core_data_*")}`.
  - New ids should be treated as absent when the latest known id validates and the next ids return HTTP 500.

## Persistent Chat Notes

These notes are maintained in `docs/daily_handoff_notes.md` and are preserved across automatic refreshes.

{handoff_notes()}

## Unresolved Issues

- Confirm the next scheduled daily handoff LaunchAgent run succeeds at 05:00 JST.
- Confirm the next scheduled weekly CC LaunchAgent run succeeds on Sunday 02:00 JST.
- Verify the WSM/site integration path the first time new `update_core_data` rows appear beyond the latest local snapshot.

## Stash And Scratch

```text
{fenced_or_none(stash_list)}
```
"""

    HANDOFF_PATH.write_text(content, encoding="utf-8")
    print(f"[DONE] refreshed {HANDOFF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
