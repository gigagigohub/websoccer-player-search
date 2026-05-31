#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import ssl
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fetch_cc_all_worlds_completed import API_HOST, UA_FALLBACK, local_auth_from_container


DEFAULT_SEARCH_PROFILE = Path("/Users/gigagigo/Codex/WebSoccer/websoccer_local_backups/account_transfer/teams/10527301_openai/current")
SEARCH_PATH = "/trade/search/.json"
DETAIL_PATH_TEMPLATE = "/trade/detail/{team_id}/{trade_id}/.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Search existing WebSoccer trade listings by player_id.")
    p.add_argument("player_ids", nargs="+", type=int, help="Player id(s) to search.")
    p.add_argument(
        "--profile-data",
        default=str(DEFAULT_SEARCH_PROFILE),
        help=f"Profile Data directory used only for auth (default: OpenAI profile {DEFAULT_SEARCH_PROFILE})",
    )
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument(
        "--no-offers",
        action="store_true",
        help="Do not fetch trade detail rows for currently offered players.",
    )
    p.add_argument("--json", action="store_true", help="Print raw normalized JSON instead of Markdown.")
    p.add_argument("--tsv", action="store_true", help="Print tab-separated output instead of Markdown.")
    p.add_argument("--pretty", action="store_true", help="Print a compact grouped text view.")
    return p.parse_args()


def post_search(player_id: int, auth, timeout_sec: float) -> tuple[bool, dict[str, Any] | str]:
    body = urllib.parse.urlencode({"json": json.dumps([player_id, 0], separators=(",", ":"))}).encode("utf-8")
    req = urllib.request.Request(
        f"https://{API_HOST}{SEARCH_PATH}",
        data=body,
        headers={
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Websoccer-gate-key": auth.current_gate_key(),
            "User-Agent": auth.user_agent or UA_FALLBACK,
            "Accept-Language": "ja",
            "Connection": "keep-alive",
        },
        method="POST",
    )
    if auth.cookie:
        req.add_header("Cookie", auth.cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl._create_unverified_context()) as res:
            raw = res.read().decode("utf-8", errors="replace")
        return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def get_detail(team_id: int, trade_id: int, auth, timeout_sec: float) -> tuple[bool, dict[str, Any] | str]:
    path = DETAIL_PATH_TEMPLATE.format(team_id=team_id, trade_id=trade_id)
    req = urllib.request.Request(
        f"https://{API_HOST}{path}",
        headers={
            "Accept": "*/*",
            "Websoccer-gate-key": auth.current_gate_key(),
            "User-Agent": auth.user_agent or UA_FALLBACK,
            "Accept-Language": "ja",
            "Connection": "keep-alive",
        },
        method="GET",
    )
    if auth.cookie:
        req.add_header("Cookie", auth.cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec, context=ssl._create_unverified_context()) as res:
            raw = res.read().decode("utf-8", errors="replace")
        return True, json.loads(raw)
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'ignore')[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def load_player_names(profile: Path) -> dict[int, str]:
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {int(row[0]): str(row[1] or "") for row in con.execute("select ZPLAYER_ID, ZNAME from ZMOPLAYER")}
    finally:
        con.close()


def current_season(profile: Path) -> int:
    db = profile / "Documents" / "Model" / "Model.sqlite"
    if not db.exists():
        return 0
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute("select ZSZN from ZMOTEAMDATA limit 1").fetchone()
        return int(row[0]) if row and row[0] else 0
    finally:
        con.close()


def normalize_row(target_player_id: int, row: list[Any], names: dict[int, str], season: int) -> dict[str, Any]:
    vals = list(row) + [None] * max(0, 10 - len(row))
    listed_player_id = int(vals[3]) if vals[3] is not None else None
    acquired_season = int(vals[4]) if vals[4] is not None else None
    term = season - acquired_season + 1 if season and acquired_season else None
    return {
        "searchedPlayerId": target_player_id,
        "listingTeamId": vals[0],
        "tradeId": vals[1],
        "status": vals[2],
        "playerId": listed_player_id,
        "playerName": names.get(listed_player_id or 0, ""),
        "acquiredSeason": acquired_season,
        "term": term,
        "owner": vals[5],
        "comment": vals[6],
        "condition": vals[7],
        "createdAt": vals[8],
        "updatedAt": vals[9],
        "raw": row,
    }


def normalize_offer_row(row: list[Any], names: dict[int, str], season: int) -> dict[str, Any]:
    vals = list(row) + [None] * max(0, 13 - len(row))
    offered_player_id = int(vals[4]) if vals[4] is not None else None
    acquired_season = int(vals[5]) if vals[5] is not None else None
    term = season - acquired_season + 1 if season and acquired_season else None
    return {
        "requestTeamId": vals[0],
        "requestTradeId": vals[1],
        "listingTeamId": vals[2],
        "listingTradeId": vals[3],
        "offeredPlayerId": offered_player_id,
        "offeredPlayerName": names.get(offered_player_id or 0, ""),
        "offeredAcquiredSeason": acquired_season,
        "offeredTerm": term,
        "owner": vals[6],
        "listedPlayerId": vals[7],
        "listedAcquiredSeason": vals[8],
        "status": vals[9],
        "flag": vals[10],
        "createdAt": vals[11],
        "updatedAt": vals[12],
        "raw": row,
    }


def rows_from_payload(player_id: int, payload: dict[str, Any], names: dict[int, str], season: int) -> list[dict[str, Any]]:
    raw_list = payload.get("list")
    if not isinstance(raw_list, list):
        return []
    rows = raw_list[0] if raw_list and isinstance(raw_list[0], list) else raw_list
    if not isinstance(rows, list):
        return []
    return [normalize_row(player_id, row, names, season) for row in rows if isinstance(row, list) and row]


def offers_from_detail_payload(payload: dict[str, Any], names: dict[int, str], season: int) -> list[dict[str, Any]]:
    raw_list = payload.get("list")
    if not isinstance(raw_list, list) or len(raw_list) < 2 or not isinstance(raw_list[1], list):
        return []
    return [normalize_offer_row(row, names, season) for row in raw_list[1] if isinstance(row, list) and row]


def enrich_with_offers(records: list[dict[str, Any]], auth, names: dict[int, str], season: int, timeout_sec: float) -> None:
    for rec in records:
        team_id = rec.get("listingTeamId")
        trade_id = rec.get("tradeId")
        if team_id is None or trade_id is None:
            rec["offers"] = []
            continue
        ok, payload = get_detail(int(team_id), int(trade_id), auth, timeout_sec)
        if ok and isinstance(payload, dict):
            rec["detailCode"] = payload.get("code")
            rec["detailMessage"] = payload.get("message")
            rec["offers"] = offers_from_detail_payload(payload, names, season) if payload.get("code") == "000" else []
        else:
            rec["detailError"] = payload
            rec["offers"] = []


def format_offers(rec: dict[str, Any]) -> str:
    offers = rec.get("offers") or []
    if not offers:
        return ""
    parts = []
    for offer in offers:
        name = offer.get("offeredPlayerName") or f"ID{offer.get('offeredPlayerId')}"
        term = offer.get("offeredTerm")
        label = f"{name}"
        if term:
            label += f"{term}期"
        parts.append(label)
    return " / ".join(parts)


def print_tsv(records: list[dict[str, Any]]) -> None:
    if not records:
        print("(no listings)")
        return
    print("trade_id\tname\tterm\tcomment\toffers\tcreated")
    for rec in records:
        values = [
            rec.get("tradeId"),
            rec.get("playerName"),
            rec.get("term"),
            rec.get("comment"),
            format_offers(rec),
            rec.get("createdAt"),
        ]
        print("\t".join(str(v or "") for v in values))


def md_escape(value: Any) -> str:
    text = str(value or "").strip().replace("\n", " ")
    return text.replace("|", "｜")


def print_markdown(records: list[dict[str, Any]]) -> None:
    if not records:
        print("(no listings)")
        return
    print("| Trade ID | 選手名 | 期 | コメント | 提示中 | 登録時刻 |")
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
                    md_escape(format_offers(rec)),
                    md_escape(rec.get("createdAt")),
                ]
            )
            + " |"
        )


