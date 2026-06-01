#!/usr/bin/env python3
import csv
import datetime as dt
import json
import argparse
import plistlib
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path('/Users/gigagigo/Codex/WebSoccer/websoccer-player-search')
ZIP_DIR = Path('/Users/gigagigo/Codex/WebSoccer/wsc_data/UpdateFile_p40_322')
FILLED_CSV = Path('/Users/gigagigo/Codex/WebSoccer/wsc_data/UpdateFile_inventory/updatefile_ss_events_filled.csv')

APP_DATA = ROOT / 'app' / 'data.json'

ZIP_RE = re.compile(r'p(\d+)\.zip$')

BLANK_MISSING_TITLE = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Update SS scout event list and player scout history in app/data.json.')
    p.add_argument('--zip-dir', default=str(ZIP_DIR), help='UpdateFile_pX_Y directory containing p*.zip files.')
    p.add_argument('--filled-csv', default=str(FILLED_CSV), help='Manual SS event title CSV.')
    p.add_argument('--app-data', default=str(APP_DATA), help='Target app/data.json path.')
    p.add_argument(
        '--blank-missing-title',
        action='store_true',
        help='Keep event name blank when it is not present in the manual CSV.',
    )
    return p.parse_args()


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
    if not FILLED_CSV.exists():
        return out
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


def load_existing_scout_meta(path: Path) -> Dict[int, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    out: Dict[int, dict] = {}
    for row in data.get('scouts') or []:
        try:
            event_id = int(row.get('eventId') or 0)
        except Exception:
            continue
        if event_id <= 0:
            continue
        out[event_id] = {
            'name': (row.get('name') or '').strip(),
            'nameRaw': (row.get('nameRaw') or '').strip(),
            'nameSource': (row.get('nameSource') or '').strip(),
            'shopButtonImage': row.get('shopButtonImage') or '',
        }
    return out


def collect_scout_button_event_ids(app_dir: Path) -> Set[int]:
    ids: Set[int] = set()
    button_dir = app_dir / 'images' / 'Shop' / 'btn'
    if not button_dir.exists():
        return ids
    for image_path in button_dir.glob('ss_btn_*.png'):
        m = re.fullmatch(r'ss_btn_(\d+)\.png', image_path.name)
        if m:
            ids.add(int(m.group(1)))
    return ids


def collect_player_image_ids(app_dir: Path) -> Set[int]:
    ids: Set[int] = set()
    for kind in ('static', 'action'):
        image_dir = app_dir / 'images' / 'chara' / 'players' / kind
        if not image_dir.exists():
            continue
        for image_path in image_dir.glob('*.gif'):
            try:
                ids.add(int(image_path.stem))
            except ValueError:
                continue
    return ids


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


def build_scouts(
    existing_meta: Optional[Dict[int, dict]] = None,
    scout_button_event_ids: Optional[Set[int]] = None,
) -> Tuple[List[dict], Dict[int, List[dict]]]:
    meta = load_event_meta()
    zips = load_events_from_zips()
    existing_meta = existing_meta or {}
    scout_button_event_ids = scout_button_event_ids or set()

    all_event_ids = sorted(set(meta.keys()) | set(zips.keys()))
    scouts: List[dict] = []
    player_history: Dict[int, List[dict]] = {}

    for event_id in all_event_ids:
        m = meta.get(event_id, {})
        z = zips.get(event_id, {})
        existing = existing_meta.get(event_id, {})

        fallback_name = '' if BLANK_MISSING_TITLE else z.get('nameRaw')
        name = (m.get('name') or existing.get('name') or fallback_name or '').strip()
        start = m.get('start') or z.get('start') or ''
        end = m.get('end') or z.get('end') or ''
        notes = m.get('notes') or z.get('notes') or ''
        typ = int(m.get('type') or z.get('type') or 0)
        version = int(z.get('version') or m.get('version') or 0)
        player_ids = list(z.get('playerIds') or [])
        shop_button_image = existing.get('shopButtonImage') or (
            f'./images/Shop/btn/ss_btn_{event_id}.png' if event_id in scout_button_event_ids else ''
        )

        scout = {
            'eventId': event_id,
            'name': name,
            'start': start,
            'end': end,
            'type': typ,
            'version': version,
            'notes': notes,
            'nameRaw': (m.get('nameRaw') or z.get('nameRaw') or existing.get('nameRaw') or '').strip(),
            'nameSource': (m.get('nameSource') or existing.get('nameSource') or '').strip(),
            'playerCount': len(player_ids),
            'playerIds': player_ids,
            'shopButtonImage': shop_button_image,
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


def update_data_json(
    path: Path,
    scouts: List[dict],
    history: Dict[int, List[dict]],
    now_iso: str,
    image_available_player_ids: Optional[Set[int]] = None,
) -> Tuple[int, int]:
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    players = data.get('players') or []
    changed_to_ss = 0
    linked = 0
    image_available_player_ids = image_available_player_ids or set()

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
            p['categoryPending'] = False
            p['imagePending'] = pid not in image_available_player_ids
        else:
            if 'scoutHistory' in p:
                del p['scoutHistory']

    data['generatedAt'] = now_iso
    data['scouts'] = scouts

    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return changed_to_ss, linked


def main() -> None:
    global ZIP_DIR, FILLED_CSV, APP_DATA, BLANK_MISSING_TITLE
    args = parse_args()
    ZIP_DIR = Path(args.zip_dir).expanduser().resolve()
    FILLED_CSV = Path(args.filled_csv).expanduser().resolve()
    APP_DATA = Path(args.app_data).expanduser().resolve()
    BLANK_MISSING_TITLE = bool(args.blank_missing_title)

    jst = dt.timezone(dt.timedelta(hours=9))
    now = dt.datetime.now(jst)
    now_iso = now.isoformat(timespec='seconds')

    app_dir = APP_DATA.parent
    existing_meta = load_existing_scout_meta(APP_DATA)
    scout_button_event_ids = collect_scout_button_event_ids(app_dir)
    image_available_player_ids = collect_player_image_ids(app_dir)
    scouts, history = build_scouts(existing_meta, scout_button_event_ids)
    app_changed, app_linked = update_data_json(APP_DATA, scouts, history, now_iso, image_available_player_ids)

    print(f'scout events: {len(scouts)}')
    print(f'players with scout history: {len(history)}')
    print(f'app: linked={app_linked} changed_to_ss={app_changed}')
    print(f'generatedAt: {now_iso}')


if __name__ == '__main__':
    main()
