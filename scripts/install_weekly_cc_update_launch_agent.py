#!/usr/bin/env python3
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path


LABEL = "com.gigagigo.websoccer.cc-current-season-update"
REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "scripts" / "run_weekly_cc_current_season_update.sh"
RUNTIME_DIR = Path.home() / "Library" / "Application Support" / "websoccer-player-search"
RUNTIME_WRAPPER = RUNTIME_DIR / "run_weekly_cc_current_season_update.sh"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs" / "websoccer-player-search"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, text=True, check=check, capture_output=False)


def main() -> int:
    if not WRAPPER.exists():
        print(f"[ERROR] wrapper not found: {WRAPPER}", file=sys.stderr)
        return 1

    WRAPPER.chmod(0o755)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    runtime_script = "\n".join(
        [
            "#!/bin/zsh",
            f'export WEBSOCCER_PLAYER_SEARCH_REPO="{REPO_ROOT}"',
            f'exec /bin/zsh "{WRAPPER}"',
            "",
        ]
    )
    RUNTIME_WRAPPER.write_text(runtime_script, encoding="utf-8")
    RUNTIME_WRAPPER.chmod(0o755)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            "/bin/zsh",
            str(RUNTIME_WRAPPER),
        ],
        "StartCalendarInterval": {
            "Weekday": 0,
            "Hour": 2,
            "Minute": 0,
        },
        "WorkingDirectory": str(REPO_ROOT),
        "StandardOutPath": str(LOG_DIR / "weekly-cc-update.out.log"),
        "StandardErrorPath": str(LOG_DIR / "weekly-cc-update.err.log"),
        "RunAtLoad": False,
        "ProcessType": "Interactive",
        "EnvironmentVariables": {
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
    }
    PLIST_PATH.write_bytes(plistlib.dumps(plist, sort_keys=True))

    gui_target = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", gui_target, str(PLIST_PATH)], check=False)
    run(["launchctl", "bootstrap", gui_target, str(PLIST_PATH)])
    run(["launchctl", "enable", f"{gui_target}/{LABEL}"], check=False)
    run(["launchctl", "print", f"{gui_target}/{LABEL}"], check=False)
    print(f"[DONE] installed launch agent: {PLIST_PATH}")
    print(f"[DONE] runtime wrapper: {RUNTIME_WRAPPER}")
    print("[DONE] schedule: every Sunday at 02:00, current season (--season 0)")
    print(f"[DONE] logs: {LOG_DIR / 'weekly-cc-update.out.log'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
