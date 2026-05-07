#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Rohm image link review choices to rohm_slot_data.json.")
    parser.add_argument("--app-dir", default="app")
    parser.add_argument("--review-html", default="app/rohm_duplicate_link_review.html")
    parser.add_argument("--choices", default="-", help="Choice text file, or '-' for stdin.")
    return parser.parse_args()


def load_review_items(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8")
    marker = '<script id="reviewData" type="application/json">'
    start = text.index(marker) + len(marker)
    end = text.index("</script>", start)
    payload = json.loads(text[start:end])
    return {str(item["imageKey"]): item for item in payload.get("items") or []}


def read_choice_text(path: str) -> str:
    if path == "-":
        import sys

        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def parse_choices(text: str) -> list[dict]:
    lines = []
    in_block = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "ROHM_IMAGE_LINK_CHOICES":
            in_block = True
            continue
        if line == "END":
            break
        if in_block:
            lines.append(raw)
    if not lines:
        raise ValueError("No ROHM_IMAGE_LINK_CHOICES block found.")
    return list(csv.DictReader(lines))


def validate_player_ids(app_dir: Path, choices: list[dict]) -> list[int]:
    data = json.loads((app_dir / "data.json").read_text(encoding="utf-8"))
    player_ids = {int(player["id"]) for player in data.get("players") or [] if player.get("id") is not None}
    missing = []
    for choice in choices:
        raw = (choice.get("choice_player_id") or "").strip()
        if raw and int(raw) not in player_ids:
            missing.append(int(raw))
    return sorted(set(missing))


def apply_choices(app_dir: Path, review_items: dict[str, dict], choices: list[dict]) -> dict:
    rohm_path = app_dir / "rohm_slot_data.json"
    rohm_data = json.loads(rohm_path.read_text(encoding="utf-8"))
    stats = Counter()
    missing_keys: list[str] = []
    missing_rows: list[str] = []

    for choice in choices:
        image_key = str(choice.get("image_key") or "").strip()
        if not image_key:
            continue
        item = review_items.get(image_key)
        if not item:
            missing_keys.append(image_key)
            continue
        raw_player_id = (choice.get("choice_player_id") or "").strip()
        next_player_id = int(raw_player_id) if raw_player_id else None
        for review_row in item.get("rows") or []:
            formation_id = str(int(review_row.get("formationId") or 0))
            slot = str(int(review_row.get("slot") or 0))
            rank = int(review_row.get("rank") or 0)
            rows = (
                (((rohm_data.get("formations") or {}).get(formation_id) or {}).get("slots") or {})
                .get(slot, {})
                .get("rows")
                or []
            )
            target = next((row for row in rows if int(row.get("rank") or 0) == rank), None)
            if target is None:
                missing_rows.append(f"{image_key}:{formation_id}:{slot}:rank{rank}")
                continue
            before = target.get("localPlayerId")
            if before == next_player_id:
                stats["unchanged"] += 1
            elif next_player_id is None:
                target["localPlayerId"] = None
                stats["unlinked"] += 1
            else:
                target["localPlayerId"] = next_player_id
                stats["linked"] += 1
            stats["rows_seen"] += 1

    rohm_path.write_text(json.dumps(rohm_data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {
        "choices": len(choices),
        "stats": dict(stats),
        "missing_keys": missing_keys,
        "missing_rows": missing_rows,
        "path": str(rohm_path),
    }


def main() -> int:
    args = parse_args()
    app_dir = Path(args.app_dir).expanduser().resolve()
    review_items = load_review_items(Path(args.review_html).expanduser().resolve())
    choices = parse_choices(read_choice_text(args.choices))
    missing_player_ids = validate_player_ids(app_dir, choices)
    if missing_player_ids:
        raise SystemExit(f"choice_player_id not found in data.json: {missing_player_ids}")
    result = apply_choices(app_dir, review_items, choices)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["missing_keys"] or result["missing_rows"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
