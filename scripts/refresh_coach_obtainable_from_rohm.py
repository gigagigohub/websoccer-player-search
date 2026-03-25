#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup


ROHM_URL = "https://rohm.websoccer.info/headcoach"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Refresh coaches_data.obtainable from rohm headcoach page")
    p.add_argument(
        "--coaches-json",
        default="/Users/k.nishimura/work/coding/websoccer-player-search/app/coaches_data.json",
    )
    p.add_argument(
        "--out",
        default="",
        help="Output path (default: overwrite --coaches-json)",
    )
    return p.parse_args()


def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def parse_obtainable_map(html: str) -> Dict[str, List[Dict[str, int]]]:
    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, List[Dict[str, int]]] = {}

    for row in soup.select("div.row"):
        left = row.find("div", class_="col-md-2")
        right = row.find("div", class_="col-md-10")
        if not left or not right:
            continue
        name_a = left.select_one(".NamePlate a")
        if not name_a:
            continue
        coach_name = name_a.get_text(strip=True)
        if not coach_name:
            continue

        section_row = None
        for child in right.find_all("div", class_="row", recursive=False):
            if child.find("a", href=re.compile(r"^/formation/\d+")):
                section_row = child
                break
        if section_row is None:
            out[coach_name] = []
            continue

        rows: List[Dict[str, int]] = []
        for cell in section_row.find_all("div", class_=re.compile(r"\bcol-md-\d+\b")):
            link = cell.find("a", href=re.compile(r"^/formation/\d+"))
            if not link:
                continue
            m_fid = re.search(r"/formation/(\d+)", link.get("href", ""))
            if not m_fid:
                continue
            fid = int(m_fid.group(1))
            cell_text = cell.get_text(" ", strip=True)
            m_season = re.search(r"\((\d+)期目〜\)", cell_text)
            from_season = int(m_season.group(1)) if m_season else 1
            rows.append({"formationId": fid, "fromSeason": from_season})

        # Deduplicate by formationId keeping smaller fromSeason.
        best: Dict[int, int] = {}
        for r in rows:
            fid = r["formationId"]
            fs = r["fromSeason"]
            prev = best.get(fid)
            if prev is None or fs < prev:
                best[fid] = fs
        deduped = [{"formationId": fid, "fromSeason": best[fid]} for fid in sorted(best.keys())]
        out[coach_name] = deduped

    return out


def main() -> None:
    args = parse_args()
    coaches_path = Path(args.coaches_json)
    out_path = Path(args.out) if args.out else coaches_path

    with coaches_path.open("r", encoding="utf-8") as f:
        src = json.load(f)

    html = fetch_html(ROHM_URL)
    obtained = parse_obtainable_map(html)

    updated = copy.deepcopy(src)
    coaches = updated.get("coaches", [])

    missing_names: List[str] = []
    replaced = 0
    for c in coaches:
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        if name not in obtained:
            missing_names.append(name)
            continue
        rows = obtained[name]
        c["obtainable"] = rows
        c["formationObtainableIds"] = [r["formationId"] for r in rows]
        replaced += 1

    updated.setdefault("meta", {})
    updated["meta"]["source"] = "formations_data + sp.rohm.websoccer.info/headcoach"
    updated["meta"]["generatedAt"] = dt.datetime.now().isoformat()
    updated["meta"]["obtainableReplacedFromRohmAt"] = dt.datetime.now().isoformat()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[DONE] replaced coaches: {replaced}/{len(coaches)}")
    if missing_names:
        print("[WARN] missing coach names on rohm:", ", ".join(missing_names))


if __name__ == "__main__":
    main()

