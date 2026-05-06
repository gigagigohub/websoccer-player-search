#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageChops


BASE_URL = "https://rohm.websoccer.info"
FORMATION_ALIAS = {
    "トッテナム 2018-19": "ロンドンT 2018-19",
}
NR_RATE_BY_ROHM_CATEGORY = {
    "無": {1, 2, 3},
    "銅": {4},
    "銀": {5, 6},
    "金": {7},
}
LINKABLE_CATEGORIES = {"無", "銅", "銀", "金", "PS", "CM", "CC"}
IMAGE_MSE_THRESHOLD = 60.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build static Rohm slot ranking data for formation details.")
    p.add_argument("--app-dir", default=str(Path.cwd() / "app"))
    p.add_argument("--out", default=None)
    p.add_argument("--cache-dir", default=None)
    p.add_argument("--sleep", type=float, default=0.03)
    p.add_argument("--limit-formations", type=int, default=0)
    return p.parse_args()


def normalize(value: str) -> str:
    s = unicodedata.normalize("NFKC", str(value or "")).lower()
    s = s.replace("ヴァ", "バ")
    return re.sub(r"[\s・･\.\-‐‑‒–—―ー]", "", s)


def formation_year_label(year: int | str | None, stride: int | str | None) -> str:
    y = int(year or 0)
    s = int(stride or 0)
    if y <= 0:
        return ""
    if s == 1:
        return f"{y}-{str((y + 1) % 100).zfill(2)}"
    return str(y)


