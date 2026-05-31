#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path


DEFAULT_INDEX = (
    Path.home()
    / "Codex"
    / "WebSoccer"
    / "websoccer_local_backups"
    / "account_transfer"
    / "_index"
    / "players_index.json"
)
DEFAULT_OUT = DEFAULT_INDEX.parent / "rosters.html"
DEFAULT_APP_DIR = Path(__file__).resolve().parents[1] / "app"
TEAM_ORDER = {
    10052201: 10,  # はたのっちFC 99
    9710901: 20,  # FC虹
    9737901: 30,  # エドリアーノ強くねか
    9725201: 40,  # 中村サッカー倶楽部
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build an image roster report for stored local WebSoccer profiles.")
    p.add_argument("--index-json", default=str(DEFAULT_INDEX))
    p.add_argument("--app-dir", default=str(DEFAULT_APP_DIR))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    return p.parse_args()


def load_site_players(app_dir: Path) -> dict[int, dict]:
    data_path = app_dir / "data.json"
    if not data_path.exists():
        return {}
    data = json.loads(data_path.read_text(encoding="utf-8"))
    return {int(p["id"]): p for p in data.get("players") or [] if p.get("id") is not None}


def ensure_image_symlink(out_dir: Path, app_dir: Path) -> str:
    link = out_dir / "app-images"
    target = app_dir / "images"
    if link.exists() or link.is_symlink():
        if link.is_symlink() and Path(os.readlink(link)) == target:
            return "app-images"
        if link.resolve() == target.resolve():
            return "app-images"
        raise RuntimeError(f"image link path already exists and points elsewhere: {link}")
    link.symlink_to(target, target_is_directory=True)
    return "app-images"


def player_image(app_dir: Path, image_root: str, player_id: int | str | None) -> tuple[str, str]:
    if player_id is None:
        return f"{image_root}/chara/players/pending.svg", "missing"
    static = app_dir / "images" / "chara" / "players" / "static" / f"{player_id}.gif"
    action = app_dir / "images" / "chara" / "players" / "action" / f"{player_id}.gif"
    if static.exists():
        return f"{image_root}/chara/players/static/{player_id}.gif", "static"
    if action.exists():
        return f"{image_root}/chara/players/action/{player_id}.gif", "action"
    return f"{image_root}/chara/players/pending.svg", "missing"


def get_category(player: dict | None) -> str:
    if not player:
        return ""
    if player.get("categoryPending"):
        return ""
    if not player.get("category") and isinstance(player.get("categoryMembership"), list) and not player.get("categoryMembership"):
        return ""
    if player.get("retired") and player.get("category") == "RT":
        return "NR"
    if player.get("category"):
        return str(player["category"])
    flags = player.get("flags") or {}
    has_cm = bool(flags.get("CM"))
    has_ss = bool(flags.get("SS"))
    if has_cm and has_ss:
        return "CM/SS"
    if has_cm:
        return "CM"
    if has_ss:
        return "SS"
    return "NR"


def has_category_membership(player: dict | None, category: str) -> bool:
    if not player:
        return False
    return category in [str(x) for x in (player.get("categoryMembership") or [])]


def type_class_by_player(player: dict | None) -> str:
    type_label = get_category(player)
    if type_label == "NR":
        rate = int(player.get("rate") or 0) if player else 0
        if rate == 7:
            return "cat-nr-r7"
        if rate in {5, 6}:
            return "cat-nr-r56"
        if rate == 4:
            return "cat-nr-r4"
        return "cat-nr-r13"
    if type_label == "SS":
        return "cat-ss"
    if type_label == "CM":
        return "cat-cm"
    if type_label == "CM/SS":
        return "cat-cmss"
    if type_label == "CC":
        return "cat-cc"
    return "cat-na"


def category_badges(player: dict | None) -> str:
    type_label = get_category(player)
    if not type_label:
        return ""
    if type_label == "CM/SS":
        return '<span class="type-badge cat-ss">SS</span><span class="type-badge cat-cm">CM</span>'
    if type_label == "NR" and has_category_membership(player, "CM"):
        return f'<span class="type-badge {type_class_by_player(player)}">NR</span><span class="type-badge cat-cm">CM</span>'
    return f'<span class="type-badge {type_class_by_player(player)}">{html.escape(type_label)}</span>'


def pos_class(position: str) -> str:
    pos = (position or "").strip().upper()
    if pos in {"GK", "DF", "MF", "FW"}:
        return f"pos-{pos.lower()}"
    return "pos-na"


def metric_chip(label: str, value: object, klass: str) -> str:
    text = "-" if value is None or value == "" else str(value)
    return (
        f'<span class="metric-chip {klass}">'
        f'<span class="metric-key">{html.escape(label)}</span>'
        f'<span class="metric-num">{html.escape(text)}</span>'
        "</span>"
    )


def main() -> int:
    args = parse_args()
    index_path = Path(args.index_json).expanduser().resolve()
    app_dir = Path(args.app_dir).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    site_players = load_site_players(app_dir)
    image_root = ensure_image_symlink(out.parent, app_dir)

    by_team: dict[tuple[str, int, str, int], list[dict]] = {}
    for row in data.get("rows") or []:
        key = (
            str(row.get("teamName") or ""),
            int(row.get("teamId") or 0),
            str(row.get("ownerName") or ""),
            int(row.get("teamSeason") or 0),
        )
        by_team.setdefault(key, []).append(row)

    css = """
    :root { color-scheme: dark; --bg: #090c13; --panel: #121827; --panel2: #172035; --text: #e1e9ff; --sub: #8ea1c8; --line: #2a364f; --head: #1a2740; --brand: #3f7fff; }
    * { box-sizing: border-box; }
    body { position: relative; isolation: isolate; font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif; margin: 0; padding: 20px; background: var(--bg); color: var(--text); }
    body::before { content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none; background-color: var(--bg); background-image: radial-gradient(circle at 15% -10%, rgba(73,119,214,.30) 0, transparent 45%), radial-gradient(circle at 95% 5%, rgba(32,54,31,.25) 0, transparent 35%); background-repeat: no-repeat; background-size: 100% 2400px; }
    h1 { font-size: 22px; margin: 0 0 14px; letter-spacing: 0; }
    h2 { font-size: 17px; margin: 26px 0 6px; color: #f3f7ff; letter-spacing: 0; }
    .meta { color: var(--sub); font-size: 12px; margin-bottom: 8px; }
    .roster { width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; background: rgba(18,24,39,.96); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; box-shadow: 0 10px 28px rgba(0,0,0,.18); }
    .roster th { background: linear-gradient(180deg, #20304b 0%, #172235 100%); color: #bcd0f4; font-size: 11px; font-weight: 800; text-align: left; padding: 5px 6px; border-bottom: 1px solid #31486e; white-space: nowrap; }
    .roster td { padding: 3px 6px; border-bottom: 1px solid rgba(42,54,79,.72); vertical-align: middle; font-size: 12px; }
    .roster tbody tr:nth-child(even) { background: rgba(255,255,255,.018); }
    .roster tbody tr:hover { background: #1a2740; }
    .roster tr:last-child td { border-bottom: 0; }
    .no { width: 34px; text-align: right; color: var(--sub); }
    .pic { width: 50px; }
    .portrait { width: 42px; height: 38px; overflow: hidden; display: flex; align-items: flex-start; justify-content: center; }
    .portrait img { width: 42px; height: 54px; object-fit: contain; object-position: top center; display: block; transform: translateY(-1px); }
    .player-name { min-width: 0; }
    .name { font-weight: 800; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.25; }
    .compact { width: 64px; white-space: nowrap; }
    .catcol { width: 76px; white-space: nowrap; }
    .term { width: 58px; white-space: nowrap; }
    .pid { width: 68px; color: var(--sub); white-space: nowrap; }
    .params { width: 162px; white-space: nowrap; }
    .badge { display: inline-block; border: 1px solid #33466d; border-radius: 999px; padding: 1px 6px; margin-right: 3px; background: #1a2740; color: #dce8ff; font-size: 10px; line-height: 1.45; }
    .type-badge { display: inline-block; min-width: 24px; text-align: center; border: 0; border-radius: 5px; padding: 1px 5px; margin-right: 3px; color: #fff; font-weight: 800; font-size: 10px; line-height: 1.45; text-shadow: 0 1px 1px rgba(0,0,0,.25); }
    .pos-badge { display: inline-block; min-width: 26px; text-align: center; border: 0; border-radius: 6px; padding: 1px 6px; color: #fff; font-size: 10px; font-weight: 800; line-height: 1.45; letter-spacing: .02em; text-shadow: 0 1px 1px rgba(0,0,0,.25); }
    .pos-gk { background: linear-gradient(180deg, #596176 0%, #303749 100%); }
    .pos-df { background: linear-gradient(180deg, #4fb2ff 0%, #1f2ea7 100%); }
    .pos-mf { background: linear-gradient(180deg, #67d847 0%, #1f7d39 100%); }
    .pos-fw { background: linear-gradient(180deg, #ff6542 0%, #b82214 100%); }
    .pos-na { background: linear-gradient(180deg, #596176 0%, #303749 100%); }
    .metric-chip { display: inline-grid; grid-template-columns: auto 2ch; align-items: center; gap: 3px; width: 48px; margin-right: 3px; padding: 1px 4px; border: 1px solid #30415d; border-radius: 7px; background: #162136; font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }
    .metric-chip .metric-key { color: var(--sub); font-size: 9px; line-height: 1; font-weight: 800; }
    .metric-chip .metric-num { color: #ecf2ff; font-size: 12px; line-height: 1; font-weight: 800; font-style: italic; text-align: right; }
    .metric-chip.m-speed { border-color: rgba(31,46,167,.78); box-shadow: inset 3px 0 0 #1f2ea7; }
    .metric-chip.m-tech { border-color: rgba(31,125,57,.75); box-shadow: inset 3px 0 0 #1f7d39; }
    .metric-chip.m-power { border-color: rgba(184,34,20,.75); box-shadow: inset 3px 0 0 #b82214; }
    .cat-nr-r13 { color: #202b3a; text-shadow: none; background: linear-gradient(180deg, #dbe2ec 0%, #bcc8d8 100%); box-shadow: inset 0 1px 0 rgba(246,249,255,.62), inset 0 -1px 0 rgba(120,133,152,.34), 0 0 0 1px rgba(108,123,145,.42); }
    .cat-nr-r4 { color: #2f1f12; text-shadow: 0 1px 0 rgba(255,228,204,.45); background: linear-gradient(180deg, rgba(255,255,255,.38) 0%, rgba(255,255,255,0) 22%), linear-gradient(180deg, #e4ae7c 0%, #c47d3c 46%, #7f4418 100%); box-shadow: inset 0 1px 0 rgba(255,229,200,.62), inset 0 -1px 0 rgba(67,34,11,.5), 0 0 0 1px rgba(114,63,25,.55); }
    .cat-nr-r56 { color: #1b2332; text-shadow: 0 1px 0 rgba(244,248,255,.58); background: linear-gradient(180deg, rgba(255,255,255,.52) 0%, rgba(255,255,255,0) 24%), linear-gradient(180deg, #c8cfdd 0%, #8b98ad 44%, #4f5b71 100%); box-shadow: inset 0 1px 0 rgba(242,247,255,.62), inset 0 -1px 0 rgba(39,48,67,.56), 0 0 0 1px rgba(79,92,117,.66); }
    .cat-nr-r7 { color: #3e2f0e; text-shadow: 0 1px 0 rgba(255,246,201,.58); background: linear-gradient(180deg, rgba(255,255,255,.42) 0%, rgba(255,255,255,0) 24%), linear-gradient(180deg, #ffeaa4 0%, #e5bc45 42%, #bb8920 100%); box-shadow: inset 0 1px 0 rgba(255,246,197,.78), inset 0 -1px 0 rgba(102,69,9,.45), 0 0 0 1px rgba(173,126,22,.52); }
    .cat-ss { background-color: #5d2cc0; background-image: linear-gradient(180deg, rgba(255,255,255,.24) 0%, rgba(255,255,255,.03) 22%, rgba(0,0,0,0) 48%, rgba(0,0,0,.14) 100%), url("app-images/badges/ss-category-badge-bg.png?v=20260504-ssbadge6"); background-position: center; background-repeat: no-repeat; background-size: 100% 100%; box-shadow: inset 0 1px 0 rgba(255,255,255,.5), inset 0 -1px 0 rgba(39,18,91,.5), 0 0 0 1px rgba(104,68,178,.5); }
    .cat-cm { background: linear-gradient(180deg, #63b5e8 0%, #2f6fb3 100%); }
    .cat-cmss { color: #fff7d1; background: linear-gradient(180deg, #ffd56b 0%, #d79b1b 55%, #9b6600 100%); }
    .cat-cc { color: #ffde78; background: linear-gradient(180deg, #2a2a2f 0%, #101114 58%, #050507 100%); }
    """
    parts = [
        "<!doctype html>",
        '<html lang="ja"><head><meta charset="utf-8">',
        "<title>WebSoccer Local Rosters</title>",
        f"<style>{css}</style></head><body>",
        "<h1>WebSoccer Local Rosters</h1>",
        f'<div class="meta">Source: {html.escape(str(index_path))}</div>',
    ]
    def team_sort_key(item: tuple[tuple[str, int, str, int], list[dict]]) -> tuple[int, str]:
        (team_name, team_id, _owner, _season), _rows = item
        return (TEAM_ORDER.get(team_id, 999), team_name)

    for (team_name, team_id, owner, season), rows in sorted(by_team.items(), key=team_sort_key):
        parts.append(f"<h2>{html.escape(team_name)}</h2>")
        parts.append(
            f'<div class="meta">team_id={team_id} / owner={html.escape(owner)} / season={season} / players={len(rows)}</div>'
        )
        parts.append('<table class="roster">')
        parts.append(
            "<thead><tr>"
            '<th class="no">#</th><th class="pic"></th><th class="compact">ポジ</th><th class="catcol">カテゴリ</th>'
            '<th>選手</th><th class="term">期数</th><th class="params">スピ/テク/パワ</th><th class="pid">ID</th>'
            "</tr></thead><tbody>"
        )
        for row in sorted(rows, key=lambda r: int(r.get("rosterNo") or 0)):
            player_id = row.get("playerId")
            site_player = site_players.get(int(player_id or 0))
            src, img_kind = player_image(app_dir, image_root, player_id)
            name = html.escape(str(row.get("name") or ""))
            full = html.escape(str(row.get("fullName") or ""))
            badges = category_badges(site_player)
            position = html.escape(str((site_player or {}).get("position") or ""))
            power = html.escape(str(row.get("power") if row.get("power") is not None else ""))
            technique = html.escape(str(row.get("technique") if row.get("technique") is not None else ""))
            speed = html.escape(str(row.get("speed") if row.get("speed") is not None else ""))
            pos_raw = str((site_player or {}).get("position") or "")
            pos_badge = f'<span class="pos-badge {pos_class(pos_raw)}">{html.escape(pos_raw)}</span>'
            param_html = (
                metric_chip("スピ", row.get("speed"), "m-speed")
                + metric_chip("テク", row.get("technique"), "m-tech")
                + metric_chip("パワ", row.get("power"), "m-power")
            )
            parts.append(
                "<tr>"
                f'<td class="no">{int(row.get("rosterNo") or 0)}</td>'
                f'<td class="pic"><div class="portrait"><img src="{html.escape(src)}" alt="{name}" title="img {img_kind}"></div></td>'
                f'<td class="compact">{pos_badge}</td>'
                f'<td class="catcol">{badges}</td>'
                f'<td class="player-name"><div class="name">{name}</div></td>'
                f'<td class="term"><span class="badge">{html.escape(str(row.get("termNo") or ""))}期目</span></td>'
                f'<td class="params">{param_html}</td>'
                f'<td class="pid">{html.escape(str(row.get("playerId") or ""))}</td>'
                "</tr>"
            )
        parts.append("</tbody></table>")
    parts.append("</body></html>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"[DONE] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
