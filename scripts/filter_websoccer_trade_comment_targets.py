#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from search_websoccer_trade_listings import (
    DEFAULT_SEARCH_PROFILE,
    current_season,
    load_player_names,
    md_escape,
    post_search,
    rows_from_payload,
)
from fetch_cc_all_worlds_completed import local_auth_from_container


APP_DATA = Path(__file__).resolve().parents[1] / "app" / "data.json"
CATEGORIES = {"NR", "SS", "CM", "CC"}
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
COMMENT_SEPARATORS = re.compile(r"[\s,，、/／・;；]+")
OPEN_REQUEST_COMMENTS = {"", "いいやつ", "使いません"}
SAME_PLAYER_FIRST_TERM_PATTERNS = ("若返り",)
NAMED_FIRST_TERM_PATTERNS = ("低期",)
EXCLUDE_CANDIDATE_PATTERNS = ("覚醒",)
PLAYER_NAME_ALIASES: dict[str, str] = {}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Search trade listings for a specified player/term and list listings whose comments "
            "name a first-term non-SS desired player."
        )
    )
    p.add_argument("player", help="Listed player name, e.g. ビーティー or ビーティーNR.")
    p.add_argument("term", nargs="?", type=int, help="Listed player term to match, e.g. 3. Omit to search all terms.")
    p.add_argument(
        "--category",
        default="",
        help="Listed player category to search. If omitted, suffixes like ビーティーNR are recognized; otherwise default is NR.",
    )
    p.add_argument(
        "--profile-data",
        default=str(DEFAULT_SEARCH_PROFILE),
        help=f"Profile Data directory used only for auth (default: OpenAI profile {DEFAULT_SEARCH_PROFILE})",
    )
    p.add_argument("--app-data", default=str(APP_DATA))
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument("--json", action="store_true", help="Print raw normalized JSON instead of Markdown.")
    return p.parse_args()


def load_site_players(app_data: Path) -> list[dict[str, Any]]:
    data = json.loads(app_data.read_text(encoding="utf-8"))
    return [p for p in data.get("players") or [] if isinstance(p, dict) and (p.get("id") or p.get("playerId"))]


def split_player_and_category(text: str, category: str) -> tuple[str, str]:
    player = text.strip()
    cat = category.strip().upper()
    if cat:
        return player, cat
    upper = player.upper()
    for suffix in sorted(CATEGORIES, key=len, reverse=True):
        if upper.endswith(suffix):
            return player[: -len(suffix)].strip(), suffix
    return player, "NR"


def name_variants(name: str) -> set[str]:
    variants = {name}
    if name.endswith("ー"):
        variants.add(name.rstrip("ー"))
    else:
        variants.add(name + "ー")
    return {v for v in variants if v}


def resolve_listed_player(players: list[dict[str, Any]], player_name: str, category: str) -> tuple[list[int], str]:
    targets = name_variants(player_name)
    ids: list[int] = []
    canonical_name = player_name
    for player in players:
        if player.get("name") not in targets and player.get("fullName") not in targets:
            continue
        if category and str(player.get("category") or "").upper() != category:
            continue
        if str(category or "").upper() == "NR" and player.get("retired"):
            continue
        player_id = player.get("id") or player.get("playerId")
        if player_id is not None:
            ids.append(int(player_id))
            canonical_name = str(player.get("name") or player_name)
    return sorted(set(ids)), canonical_name


def unique_player_names(players: list[dict[str, Any]]) -> list[str]:
    names: set[str] = set()
    surname_to_names: dict[str, set[str]] = {}
    for player in players:
        for key in ("name", "fullName"):
            value = str(player.get(key) or "").strip()
            if len(value) >= 2:
                names.add(value)
                parts = [part for part in re.split(r"[\s　]+", value) if part]
                if len(parts) >= 2 and len(parts[0]) >= 2:
                    surname_to_names.setdefault(parts[0], set()).add(value)
    PLAYER_NAME_ALIASES.clear()
    for surname, canonical_names in surname_to_names.items():
        if len(canonical_names) == 1 and surname not in names:
            canonical = next(iter(canonical_names))
            PLAYER_NAME_ALIASES[surname] = canonical
            names.add(surname)
    return sorted(names, key=len, reverse=True)


