#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_ENV_FILE = Path.home() / ".websoccer_pushover.env"
PUSHOVER_ENDPOINT = "https://api.pushover.net/1/messages.json"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send a Pushover notification without printing secrets.")
    p.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help=f"Secret env file (default: {DEFAULT_ENV_FILE})")
    p.add_argument("--title", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--priority", default="0")
    p.add_argument("--sound", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(Path(args.env_file).expanduser())

    token = os.environ.get("PUSHOVER_APP_TOKEN", "")
    user = os.environ.get("PUSHOVER_USER_KEY", "")
    if not token or not user:
        print(
            "[WARN] Pushover notification skipped: PUSHOVER_APP_TOKEN/PUSHOVER_USER_KEY not configured.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    payload = {
        "token": token,
        "user": user,
        "title": args.title,
        "message": args.message,
        "priority": args.priority,
    }
    if args.sound:
        payload["sound"] = args.sound

    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(PUSHOVER_ENDPOINT, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                print(f"[WARN] Pushover notification returned HTTP {response.status}.", file=sys.stderr, flush=True)
                return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] Pushover notification failed: {exc}", file=sys.stderr, flush=True)
        return 1

    print("[INFO] Pushover notification sent.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
