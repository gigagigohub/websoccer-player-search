#!/usr/bin/env python3
import csv
import datetime as dt
import json
import plistlib
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path('/Users/k.nishimura/work/coding/websoccer-player-search')
ZIP_DIR = Path('/Users/k.nishimura/work/coding/wsc_data/UpdateFile_p40_322')
FILLED_CSV = Path('/Users/k.nishimura/work/coding/wsc_data/UpdateFile_inventory/updatefile_ss_events_filled.csv')

APP_DATA = ROOT / 'app' / 'data.json'
DOCS_DATA = ROOT / 'docs' / 'data.json'

ZIP_RE = re.compile(r'p(\d+)\.zip$')


def to_text(v) -> str:
    if isinstance(v, dt.datetime):
        return v.strftime('%Y-%m-%d %H:%M:%S')
    if v is None:
        return ''
    return str(v)


def parse_player_ids(raw) -> List[int]:
    out: List[int] = []
    for token in str(raw or '').split(','):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            out.append(int(token))
    return out


def load_event_meta() -> Dict[int, dict]:
    out: Dict[int, dict] = {}
    with FILLED_CSV.open('r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                event_id = int(row.get('event_id') or 0)
            except ValueError:
                continue
            if event_id <= 0:
                continue
            out[event_id] = {
                'version': int(row.get('version') or 0),
                'eventId': event_id,
                'type': int(row.get('type') or 0),
                'start': row.get('start') or '',
                'end': row.get('end') or '',
                'name': (row.get('tag_ev5_filled') or row.get('tag_ev5') or '').strip(),
                'nameRaw': (row.get('tag_ev5') or '').strip(),
                'nameSource': (row.get('tag_ev5_source') or '').strip(),
                'notes': row.get('notes_ev4') or '',
                'playerCountMeta': int(row.get('player_id_count') or 0),
            }
    return out


def load_events_from_zips() -> Dict[int, dict]:
    latest: Dict[int, dict] = {}
    for zp in sorted(ZIP_DIR.glob('p*.zip')):
        m = ZIP_RE.search(zp.name)
        if not m:
            continue
        version = int(m.group(1))
        with zipfile.ZipFile(zp) as zf:
            plist_names = [n for n in zf.namelist() if n.endswith('/Resources/PropertyList/ss.plist')]
            if not plist_names:
                continue
            try:
                data = plistlib.loads(zf.read(plist_names[0]))
            except Exception:
                continue

        if not isinstance(data, list):
            continue

        for row in data:
            if not isinstance(row, list) or len(row) < 7:
                continue
            try:
                event_id = int(row[0])
            except Exception:
                continue
            rec = {
                'version': version,
                'eventId': event_id,
                'type': int(row[1]) if str(row[1]).isdigit() else 0,
                'start': to_text(row[2]),
                'end': to_text(row[3]),
                'notes': to_text(row[4]),
                'nameRaw': to_text(row[5]).strip(),
                'playerIds': parse_player_ids(row[6]),
            }
            prev = latest.get(event_id)
            if prev is None or rec['version'] >= prev['version']:
                latest[event_id] = rec
    return latest


def build_scouts() -> Tuple[List[dict], Dict[int, List[dict]]]:
    meta = load_event_meta()
    zips = load_events_from_zips()

    all_event_ids = sorted(set(meta.keys()) | set(zips.keys()))
    scouts: List[dict] = []
    player_history: Dict[int, List[dict]] = {}

    for event_id in all_event_ids:
        m = meta.get(event_id, {})
        z = zips.get(event_id, {})

        name = (m.get('name') or z.get('nameRaw') or '').strip()
        start = m.get('start') or z.get('start') or ''
        end = m.get('end') or z.get('end') or ''
        notes = m.get('notes') or z.get('notes') or ''
        typ = int(m.get('type') or z.get('type') or 0)
        version = int(z.get('version') or m.get('version') or 0)
        player_ids = list(z.get('playerIds') or [])

        scout = {
            'eventId': event_id,
            'name': name,
            'start': start,
            'end': end,
            'type': typ,
            'version': version,
            'notes': notes,
            'nameRaw': (m.get('nameRaw') or z.get('nameRaw') or '').strip(),
            'nameSource': (m.get('nameSource') or '').strip(),
            'playerCount': len(player_ids),
            'playerIds': player_ids,
        }
        scouts.append(scout)

        for idx, pid in enumerate(player_ids, start=1):
            player_history.setdefault(pid, []).append({
                'eventId': event_id,
                'name': name,
                'start': start,
                'end': end,
                'type': typ,
                'version': version,
                'order': idx,
            })

    for pid, rows in player_history.items():
        rows.sort(key=lambda x: (x.get('start') or '', x.get('eventId') or 0), reverse=True)

    scouts.sort(key=lambda x: x.get('eventId', 0), reverse=True)
    return scouts, player_history


def update_data_json(path: Path, scouts: List[dict], history: Dict[int, List[dict]], now_iso: str) -> Tuple[int, int]:
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    players = data.get('players') or []
    changed_to_ss = 0
    linked = 0

    for p in players:
        pid = int(p.get('id') or 0)
        rows = history.get(pid, [])
        if rows:
            linked += 1
            p['scoutHistory'] = rows
            cat = str(p.get('category') or '')
            if cat != 'SS':
                changed_to_ss += 1
                p['category'] = 'SS'
                p['categoryMembership'] = ['SS']
                flags = p.get('flags')
                if not isinstance(flags, dict):
                    flags = {}
                    p['flags'] = flags
                flags['SS'] = True
                flags['CM'] = False
        else:
            if 'scoutHistory' in p:
                del p['scoutHistory']

    data['generatedAt'] = now_iso
    data['scouts'] = scouts

    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    return changed_to_ss, linked


def main() -> None:
    jst = dt.timezone(dt.timedelta(hours=9))
    now = dt.datetime.now(jst)
    now_iso = now.isoformat(timespec='seconds')

    scouts, history = build_scouts()
    app_changed, app_linked = update_data_json(APP_DATA, scouts, history, now_iso)
    docs_changed, docs_linked = update_data_json(DOCS_DATA, scouts, history, now_iso)

    print(f'scout events: {len(scouts)}')
    print(f'players with scout history: {len(history)}')
    print(f'app: linked={app_linked} changed_to_ss={app_changed}')
    print(f'docs: linked={docs_linked} changed_to_ss={docs_changed}')
    print(f'generatedAt: {now_iso}')


if __name__ == '__main__':
    main()
