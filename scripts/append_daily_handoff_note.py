#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTES_PATH = REPO_ROOT / "docs" / "daily_handoff_notes.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append a durable note to docs/daily_handoff_notes.md.")
    p.add_argument("--section", default="Chat Notes", help="Markdown section title to append under.")
    p.add_argument("--note", required=True, help="Note text. Do not include secrets.")
    p.add_argument("--date", default="", help="Override date label. Default: today in JST.")
    return p.parse_args()


def ensure_notes_file() -> None:
    if NOTES_PATH.exists():
        return
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTES_PATH.write_text(
        "# Daily Handoff Notes\n\n"
        "Use this file for durable context learned during chats. "
        "`scripts/refresh_daily_handoff.py` includes this content in `docs/daily_handoff.md` "
        "on every automatic refresh.\n",
        encoding="utf-8",
    )


def append_note(section: str, note: str, date_label: str) -> None:
    section = section.strip().lstrip("#").strip() or "Chat Notes"
    note = " ".join(note.strip().split())
    if not note:
        raise ValueError("empty note")
    ensure_notes_file()
    text = NOTES_PATH.read_text(encoding="utf-8")
    heading = f"## {section}"
    entry = f"- {date_label}: {note}"
    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n\n{entry}\n"
    else:
        lines = text.rstrip().splitlines()
        insert_at = len(lines)
        for idx, line in enumerate(lines):
            if idx == 0:
                continue
            if line == heading:
                insert_at = idx + 1
                while insert_at < len(lines) and lines[insert_at].strip() == "":
                    insert_at += 1
                break
        lines.insert(insert_at, entry)
        text = "\n".join(lines).rstrip() + "\n"
    NOTES_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    args = parse_args()
    date_label = args.date.strip() or datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")
    append_note(args.section, args.note, date_label)
    print(f"[DONE] appended note to {NOTES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
