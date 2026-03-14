#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import zipfile
from collections import OrderedDict

METRIC_MAP = OrderedDict([
    ('スピ', 'SPD'),
    ('テク', 'TEC'),
    ('パワ', 'PWR'),
    ('スタ', 'STM'),
    ('ラフ', 'RGH'),
    ('個性', 'CST'),
    ('人気', 'POP'),
    ('PK', 'PK'),
    ('FK', 'FK'),
    ('CK', 'CK'),
    ('CP', 'CAP'),
    ('知性', 'INTE'),
    ('感性', 'SEN'),
    ('個人', 'STDP'),
    ('組織', 'TMP'),
])

POS_TYPE_MAP = {
    1: 'FW',
    2: 'MF',
    3: 'DF',
    4: 'GK',
}


def season_label(raw_szn_no: int) -> str:
    return f"{raw_szn_no + 1}期"


def to_grid(param: dict, is_gk: bool):
    r = lambda n: int(param.get(f'R{n}', 0) or 0)
    gk_left = r(13) if is_gk else None
    gk_right = r(15) if is_gk else None
    return [
        [r(1), r(2), r(3)],
        [r(4), r(5), r(6)],
        [r(7), r(8), r(9)],
        [r(10), r(11), r(12)],
        [gk_left, r(14), gk_right],
    ]


def make_periods(params: list):
    rows = sorted(params, key=lambda x: int(x.get('SZN_NO', 0) or 0))
    periods = []
    for row in rows:
        metrics = {jp: int(row.get(en, 0) or 0) for jp, en in METRIC_MAP.items()}
        periods.append({
            'season': season_label(int(row.get('SZN_NO', 0) or 0)),
            'metrics': metrics,
        })
    return periods


def pick_peak_metrics(periods: list):
    if not periods:
        return {k: 0 for k in METRIC_MAP.keys()}, 0

    def total(m):
        return int(m.get('スピ', 0)) + int(m.get('テク', 0)) + int(m.get('パワ', 0))

    best_total = max(total(p['metrics']) for p in periods)
    peak = next((p for p in periods if total(p['metrics']) == best_total), periods[0])
    return dict(peak['metrics']), best_total


def min_max_metrics(periods: list):
    if not periods:
        z = {k: 0 for k in METRIC_MAP.keys()}
        return z, z
    max_m = {}
    min_m = {}
    for k in METRIC_MAP.keys():
        vals = [int(p['metrics'].get(k, 0)) for p in periods]
        max_m[k] = max(vals)
        min_m[k] = min(vals)
    return max_m, min_m


def make_heatmaps(params: list, pos_type: int):
    rows = sorted(params, key=lambda x: int(x.get('SZN_NO', 0) or 0))
    is_gk = (int(pos_type) == 4)

    by_season = OrderedDict()
    segment_list = []
    prev_grid = None
    seg_start = None

    for row in rows:
        raw = int(row.get('SZN_NO', 0) or 0)
        label = season_label(raw)
        grid = to_grid(row, is_gk)
        by_season[label] = grid

        if prev_grid is None or grid != prev_grid:
            seg_start = raw + 1
            segment_list.append({
                'label': f'{seg_start}期〜',
                'start': seg_start,
                'grid': grid,
            })
            prev_grid = grid

    return segment_list, by_season


