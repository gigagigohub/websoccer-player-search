#!/usr/bin/env python3
from __future__ import annotations

import argparse
import string
import json
import random
import secrets


ALPHABET = string.ascii_letters
MIN_NAME_LEN = 5
MAX_NAME_LEN = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate the default identity for a new WebSoccer team.")
    p.add_argument("--count", type=int, default=1, help="Number of identities to generate.")
    p.add_argument("--min-len", type=int, default=MIN_NAME_LEN, help="Minimum generated name length.")
    p.add_argument("--max-len", type=int, default=MAX_NAME_LEN, help="Maximum generated name length.")
    p.add_argument("--seed", type=int, default=None, help="Optional deterministic seed for testing.")
    p.add_argument("--json", action="store_true", help="Print JSON instead of plain text.")
    return p.parse_args()


def random_ascii_name(rng: random.Random | secrets.SystemRandom, min_len: int, max_len: int) -> str:
    length = rng.randint(min_len, max_len)
    return "".join(rng.choice(ALPHABET) for _ in range(length))


def random_identity(rng: random.Random | secrets.SystemRandom, min_len: int, max_len: int) -> dict[str, str]:
    team_name = random_ascii_name(rng, min_len, max_len)
    owner_name = random_ascii_name(rng, min_len, max_len)
    while owner_name == team_name:
        owner_name = random_ascii_name(rng, min_len, max_len)
    return {"team_name": team_name, "owner_name": owner_name}


def main() -> int:
    args = parse_args()
    if args.count < 1:
        raise ValueError("--count must be >= 1")
    if args.min_len < 1 or args.max_len < args.min_len:
        raise ValueError("--min-len must be >= 1 and --max-len must be >= --min-len")
    rng: random.Random | secrets.SystemRandom = random.Random(args.seed) if args.seed is not None else secrets.SystemRandom()
    rows = [random_identity(rng, args.min_len, args.max_len) for _ in range(args.count)]
    if args.json:
        print(json.dumps(rows[0] if args.count == 1 else rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"team_name={row['team_name']}\towner_name={row['owner_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
