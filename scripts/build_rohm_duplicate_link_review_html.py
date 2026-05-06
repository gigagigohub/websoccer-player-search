#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://rohm.websoccer.info"
CATEGORY_ORDER = {"NR": 0, "CC": 1, "SS": 2, "CM": 3}


def cache_path(cache_dir: Path, url: str, suffix: str) -> Path:
    return cache_dir / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}{suffix}"


def fetch_text(url: str, cache_dir: Path, sleep: float = 0.02) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, url, ".html")
    if path.exists():
        return path.read_text(encoding="utf-8")
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    res.encoding = "utf-8"
    path.write_text(res.text, encoding="utf-8")
    if sleep:
        time.sleep(sleep)
    return res.text


def parse_slot_rohm_player_ids(slot_url: str, cache_dir: Path) -> dict[int, int]:
    cached = cache_path(cache_dir, slot_url, ".html")
    if not cached.exists():
        return {}
    soup = BeautifulSoup(cached.read_text(encoding="utf-8"), "html.parser")
    table = soup.find("table")
    result: dict[int, int] = {}
    if not table:
        return result
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if not cells or "平均値" in cells:
            continue
        rank_match = re.search(r"(\d+)", cells[0] if cells else "")
        if not rank_match:
            continue
        rohm_player_id = 0
        for a in tr.find_all("a"):
            m = re.search(r"/player/(\d+)", a.get("href") or "")
            if m:
                rohm_player_id = int(m.group(1))
                break
        if rohm_player_id:
            result[int(rank_match.group(1))] = rohm_player_id
    return result


def extract_rohm_player_image_url(rohm_player_id: int, cache_dir: Path) -> str:
    if not rohm_player_id:
        return ""
    try:
        text = fetch_text(f"{BASE_URL}/player/{rohm_player_id}", cache_dir)
    except Exception:
        return ""
    m = re.search(r'''src=["']([^"']*/images/player/static/[^"']+)["']''', text)
    if not m:
        return ""
    return urljoin(BASE_URL, m.group(1))


def category_parts(player: dict) -> list[str]:
    parts = player.get("categoryMembership")
    if isinstance(parts, list) and parts:
        return [str(x) for x in parts]
    category = str(player.get("category") or "")
    return [x.strip() for x in category.split("/") if x.strip()] or [category or "-"]


def primary_category(player: dict) -> str:
    parts = category_parts(player)
    return sorted(parts, key=lambda x: CATEGORY_ORDER.get(x, 99))[0] if parts else "-"


def candidate_sort_key(player: dict) -> tuple:
    category = primary_category(player)
    return (
        CATEGORY_ORDER.get(category, 99),
        int(player.get("rate") or 0),
        int(player.get("id") or 0),
    )


