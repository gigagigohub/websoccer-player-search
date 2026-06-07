#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path


LABEL = "com.gigagigo.websoccer.trade-chain-maintenance-sweep"
REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = Path.home() / "Library" / "Application Support" / "websoccer-player-search"
RUNTIME_WRAPPER = RUNTIME_DIR / "run_trade_chain_maintenance_sweep.sh"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, text=True, check=check, capture_output=False)


def main() -> int:
    gui_target = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", gui_target, str(PLIST_PATH)], check=False)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        print(f"[DONE] removed retired launch agent plist: {PLIST_PATH}")
    else:
        print(f"[INFO] retired launch agent plist already absent: {PLIST_PATH}")
    if RUNTIME_WRAPPER.exists():
        RUNTIME_WRAPPER.unlink()
        print(f"[DONE] removed retired runtime wrapper: {RUNTIME_WRAPPER}")
    print("[DONE] Sunday trade-chain maintenance sweep is retired.")
    print("[DONE] Daily login-bonus/profile sync now handles trade completion reporting every morning, including Sunday.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
