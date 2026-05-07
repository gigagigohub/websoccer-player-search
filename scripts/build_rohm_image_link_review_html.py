#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path


SOURCE_HTML = Path("app/prepared/rohm_duplicate_link_review.html")
OUT_HTML = Path("app/rohm_duplicate_link_review.html")
OUT_CSV = Path("app/prepared/rohm_image_link_review.csv")

CATEGORY_ORDER = {"NR": 0, "CC": 1, "SS": 2, "CM": 3}


def load_row_review_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    marker = '<script id="reviewData" type="application/json">'
    start = text.index(marker) + len(marker)
    end = text.index("</script>", start)
    return json.loads(text[start:end])


def candidate_sort_key(candidate: dict) -> tuple:
    return (
        CATEGORY_ORDER.get(str(candidate.get("category") or ""), 99),
        int(candidate.get("rate") or 0),
        int(candidate.get("id") or 0),
    )


def public_image_path(path: str) -> str:
    value = str(path or "")
    if value.startswith("../images/"):
        return "./images/" + value[len("../images/"):]
    return value


def aggregate_by_rohm_image(row_payload: dict) -> list[dict]:
    by_image: dict[str, dict] = {}
    for group in row_payload.get("groups") or []:
        candidate_by_id = {int(c["id"]): c for c in group.get("candidates") or []}
        for row in group.get("rows") or []:
            image_url = row.get("sourceImageUrl") or row.get("fallbackImage") or ""
            if not image_url:
                continue
            item = by_image.setdefault(image_url, {
                "imageKey": f"img{len(by_image) + 1}",
                "sourceImageUrl": image_url,
                "rohmPlayerIds": set(),
                "rohmNames": set(),
                "rohmCategories": set(),
                "currentPlayerIds": set(),
                "currentNames": set(),
                "formationSlots": set(),
                "reviewIds": [],
                "rows": [],
                "candidates": {},
            })
            rohm_player_id = row.get("rohmPlayerId")
            if rohm_player_id:
                item["rohmPlayerIds"].add(int(rohm_player_id))
            if row.get("rohmPlayerName"):
                item["rohmNames"].add(str(row["rohmPlayerName"]))
            if row.get("rohmCategory"):
                item["rohmCategories"].add(str(row["rohmCategory"]))
            current_id = row.get("currentPlayerId")
            if current_id:
                item["currentPlayerIds"].add(int(current_id))
                if int(current_id) in candidate_by_id:
                    item["currentNames"].add(candidate_by_id[int(current_id)].get("name") or "")
            item["formationSlots"].add(f"{group.get('formationId')}:{group.get('slot')}")
            item["reviewIds"].append(row.get("reviewId"))
            item["rows"].append({
                "formationId": group.get("formationId"),
                "formationLabel": group.get("formationLabel"),
                "slot": group.get("slot"),
                "rank": row.get("rank"),
                "rohmPlayerId": row.get("rohmPlayerId"),
                "rohmPlayerName": row.get("rohmPlayerName"),
                "currentPlayerId": row.get("currentPlayerId"),
            })
            for candidate in candidate_by_id.values():
                item["candidates"][int(candidate["id"])] = candidate

    result = []
    for item in by_image.values():
        candidates = []
        for candidate in sorted(item["candidates"].values(), key=candidate_sort_key):
            normalized = dict(candidate)
            normalized["staticImage"] = public_image_path(normalized.get("staticImage") or "")
            normalized["actionImage"] = public_image_path(normalized.get("actionImage") or "")
            candidates.append(normalized)
        result.append({
            "imageKey": item["imageKey"],
            "sourceImageUrl": item["sourceImageUrl"],
            "rohmPlayerIds": sorted(item["rohmPlayerIds"]),
            "rohmNames": sorted(x for x in item["rohmNames"] if x),
            "rohmCategories": sorted(item["rohmCategories"]),
            "currentPlayerIds": sorted(item["currentPlayerIds"]),
            "currentNames": sorted(x for x in item["currentNames"] if x),
            "formationSlots": sorted(item["formationSlots"], key=lambda x: [int(n) for n in x.split(":")]),
            "reviewIds": [x for x in item["reviewIds"] if x],
            "rows": sorted(item["rows"], key=lambda r: (int(r.get("formationId") or 0), int(r.get("slot") or 0), int(r.get("rank") or 0))),
            "candidates": candidates,
            "occurrenceCount": len(item["rows"]),
        })
    result.sort(key=lambda item: (-int(item["occurrenceCount"]), item["rohmNames"], item["sourceImageUrl"]))
    return result