def build_review(app_dir: Path, cache_dir: Path) -> tuple[list[dict], list[dict]]:
    rohm_data = json.loads((app_dir / "rohm_slot_data.json").read_text(encoding="utf-8"))
    data = json.loads((app_dir / "data.json").read_text(encoding="utf-8"))
    players = list(data.get("players") or [])
    players_by_id = {int(p["id"]): p for p in players if p.get("id") is not None}
    players_by_person: dict[int, list[dict]] = defaultdict(list)
    for player in players:
        person_id = player.get("personId")
        if person_id is None:
            continue
        players_by_person[int(person_id)].append(player)
    for person_players in players_by_person.values():
        person_players.sort(key=candidate_sort_key)

    groups: list[dict] = []
    csv_rows: list[dict] = []
    group_seq = 0
    review_seq = 0

    for formation_key, formation in (rohm_data.get("formations") or {}).items():
        formation_id = int(formation.get("localFormationId") or formation_key)
        formation_label = formation.get("localFormationLabel") or formation.get("localFormationName") or str(formation_id)
        for slot_key, slot in (formation.get("slots") or {}).items():
            slot_no = int(slot_key)
            rows = list(slot.get("rows") or [])
            by_local_id: dict[int, list[dict]] = defaultdict(list)
            for row in rows:
                local_id = row.get("localPlayerId")
                if local_id:
                    by_local_id[int(local_id)].append(row)
            duplicate_items = {player_id: rs for player_id, rs in by_local_id.items() if len(rs) > 1}
            if not duplicate_items:
                continue
            rank_to_rohm_id = parse_slot_rohm_player_ids(str(slot.get("url") or ""), cache_dir)
            for duplicated_player_id, duplicate_rows in sorted(duplicate_items.items()):
                group_seq += 1
                current_player = players_by_id.get(duplicated_player_id)
                person_id = int(current_player.get("personId")) if current_player and current_player.get("personId") is not None else None
                candidates = []
                if person_id is not None:
                    for candidate in players_by_person.get(person_id, []):
                        candidate_id = int(candidate["id"])
                        candidates.append({
                            "id": candidate_id,
                            "name": candidate.get("name") or "",
                            "fullName": candidate.get("fullName") or "",
                            "category": primary_category(candidate),
                            "categories": category_parts(candidate),
                            "rate": candidate.get("rate") or "",
                            "personId": person_id,
                            "staticImage": f"../images/chara/players/static/{candidate_id}.gif",
                            "actionImage": f"../images/chara/players/action/{candidate_id}.gif",
                        })
                group_rows = []
                for row in duplicate_rows:
                    review_seq += 1
                    rank = int(row.get("rank") or 0)
                    rohm_player_id = int(rank_to_rohm_id.get(rank) or 0)
                    review_row = {
                        "reviewId": f"r{review_seq}",
                        "formationId": formation_id,
                        "formationLabel": formation_label,
                        "slot": slot_no,
                        "rank": rank,
                        "rohmPlayerName": row.get("playerName") or "",
                        "rohmCategory": row.get("rohmCategory") or "",
                        "uses": row.get("uses"),
                        "avgPts": row.get("avgPts"),
                        "goals": row.get("goals"),
                        "assists": row.get("assists"),
                        "rohmPlayerId": rohm_player_id,
                        "rohmPlayerUrl": f"{BASE_URL}/player/{rohm_player_id}" if rohm_player_id else "",
                        "sourceImageUrl": "",
                        "fallbackImage": f"../images/chara/players/static/{duplicated_player_id}.gif",
                        "currentPlayerId": duplicated_player_id,
                    }
                    group_rows.append(review_row)
                    csv_rows.append({
                        "review_id": review_row["reviewId"],
                        "formation_id": formation_id,
                        "formation_label": formation_label,
                        "slot": slot_no,
                        "rank": rank,
                        "rohm_player_id": rohm_player_id,
                        "rohm_player_name": review_row["rohmPlayerName"],
                        "rohm_category": review_row["rohmCategory"],
                        "current_player_id": duplicated_player_id,
                        "current_player_name": current_player.get("name") if current_player else "",
                        "current_person_id": person_id if person_id is not None else "",
                        "candidate_ids": " ".join(str(c["id"]) for c in candidates),
                    })
                groups.append({
                    "groupId": f"g{group_seq}",
                    "formationId": formation_id,
                    "formationLabel": formation_label,
                    "slot": slot_no,
                    "duplicatedPlayerId": duplicated_player_id,
                    "duplicatedPlayerName": current_player.get("name") if current_player else "",
                    "duplicatedPersonId": person_id,
                    "duplicateCount": len(duplicate_rows),
                    "candidates": candidates,
                    "rows": group_rows,
                })
    hydrate_rohm_images(groups, cache_dir)
    return groups, csv_rows