def extract_images(resources_zip: str, out_static_dir: str, out_action_dir: str):
    if os.path.exists(out_static_dir):
        shutil.rmtree(out_static_dir)
    if os.path.exists(out_action_dir):
        shutil.rmtree(out_action_dir)
    os.makedirs(out_static_dir, exist_ok=True)
    os.makedirs(out_action_dir, exist_ok=True)

    static_prefix = 'Resources/img/chara/players/static/'
    action_prefix = 'Resources/img/chara/players/action/'

    count_static = 0
    count_action = 0

    with zipfile.ZipFile(resources_zip, 'r') as zf:
        for name in zf.namelist():
            if name.startswith(static_prefix) and name.endswith('@2x.gif'):
                sid = os.path.basename(name).replace('@2x.gif', '')
                if sid.isdigit():
                    with zf.open(name) as src, open(os.path.join(out_static_dir, f'{sid}.gif'), 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    count_static += 1
            elif name.startswith(action_prefix) and name.endswith('@2x.gif'):
                sid = os.path.basename(name).replace('@2x.gif', '')
                if sid.isdigit():
                    with zf.open(name) as src, open(os.path.join(out_action_dir, f'{sid}.gif'), 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    count_action += 1

    return count_static, count_action


def build_nation_lookup(sqlite_path: str):
    nation_lookup = {}
    if sqlite_path and os.path.exists(sqlite_path):
        conn = sqlite3.connect(sqlite_path)
        cur = conn.cursor()
        cur.execute("SELECT ZNATION_ID, ZNAME FROM ZMONATION")
        for nid, name in cur.fetchall():
            try:
                nation_lookup[int(nid)] = str(name or "")
            except (TypeError, ValueError):
                continue
        conn.close()
    return nation_lookup


def convert_players(input_players: list, nation_lookup: dict):
    out = []
    for src in sorted(input_players, key=lambda p: int(p['playerId'])):
        pid = int(src['playerId'])
        p = src.get('player', {})
        params = src.get('params', [])
        category = src.get('category') or 'NR'
        info = src.get('info') or {}
        nation_id = int(p.get('NATION_ID', 0) or 0)
        nation_name = nation_lookup.get(nation_id) or f"国籍ID:{nation_id}"

        periods = make_periods(params)
        metric_values, best_total = pick_peak_metrics(periods)
        max_metrics, min_metrics = min_max_metrics(periods)
        segments, by_season = make_heatmaps(params, int(p.get('POS_TYPE', 0) or 0))

        flags = {
            'CM': category in ('CM', 'CM/SS'),
            'SS': category in ('SS', 'CM/SS'),
        }

        out.append({
            'id': pid,
            'name': p.get('NAME') or p.get('FULLNAME') or f'ID{pid}',
            'url': f'https://caselli.websoccer.info/players/{pid}',
            'periods': periods,
            'metricValues': metric_values,
            'maxMetrics': max_metrics,
            'minMetrics': min_metrics,
            'bestTotal': best_total,
            'flags': flags,
            'position': POS_TYPE_MAP.get(int(p.get('POS_TYPE', 0) or 0), 'MF'),
            'category': category,
            'categoryMembership': src.get('categoryMembership') or [category],
            'rate': int(p.get('RARITY', 0) or 0),
            'positionHeatmaps': segments,
            'positionHeatmapBySeason': by_season,
            'fullName': p.get('FULLNAME') or p.get('NAME') or '',
            'nationality': nation_name,
            'nationId': nation_id,
            'playType': info.get('PLAY_TYPE') or '',
            'height': int(p.get('TALL', 0) or 0),
            'weight': int(p.get('WEIGHT', 0) or 0),
            'description': info.get('DESCRIPTION_TEXT') or '',
        })
    return out


def main():
    ap = argparse.ArgumentParser(description='Import iOS source data/images into site app/docs')
    ap.add_argument('--input-json', default='app/prepared/players_ios_source_categorized_lifecycle.json')
    ap.add_argument('--resources-zip', required=True)
    ap.add_argument('--app-dir', default='app')
    ap.add_argument('--docs-dir', default='docs')
    ap.add_argument('--sqlite-path', default='')
    args = ap.parse_args()

    with open(args.input_json, 'r', encoding='utf-8') as f:
        src = json.load(f)

    nation_lookup = build_nation_lookup(args.sqlite_path)
    players = convert_players(src.get('players', []), nation_lookup)

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds')
    out_data = {
        'source': 'ios-product-sqlite+resources-p313',
        'generatedAt': now,
        'metrics': list(METRIC_MAP.keys()),
        'players': players,
    }

    app_data_path = os.path.join(args.app_dir, 'data.json')
    docs_data_path = os.path.join(args.docs_dir, 'data.json')

    with open(app_data_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, ensure_ascii=False)
    with open(docs_data_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, ensure_ascii=False)

    app_static = os.path.join(args.app_dir, 'images/chara/players/static')
    app_action = os.path.join(args.app_dir, 'images/chara/players/action')
    docs_static = os.path.join(args.docs_dir, 'images/chara/players/static')
    docs_action = os.path.join(args.docs_dir, 'images/chara/players/action')

    app_counts = extract_images(args.resources_zip, app_static, app_action)
    docs_counts = extract_images(args.resources_zip, docs_static, docs_action)

    print('Wrote', app_data_path)
    print('Wrote', docs_data_path)
    print('App images static/action', app_counts)
    print('Docs images static/action', docs_counts)
    print('Players', len(players), 'generatedAt', now)


if __name__ == '__main__':
    main()
