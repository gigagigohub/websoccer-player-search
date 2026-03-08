#!/usr/bin/env python3
import argparse
import json
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://caselli.websoccer.info"
PLAYERS_URL = f"{BASE_URL}/players"

TARGET_METRICS = [
    "スピ",
    "テク",
    "パワ",
    "スタ",
    "ラフ",
    "個性",
    "人気",
    "PK",
    "FK",
    "CK",
    "CP",
    "知性",
    "感性",
    "個人",
    "組織",
]

METRIC_ALIASES = {
    "ＰＫ": "PK",
    "ＦＫ": "FK",
    "ＣＫ": "CK",
    "ＣＰ": "CP",
}


@dataclass
class PlayerSummary:
    player_id: int
    name: str
    url: str


def normalize_header(text: str) -> str:
    t = re.sub(r"\s+", "", text.strip())
    return METRIC_ALIASES.get(t, t)


def extract_int(text: str) -> Optional[int]:
    m = re.search(r"-?\d+", text)
    if not m:
        return None
    return int(m.group(0))


def get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def detect_total_pages(soup: BeautifulSoup) -> int:
    title_text = soup.title.get_text(strip=True) if soup.title else ""
    m = re.search(r"\(\s*\d+\s*/\s*(\d+)\s*\)", title_text)
    if m:
        return int(m.group(1))

    h2 = soup.find("h2")
    h2_text = h2.get_text(" ", strip=True) if h2 else ""
    m = re.search(r"\(\s*\d+\s*/\s*(\d+)\s*\)", h2_text)
    if m:
        return int(m.group(1))
    return 1


def extract_player_summaries(soup: BeautifulSoup) -> List[PlayerSummary]:
    out: List[PlayerSummary] = []
    seen: Set[int] = set()
    for a in soup.select('a[href^="/players/"]'):
        href = a.get("href", "")
        m = re.fullmatch(r"/players/(\d+)", href)
        if not m:
            continue

        player_id = int(m.group(1))
        if player_id in seen:
            continue

        name = a.get_text(strip=True)
        if not name:
            continue

        seen.add(player_id)
        out.append(PlayerSummary(player_id=player_id, name=name, url=f"{BASE_URL}{href}"))
    return out