def hydrate_rohm_images(groups: list[dict], cache_dir: Path) -> None:
    rohm_ids = sorted({
        int(row.get("rohmPlayerId") or 0)
        for group in groups
        for row in group.get("rows", [])
        if row.get("rohmPlayerId")
    })
    print(f"fetching Rohm image URLs: {len(rohm_ids)} unique players", flush=True)
    image_urls: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(extract_rohm_player_image_url, rohm_id, cache_dir): rohm_id for rohm_id in rohm_ids}
        for idx, future in enumerate(as_completed(futures), start=1):
            rohm_id = futures[future]
            try:
                image_urls[rohm_id] = future.result() or ""
            except Exception:
                image_urls[rohm_id] = ""
            if idx % 100 == 0 or idx == len(rohm_ids):
                print(f"  {idx}/{len(rohm_ids)}", flush=True)
    for group in groups:
        for row in group.get("rows", []):
            row["sourceImageUrl"] = image_urls.get(int(row.get("rohmPlayerId") or 0), "")


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "review_id",
        "formation_id",
        "formation_label",
        "slot",
        "rank",
        "rohm_player_id",
        "rohm_player_name",
        "rohm_category",
        "current_player_id",
        "current_player_name",
        "current_person_id",
        "candidate_ids",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_html(path: Path, groups: list[dict]) -> None:
    payload = json.dumps({"groups": groups}, ensure_ascii=False, separators=(",", ":"))
    safe_payload = payload.replace("</", "<\\/")
    html_text = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Rohm Duplicate Link Review</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08121f;
      --panel: #132238;
      --panel-2: #182b48;
      --line: #2e466c;
      --text: #e9f1ff;
      --muted: #9fb0ca;
      --accent: #8db4ff;
      --ok: #74d3a7;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); }}
    header {{ position: sticky; top: 0; z-index: 10; padding: 12px 14px; background: rgba(8, 18, 31, .96); border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0 0 8px; font-size: 18px; }}
    .summary {{ color: var(--muted); font-size: 12px; line-height: 1.5; }}
    .controls {{ display: grid; grid-template-columns: 1fr auto auto; gap: 8px; align-items: center; margin-top: 10px; }}
    input[type="search"], textarea {{ width: 100%; border: 1px solid var(--line); border-radius: 8px; background: #0d1a2d; color: var(--text); padding: 9px 10px; }}
    button {{ border: 1px solid var(--line); border-radius: 8px; background: #20365a; color: var(--text); padding: 9px 10px; font-weight: 700; }}
    button:active {{ transform: translateY(1px); }}
    main {{ padding: 12px; max-width: 1180px; margin: 0 auto; }}
    .group {{ border: 1px solid var(--line); border-radius: 10px; background: var(--panel); margin-bottom: 12px; overflow: hidden; }}
    .group-head {{ display: flex; gap: 8px; justify-content: space-between; align-items: baseline; padding: 10px 12px; background: linear-gradient(180deg, #1a3153, #14243b); }}
    .group-title {{ font-weight: 800; font-size: 14px; }}
    .group-meta {{ color: var(--muted); font-size: 12px; }}
    .review-row {{ display: grid; grid-template-columns: 150px 1fr; gap: 10px; padding: 10px 12px; border-top: 1px solid rgba(255,255,255,.08); }}
    .source-card {{ border: 1px solid rgba(141,180,255,.35); border-radius: 8px; background: #0c192b; padding: 8px; min-width: 0; }}
    .source-img-wrap {{ height: 112px; display: flex; align-items: flex-end; justify-content: center; overflow: hidden; background: radial-gradient(circle at 50% 90%, rgba(141,180,255,.18), transparent 65%); border-radius: 6px; }}
    .source-img-wrap img {{ max-height: 128px; max-width: 98px; object-fit: contain; }}
    .source-name {{ margin-top: 6px; font-size: 12px; font-weight: 800; overflow-wrap: anywhere; }}
    .source-stats {{ color: var(--muted); font-size: 11px; line-height: 1.35; }}
    .candidate-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 8px; align-items: stretch; }}
    .candidate {{ position: relative; display: grid; grid-template-rows: auto 1fr; min-height: 160px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2); padding: 7px; cursor: pointer; }}
    .candidate input {{ position: absolute; top: 7px; left: 7px; width: 18px; height: 18px; accent-color: var(--accent); }}
    .candidate:has(input:checked) {{ border-color: var(--ok); box-shadow: 0 0 0 2px rgba(116,211,167,.18); }}
    .candidate-img {{ height: 92px; display: flex; align-items: flex-end; justify-content: center; overflow: hidden; border-radius: 6px; background: rgba(255,255,255,.04); }}
    .candidate-img img {{ max-height: 106px; max-width: 88px; object-fit: contain; }}
    .candidate-info {{ margin-top: 6px; min-width: 0; }}
    .candidate-name {{ font-size: 12px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .candidate-sub {{ color: var(--muted); font-size: 11px; line-height: 1.35; }}
    .none-choice {{ display: flex; align-items: center; justify-content: center; text-align: center; min-height: 160px; color: #ffd5d5; }}
    .output-wrap {{ margin: 14px 0 24px; display: grid; gap: 8px; }}
    textarea {{ min-height: 170px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }}
    .hidden {{ display: none !important; }}
    @media (max-width: 760px) {{
      .controls {{ grid-template-columns: 1fr; }}
      .review-row {{ grid-template-columns: 1fr; }}
      .source-card {{ display: grid; grid-template-columns: 96px 1fr; gap: 8px; align-items: center; }}
      .source-img-wrap {{ height: 92px; }}
      .candidate-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Rohm Duplicate Link Review</h1>
    <div class="summary" id="summary"></div>
    <div class="controls">
      <input id="search" type="search" placeholder="formation / slot / player / id で絞り込み" />
      <button id="showUnchecked" type="button">Unchecked only</button>
      <button id="generate" type="button">Generate Text</button>
    </div>
  </header>
  <main>
    <div id="groups"></div>
    <div class="output-wrap">
      <textarea id="output" placeholder="Generate Textで貼り付け用テキストを生成"></textarea>
      <button id="copy" type="button">Copy</button>
    </div>
  </main>
  <script id="reviewData" type="application/json">__REVIEW_PAYLOAD__</script>
  <script>
    const data = JSON.parse(document.getElementById("reviewData").textContent);
    const storageKey = "rohm-duplicate-link-review-v1";
    let choices = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
    let uncheckedOnly = false;
    const groupsEl = document.getElementById("groups");
    const searchEl = document.getElementById("search");
    const summaryEl = document.getElementById("summary");
    const outputEl = document.getElementById("output");

    function esc(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[ch]));
    }}

    function imgTag(src, fallback, alt) {{
      const fallbackCode = fallback ? `this.onerror=null;this.src='${{esc(fallback)}}';` : "this.style.display='none';";
      return `<img loading="lazy" src="${{esc(src || fallback || "")}}" alt="${{esc(alt || "")}}" onerror="${{fallbackCode}}" />`;
    }}

    function rowIsChecked(row) {{
      return Boolean(choices[row.reviewId]);
    }}

    function groupMatches(group, term) {{
      if (!term) return true;
      const hay = [
        group.formationId, group.formationLabel, group.slot,
        group.duplicatedPlayerId, group.duplicatedPlayerName, group.duplicatedPersonId,
        ...group.rows.flatMap((r) => [r.rank, r.rohmPlayerId, r.rohmPlayerName, r.rohmCategory]),
      ].join(" ").toLowerCase();
      return hay.includes(term.toLowerCase());
    }}

    function render() {{
      const term = searchEl.value.trim();
      let visibleGroups = 0;
      let visibleRows = 0;
      const chunks = [];
      data.groups.forEach((group) => {{
        if (!groupMatches(group, term)) return;
        const rows = group.rows.filter((row) => !uncheckedOnly || !rowIsChecked(row));
        if (!rows.length) return;
        visibleGroups += 1;
        visibleRows += rows.length;
        const candidateHtml = (row) => {{
          const candidates = group.candidates.map((candidate) => {{
            const checked = choices[row.reviewId] === String(candidate.id) ? "checked" : "";
            return `<label class="candidate">
              <input type="radio" name="${{esc(row.reviewId)}}" value="${{esc(candidate.id)}}" ${{checked}} />
              <div class="candidate-img">${{imgTag(candidate.staticImage, candidate.actionImage, candidate.name)}}</div>
              <div class="candidate-info">
                <div class="candidate-name">ID ${{esc(candidate.id)}} ${{esc(candidate.name)}}</div>
                <div class="candidate-sub">${{esc(candidate.category)}} / person ${{esc(candidate.personId)}} / rate ${{esc(candidate.rate)}}</div>
              </div>
            </label>`;
          }).join("");
          const noneChecked = choices[row.reviewId] === "none" ? "checked" : "";
          return `${{candidates}}<label class="candidate none-choice">
            <input type="radio" name="${{esc(row.reviewId)}}" value="none" ${{noneChecked}} />
            <span>該当なし</span>
          </label>`;
        }};
        const rowsHtml = rows.map((row) => `<div class="review-row" data-review-id="${{esc(row.reviewId)}}">
          <div class="source-card">
            <div class="source-img-wrap">${{imgTag(row.sourceImageUrl, row.fallbackImage, row.rohmPlayerName)}}</div>
            <div>
              <div class="source-name">#${{esc(row.rank)}} ${{esc(row.rohmPlayerName)}} <span class="source-stats">(${{esc(row.rohmCategory)}})</span></div>
              <div class="source-stats">Rohm ID: ${{esc(row.rohmPlayerId || "-")}} / current ID: ${{esc(row.currentPlayerId)}}</div>
              <div class="source-stats">Games ${{esc(row.uses)}} / Avg ${{esc(row.avgPts)}} / Goals ${{esc(row.goals)}} / Ast ${{esc(row.assists)}}</div>
            </div>
          </div>
          <div class="candidate-grid">${{candidateHtml(row)}}</div>
        </div>`).join("");
        chunks.push(`<section class="group">
          <div class="group-head">
            <div class="group-title">${{esc(group.formationLabel)}} / Slot ${{esc(group.slot)}}</div>
            <div class="group-meta">duplicate local ID ${{esc(group.duplicatedPlayerId)}} ${{esc(group.duplicatedPlayerName || "")}} / ${{esc(group.duplicateCount)}} rows</div>
          </div>
          ${{rowsHtml}}
        </section>`);
      }});
      groupsEl.innerHTML = chunks.join("");
      summaryEl.textContent = `${{data.groups.length}} duplicate groups / ${{data.groups.reduce((sum, g) => sum + g.rows.length, 0)}} review rows / visible ${{visibleGroups}} groups, ${{visibleRows}} rows`;
    }}

    groupsEl.addEventListener("change", (event) => {{
      const input = event.target.closest("input[type='radio']");
      if (!input) return;
      choices[input.name] = input.value;
      localStorage.setItem(storageKey, JSON.stringify(choices));
      if (uncheckedOnly) render();
    }});
    searchEl.addEventListener("input", render);
    document.getElementById("showUnchecked").addEventListener("click", () => {{
      uncheckedOnly = !uncheckedOnly;
      document.getElementById("showUnchecked").textContent = uncheckedOnly ? "Show all" : "Unchecked only";
      render();
    }});
    document.getElementById("generate").addEventListener("click", () => {{
      const lines = ["ROHM_DUPLICATE_LINK_CHOICES", "formation_id,slot,rank,rohm_player_id,rohm_player_name,current_player_id,choice_player_id,choice_label"];
      data.groups.forEach((group) => {{
        group.rows.forEach((row) => {{
          const choice = choices[row.reviewId];
          if (!choice) return;
          const label = choice === "none" ? "該当なし" : (group.candidates.find((c) => String(c.id) === String(choice))?.name || "");
          lines.push([group.formationId, group.slot, row.rank, row.rohmPlayerId || "", row.rohmPlayerName, row.currentPlayerId, choice === "none" ? "" : choice, label].map((v) => `"${{String(v ?? "").replace(/"/g, '""')}}"`).join(","));
        }});
      }});
      lines.push("END");
      outputEl.value = lines.join("\\n");
    }});
    document.getElementById("copy").addEventListener("click", async () => {{
      outputEl.select();
      try {{ await navigator.clipboard.writeText(outputEl.value); }} catch (_) {{ document.execCommand("copy"); }}
    }});
    render();
  </script>
</body>
</html>
"""
    html_text = html_text.replace("__REVIEW_PAYLOAD__", safe_payload).replace("{{", "{").replace("}}", "}")
    path.write_text(html_text, encoding="utf-8")


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    app_dir = repo / "app"
    cache_dir = repo / ".cache" / "rohm"
    out_html = app_dir / "prepared" / "rohm_duplicate_link_review.html"
    out_csv = app_dir / "prepared" / "rohm_duplicate_link_review.csv"
    groups, csv_rows = build_review(app_dir, cache_dir)
    write_html(out_html, groups)
    write_csv(out_csv, csv_rows)
    print(f"wrote {out_html} ({len(groups)} groups)")
    print(f"wrote {out_csv} ({len(csv_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
