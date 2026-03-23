#!/usr/bin/env python3
import datetime as dt
import json
import plistlib
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path('/Users/k.nishimura/work/coding/websoccer-player-search')
ZIP_DIR = Path('/Users/k.nishimura/Desktop/UpdateFile_p40_320')

APP_DATA = ROOT / 'app' / 'data.json'
DOCS_DATA = ROOT / 'docs' / 'data.json'

ZIP_RE = re.compile(r'p(\d+)\.zip$')
CM_PLISTS = [
    ('ChallengeMatchList.plist', 'regular'),
    ('ChallengeMatchListByWday.plist', 'weekday'),
    ('ChallengeMatchListTounament.plist', 'tournament'),
]
CATEGORY_ORDER = {'NR': 0, 'CC': 1, 'SS': 2, 'CM': 3, 'CM/SS': 4, 'NA': 5, 'RT': 6}


def _find_member(zf: zipfile.ZipFile, name: str) -> str:
    target = f'/Resources/PropertyList/{name}'
    for member in zf.namelist():
        if member.endswith(target):
            return member
    return ''


def _to_text(v) -> str:
    if isinstance(v, dt.datetime):
        return v.strftime('%Y-%m-%d %H:%M:%S')
    if v is None:
        return ''
    return str(v)


def _extract_present_player_ids(row: dict) -> List[int]:
    out: List[int] = []
    seen = set()
    for item in (row.get('present') or []):
        if not isinstance(item, dict):
            continue
        typ = int(item.get('type') or 0)
        pid = int(item.get('id') or 0)
        if typ != 10 or pid <= 0 or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def _build_cm_data() -> Tuple[List[dict], Dict[int, List[dict]]]:
    latest_events: Dict[int, dict] = {}

    for zp in sorted(ZIP_DIR.glob('p*.zip')):
        m = ZIP_RE.search(zp.name)
        if not m:
            continue
        version = int(m.group(1))
        with zipfile.ZipFile(zp) as zf:
            for plist_name, mode in CM_PLISTS:
                member = _find_member(zf, plist_name)
                if not member:
                    continue
                try:
                    data = plistlib.loads(zf.read(member))
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue

                for row in data:
                    if not isinstance(row, dict):
                        continue
                    event_id = int(row.get('id') or 0)
                    if event_id <= 0:
                        continue
                    player_ids = _extract_present_player_ids(row)
                    if not player_ids:
                        continue

                    record = {
                        'eventId': event_id,
                        'name': _to_text(row.get('name')).strip(),
                        'start': _to_text(row.get('begin')).strip(),
                        'end': _to_text(row.get('end')).strip(),
                        'mode': mode,
                        'version': version,
                        'playerIds': player_ids,
                    }
                    prev = latest_events.get(event_id)
                    if prev is None or record['version'] >= prev['version']:
                        latest_events[event_id] = record

    events = sorted(
        latest_events.values(),
        key=lambda x: (x.get('start') or '', int(x.get('eventId') or 0)),
        reverse=True,
    )

    history: Dict[int, List[dict]] = {}
    for event in events:
        for idx, pid in enumerate(event.get('playerIds') or [], start=1):
            history.setdefault(int(pid), []).append({
                'eventId': int(event.get('eventId') or 0),
                'name': event.get('name') or '',
                'start': event.get('start') or '',
                'end': event.get('end') or '',
                'mode': event.get('mode') or '',
                'version': int(event.get('version') or 0),
                'order': idx,
            })

    for pid, rows in history.items():
        rows.sort(key=lambda x: ((x.get('start') or ''), int(x.get('eventId') or 0)), reverse=True)

    event_rows = []
    for event in events:
        event_rows.append({
            'eventId': int(event.get('eventId') or 0),
            'name': event.get('name') or '',
            'start': event.get('start') or '',
            'end': event.get('end') or '',
            'mode': event.get('mode') or '',
            'version': int(event.get('version') or 0),
            'playerCount': len(event.get('playerIds') or []),
            'playerIds': [int(x) for x in (event.get('playerIds') or [])],
        })

    return event_rows, history


def _normalize_membership(membership, category: str) -> List[str]:
    out = []
    if isinstance(membership, list):
        out.extend(str(x) for x in membership if x)
    if category and category not in out:
        out.append(category)
    unique = []
    seen = set()
    for x in out:
        if x in seen:
            continue
        seen.add(x)
        unique.append(x)
    unique.sort(key=lambda c: CATEGORY_ORDER.get(c, 999))
    return unique


def _has_ss_marker(player: dict) -> bool:
    category = str(player.get('category') or '')
    if category in ('SS', 'CM/SS'):
        return True
    flags = player.get('flags') if isinstance(player.get('flags'), dict) else {}
    if bool(flags.get('SS')):
        return True
    scout_history = player.get('scoutHistory')
    return isinstance(scout_history, list) and len(scout_history) > 0


def _update_data_json(path: Path, cm_events: List[dict], cm_history: Dict[int, List[dict]], now_iso: str) -> Tuple[int, int, int]:
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    players = data.get('players') or []
    linked = 0
    changed_to_cm = 0
    changed_to_cmss = 0

    for p in players:
        pid = int(p.get('id') or 0)
        rows = cm_history.get(pid, [])
        if rows:
            linked += 1
            p['cmHistory'] = rows

            has_ss = _has_ss_marker(p)
            next_category = 'CM/SS' if has_ss else 'CM'
            prev_category = str(p.get('category') or '')
            if prev_category != next_category:
                if next_category == 'CM/SS':
                    changed_to_cmss += 1
                else:
                    changed_to_cm += 1
            p['category'] = next_category
            p['categoryMembership'] = _normalize_membership(p.get('categoryMembership'), next_category)

            flags = p.get('flags') if isinstance(p.get('flags'), dict) else {}
            flags['CM'] = True
            flags['SS'] = has_ss
            p['flags'] = flags
        else:
            if 'cmHistory' in p:
                del p['cmHistory']

    data['generatedAt'] = now_iso
    data['cmEvents'] = cm_events

    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    return linked, changed_to_cm, changed_to_cmss


def main() -> None:
    jst = dt.timezone(dt.timedelta(hours=9))
    now = dt.datetime.now(jst)
    now_iso = now.isoformat(timespec='seconds')

    cm_events, cm_history = _build_cm_data()
    app_linked, app_to_cm, app_to_cmss = _update_data_json(APP_DATA, cm_events, cm_history, now_iso)
    docs_linked, docs_to_cm, docs_to_cmss = _update_data_json(DOCS_DATA, cm_events, cm_history, now_iso)

    print(f'cm events: {len(cm_events)}')
    print(f'players with cm history: {len(cm_history)}')
    print(f'app: linked={app_linked} changed_to_cm={app_to_cm} changed_to_cmss={app_to_cmss}')
    print(f'docs: linked={docs_linked} changed_to_cm={docs_to_cm} changed_to_cmss={docs_to_cmss}')
    print(f'generatedAt: {now_iso}')


if __name__ == '__main__':
    main()