def created_time(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 16 and text[10] == " ":
        return text[11:16]
    return text


def print_pretty(records: list[dict[str, Any]]) -> None:
    if not records:
        print("(no listings)")
        return
    records = sorted(
        records,
        key=lambda rec: (
            rec.get("term") if rec.get("term") is not None else 99,
            str(rec.get("createdAt") or ""),
            int(rec.get("tradeId") or 0),
        ),
    )
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for rec in records:
        grouped.setdefault(rec.get("term"), []).append(rec)

    print(f"Listings: {len(records)}")
    for term, term_records in grouped.items():
        term_label = f"{term}期目" if term else "期不明"
        print()
        print(f"{term_label} ({len(term_records)}件)")
        print("-" * 72)
        for rec in term_records:
            trade_id = rec.get("tradeId") or ""
            time = created_time(rec.get("createdAt"))
            comment = str(rec.get("comment") or "").strip() or "-"
            offers = format_offers(rec) or "-"
            print(f"{trade_id}  {time}  comment: {comment}")
            wrapped = textwrap.wrap(
                offers,
                width=64,
                initial_indent=" " * 18 + "offers : ",
                subsequent_indent=" " * 27,
                break_long_words=False,
                replace_whitespace=False,
            )
            print("\n".join(wrapped) if wrapped else f"{' ' * 18}offers : -")


def main() -> int:
    args = parse_args()
    profile = Path(args.profile_data).expanduser().resolve()
    auth = local_auth_from_container(profile)
    if not auth:
        raise RuntimeError(f"could not generate auth from profile: {profile}")
    names = load_player_names(profile)
    season = current_season(profile)
    results: dict[str, Any] = {
        "authProfile": str(profile),
        "authTeamId": auth.local_team_id,
        "currentSeason": season,
        "queries": [],
    }
    all_records: list[dict[str, Any]] = []
    for player_id in args.player_ids:
        ok, payload = post_search(player_id, auth, args.timeout_sec)
        query: dict[str, Any] = {"playerId": player_id, "ok": ok}
        if isinstance(payload, dict):
            query["code"] = payload.get("code")
            query["message"] = payload.get("message")
            query["records"] = rows_from_payload(player_id, payload, names, season)
            if not args.no_offers:
                enrich_with_offers(query["records"], auth, names, season, args.timeout_sec)
            all_records.extend(query["records"])
        else:
            query["error"] = payload
            query["records"] = []
        results["queries"].append(query)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for query in results["queries"]:
            print(f"[SEARCH] player_id={query['playerId']} code={query.get('code')} records={len(query['records'])}")
            if args.tsv:
                print_tsv(query["records"])
            elif args.pretty:
                print_pretty(query["records"])
            else:
                print_markdown(query["records"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
