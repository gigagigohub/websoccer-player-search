#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "v4_clean_uniform_data.json"
DEST = ROOT / "app" / "cc_range_data.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build CC champion TPI range data from v4 TPI coefficients.")
    p.add_argument("--source", default=str(SOURCE), help="Source v4_clean_uniform_data.json path.")
    p.add_argument("--dest", default=str(DEST), help="Destination cc_range_data.json path.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    meta = payload.get("meta") or {}
    out = {
        "rows": meta.get("championTpiGridStats") or [],
        "skippedFinals": meta.get("championTpiSkippedFinals") or 0,
        "step": meta.get("championTpiGridStep") or 5,
        "metric": "tpi",
        "source": source.name,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {dest}")

if __name__ == "__main__":
    main()
