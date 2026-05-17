#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "v4_clean_uniform_data.json"
DEST = ROOT / "app" / "cc_range_data.json"

def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    meta = payload.get("meta") or {}
    out = {
        "rows": meta.get("championTpiGridStats") or [],
        "skippedFinals": meta.get("championTpiSkippedFinals") or 0,
        "step": meta.get("championTpiGridStep") or 5,
        "metric": "tpi",
        "source": "v4_clean_uniform_data.json",
    }
    DEST.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {DEST}")

if __name__ == "__main__":
    main()
