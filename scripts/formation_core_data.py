"""Validated smartphone formation definitions supplied separately from app DB/ZIP."""
import json
from pathlib import Path

DEFAULT_SNAPSHOT = Path(__file__).resolve().parents[1] / 'data' / 'formation_core_data.json'


def validate_payload(payload):
    if payload.get('code') != '000' or not payload.get('formations'):
        raise ValueError('Formation API did not return successful nonempty definitions')
    seen = set()
    for row in payload['formations']:
        fid = row['formation_id']
        if not isinstance(fid, int) or fid <= 0 or fid in seen:
            raise ValueError('Invalid or duplicate formation ID')
        seen.add(fid)
        if not all(row.get(k) for k in ('name', 'system', 'year', 'description', 'subtitle')):
            raise ValueError('Incomplete formation definition')
        positions = row['position_info']
        if len(positions) != 11 or {p['pos'] for p in positions} != set(range(1, 12)):
            raise ValueError('Formation must have exactly eleven unique positions')
        for pos in positions:
            if not all(isinstance(pos[k], (int, float)) for k in ('x', 'y')):
                raise ValueError('Invalid position coordinates')
        keys = row['keypos']
        if len(keys) != 4 or {k['keypos'] for k in keys} != {1, 2, 3, 4}:
            raise ValueError('Formation must have four ranked key positions')
        for key in keys:
            if key['pos'] not in range(1, 12) or not key.get('description'):
                raise ValueError('Invalid key position')
        for key in ('spd', 'tec', 'pwr', 'off', 'def', 'mid', 'ttl', 'stm', 'dif'):
            if not isinstance(row[key], int):
                raise ValueError('Invalid formation parameter')
    return payload['formations']


def overlay_sources(src, payload):
    rows = validate_payload(payload)
    ids = {r['formation_id'] for r in rows}
    out = dict(src)
    out["core_formation_ids"] = ids
    for group in ('formation', 'formation_info', 'formation_pos', 'formation_key'):
        out[group] = [r for r in src.get(group, []) if int(r['ZFORMATION_ID']) not in ids]
    for r in rows:
        base = {'ZFORMATION_ID': r['formation_id']}
        out['formation'].append({**base, **{'Z'+k.upper(): r[k] for k in ('name', 'year', 'system', 'stride')}})
        out['formation_info'].append({**base, **{'Z'+k.upper(): r[k] for k in ('spd', 'tec', 'pwr', 'off', 'def', 'mid', 'ttl', 'stm', 'dif')}, 'ZDESCRIPTION_TEXT': r['description'], 'ZSUBTITLE': r['subtitle']})
        out['formation_pos'].extend({**base, 'ZPOS': p['pos'], 'ZX': p['x'], 'ZY': p['y']} for p in r['position_info'])
        out['formation_key'].extend({**base, 'ZPOS': p['pos'], 'ZKEYPOS': p['keypos'], 'ZSUBTITLE': p['subtitle'], 'ZDESCRIPTION_TEXT': p['description']} for p in r['keypos'])
    understanding = payload.get('headcoaches_understanding', [])
    pairs = {(r['headcoach_id'], r['formation_id']) for r in understanding}
    if len(pairs) != len(understanding) or any(r['formation_id'] not in ids or r['depth'] not in (0, 1, 2, 3, 4) for r in understanding):
        raise ValueError('Invalid understanding rows')
    out['coach_understanding'] = [r for r in src.get('coach_understanding', []) if (int(r['ZHEADCOACH_ID']), int(r['ZFORMATION_ID'])) not in pairs]
    out['coach_understanding'].extend({'ZHEADCOACH_ID': r['headcoach_id'], 'ZFORMATION_ID': r['formation_id'], 'ZDEPTH': r['depth']} for r in understanding)
    return out


def load_overlay(src, path=DEFAULT_SNAPSHOT):
    if not Path(path).exists():
        return src
    return overlay_sources(src, json.loads(Path(path).read_text(encoding='utf-8')))


def overlay_coach_depths(coaches, path=DEFAULT_SNAPSHOT):
    """Refresh understanding only; acquisition conditions are independent manual data."""
    if not Path(path).exists():
        return coaches
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    validate_payload(payload)
    rows = payload.get('headcoaches_understanding', [])
    for coach in coaches:
        depths = set(coach.get('depth4FormationIds', []))
        for row in rows:
            if row['headcoach_id'] == coach['id']:
                depths.discard(row['formation_id'])
                if row['depth'] == 4:
                    depths.add(row['formation_id'])
        coach['depth4FormationIds'] = sorted(depths)
    return coaches
