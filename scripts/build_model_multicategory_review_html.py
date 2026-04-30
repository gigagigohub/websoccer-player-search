#!/usr/bin/env python3
import argparse
import csv
import html
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


DEFAULT_REPO = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DB = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db/wsm_2604261329.sqlite3")
DEFAULT_FORMATIONS_JSON = DEFAULT_REPO / "app/formations_data.json"
DEFAULT_OVERRIDES_CSV = DEFAULT_REPO / "data/formation_model_card_overrides.csv"
DEFAULT_PLAYER_DIR = DEFAULT_REPO / "app/images/chara/players/static"
DEFAULT_OUT = DEFAULT_REPO / "app/prepared/model_multicategory_card_review.html"
DEFAULT_OUT_CSV = DEFAULT_REPO / "app/prepared/model_multicategory_card_review.csv"

CATEGORY_ORDER = {
    "NR": 0,
    "SS": 1,
    "CM/SS": 2,
    "CM": 3,
    "CC": 4,
    "RT": 5,
    "": 9,
}


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def relative_player_src(player_dir, player_id):
    path = Path(player_dir) / f"{player_id}.gif"
    if not path.exists():
        return ""
    return f"../images/chara/players/static/{html.escape(str(player_id))}.gif"


def load_players(master_db):
    conn = sqlite3.connect(str(master_db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              p.ZPLAYER_ID AS player_id,
              p.ZNAME AS player_name,
              p.ZFULLNAME AS player_fullname,
              COALESCE(n.ZNAME, '') AS nation,
              COALESCE(info.ZPLAY_TYPE, '') AS play_type,
              i.canonical_person_id,
              COALESCE(c.category, '') AS category,
              COALESCE(c.retired, 0) AS retired
            FROM ao__ZMOPLAYER p
            JOIN player_person_identity i ON i.player_id = p.ZPLAYER_ID
            LEFT JOIN ao__ZMONATION n ON n.ZNATION_ID = p.ZNATION_ID
            LEFT JOIN ao__ZMOPLAYERSINFO info ON info.Z_PK = p.ZINFO
            LEFT JOIN manual_player_category c ON c.player_id = p.ZPLAYER_ID
            ORDER BY i.canonical_person_id, p.ZPLAYER_ID
            """
        ).fetchall()
    finally:
        conn.close()
    players = {}
    grouped = defaultdict(list)
    for row in rows:
        player = dict(row)
        player["player_id"] = to_int(player["player_id"])
        player["canonical_person_id"] = to_int(player["canonical_person_id"])
        player["retired"] = to_int(player["retired"])
        players[player["player_id"]] = player
        grouped[player["canonical_person_id"]].append(player)
    for cards in grouped.values():
        cards.sort(key=card_sort_key)
    return players, grouped


def card_sort_key(card):
    category = str(card.get("category") or "")
    return (CATEGORY_ORDER.get(category, 8), int(card.get("player_id") or 0))


def load_applied_keys(path):
    return {
        (to_int(row.get("formation_id")), to_int(row.get("slot")))
        for row in read_csv(path)
        if to_int(row.get("formation_id")) and to_int(row.get("slot"))
    }


def category_has_ss_or_cm(category):
    parts = {part.strip().upper() for part in str(category or "").replace("/", ",").split(",")}
    return "SS" in parts or "CM" in parts


def distinct_categories(cards):
    return {
        str(card.get("category") or "")
        for card in cards
        if str(card.get("category") or "").strip()
    }


def formation_title(formation):
    name = str(formation.get("name") or "")
    year = str(formation.get("year") or "")
    return f"{name} {year}".strip()


def player_label(player):
    name = str(player.get("player_name") or "")
    fullname = str(player.get("player_fullname") or "")
    if fullname and fullname != name:
        return f"{name} / {fullname}"
    return name or fullname


def build_context_by_formation(formations, player_dir):
    contexts = {}
    for formation in formations:
        fid = to_int(formation.get("id"))
        context = []
        for slot in formation.get("modelSlots") or []:
            player_id = to_int(slot.get("playerId"))
            category = str(slot.get("category") or "")
            if not player_id or not category_has_ss_or_cm(category):
                continue
            context.append(
                {
                    "slot": to_int(slot.get("slot")),
                    "player_id": player_id,
                    "model_name": str(slot.get("modelName") or ""),
                    "source_name": str(slot.get("sourceName") or ""),
                    "player_name": str(slot.get("playerName") or ""),
                    "category": category,
                    "link_source": str(slot.get("linkSource") or ""),
                    "image": relative_player_src(player_dir, player_id),
                }
            )
        context.sort(key=lambda item: item["slot"])
        contexts[fid] = context
    return contexts


def candidate_rows(formations, players, grouped_players, applied_keys):
    rows = []
    for formation in formations:
        fid = to_int(formation.get("id"))
        title = formation_title(formation)
        for slot in formation.get("modelSlots") or []:
            slot_no = to_int(slot.get("slot"))
            key = (fid, slot_no)
            if key in applied_keys:
                continue
            player_id = to_int(slot.get("playerId"))
            if not player_id:
                continue
            current_player = players.get(player_id)
            if not current_player:
                continue
            person_id = to_int(current_player.get("canonical_person_id"))
            cards = grouped_players.get(person_id) or []
            categories = distinct_categories(cards)
            if len(cards) < 2 or len(categories) < 2:
                continue
            ordered_cards = sorted(
                cards,
                key=lambda card: (
                    0 if to_int(card.get("player_id")) == player_id else 1,
                    *card_sort_key(card),
                ),
            )
            rows.append(
                {
                    "formation_id": fid,
                    "formation": title,
                    "slot": slot_no,
                    "model_name": str(slot.get("modelName") or ""),
                    "source_name": str(slot.get("sourceName") or ""),
                    "current_player_id": player_id,
                    "current_category": str(slot.get("category") or ""),
                    "link_source": str(slot.get("linkSource") or ""),
                    "person_id": person_id,
                    "cards": ordered_cards,
                    "categories": sorted(categories, key=lambda cat: CATEGORY_ORDER.get(cat, 8)),
                }
            )
    rows.sort(key=lambda row: (row["formation_id"], row["slot"]))
    return rows


def write_review_csv(rows, out_csv):
    fieldnames = [
        "formation_id",
        "formation",
        "slot",
        "model_name",
        "source_name",
        "current_player_id",
        "current_category",
        "link_source",
        "person_id",
        "categories",
        "candidate_player_ids",
    ]
    with Path(out_csv).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output_row = {
                key: row.get(key, "")
                for key in fieldnames
                if key not in {"categories", "candidate_player_ids"}
            }
            output_row["categories"] = "/".join(row["categories"])
            output_row["candidate_player_ids"] = ",".join(str(card["player_id"]) for card in row["cards"])
            writer.writerow(output_row)


def render_context(row, context):
    items = [item for item in context if item["slot"] != row["slot"]]
    if not items:
        return '<div class="context-empty">同フォーメーション内のSS/CM指定なし</div>'
    cards = []
    for item in items:
        image = item["image"]
        img_html = f'<img src="{image}" alt="">' if image else '<span class="no-image">no image</span>'
        cards.append(
            f"""
            <div class="context-card">
              {img_html}
              <div>
                <strong>slot {item["slot"]}</strong>
                <span>{html.escape(item["model_name"])}</span>
                <small>id {item["player_id"]} / {html.escape(item["category"])} / {html.escape(item["link_source"])}</small>
              </div>
            </div>
            """
        )
    return "".join(cards)


def render_option(row, option_no, card, player_dir):
    player_id = to_int(card.get("player_id"))
    image = relative_player_src(player_dir, player_id)
    img_html = f'<img src="{image}" alt="">' if image else '<span class="no-image">no image</span>'
    tags = []
    if player_id == row["current_player_id"]:
        tags.append("current")
    if card.get("retired"):
        tags.append("retired")
    tag_html = "".join(f"<em>{html.escape(tag)}</em>" for tag in tags)
    return f"""
      <label class="option-card">
        <input type="radio" name="choice-{row["formation_id"]}-{row["slot"]}" value="{option_no}" data-player-id="{player_id}">
        <span class="option-number">{option_no}</span>
        {img_html}
        <span class="option-meta">
          <strong>{html.escape(player_label(card))}</strong>
          <small>id {player_id} / {html.escape(str(card.get("category") or ""))}</small>
          <small>{html.escape(str(card.get("nation") or ""))} / {html.escape(str(card.get("play_type") or ""))}</small>
          <span class="tags">{tag_html}</span>
        </span>
      </label>
    """


def render_hold_option(row, option_no):
    return f"""
      <label class="option-card hold-option">
        <input type="radio" name="choice-{row["formation_id"]}-{row["slot"]}" value="{option_no}" data-player-id="0">
        <span class="option-number">{option_no}</span>
        <span class="hold-text">保留</span>
      </label>
    """


def build_html(rows, contexts, player_dir, title):
    rendered = []
    for index, row in enumerate(rows, 1):
        option_html = [
            render_option(row, option_no, card, player_dir)
            for option_no, card in enumerate(row["cards"], 1)
        ]
        option_html.append(render_hold_option(row, len(row["cards"]) + 1))
        rendered.append(
            f"""
            <tr data-formation-id="{row["formation_id"]}"
                data-slot="{row["slot"]}"
                data-model-name="{html.escape(row["model_name"])}">
              <td class="row-label">
                <div class="row-index">#{index}</div>
                <strong>{html.escape(row["formation"])}</strong>
                <span>slot {row["slot"]}: {html.escape(row["model_name"])}</span>
                <small>source: {html.escape(row["source_name"])}</small>
                <small>current id {row["current_player_id"]} / {html.escape(row["current_category"])} / {html.escape(row["link_source"])}</small>
                <small>person {row["person_id"]} / {' / '.join(html.escape(cat) for cat in row["categories"])}</small>
              </td>
              <td class="context-cell">
                {render_context(row, contexts.get(row["formation_id"], []))}
              </td>
              <td class="choices-cell">{''.join(option_html)}</td>
            </tr>
            """
        )

    return f"""<!doctype html>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  :root {{
    color-scheme: light;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
  }}
  body {{
    margin: 18px;
    background: #f5f6f8;
    color: #111827;
  }}
  h1 {{
    margin: 0 0 8px;
    font-size: 21px;
  }}
  .toolbar {{
    position: sticky;
    top: 0;
    z-index: 3;
    display: grid;
    gap: 9px;
    padding: 12px;
    margin: 0 0 12px;
    background: rgba(245, 246, 248, 0.97);
    border: 1px solid #d7dce3;
    border-radius: 8px;
  }}
  .toolbar p {{
    margin: 0;
    color: #475569;
    font-size: 13px;
  }}
  textarea {{
    width: 100%;
    min-height: 126px;
    box-sizing: border-box;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
  }}
  button {{
    width: fit-content;
    padding: 8px 12px;
    border: 1px solid #9aa4b2;
    background: #fff;
    color: #111827;
    border-radius: 6px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: #fff;
  }}
  th, td {{
    border: 1px solid #d7dce3;
    padding: 8px;
    vertical-align: top;
  }}
  th {{
    position: sticky;
    top: 210px;
    z-index: 2;
    background: #eef1f5;
    text-align: left;
  }}
  .row-label {{
    width: 218px;
  }}
  .row-label strong,
  .row-label span,
  .row-index,
  .row-label small {{
    display: block;
  }}
  .row-index,
  small {{
    color: #64748b;
  }}
  .context-cell {{
    width: 310px;
  }}
  .context-card {{
    display: inline-grid;
    grid-template-columns: 54px minmax(0, 1fr);
    gap: 6px;
    width: 146px;
    min-height: 68px;
    margin: 0 5px 5px 0;
    padding: 5px;
    box-sizing: border-box;
    border: 1px solid #d7dce3;
    border-radius: 7px;
    background: #f8fafc;
    vertical-align: top;
  }}
  .context-card img {{
    width: 48px;
    height: 55px;
    object-fit: contain;
  }}
  .context-card strong,
  .context-card span,
  .context-card small {{
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
  }}
  .context-empty {{
    color: #94a3b8;
    font-size: 12px;
  }}
  .option-card {{
    display: inline-grid;
    grid-template-columns: 18px 24px 82px minmax(0, 1fr);
    align-items: center;
    gap: 7px;
    width: 286px;
    min-height: 112px;
    box-sizing: border-box;
    padding: 6px;
    margin: 0 6px 6px 0;
    border: 2px solid #d7dce3;
    border-radius: 8px;
    background: #fff;
    vertical-align: top;
  }}
  .option-card:has(input:checked) {{
    border-color: #2563eb;
    background: #eff6ff;
  }}
  .option-card input {{
    width: 18px;
    height: 18px;
  }}
  .option-number {{
    min-width: 22px;
    font-size: 24px;
    font-weight: 700;
  }}
  .option-card img {{
    width: 82px;
    height: 94px;
    object-fit: contain;
  }}
  .option-meta {{
    display: grid;
    gap: 4px;
    min-width: 0;
  }}
  .option-meta strong {{
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 13px;
  }}
  .tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }}
  .tags em {{
    display: inline-block;
    padding: 2px 5px;
    border-radius: 999px;
    background: #e5e7eb;
    color: #475569;
    font-style: normal;
    font-size: 11px;
  }}
  .hold-option {{
    grid-template-columns: 18px 24px 1fr;
    width: 134px;
  }}
  .hold-text {{
    font-weight: 700;
  }}
  .no-image {{
    display: grid;
    place-items: center;
    width: 82px;
    height: 94px;
    color: #94a3b8;
    background: #f1f5f9;
    border: 1px dashed #cbd5e1;
    font-size: 11px;
  }}
  @media (max-width: 760px) {{
    body {{
      margin: 10px;
    }}
    th {{
      position: static;
    }}
    table,
    thead,
    tbody,
    tr,
    th,
    td {{
      display: block;
      width: 100%;
      box-sizing: border-box;
    }}
    thead {{
      display: none;
    }}
    tr {{
      margin: 0 0 12px;
      border: 1px solid #d7dce3;
      background: #fff;
    }}
    th, td {{
      border: 0;
      border-bottom: 1px solid #eef1f5;
    }}
    .row-label,
    .context-cell {{
      width: 100%;
    }}
    .option-card {{
      width: min(100%, 360px);
    }}
  }}
