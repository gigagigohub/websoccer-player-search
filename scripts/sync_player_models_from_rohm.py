#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

JST = dt.timezone(dt.timedelta(hours=9))
BASE_URL = "https://sp.rohm.websoccer.info"
LIST_URL = f"{BASE_URL}/player/list/normal"


def now_jst_iso() -> str:
    return dt.datetime.now(JST).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync player model names from rohm normal player pages into master DB")
    p.add_argument(
        "--master-db",
        default=str(Path.home() / "Desktop" / "websoccer_master_db" / "wsm_2603292024.sqlite3"),
    )
    p.add_argument("--list-url", default=LIST_URL)
    p.add_argument("--timeout-sec", type=float, default=15.0)
    p.add_argument("--delay-sec", type=float, default=0.0)
    p.add_argument("--max-pages", type=int, default=0, help="0 means auto (follow pager max)")
    p.add_argument(
        "--unresolved-out",
        default=str(Path.cwd() / "app" / "prepared" / "player_model_unresolved_candidates.json"),
    )
    p.add_argument(
        "--reset-table",
        action="store_true",
        help="Delete existing manual_player_model rows before writing freshly resolved mappings.",
    )
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def normalize_name(text: str) -> str:
    s = str(text or "").strip().lower()
    s = s.replace("・", "").replace("･", "").replace("·", "")
    s = s.replace(" ", "")
    s = re.sub(r"[\u30a1-\u30f6]", lambda m: chr(ord(m.group(0)) - 0x60), s)
    return s