def nr_player_names(players: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for player in players:
        if str(player.get("category") or "").upper() != "NR":
            continue
        if player.get("retired"):
            continue
        for key in ("name", "fullName"):
            value = str(player.get(key) or "").strip()
            if len(value) >= 2:
                names.add(value)
    return names


def has_ss_designation(text: str) -> bool:
    normalized = text.upper().replace("Ｓ", "S")
    return "SS" in normalized


def numbers_in_text(text: str) -> list[int]:
    normalized = text.translate(FULLWIDTH_DIGITS)
    return [int(m.group(0)) for m in re.finditer(r"\d+", normalized)]


def wanted_terms_from_numbers(numbers: list[int]) -> list[int]:
    return sorted({n for n in numbers if 1 <= n <= 15})


def first_player_name_in_text(text: str, player_names: list[str]) -> str:
    matches: list[tuple[int, int, str]] = []
    for name in player_names:
        start = text.find(name)
        if start >= 0:
            matches.append((start, -len(name), name))
    if not matches:
        return ""
    matches.sort()
    return matches[0][2]


def has_nr_category(name: str, nr_names: set[str]) -> bool:
    return PLAYER_NAME_ALIASES.get(name, name) in nr_names


def comment_candidates(comment: str, player_names: list[str] | None = None) -> list[str]:
    protected: dict[str, str] = {}
    text = comment
    for idx, name in enumerate(sorted((player_names or []), key=len, reverse=True)):
        if "・" not in name or name not in text:
            continue
        token = f"\u0000P{idx}\u0000"
        text = text.replace(name, token)
        protected[token] = name
    candidates = [part.strip() for part in COMMENT_SEPARATORS.split(text) if part.strip()]
    for token, name in protected.items():
        candidates = [candidate.replace(token, name) for candidate in candidates]
    return candidates or [comment]


def term_only_candidate(candidate: str) -> bool:
    text = candidate.translate(FULLWIDTH_DIGITS)
    return bool(re.fullmatch(r"\d+\s*(?:期|期目)?", text))


def analyze_candidate(candidate: str, player_names: list[str], nr_names: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "candidate": candidate,
        "wantedPlayerName": "",
        "include": False,
        "excludeReason": "",
        "numbers": [],
        "wantedTerms": [],
    }
    if any(pattern in candidate for pattern in EXCLUDE_CANDIDATE_PATTERNS):
        result["excludeReason"] = "excluded_comment_pattern"
        result["excludePattern"] = next(pattern for pattern in EXCLUDE_CANDIDATE_PATTERNS if pattern in candidate)
        return result
    if has_ss_designation(candidate):
        result["excludeReason"] = "ss_designation"
        return result
    if any(pattern in candidate for pattern in SAME_PLAYER_FIRST_TERM_PATTERNS):
        result["include"] = True
        result["matchedCandidate"] = next(pattern for pattern in SAME_PLAYER_FIRST_TERM_PATTERNS if pattern in candidate)
        result["matchType"] = "same_player_first_term_comment"
        return result
    if any(pattern in candidate for pattern in NAMED_FIRST_TERM_PATTERNS):
        wanted = first_player_name_in_text(candidate, player_names)
        if not wanted:
            result["excludeReason"] = "no_player_name"
            return result
        if not has_nr_category(wanted, nr_names):
            result["excludeReason"] = "wanted_player_without_nr"
            result["wantedPlayerName"] = wanted
            return result
        result["wantedPlayerName"] = PLAYER_NAME_ALIASES.get(wanted, wanted)
        result["include"] = True
        result["matchedCandidate"] = next(pattern for pattern in NAMED_FIRST_TERM_PATTERNS if pattern in candidate)
        result["matchType"] = "named_first_term_comment"
        return result
    nums = numbers_in_text(candidate)
    result["numbers"] = nums
    result["wantedTerms"] = wanted_terms_from_numbers(nums)
    wanted = first_player_name_in_text(candidate, player_names)
    if not wanted:
        result["excludeReason"] = "no_player_name"
        return result
    if not has_nr_category(wanted, nr_names):
        result["excludeReason"] = "wanted_player_without_nr"
        result["wantedPlayerName"] = PLAYER_NAME_ALIASES.get(wanted, wanted)
        return result
    result["wantedPlayerName"] = PLAYER_NAME_ALIASES.get(wanted, wanted)
    result["include"] = True
    return result


def analyze_comment(comment_value: Any, player_names: list[str], nr_names: set[str]) -> dict[str, Any]:
    comment = str(comment_value or "").strip()
    result: dict[str, Any] = {
        "comment": comment,
        "wantedPlayerName": "",
        "include": False,
        "excludeReason": "",
        "numbers": [],
        "wantedTerms": [],
        "candidates": [],
    }
    if comment in OPEN_REQUEST_COMMENTS:
        result["include"] = True
        result["matchedCandidate"] = comment
        result["matchType"] = "open_request_comment"
        return result
    raw_candidates = comment_candidates(comment, player_names)
    candidates: list[str] = []
    idx = 0
    while idx < len(raw_candidates):
        candidate = raw_candidates[idx]
        if first_player_name_in_text(candidate, player_names):
            parts = [candidate]
            next_idx = idx + 1
            while next_idx < len(raw_candidates) and term_only_candidate(raw_candidates[next_idx]):
                parts.append(raw_candidates[next_idx])
                next_idx += 1
            if len(parts) > 1:
                candidates.append(" ".join(parts))
                idx = next_idx
                continue
        candidates.append(candidate)
        idx += 1
    candidate_results = [analyze_candidate(candidate, player_names, nr_names) for candidate in candidates]
    result["candidates"] = candidate_results
    result["numbers"] = [n for candidate in candidate_results for n in candidate.get("numbers", [])]
    result["wantedTerms"] = [n for candidate in candidate_results for n in candidate.get("wantedTerms", [])]
    for candidate in candidate_results:
        if candidate.get("include"):
            result["wantedPlayerName"] = candidate.get("wantedPlayerName", "")
            result["wantedTerms"] = candidate.get("wantedTerms", [])
            result["include"] = True
            result["matchedCandidate"] = candidate.get("candidate", "")
            result["matchType"] = candidate.get("matchType") or "player_name_candidate"
            return result
    result["excludeReason"] = "no_valid_candidate"
    return result


def search_records(player_ids: list[int], profile: Path, timeout_sec: float) -> tuple[int, list[dict[str, Any]]]:
    auth = local_auth_from_container(profile)
    if not auth:
        raise RuntimeError(f"could not generate auth from profile: {profile}")
    names = load_player_names(profile)
    season = current_season(profile)
    records: list[dict[str, Any]] = []
    for player_id in player_ids:
        ok, payload = post_search(player_id, auth, timeout_sec)
        if not ok or not isinstance(payload, dict):
            raise RuntimeError(f"trade search failed for player_id={player_id}: {payload}")
        if payload.get("code") != "000":
            raise RuntimeError(f"trade search code={payload.get('code')} message={payload.get('message')}")
        records.extend(rows_from_payload(player_id, payload, names, season))
    return season, records


def display_wanted(rec: dict[str, Any]) -> str:
    analysis = rec.get("commentAnalysis") or {}
    wanted = str(analysis.get("wantedPlayerName") or "").strip()
    if wanted:
        return wanted
    if analysis.get("matchType") == "open_request_comment":
        return "指定なし"
    if analysis.get("matchType") == "same_player_first_term_comment":
        return str(rec.get("playerName") or "出品選手")
    return ""


def md_table(records: list[dict[str, Any]]) -> None:
    if not records:
        print("(no matching listings)")
        return
    print("| Trade ID | 出品選手 | 期 | コメント | 希望選手 | 登録時刻 |")
    print("|---:|---|---:|---|---|---|")
    for rec in records:
        print(
            "| "
            + " | ".join(
                [
                    md_escape(rec.get("tradeId")),
                    md_escape(rec.get("playerName")),
                    f"{rec.get('term') or ''}期目",
                    md_escape(rec.get("comment")),
                    md_escape(display_wanted(rec)),
                    md_escape(rec.get("createdAt")),
                ]
            )
            + " |"
        )


def main() -> int:
    args = parse_args()
    players = load_site_players(Path(args.app_data).expanduser().resolve())
    player_name, category = split_player_and_category(args.player, args.category)
    player_ids, canonical_player_name = resolve_listed_player(players, player_name, category)
    if not player_ids:
        raise SystemExit(f"[ERROR] player not found: name={player_name} category={category}")

    season, records = search_records(player_ids, Path(args.profile_data).expanduser().resolve(), args.timeout_sec)
    if args.term is not None:
        records = [rec for rec in records if rec.get("term") == args.term]
    player_names = unique_player_names(players)
    nr_names = nr_player_names(players)
    for rec in records:
        rec["commentAnalysis"] = analyze_comment(rec.get("comment"), player_names, nr_names)
    matches = [rec for rec in records if (rec.get("commentAnalysis") or {}).get("include")]

    output = {
        "query": {
            "playerName": player_name,
            "canonicalPlayerName": canonical_player_name,
            "category": category,
            "playerIds": player_ids,
            "term": args.term,
            "currentSeason": season,
        },
        "recordsSearched": len(records),
        "recordsMatched": len(matches),
        "matches": matches,
        "excluded": [rec for rec in records if not (rec.get("commentAnalysis") or {}).get("include")],
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(
            f"[FILTER] {player_name}{category} "
            f"{str(args.term) + '期目' if args.term is not None else '全期'} "
            f"resolved={canonical_player_name} "
            f"player_ids={','.join(str(i) for i in player_ids)} searched={len(records)} matched={len(matches)}"
        )
        md_table(matches)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
