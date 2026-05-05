#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Write small site-wide metadata JSON for the static app.")
    p.add_argument("--app-dir", default=str(Path.cwd() / "app"))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    app_dir = Path(args.app_dir).expanduser().resolve()
    data_path = app_dir / "data.json"
    formations_path = app_dir / "formations_data.json"
    out_path = app_dir / "site_meta.json"

    data = json.loads(data_path.read_text(encoding="utf-8")) if data_path.exists() else {}
    formations = json.loads(formations_path.read_text(encoding="utf-8")) if formations_path.exists() else {}
    generated_from = formations.get("meta", {}).get("generatedFrom", {})
    cc_data = formations.get("meta", {}).get("ccData") or {
        "seasonStart": generated_from.get("ccSeasonStart"),
        "seasonEnd": generated_from.get("ccSeasonEnd"),
        "games": generated_from.get("ccGames"),
    }
    meta = {
        "generatedAt": data.get("generatedAt") or formations.get("meta", {}).get("generatedAt"),
        "source": data.get("source") or "site",
        "ccData": {
            "seasonStart": cc_data.get("seasonStart"),
            "seasonEnd": cc_data.get("seasonEnd"),
            "games": cc_data.get("games"),
        },
    }
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