def parse_page_fields(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    fields: Dict[str, str] = {}
    for tr in soup.select("tr"):
        cells = tr.select("th,td")
        if len(cells) < 2:
            continue
        key = cells[0].get_text(" ", strip=True)
        val = cells[1].get_text(" ", strip=True)
        if key:
            fields[key] = val
    return fields


def fetch_html(session: requests.Session, url: str, timeout: float) -> str:
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text


def collect_player_links(session: requests.Session, list_url: str, timeout: float, max_pages: int) -> Dict[int, Dict[str, str]]:
    first_html = fetch_html(session, list_url, timeout)
    first_soup = BeautifulSoup(first_html, "html.parser")

    page_nums = set([0])
    for a in first_soup.select('a[href*="/player/list/normal/"]'):
        href = a.get("href") or ""
        m = re.search(r"/player/list/normal/(\d+)", href)
        if m:
            page_nums.add(int(m.group(1)))
    max_page = max(page_nums) if page_nums else 0
    if max_pages > 0:
        max_page = min(max_page, max_pages - 1)

    pages = [0] + [p for p in range(1, max_page + 1)]
    out: Dict[int, Dict[str, str]] = {}

    def parse_links(html: str):
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select('a[href^="/player/"]'):
            href = a.get("href") or ""
            m = re.fullmatch(r"/player/(\d+)", href)
            if not m:
                continue
            pid = int(m.group(1))
            name = a.get_text(" ", strip=True)
            if not name:
                continue
            # strip category suffix e.g. "ゾーネ (銅)"
            name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
            if pid not in out:
                out[pid] = {
                    "playerId": pid,
                    "name": name,
                    "url": urljoin(BASE_URL, href),
                }

    parse_links(first_html)
    for idx, page_no in enumerate(pages[1:], start=2):
        page_url = f"{BASE_URL}/player/list/normal/{page_no}"
        try:
            html = fetch_html(session, page_url, timeout)
        except Exception as e:
            print(f"[WARN] failed list page {page_no}: {e}", flush=True)
            continue
        parse_links(html)
        if idx % 5 == 0:
            print(f"[LIST] pages={idx}/{len(pages)} players={len(out)}", flush=True)
    print(f"[LIST] done pages={len(pages)} players={len(out)}", flush=True)
    return out


def load_master_players(conn: sqlite3.Connection):
    conn.row_factory = sqlite3.Row
    nations = {
        int(r["ZNATION_ID"]): (r["ZNAME"] or "")
        for r in conn.execute("SELECT ZNATION_ID, ZNAME FROM ao__ZMONATION")
    }
    infos = {
        int(r["Z_PK"]): {
            "playType": r["ZPLAY_TYPE"] or "",
            "description": r["ZDESCRIPTION_TEXT"] or "",
        }
        for r in conn.execute("SELECT Z_PK, ZPLAY_TYPE, ZDESCRIPTION_TEXT FROM ao__ZMOPLAYERSINFO")
    }
    players = []
    for r in conn.execute(
        """
        SELECT ZPLAYER_ID, ZPERSON_ID, ZNAME, ZFULLNAME, ZNATION_ID, ZINFO
        FROM ao__ZMOPLAYER
        """
    ):
        pid = int(r["ZPLAYER_ID"] or 0)
        person = int(r["ZPERSON_ID"] or 0)
        name = r["ZNAME"] or ""
        full = r["ZFULLNAME"] or ""
        nation_id = int(r["ZNATION_ID"] or 0)
        info = infos.get(int(r["ZINFO"] or 0), {})
        players.append(
            {
                "playerId": pid,
                "personId": person,
                "name": name,
                "fullName": full,
                "nationId": nation_id,
                "nation": nations.get(nation_id, ""),
                "playType": info.get("playType", ""),
                "description": info.get("description", ""),
                "normName": normalize_name(name),
            }
        )
    return players


def upsert_manual_model_rows(
    conn: sqlite3.Connection,
    rows: List[Tuple[int, str, str, str, int, str, str, str]],
) -> None:
    conn.executemany(
        """
        INSERT INTO manual_player_model
          (person_id, model_name, source_url, source_method, is_manual, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(person_id) DO UPDATE SET
          model_name=excluded.model_name,
          source_url=excluded.source_url,
          source_method=excluded.source_method,
          is_manual=excluded.is_manual,
          notes=excluded.notes,
          updated_at=excluded.updated_at
        """,
        rows,
    )


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS manual_player_model (
          person_id INTEGER PRIMARY KEY,
          model_name TEXT NOT NULL,
          source_url TEXT NOT NULL,
          source_method TEXT NOT NULL DEFAULT 'manual_update',
          is_manual INTEGER NOT NULL DEFAULT 1,
          notes TEXT,
          updated_at TEXT NOT NULL
        )
        """
    )


def main() -> int:
    args = parse_args()
    db_path = Path(args.master_db).expanduser().resolve()
    if not db_path.exists():
        raise FileNotFoundError(f"master db not found: {db_path}")

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    player_links = collect_player_links(session, args.list_url, args.timeout_sec, args.max_pages)
    rohm_records: Dict[int, Dict[str, str]] = {}

    ids = sorted(player_links)
    for i, pid in enumerate(ids, start=1):
        rec = dict(player_links[pid])
        url = rec["url"]
        try:
            html = fetch_html(session, url, args.timeout_sec)
            fields = parse_page_fields(html)
            rec["modelName"] = (fields.get("モデル") or "").strip()
            rec["nation"] = (fields.get("国籍") or "").strip()
            rec["position"] = (fields.get("ポジション") or "").strip()
            rohm_records[pid] = rec
        except Exception as e:
            print(f"[WARN] detail fail player_id={pid}: {e}", flush=True)
        if i % 100 == 0 or i == len(ids):
            print(f"[DETAIL] {i}/{len(ids)}", flush=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_table(conn)

    players = load_master_players(conn)
    players_by_id = {p["playerId"]: p for p in players}
    person_players = defaultdict(list)
    for p in players:
        if p["personId"] > 0:
            person_players[p["personId"]].append(p)

    # NOTE:
    # Do NOT map by player_id. Site player ID and app internal player_id are not guaranteed to be aligned.
    # Use strict name-based mapping only.
    person_model_candidates = defaultdict(set)  # person -> {(model, method, url)}

    # Name mapping.
    rohm_models_by_name = defaultdict(set)
    rohm_urls_by_name = defaultdict(set)
    for rec in rohm_records.values():
        model = (rec.get("modelName") or "").strip()
        if not model:
            continue
        n = normalize_name(rec.get("name") or "")
        if not n:
            continue
        rohm_models_by_name[n].add(model)
        rohm_urls_by_name[n].add(rec.get("url") or args.list_url)

    for person, plist in person_players.items():
        if person_model_candidates.get(person):
            continue
        name_keys = {p["normName"] for p in plist if p.get("normName")}
        models = set()
        urls = set()
        for nk in name_keys:
            models.update(rohm_models_by_name.get(nk, set()))
            urls.update(rohm_urls_by_name.get(nk, set()))
        if len(models) == 1:
            person_model_candidates[person].add((next(iter(models)), "name_exact", sorted(urls)[0] if urls else args.list_url))

    # Final resolved + unresolved.
    resolved_rows = []
    unresolved = []
    now = now_jst_iso()

    for person, plist in sorted(person_players.items()):
        cands = person_model_candidates.get(person, set())
        if len(cands) == 1:
            model, method, src = next(iter(cands))
            resolved_rows.append(
                (
                    int(person),
                    model,
                    src,
                    method,
                    1,
                    "manual_import_from_rohm_normal_list",
                    now,
                )
            )
            continue
        if len(cands) > 1:
            unresolved.append(
                {
                    "personId": person,
                    "players": [
                        {
                            "playerId": p["playerId"],
                            "name": p["name"],
                            "nation": p["nation"],
                            "playType": p["playType"],
                        }
                        for p in sorted(plist, key=lambda x: x["playerId"])
                    ],
                    "reason": "conflicting_models_for_same_person",
                    "candidates": [
                        {
                            "modelName": m,
                            "method": meth,
                            "sourceUrl": src,
                        }
                        for (m, meth, src) in sorted(cands)
                    ],
                }
            )
            continue

        # Suggest candidates by nation + name similarity.
        p0 = sorted(plist, key=lambda x: x["playerId"])[0]
        base_name = p0.get("name") or ""
        base_norm = normalize_name(base_name)
        base_nation = (p0.get("nation") or "").strip()
        scored = []
        for rec in rohm_records.values():
            model = (rec.get("modelName") or "").strip()
            if not model:
                continue
            name = rec.get("name") or ""
            name_norm = normalize_name(name)
            sim = SequenceMatcher(None, base_norm, name_norm).ratio()
            score = sim * 10.0
            if base_nation and rec.get("nation") and base_nation == rec.get("nation"):
                score += 3.0
            if base_norm and base_norm in name_norm:
                score += 2.0
            scored.append((score, rec))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = []
        seen = set()
        for score, rec in scored:
            key = (rec.get("name"), rec.get("modelName"))
            if key in seen:
                continue
            seen.add(key)
            top.append(
                {
                    "score": round(score, 3),
                    "rohmPlayerId": rec.get("playerId"),
                    "name": rec.get("name"),
                    "nation": rec.get("nation"),
                    "position": rec.get("position"),
                    "modelName": rec.get("modelName"),
                    "sourceUrl": rec.get("url"),
                }
            )
            if len(top) >= 5:
                break
        unresolved.append(
            {
                "personId": person,
                "players": [
                    {
                        "playerId": p["playerId"],
                        "name": p["name"],
                        "nation": p["nation"],
                        "playType": p["playType"],
                        "description": p["description"][:140],
                    }
                    for p in sorted(plist, key=lambda x: x["playerId"])
                ],
                "reason": "no_direct_or_unique_name_match",
                "candidates": top,
            }
        )

    # Enforce: one model_name must map to exactly one person_id.
    # Keep the strongest person candidate for each model:
    #  1) more variants/rows in master player table
    #  2) larger max player_id
    #  3) larger person_id
    person_strength: Dict[int, Tuple[int, int, int]] = {}
    for person, plist in person_players.items():
        player_ids = [int(p["playerId"]) for p in plist if int(p.get("playerId") or 0) > 0]
        person_strength[int(person)] = (
            len(player_ids),
            max(player_ids) if player_ids else 0,
            int(person),
        )

    grouped_by_model: Dict[str, List[Tuple[int, str, str, str, int, str, str]]] = defaultdict(list)
    for row in resolved_rows:
        grouped_by_model[row[1]].append(row)

    deduped_rows: List[Tuple[int, str, str, str, int, str, str]] = []
    for model_name, rows in grouped_by_model.items():
        if len(rows) == 1:
            deduped_rows.extend(rows)
            continue
        rows_sorted = sorted(
            rows,
            key=lambda r: person_strength.get(int(r[0]), (0, 0, int(r[0]))),
            reverse=True,
        )
        keep = rows_sorted[0]
        deduped_rows.append(keep)
        for dropped in rows_sorted[1:]:
            unresolved.append(
                {
                    "personId": int(dropped[0]),
                    "players": [
                        {
                            "playerId": p["playerId"],
                            "name": p["name"],
                            "nation": p["nation"],
                            "playType": p["playType"],
                        }
                        for p in sorted(person_players.get(int(dropped[0]), []), key=lambda x: x["playerId"])
                    ],
                    "reason": "duplicate_model_name_across_multiple_persons_dropped",
                    "candidates": [
                        {
                            "modelName": model_name,
                            "keptPersonId": int(keep[0]),
                            "droppedPersonId": int(dropped[0]),
                        }
                    ],
                }
            )

    resolved_rows = deduped_rows

    # Exclude unresolved rows that are considered "no model exists" by site rule:
    # - modelPlayer is blank for the person in current site data
    # - and that player name has no same-name variants
    name_counts = defaultdict(int)
    for p in players:
        nm = str(p.get("name") or "").strip()
        if nm:
            name_counts[nm] += 1
    person_site_rows = defaultdict(list)
    for p in players:
        person_site_rows[int(p.get("personId") or 0)].append(p)

    filtered_unresolved = []
    excluded_by_no_model_rule = []
    for item in unresolved:
        person = int(item.get("personId") or 0)
        site_rows = person_site_rows.get(person, [])
        if not site_rows:
            filtered_unresolved.append(item)
            continue
        all_blank_model = all(not str(r.get("modelPlayer") or "").strip() for r in site_rows)
        unique_name = all(
            name_counts.get(str(r.get("name") or "").strip(), 0) == 1
            for r in site_rows
            if str(r.get("name") or "").strip()
        )
        is_white_nr_only = all(
            str(r.get("category") or "") == "NR" and int(r.get("rate") or 0) <= 3
            for r in site_rows
        )
        if all_blank_model and unique_name:
            excluded_by_no_model_rule.append(person)
            continue
        if is_white_nr_only:
            excluded_by_no_model_rule.append(person)
            continue
        filtered_unresolved.append(item)
    unresolved = filtered_unresolved

    # Candidates for unresolved should not include model names already assigned to any person.
    assigned_models = {str(r[1]).strip() for r in resolved_rows if str(r[1]).strip()}
    for item in unresolved:
        cands = item.get("candidates") or []
        filtered = []
        for c in cands:
            m = str(c.get("modelName") or "").strip()
            if not m:
                continue
            if m in assigned_models:
                continue
            filtered.append(c)
        item["candidates"] = filtered

    if not args.dry_run:
        if args.reset_table:
            conn.execute("DELETE FROM manual_player_model")
        upsert_manual_model_rows(conn, resolved_rows)
        conn.commit()

    unresolved_path = Path(args.unresolved_out).expanduser().resolve()
    unresolved_path.parent.mkdir(parents=True, exist_ok=True)
    unresolved_path.write_text(
        json.dumps(
            {
                "generatedAt": now,
                "sourceUrl": args.list_url,
                "masterDb": str(db_path),
                "resolvedCount": len(resolved_rows),
                "unresolvedCount": len(unresolved),
                "excludedNoModelByRuleCount": len(excluded_by_no_model_rule),
                "excludedNoModelByRulePersonIds": sorted(set(excluded_by_no_model_rule)),
                "unresolved": unresolved,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[DONE] resolved={len(resolved_rows)} unresolved={len(unresolved)} dry_run={args.dry_run}")
    print(f"[OUT] unresolved candidates: {unresolved_path}")

    # short preview
    for item in unresolved[:20]:
        names = ", ".join(f"{p['name']}(ID:{p['playerId']})" for p in item.get("players", []))
        c0 = item.get("candidates", [])
        ctext_parts = []
        for c in c0[:3]:
            cname = c.get("name") or c.get("method") or "-"
            cmodel = c.get("modelName") or "-"
            ctext_parts.append(f"{cname}→{cmodel}")
        ctext = "; ".join(ctext_parts)
        print(f"[UNRESOLVED] person={item.get('personId')} players=[{names}] cand=[{ctext}]")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