def write_csv(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "image_key",
            "occurrence_count",
            "rohm_player_ids",
            "rohm_names",
            "rohm_categories",
            "current_player_ids",
            "formation_slots",
            "candidate_ids",
            "source_image_url",
        ], lineterminator="\n")
        writer.writeheader()
        for item in items:
            writer.writerow({
                "image_key": item["imageKey"],
                "occurrence_count": item["occurrenceCount"],
                "rohm_player_ids": " ".join(str(x) for x in item["rohmPlayerIds"]),
                "rohm_names": " / ".join(item["rohmNames"]),
                "rohm_categories": " / ".join(item["rohmCategories"]),
                "current_player_ids": " ".join(str(x) for x in item["currentPlayerIds"]),
                "formation_slots": " ".join(item["formationSlots"]),
                "candidate_ids": " ".join(str(c["id"]) for c in item["candidates"]),
                "source_image_url": item["sourceImageUrl"],
            })


def write_html(path: Path, items: list[dict]) -> None:
    payload = json.dumps({"items": items}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Rohm Image Link Review</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #08121f;
      --panel: #132238;
      --panel-2: #182b48;
      --line: #2e466c;
      --text: #e9f1ff;
      --muted: #9fb0ca;
      --accent: #8db4ff;
      --ok: #74d3a7;
      --warn: #ffd38a;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); }
    header {
      position: sticky;
      top: 0;
      z-index: 20;
      padding: 10px 12px;
      background: rgba(8, 18, 31, .98);
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0 0 6px; font-size: 17px; }
    .summary { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .controls { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; margin-top: 8px; }
    input[type="search"], textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0d1a2d;
      color: var(--text);
      padding: 9px 10px;
      font-size: 14px;
    }
    button {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #20365a;
      color: var(--text);
      padding: 9px 10px;
      font-weight: 800;
      font-size: 13px;
    }
    button:active { transform: translateY(1px); }
    main { padding: 10px; max-width: 1120px; margin: 0 auto; }
    .card {
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel);
      margin-bottom: 10px;
      overflow: hidden;
    }
    .card.is-complete { border-color: rgba(116,211,167,.55); }
    .card-head {
      display: grid;
      grid-template-columns: 92px 1fr;
      gap: 10px;
      padding: 10px;
      background: linear-gradient(180deg, #1a3153, #14243b);
    }
    .source-img {
      height: 110px;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      overflow: hidden;
      border-radius: 8px;
      background: radial-gradient(circle at 50% 90%, rgba(141,180,255,.18), transparent 65%);
    }
    .source-img img { max-height: 128px; max-width: 90px; object-fit: contain; }
    .title { font-size: 14px; font-weight: 900; overflow-wrap: anywhere; }
    .meta { margin-top: 4px; color: var(--muted); font-size: 12px; line-height: 1.42; }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 30px;
      height: 18px;
      padding: 0 6px;
      border-radius: 6px;
      border: 1px solid rgba(255,255,255,.18);
      background: #20365a;
      color: #fff;
      font-size: 10px;
      font-weight: 900;
      margin-right: 4px;
    }
    .candidate-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
      gap: 8px;
      padding: 10px;
    }
    .candidate {
      position: relative;
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 160px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      padding: 7px;
      cursor: pointer;
    }
    .candidate input {
      position: absolute;
      top: 7px;
      left: 7px;
      width: 19px;
      height: 19px;
      accent-color: var(--accent);
    }
    .candidate:has(input:checked) {
      border-color: var(--ok);
      box-shadow: 0 0 0 2px rgba(116,211,167,.18);
    }
    .candidate-img {
      height: 92px;
      display: flex;
      align-items: flex-end;
      justify-content: center;
      overflow: hidden;
      border-radius: 6px;
      background: rgba(255,255,255,.04);
    }
    .candidate-img img { max-height: 106px; max-width: 88px; object-fit: contain; }
    .candidate-name {
      margin-top: 6px;
      font-size: 12px;
      font-weight: 900;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .candidate-sub { color: var(--muted); font-size: 11px; line-height: 1.35; }
    .none-choice {
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      color: #ffd5d5;
    }
    .details {
      border-top: 1px solid rgba(255,255,255,.08);
      padding: 8px 10px 10px;
    }
    .details summary { cursor: pointer; color: var(--muted); font-size: 12px; }
    .rows { margin-top: 7px; display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
    .output-wrap { display: grid; gap: 8px; margin: 14px 0 24px; }
    textarea { min-height: 170px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    @media (max-width: 760px) {
      .controls { grid-template-columns: 1fr; }
      .card-head { grid-template-columns: 82px 1fr; }
      .source-img { height: 96px; }
      .candidate-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
  </style>
</head>
<body>
  <header>
    <h1>Rohm Image Link Review</h1>
    <div id="summary" class="summary"></div>
    <div class="controls">
      <input id="search" type="search" placeholder="選手名 / ID / formation / slot で絞り込み" />
      <button id="toggleUnchecked" type="button">Unchecked only</button>
      <button id="generate" type="button">Generate Text</button>
    </div>
  </header>
  <main>
    <div id="cards"></div>
    <div class="output-wrap">
      <textarea id="output" placeholder="Generate Textで貼り付け用テキストを生成"></textarea>
      <button id="copy" type="button">Copy</button>
    </div>
  </main>
  <script id="reviewData" type="application/json">__PAYLOAD__</script>
  <script>
    const data = JSON.parse(document.getElementById("reviewData").textContent);
    const storageKey = "rohm-image-link-review-v1";
    let choices = JSON.parse(localStorage.getItem(storageKey) || "{}");
    let uncheckedOnly = false;
    const cardsEl = document.getElementById("cards");
    const searchEl = document.getElementById("search");
    const summaryEl = document.getElementById("summary");
    const outputEl = document.getElementById("output");

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }
    function imgTag(src, fallback, alt) {
      const fallbackCode = fallback ? `this.onerror=null;this.src='${esc(fallback)}';` : "this.style.display='none';";
      return `<img loading="lazy" src="${esc(src || fallback || "")}" alt="${esc(alt || "")}" onerror="${fallbackCode}" />`;
    }
    function itemText(item) {
      return [
        item.imageKey, item.rohmPlayerIds.join(" "), item.rohmNames.join(" "), item.rohmCategories.join(" "),
        item.currentPlayerIds.join(" "), item.currentNames.join(" "), item.formationSlots.join(" "),
        item.candidates.map((c) => `${c.id} ${c.name} ${c.fullName || ""}`).join(" "),
      ].join(" ").toLowerCase();
    }
    function render() {
      const term = searchEl.value.trim().toLowerCase();
      const chunks = [];
      let visible = 0;
      let checked = 0;
      data.items.forEach((item) => {
        if (choices[item.imageKey]) checked += 1;
        if (uncheckedOnly && choices[item.imageKey]) return;
        if (term && !itemText(item).includes(term)) return;
        visible += 1;
        const selected = choices[item.imageKey];
        const candidates = item.candidates.map((candidate) => {
          const checkedAttr = String(selected) === String(candidate.id) ? "checked" : "";
          return `<label class="candidate">
            <input type="radio" name="${esc(item.imageKey)}" value="${esc(candidate.id)}" ${checkedAttr} />
            <div class="candidate-img">${imgTag(candidate.staticImage, candidate.actionImage, candidate.name)}</div>
            <div>
              <div class="candidate-name">ID ${esc(candidate.id)} ${esc(candidate.name)}</div>
              <div class="candidate-sub">${esc(candidate.category)} / person ${esc(candidate.personId)} / rate ${esc(candidate.rate)}</div>
            </div>
          </label>`;
        }).join("");
        const noneChecked = selected === "none" ? "checked" : "";
        const rowPreview = item.rows.slice(0, 16).map((row) =>
          `<div>${esc(row.formationLabel)} / Slot ${esc(row.slot)} / #${esc(row.rank)} / Rohm ${esc(row.rohmPlayerId)} ${esc(row.rohmPlayerName)} / current ${esc(row.currentPlayerId)}</div>`
        ).join("");
        chunks.push(`<section class="card ${selected ? "is-complete" : ""}">
          <div class="card-head">
            <div class="source-img">${imgTag(item.sourceImageUrl, "", item.rohmNames.join(" / "))}</div>
            <div>
              <div class="title">${esc(item.rohmNames.join(" / ") || "Unknown")} ${item.rohmCategories.map((x) => `<span class="badge">${esc(x)}</span>`).join("")}</div>
              <div class="meta">Rohm IDs: ${esc(item.rohmPlayerIds.join(", "))} / current IDs: ${esc(item.currentPlayerIds.join(", "))}</div>
              <div class="meta">Occurrences: ${esc(item.occurrenceCount)} / formation-slot: ${esc(item.formationSlots.length)} / candidates: ${esc(item.candidates.length)}</div>
              <div class="meta">Current names: ${esc(item.currentNames.join(" / ") || "-")}</div>
            </div>
          </div>
          <div class="candidate-grid">
            ${candidates}
            <label class="candidate none-choice">
              <input type="radio" name="${esc(item.imageKey)}" value="none" ${noneChecked} />
              <span>該当なし</span>
            </label>
          </div>
          <details class="details">
            <summary>対象行 ${esc(item.occurrenceCount)}件を表示</summary>
            <div class="rows">${rowPreview}${item.rows.length > 16 ? `<div>...and ${item.rows.length - 16} more</div>` : ""}</div>
          </details>
        </section>`);
      });
      cardsEl.innerHTML = chunks.join("");
      summaryEl.textContent = `${data.items.length} Rohm images / ${checked} checked / visible ${visible}`;
    }
    cardsEl.addEventListener("change", (event) => {
      const input = event.target.closest("input[type='radio']");
      if (!input) return;
      choices[input.name] = input.value;
      localStorage.setItem(storageKey, JSON.stringify(choices));
      if (uncheckedOnly) render();
      else input.closest(".card")?.classList.add("is-complete");
      summaryEl.textContent = `${data.items.length} Rohm images / ${Object.keys(choices).length} checked / visible ${document.querySelectorAll(".card").length}`;
    });
    searchEl.addEventListener("input", render);
    document.getElementById("toggleUnchecked").addEventListener("click", () => {
      uncheckedOnly = !uncheckedOnly;
      document.getElementById("toggleUnchecked").textContent = uncheckedOnly ? "Show all" : "Unchecked only";
      render();
    });
    document.getElementById("generate").addEventListener("click", () => {
      const lines = ["ROHM_IMAGE_LINK_CHOICES", "image_key,rohm_player_ids,rohm_names,current_player_ids,formation_slots,choice_player_id,choice_label"];
      data.items.forEach((item) => {
        const choice = choices[item.imageKey];
        if (!choice) return;
        const candidate = item.candidates.find((c) => String(c.id) === String(choice));
        const label = choice === "none" ? "該当なし" : (candidate?.name || "");
        const values = [
          item.imageKey,
          item.rohmPlayerIds.join(" "),
          item.rohmNames.join(" / "),
          item.currentPlayerIds.join(" "),
          item.formationSlots.join(" "),
          choice === "none" ? "" : choice,
          label,
        ];
        lines.push(values.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","));
      });
      lines.push("END");
      outputEl.value = lines.join("\\n");
    });
    document.getElementById("copy").addEventListener("click", async () => {
      outputEl.select();
      try { await navigator.clipboard.writeText(outputEl.value); } catch (_) { document.execCommand("copy"); }
    });
    render();
  </script>
</body>
</html>
"""
    path.write_text(html.replace("__PAYLOAD__", payload), encoding="utf-8")


def main() -> int:
    payload = load_row_review_payload(SOURCE_HTML)
    items = aggregate_by_rohm_image(payload)
    write_html(OUT_HTML, items)
    write_csv(OUT_CSV, items)
    print(f"wrote {OUT_HTML} ({len(items)} image groups)")
    print(f"wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
