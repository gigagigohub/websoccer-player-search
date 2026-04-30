#!/usr/bin/env python3
import argparse
import base64
import colorsys
import csv
import html
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


DEFAULT_REPO = Path(__file__).resolve().parents[1]
DEFAULT_MASTER_DB = Path("/Users/k.nishimura/work/coding/wsc_data/websoccer_master_db/wsm_2604261329.sqlite3")
DEFAULT_REVIEW_CSV = DEFAULT_REPO / "app/prepared/model_uniform_card_review.csv"
DEFAULT_OVERRIDES_CSV = DEFAULT_REPO / "data/formation_model_card_overrides.csv"
DEFAULT_UNIFORM_DIR = Path("/Users/k.nishimura/work/coding/wsc_data/Resources/img/uniforms/home")
DEFAULT_PLAYER_DIR = DEFAULT_REPO / "app/images/chara/players/static"
DEFAULT_OUT = DEFAULT_REPO / "app/prepared/model_uniform_card_review.html"


def read_csv(path):
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def data_url(path):
    path = Path(path)
    if not path.exists():
        return ""
    return "data:image/gif;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


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
              i.canonical_person_id,
              COALESCE(c.category, '') AS category
            FROM ao__ZMOPLAYER p
            JOIN player_person_identity i ON i.player_id = p.ZPLAYER_ID
            LEFT JOIN manual_player_category c ON c.player_id = p.ZPLAYER_ID
            """
        ).fetchall()
    finally:
        conn.close()
    return {str(row["player_id"]): dict(row) for row in rows}


def players_by_person(players):
    grouped = defaultdict(list)
    for player in players.values():
        grouped[str(player.get("canonical_person_id") or "")].append(player)
    for cards in grouped.values():
        cards.sort(key=lambda card: int(card.get("player_id") or 0))
    return grouped


def load_applied_overrides(path):
    if not Path(path).exists():
        return {}
    return {
        (row.get("formation_id"), row.get("slot")): row
        for row in read_csv(path)
        if row.get("formation_id") and row.get("slot")
    }


def color_label(r, g, b):
    mx = max(r, g, b)
    mn = min(r, g, b)
    if mx < 45:
        return "black"
    if mn > 220 and mx - mn < 35:
        return "white"
    if mx - mn < 22:
        return "gray" if mx > 90 else "black"
    hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hue *= 360
    if saturation < 0.16:
        if lightness > 0.78:
            return "white"
        if lightness < 0.25:
            return "black"
        return "gray"
    if hue < 15 or hue >= 345:
        return "red"
    if hue < 35:
        return "orange"
    if hue < 58:
        return "yellow"
    if hue < 85:
        return "lime"
    if hue < 155:
        return "green"
    if hue < 190:
        return "cyan"
    if hue < 245:
        return "blue"
    if hue < 280:
        return "purple"
    if hue < 330:
        return "magenta"
    return "red"


def image_palette(path, kind):
    path = Path(path)
    if not path.exists():
        return {}
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    box = (8, 5, w - 8, int(h * 0.78)) if kind == "uniform" else (
        int(w * 0.25),
        int(h * 0.38),
        int(w * 0.76),
        int(h * 0.78),
    )
    counts = Counter()
    for r, g, b, a in im.crop(box).getdata():
        if a < 80:
            continue
        if kind == "player":
            hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            degree = hue * 360
            if 12 <= degree <= 48 and saturation > 0.18 and 0.28 < lightness < 0.82:
                continue
            if r > 95 and g > 45 and b < 55 and r > g * 1.15:
                continue
        counts[color_label(r, g, b)] += 1
    total = sum(counts.values()) or 1
    return dict(
        sorted(
            ((k, v / total) for k, v in counts.items() if v / total >= 0.035),
            key=lambda item: -item[1],
        )[:5]
    )


def uniform_score(ref_palette, card_palette):
    keys = set(ref_palette) | set(card_palette)
    if not keys:
        return 0.0
    overlap = sum(min(ref_palette.get(k, 0), card_palette.get(k, 0)) for k in keys)
    union = sum(max(ref_palette.get(k, 0), card_palette.get(k, 0)) for k in keys) or 1
    ref_dom = max(ref_palette.items(), key=lambda item: item[1])[0] if ref_palette else ""
    card_dom = max(card_palette.items(), key=lambda item: item[1])[0] if card_palette else ""
    return overlap / union + (0.1 if ref_dom == card_dom else 0)


def option_cell(
    row,
    number,
    player,
    score,
    player_dir,
    is_current=False,
    is_auto_top=False,
    is_auto_second=False,
    is_applied=False,
):
    if not player:
        return f"""
          <label class="option-card hold-option">
            <input type="radio" name="choice-{html.escape(row['key'])}" value="{number}" data-player-id="0">
            <span class="option-number">{number}</span>
            <span class="hold-text">保留</span>
          </label>
        """
    player_id = str(player.get("player_id") or "")
    player_name = player.get("player_name") or ""
    category = player.get("category") or ""
    image = data_url(player_dir / f"{player_id}.gif")
    tags = []
    if is_current:
        tags.append("current")
    if is_auto_top:
        tags.append("auto top")
    if is_auto_second:
        tags.append("auto next")
    if is_applied:
        tags.append("applied")
    tag_html = "".join(f"<em>{html.escape(tag)}</em>" for tag in tags)
    return f"""
      <label class="option-card">
        <input type="radio" name="choice-{html.escape(row['key'])}" value="{number}" data-player-id="{html.escape(player_id)}">
        <span class="option-number">{number}</span>
        <img src="{image}" alt="" width="82" height="94">
        <span class="option-meta">
          <strong>{html.escape(player_name)}</strong>
          <small>id {html.escape(player_id)} / {html.escape(category)} / score {score:.3f}</small>
          <span class="tags">{tag_html}</span>
        </span>
      </label>
    """


def build_html(rows, players, grouped_players, applied_overrides, uniform_dir, player_dir, title):
    rendered_rows = []
    for index, row in enumerate(rows, 1):
        row["key"] = f"{row['formation_id']}-{row['slot']}"
        uniform_path = uniform_dir / f"{row['uniform_id']}@2x.gif"
        uniform_image = data_url(uniform_path)
        ref_palette = image_palette(uniform_path, "uniform")
        current_player = players.get(str(row.get("option1_current")))
        person_id = str(current_player.get("canonical_person_id") or "") if current_player else ""
        cards = grouped_players.get(person_id, [])
        scored_cards = []
        for card in cards:
            card_id = str(card.get("player_id") or "")
            card_palette = image_palette(player_dir / f"{card_id}.gif", "player")
            scored_cards.append((uniform_score(ref_palette, card_palette), card))
        scored_cards.sort(
            key=lambda item: (
                0 if str(item[1].get("player_id")) == str(row.get("option1_current")) else 1,
                -item[0],
                int(item[1].get("player_id") or 0),
            )
        )
        auto_top = str(row.get("option2_top") or "")
        auto_second = str(row.get("option3_second") or "")
        applied = applied_overrides.get((row.get("formation_id"), row.get("slot")), {})
        applied_player_id = str(applied.get("player_id") or "")
        options = []
        for option_index, (score, card) in enumerate(scored_cards, 1):
            card_id = str(card.get("player_id") or "")
            options.append(
                option_cell(
                    row,
                    str(option_index),
                    card,
                    score,
                    player_dir,
                    is_current=card_id == str(row.get("option1_current")),
                    is_auto_top=card_id == auto_top,
                    is_auto_second=card_id == auto_second,
                    is_applied=card_id == applied_player_id,
                )
            )
        options.append(
            option_cell(
                row,
                str(len(scored_cards) + 1),
                None,
                0.0,
                player_dir,
                is_applied=applied_player_id == "0",
            )
        )
        rendered_rows.append(
            f"""
            <tr data-formation-id="{html.escape(row['formation_id'])}"
                data-slot="{html.escape(row['slot'])}"
                data-model-name="{html.escape(row['model_name'])}">
              <td class="row-label">
                <div class="row-index">#{index}</div>
                <strong>{html.escape(row['formation'])} {html.escape(row['year'])}</strong>
                <span>slot {html.escape(row['slot'])}: {html.escape(row['model_name'])}</span>
              </td>
              <td class="ref-cell">
                <img src="{uniform_image}" alt="" width="79" height="87">
                <small>{html.escape(row['uniform_id'])} {html.escape(row['uniform_name'])} {html.escape(row['uniform_year'])}</small>
              </td>
              <td>{''.join(options)}</td>
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
    margin: 20px;
    background: #f5f6f8;
    color: #111827;
  }}
  h1 {{
    margin: 0 0 8px;
    font-size: 22px;
  }}
  .toolbar {{
    position: sticky;
    top: 0;
    z-index: 2;
    display: grid;
    gap: 10px;
    padding: 12px;
    margin: 0 0 14px;
    background: rgba(245, 246, 248, 0.96);
    border: 1px solid #d7dce3;
  }}
  textarea {{
    width: 100%;
    min-height: 132px;
    box-sizing: border-box;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
  }}
  button {{
    width: fit-content;
    padding: 8px 12px;
    border: 1px solid #9aa4b2;
    background: #ffffff;
    color: #111827;
    border-radius: 6px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: #ffffff;
  }}
  th, td {{
    border: 1px solid #d7dce3;
    padding: 8px;
    vertical-align: top;
  }}
  th {{
    position: sticky;
    top: 198px;
    z-index: 1;
    background: #eef1f5;
    text-align: left;
  }}
  .row-label {{
    width: 210px;
  }}
  .row-label strong,
  .row-label span,
  .row-index,
  .ref-cell small {{
    display: block;
  }}
  .row-index,
  small {{
    color: #64748b;
  }}
  .ref-cell {{
    width: 110px;
  }}
  .option-card {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    width: 238px;
    min-height: 112px;
    box-sizing: border-box;
    padding: 6px;
    margin: 0 6px 6px 0;
    border: 2px solid #d7dce3;
    border-radius: 8px;
    background: #ffffff;
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
  .option-meta {{
    display: grid;
    gap: 4px;
  }}
  .option-meta strong {{
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
    width: 116px;
  }}
  .hold-text {{
    font-weight: 700;
  }}
</style>
<h1>{html.escape(title)}</h1>
<div class="toolbar">
  <div>1=current。2以降は同一人物に紐づく全カードIDです。最後の番号は保留。適用済みは applied タグ付き。選んだ行だけ下に出ます。</div>
  <textarea id="answer" readonly placeholder="選択するとここに貼り付け用テキストが生成されます"></textarea>
  <button id="copy" type="button">Copy</button>
</div>
<table>
  <thead>
    <tr><th>Formation</th><th>Ref</th><th>Choices</th></tr>
  </thead>
  <tbody>
    {''.join(rendered_rows)}
  </tbody>
</table>
<script>
  const answer = document.getElementById('answer');
  const copyButton = document.getElementById('copy');

  function updateAnswer() {{
    const lines = ['UNIFORM_CARD_CHOICES', 'formation_id,slot,choice,player_id,model_name'];
    document.querySelectorAll('tbody tr').forEach((row) => {{
      const checked = row.querySelector('input[type="radio"]:checked');
      if (!checked) return;
      const playerId = checked.dataset.playerId || '0';
      lines.push([
        row.dataset.formationId,
        row.dataset.slot,
        checked.value,
        playerId,
        row.dataset.modelName
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
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--overrides-csv", default=str(DEFAULT_OVERRIDES_CSV))
    parser.add_argument("--master-db", default=str(DEFAULT_MASTER_DB))
    parser.add_argument("--uniform-dir", default=str(DEFAULT_UNIFORM_DIR))
    parser.add_argument("--player-dir", default=str(DEFAULT_PLAYER_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--title", default="Model Uniform Card Review")
    parser.add_argument(
        "--only-applied-source",
        default="",
        help="If set, only include rows whose applied card override source matches this value",
    )
    args = parser.parse_args()

    rows = read_csv(args.review_csv)
    applied_overrides = load_applied_overrides(args.overrides_csv)
    if args.only_applied_source:
        rows = [
            row
            for row in rows
            if applied_overrides.get((row.get("formation_id"), row.get("slot")), {}).get("source")
            == args.only_applied_source
        ]
    players = load_players(Path(args.master_db))
    grouped_players = players_by_person(players)
    html_text = build_html(
        rows,
        players,
        grouped_players,
        applied_overrides,
        Path(args.uniform_dir),
        Path(args.player_dir),
        args.title,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")
    print(f"wrote {out} rows={len(rows)}")


if __name__ == "__main__":
    main()