def to_float(value: str) -> float | None:
    s = str(value or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_int(value: str) -> int | None:
    s = str(value or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


class Fetcher:
    def __init__(self, cache_dir: Path, sleep: float) -> None:
        self.cache_dir = cache_dir
        self.sleep = sleep
        self.session = requests.Session()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, url: str, suffix: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}{suffix}"

    def text(self, url: str) -> str:
        path = self._path_for(url, ".html")
        if path.exists():
            return path.read_text(encoding="utf-8")
        res = self.session.get(url, timeout=25)
        res.raise_for_status()
        res.encoding = "utf-8"
        text = res.text
        path.write_text(text, encoding="utf-8")
        if self.sleep:
            time.sleep(self.sleep)
        return text

    def bytes(self, url: str) -> bytes:
        path = self._path_for(url, ".bin")
        if path.exists():
            return path.read_bytes()
        res = self.session.get(url, timeout=25)
        res.raise_for_status()
        data = res.content
        path.write_bytes(data)
        if self.sleep:
            time.sleep(self.sleep)
        return data


def parse_rohm_formation_index(fetcher: Fetcher) -> dict[str, dict]:
    soup = BeautifulSoup(fetcher.text(f"{BASE_URL}/formation"), "html.parser")
    result: dict[str, dict] = {}
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        m = re.fullmatch(r"/formation/(\d+)", href)
        if not m:
            continue
        name = a.get_text(" ", strip=True)
        if not name:
            continue
        result[normalize(name)] = {
            "rohmFormationId": int(m.group(1)),
            "rohmFormationName": name,
            "url": urljoin(BASE_URL, href),
        }
    return result


def build_local_formation_map(formations: list[dict], rohm_index: dict[str, dict]) -> tuple[dict[int, dict], list[dict]]:
    mapped: dict[int, dict] = {}
    missing: list[dict] = []
    for formation in formations:
        local_id = int(formation.get("id") or 0)
        year = formation_year_label(formation.get("year"), formation.get("stride"))
        display = f"{formation.get('name') or ''} {year}".strip()
        candidates = [FORMATION_ALIAS.get(display, display), display, formation.get("name") or ""]
        hit = None
        for candidate in candidates:
            hit = rohm_index.get(normalize(candidate))
            if hit:
                break
        if hit:
            mapped[local_id] = {
                **hit,
                "localFormationId": local_id,
                "localFormationName": formation.get("name") or "",
                "localFormationLabel": display,
            }
        else:
            missing.append({
                "localFormationId": local_id,
                "localFormationName": formation.get("name") or "",
                "localFormationLabel": display,
            })
    return mapped, missing


def player_category_parts(player: dict) -> set[str]:
    membership = player.get("categoryMembership")
    if isinstance(membership, list):
        return {str(x) for x in membership}
    category = str(player.get("category") or "")
    return {x.strip() for x in category.split("/") if x.strip()} or {category}


def build_player_name_index(players: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for player in players:
        name = str(player.get("name") or "")
        if not name:
            continue
        result.setdefault(normalize(name), []).append(player)
    return result


def candidate_players(rohm_name: str, rohm_category: str, name_index: dict[str, list[dict]]) -> list[dict]:
    candidates = list(name_index.get(normalize(rohm_name), []))
    if not candidates or rohm_category not in LINKABLE_CATEGORIES:
        return []
    if rohm_category in NR_RATE_BY_ROHM_CATEGORY:
        rates = NR_RATE_BY_ROHM_CATEGORY[rohm_category]
        filtered = [
            p for p in candidates
            if "NR" in player_category_parts(p) and int(p.get("rate") or 0) in rates
        ]
        if filtered:
            return filtered
        return [p for p in candidates if "NR" in player_category_parts(p)]
    if rohm_category == "PS":
        return [p for p in candidates if "SS" in player_category_parts(p)]
    if rohm_category == "CM":
        return [p for p in candidates if "CM" in player_category_parts(p)]
    if rohm_category == "CC":
        return [p for p in candidates if "CC" in player_category_parts(p)]
    return []


def extract_current_player_image_url(fetcher: Fetcher, rohm_player_id: int) -> str:
    soup = BeautifulSoup(fetcher.text(f"{BASE_URL}/player/{rohm_player_id}"), "html.parser")
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        if "/images/player/static/" in src:
            return urljoin(BASE_URL, src)
    return ""


def load_image_from_bytes(data: bytes) -> Image.Image | None:
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def local_player_image(app_dir: Path, player_id: int) -> Image.Image | None:
    path = app_dir / "images" / "chara" / "players" / "static" / f"{player_id}.gif"
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def image_mse(a: Image.Image, b: Image.Image) -> float:
    size = (64, 64)
    aa = a.resize(size, Image.NEAREST)
    bb = b.resize(size, Image.NEAREST)
    diff = ImageChops.difference(aa, bb)
    total = 0
    for px in diff.getdata():
        total += px[0] * px[0] + px[1] * px[1] + px[2] * px[2]
    return total / (size[0] * size[1] * 3)


class PlayerMatcher:
    def __init__(self, app_dir: Path, fetcher: Fetcher, players: list[dict]) -> None:
        self.app_dir = app_dir
        self.fetcher = fetcher
        self.name_index = build_player_name_index(players)
        self.rohm_image_url_cache: dict[int, str] = {}
        self.rohm_image_cache: dict[int, Image.Image | None] = {}
        self.local_image_cache: dict[int, Image.Image | None] = {}

    def _rohm_image(self, rohm_player_id: int) -> tuple[str, Image.Image | None]:
        if rohm_player_id not in self.rohm_image_url_cache:
            self.rohm_image_url_cache[rohm_player_id] = extract_current_player_image_url(self.fetcher, rohm_player_id)
        url = self.rohm_image_url_cache[rohm_player_id]
        if rohm_player_id not in self.rohm_image_cache:
            self.rohm_image_cache[rohm_player_id] = load_image_from_bytes(self.fetcher.bytes(url)) if url else None
        return url, self.rohm_image_cache[rohm_player_id]

    def _local_image(self, player_id: int) -> Image.Image | None:
        if player_id not in self.local_image_cache:
            self.local_image_cache[player_id] = local_player_image(self.app_dir, player_id)
        return self.local_image_cache[player_id]

    def match(self, rohm_name: str, rohm_category: str, rohm_player_id: int) -> dict:
        candidates = candidate_players(rohm_name, rohm_category, self.name_index)
        if not candidates:
            return {"localPlayerId": None, "matchMethod": "unlinked", "matchStatus": "external" if rohm_category not in LINKABLE_CATEGORIES else "no_candidate"}
        if len(candidates) == 1:
            return {"localPlayerId": int(candidates[0]["id"]), "matchMethod": "name_category", "matchStatus": "linked"}

        rohm_url, rohm_image = self._rohm_image(rohm_player_id)
        scores = []
        if rohm_image:
            for candidate in candidates:
                local_id = int(candidate["id"])
                local_image = self._local_image(local_id)
                if not local_image:
                    continue
                scores.append((image_mse(rohm_image, local_image), candidate))
        if scores:
            scores.sort(key=lambda item: item[0])
            mse, best = scores[0]
            if mse <= IMAGE_MSE_THRESHOLD:
                return {
                    "localPlayerId": int(best["id"]),
                    "matchMethod": "name_category_image",
                    "matchStatus": "linked",
                    "imageMse": round(mse, 2),
                    "rohmImageUrl": rohm_url,
                }
            return {
                "localPlayerId": None,
                "matchMethod": "name_category_image",
                "matchStatus": "image_low_confidence",
                "imageMse": round(mse, 2),
                "rohmImageUrl": rohm_url,
                "candidatePlayerIds": [int(p["id"]) for p in candidates],
            }
        return {
            "localPlayerId": None,
            "matchMethod": "name_category",
            "matchStatus": "ambiguous",
            "candidatePlayerIds": [int(p["id"]) for p in candidates],
        }


def parse_position_page(fetcher: Fetcher, matcher: PlayerMatcher, rohm_formation_id: int, slot: int) -> dict:
    url = f"{BASE_URL}/formation/{rohm_formation_id}/position/{slot}"
    soup = BeautifulSoup(fetcher.text(url), "html.parser")
    h2 = soup.find("h2")
    title = h2.get_text(" ", strip=True) if h2 else ""
    average_pts = None
    m = re.search(r"平均評価点\s*([0-9.]+)", soup.get_text(" ", strip=True))
    if m:
        average_pts = to_float(m.group(1))
    updated_at = ""
    m = re.search(r"Standard score updated at\s*([0-9/: ]+)", soup.get_text(" ", strip=True))
    if m:
        updated_at = m.group(1).strip()

    table = soup.find("table")
    rows = []
    if table:
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if not cells or "平均値" in cells:
                continue
            rank_match = re.search(r"(\d+)", cells[0] if len(cells) > 0 else "")
            if not rank_match or len(cells) < 11:
                continue
            links = tr.find_all("a")
            rohm_player_id = 0
            for a in links:
                href = a.get("href") or ""
                m = re.search(r"/player/(\d+)", href)
                if m:
                    rohm_player_id = int(m.group(1))
                    break
            name = cells[1]
            category = cells[2]
            match = matcher.match(name, category, rohm_player_id) if rohm_player_id else {
                "localPlayerId": None,
                "matchMethod": "unlinked",
                "matchStatus": "no_rohm_player_id",
            }
            rows.append({
                "rank": int(rank_match.group(1)),
                "playerName": name,
                "rohmCategory": category,
                "rohmPlayerId": rohm_player_id,
                "uses": to_int(cells[3]),
                "avgPts": to_float(cells[4]),
                "deviation": to_float(cells[5]),
                "goals": to_float(cells[6]),
                "assists": to_float(cells[7]),
                "fouls": to_float(cells[8]),
                "yellow": to_float(cells[9]),
                "red": to_float(cells[10]),
                **match,
            })
            if len(rows) >= 20:
                break
    return {
        "url": url,
        "title": title,
        "averagePts": average_pts,
        "updatedAt": updated_at,
        "rows": rows,
    }


def main() -> int:
    args = parse_args()
    app_dir = Path(args.app_dir).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve() if args.out else app_dir / "rohm_slot_data.json"
    cache_dir = Path(args.cache_dir).expanduser().resolve() if args.cache_dir else app_dir.parent / ".cache" / "rohm"

    formations_data = json.loads((app_dir / "formations_data.json").read_text(encoding="utf-8"))
    players_data = json.loads((app_dir / "data.json").read_text(encoding="utf-8"))
    formations = list(formations_data.get("formations") or [])
    if args.limit_formations:
        formations = formations[:args.limit_formations]

    fetcher = Fetcher(cache_dir, args.sleep)
    rohm_index = parse_rohm_formation_index(fetcher)
    mapped, missing = build_local_formation_map(formations, rohm_index)
    matcher = PlayerMatcher(app_dir, fetcher, list(players_data.get("players") or []))

    result = {
        "source": BASE_URL,
        "generatedAt": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="seconds"),
        "formationCount": len(mapped),
        "missingFormations": missing,
        "formations": {},
    }
    for idx, formation in enumerate(formations, start=1):
        local_id = int(formation.get("id") or 0)
        mapping = mapped.get(local_id)
        if not mapping:
            continue
        print(f"[{idx}/{len(formations)}] {mapping['localFormationLabel']} -> Rohm {mapping['rohmFormationId']} {mapping['rohmFormationName']}", flush=True)
        slots = {}
        for slot in range(1, 12):
            slots[str(slot)] = parse_position_page(fetcher, matcher, int(mapping["rohmFormationId"]), slot)
        result["formations"][str(local_id)] = {
            **mapping,
            "slots": slots,
        }

    out_path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"mapped={len(mapped)} missing={len(missing)}")
    if missing:
        print("missing formations:")
        for item in missing:
            print(f"  {item['localFormationId']}: {item['localFormationLabel']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