def parse_parameter_table(soup: BeautifulSoup) -> List[Dict[str, object]]:
    heading = soup.find("h3", string=lambda s: isinstance(s, str) and "パラメータ" in s)
    if heading is None:
        return []

    table = heading.find_next("table")
    if table is None:
        return []

    headers = []
    thead = table.find("thead")
    if thead:
        for th in thead.select("th"):
            headers.append(normalize_header(th.get_text(" ", strip=True)))

    periods: List[Dict[str, object]] = []
    for tr in table.select("tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.select("td")]
        if not cells:
            continue

        row = {}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else str(i)
            row[key] = cell

        season = str(row.get("#", "")).strip()
        if not season:
            continue

        metric_values: Dict[str, int] = {}
        for metric in TARGET_METRICS:
            raw = row.get(metric)
            if raw is None:
                continue
            val = extract_int(str(raw))
            if val is None:
                continue
            metric_values[metric] = val

        if metric_values:
            periods.append({"season": season, "metrics": metric_values})

    return periods


def extract_td_values(td) -> List[str]:
    vals = [a.get_text(" ", strip=True) for a in td.select("a") if a.get_text(" ", strip=True)]
    if vals:
        return vals
    text = td.get_text(" ", strip=True)
    return [text] if text else []


def parse_special_flags(soup: BeautifulSoup) -> Dict[str, bool]:
    has_cm = False
    has_ss = False
    for tr in soup.select("table.table.table-striped tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue

        key = re.sub(r"\s+", "", th.get_text(" ", strip=True))
        vals = extract_td_values(td)
        if key == "チャレンジマッチ" and vals:
            has_cm = True
        elif key == "プレスカ" and vals:
            has_ss = True

    return {"CM": has_cm, "SS": has_ss}


def parse_related_player_refs(soup: BeautifulSoup) -> List[Tuple[int, str]]:
    heading = soup.find("h3", string=lambda s: isinstance(s, str) and "同一選手別バージョン" in s)
    if heading is None:
        return []

    # Scope to the nearest block to avoid collecting unrelated player links.
    container = heading.find_parent("div", class_="col-md-12")
    scope = container if container is not None else heading.parent

    refs: List[Tuple[int, str]] = []
    seen: Set[int] = set()
    for a in scope.select('a[href^="/players/"]'):
        href = a.get("href", "")
        m = re.fullmatch(r"/players/(\d+)", href)
        if not m:
            continue

        player_id = int(m.group(1))
        if player_id in seen:
            continue
        seen.add(player_id)
        refs.append((player_id, a.get_text(strip=True)))
    return refs


def parse_player_name(soup: BeautifulSoup, fallback_name: str) -> str:
    h2 = soup.find("h2")
    if not h2:
        return fallback_name
    text = h2.get_text(" ", strip=True)
    return text or fallback_name


def parse_player_detail(
    session: requests.Session,
    player_id: int,
    fallback_name: str = "",
) -> Tuple[Optional[Dict[str, object]], List[Tuple[int, str]]]:
    url = f"{BASE_URL}/players/{player_id}"
    soup = get_soup(session, url)
    related_refs = parse_related_player_refs(soup)
    periods = parse_parameter_table(soup)
    flags = parse_special_flags(soup)
    if not periods:
        return None, related_refs

    player_name = parse_player_name(soup, fallback_name or str(player_id))

    values_by_metric: Dict[str, List[int]] = {m: [] for m in TARGET_METRICS}
    for period in periods:
        metrics = period["metrics"]
        for metric in TARGET_METRICS:
            v = metrics.get(metric)
            if v is not None:
                values_by_metric[metric].append(v)

    cleaned_values: Dict[str, List[int]] = {}
    max_metrics: Dict[str, int] = {}
    min_metrics: Dict[str, int] = {}

    for metric, values in values_by_metric.items():
        if not values:
            continue
        uniq_sorted = sorted(set(values))
        cleaned_values[metric] = uniq_sorted
        max_metrics[metric] = max(values)
        min_metrics[metric] = min(values)

    best_total = max(
        (
            p["metrics"].get("スピ", 0)
            + p["metrics"].get("テク", 0)
            + p["metrics"].get("パワ", 0)
            for p in periods
        ),
        default=0,
    )

    return {
        "id": player_id,
        "name": player_name,
        "url": url,
        "periods": periods,
        "metricValues": cleaned_values,
        "maxMetrics": max_metrics,
        "minMetrics": min_metrics,
        "bestTotal": best_total,
        "flags": flags,
    }, related_refs


def scrape_all(output_path: Path, delay_sec: float, max_pages: Optional[int]) -> None:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; WebSoccerPlayerSearch/1.0)",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    })

    first_soup = get_soup(session, PLAYERS_URL)
    total_pages = detect_total_pages(first_soup)
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    summaries: List[PlayerSummary] = []
    seen_ids: Set[int] = set()

    for page in range(1, total_pages + 1):
        page_url = PLAYERS_URL if page == 1 else f"{BASE_URL}/players/list/{page}"
        soup = first_soup if page == 1 else get_soup(session, page_url)
        current = extract_player_summaries(soup)
        for s in current:
            if s.player_id in seen_ids:
                continue
            seen_ids.add(s.player_id)
            summaries.append(s)
        print(f"[list] page {page}/{total_pages}: +{len(current)}")
        if page != total_pages:
            time.sleep(delay_sec)

    seed_names: Dict[int, str] = {s.player_id: s.name for s in summaries}
    queue: Deque[int] = deque(seed_names.keys())
    discovered_ids: Set[int] = set(seed_names.keys())
    processed_ids: Set[int] = set()
    players: List[Dict[str, object]] = []

    i = 0
    while queue:
        player_id = queue.popleft()
        if player_id in processed_ids:
            continue
        processed_ids.add(player_id)
        i += 1

        try:
            item, related_refs = parse_player_detail(
                session,
                player_id,
                fallback_name=seed_names.get(player_id, ""),
            )

            for related_id, related_name in related_refs:
                if related_id not in discovered_ids:
                    discovered_ids.add(related_id)
                    queue.append(related_id)
                    if related_name:
                        seed_names[related_id] = related_name

            if item:
                players.append(item)
            display_name = item["name"] if item else seed_names.get(player_id, str(player_id))
            print(
                f"[player] {i} processed / {len(discovered_ids)} discovered: "
                f"{display_name} ({player_id})"
            )
        except Exception as e:
            print(f"[warn] failed {BASE_URL}/players/{player_id}: {e}")

        if queue:
            time.sleep(delay_sec)

    payload = {
        "source": BASE_URL,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": TARGET_METRICS,
        "players": players,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"saved: {output_path} (players={len(players)})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape websoccer player parameters")
    parser.add_argument(
        "--output",
        default="app/data.json",
        help="Output JSON file path (default: app/data.json)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Delay seconds between requests (default: 0.2)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit list pages for testing",
    )
    args = parser.parse_args()

    scrape_all(Path(args.output), args.delay, args.max_pages)


if __name__ == "__main__":
    main()