</style>
<h1>{html.escape(title)}</h1>
<div class="toolbar">
  <p>指定済みoverrideは除外済み。左から「行情報」「同フォーメーション内でSS/CMになっている比較カード」「このslotの同一人物カード候補」です。</p>
  <p>選んだ行だけ、下に貼り付け用テキストが生成されます。最後の番号は保留です。</p>
  <textarea id="answer" readonly placeholder="選択するとここに貼り付け用テキストが生成されます"></textarea>
  <button id="copy" type="button">Copy</button>
</div>
<table>
  <thead>
    <tr><th>Slot</th><th>Same Formation SS/CM</th><th>Choices</th></tr>
  </thead>
  <tbody>
    {''.join(rendered)}
  </tbody>
</table>
<script>
  const answer = document.getElementById('answer');
  const copyButton = document.getElementById('copy');

  function csvEscape(value) {{
    const text = String(value ?? '');
    return /[",\\n]/.test(text) ? `"${{text.replaceAll('"', '""')}}"` : text;
  }}

  function updateAnswer() {{
    const lines = ['UNIFORM_CARD_CHOICES', 'formation_id,slot,choice,player_id,model_name'];
    document.querySelectorAll('tbody tr').forEach((row) => {{
      const checked = row.querySelector('input[type="radio"]:checked');
      if (!checked) return;
      lines.push([
        row.dataset.formationId,
        row.dataset.slot,
        checked.value,
        checked.dataset.playerId || '0',
        csvEscape(row.dataset.modelName || '')
      ].join(','));
    }});
    lines.push('END');
    answer.value = lines.length > 3 ? lines.join('\\n') : '';
  }}

  document.querySelectorAll('input[type="radio"]').forEach((input) => {{
    input.addEventListener('change', updateAnswer);
  }});

  copyButton.addEventListener('click', async () => {{
    if (!answer.value) return;
    await navigator.clipboard.writeText(answer.value);
    copyButton.textContent = 'Copied';
    setTimeout(() => copyButton.textContent = 'Copy', 900);
  }});
</script>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--formations-json", default=str(DEFAULT_FORMATIONS_JSON))
    parser.add_argument("--overrides-csv", default=str(DEFAULT_OVERRIDES_CSV))
    parser.add_argument("--master-db", default=str(DEFAULT_MASTER_DB))
    parser.add_argument("--player-dir", default=str(DEFAULT_PLAYER_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--title", default="Model Multi-Category Card Review")
    args = parser.parse_args()

    data = load_json(args.formations_json)
    formations = data.get("formations") or []
    players, grouped_players = load_players(Path(args.master_db))
    applied_keys = load_applied_keys(args.overrides_csv)
    rows = candidate_rows(formations, players, grouped_players, applied_keys)
    contexts = build_context_by_formation(formations, Path(args.player_dir))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(rows, contexts, Path(args.player_dir), args.title), encoding="utf-8")
    write_review_csv(rows, Path(args.out_csv))
    print(f"wrote {out} rows={len(rows)}")
    print(f"wrote {args.out_csv}")


if __name__ == "__main__":
    main()
