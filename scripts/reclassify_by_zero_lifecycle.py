#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from typing import Dict, List, Optional

METRIC_KEYS = ['SPD', 'TEC', 'PWR']


def is_all_zero(param_row: Dict) -> bool:
    return all(int(param_row.get(k, 0) or 0) == 0 for k in METRIC_KEYS)


def collapse_start_raw(params: List[Dict]) -> Optional[int]:
    rows = sorted(params, key=lambda r: int(r.get('SZN_NO', 0) or 0))
    zero_flags = [is_all_zero(r) for r in rows]
    seasons = [int(r.get('SZN_NO', 0) or 0) for r in rows]

    for i, z in enumerate(zero_flags):
        if not z:
            continue
        if all(zero_flags[i:]):
            return seasons[i]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description='Reclassify NR/SS/CM by zero-lifecycle rule')
    parser.add_argument('--input', default='app/prepared/players_ios_source_categorized.json')
    parser.add_argument('--output', default='app/prepared/players_ios_source_categorized_lifecycle.json')
    parser.add_argument('--report', default='app/prepared/players_ios_source_categorized_lifecycle_report.json')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    counts = {'CC': 0, 'NR': 0, 'CM': 0, 'SS': 0}
    reason_counts = {
        'kept_CC': 0,
        'collapse_start_le_6_to_SS': 0,
        'collapse_start_eq_7_to_CM': 0,
        'other_to_NR': 0,
    }

    examples = {'SS': [], 'CM': [], 'NR': []}

    players_out = []
    for p in data.get('players', []):
        p2 = dict(p)
        current_cat = p.get('category')

        if current_cat == 'CC':
            p2['category'] = 'CC'
            p2['categoryMembership'] = ['CC']
            p2['categoryReason'] = 'kept_CC'
            raw_cs = collapse_start_raw(p.get('params', []))
            disp_cs = (raw_cs + 1) if raw_cs is not None else None
            p2['collapseStartSeasonRaw'] = raw_cs
            p2['collapseStartSeason'] = disp_cs
            counts['CC'] += 1
            reason_counts['kept_CC'] += 1
            players_out.append(p2)
            continue

        raw_cs = collapse_start_raw(p.get('params', []))
        cs = (raw_cs + 1) if raw_cs is not None else None
        p2['collapseStartSeasonRaw'] = raw_cs
        p2['collapseStartSeason'] = cs

        if cs is not None and cs <= 6:
            cat = 'SS'
            reason = 'collapse_start_le_6_to_SS'
        elif cs == 7:
            cat = 'CM'
            reason = 'collapse_start_eq_7_to_CM'
        else:
            cat = 'NR'
            reason = 'other_to_NR'

        p2['category'] = cat
        p2['categoryMembership'] = [cat]
        p2['categoryReason'] = reason

        counts[cat] += 1
        reason_counts[reason] += 1
        if len(examples[cat]) < 12:
            p_name = p.get('player', {}).get('NAME') or p.get('player', {}).get('FULLNAME') or ''
            examples[cat].append(
                {
                    'id': p.get('playerId'),
                    'name': p_name,
                    'collapseStartSeason': cs,
                    'collapseStartSeasonRaw': raw_cs,
                }
            )

        players_out.append(p2)

    out = dict(data)
    out['generatedAt'] = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec='seconds')
    out['categoryPolicy'] = {
        'type': 'zero_lifecycle_v1',
        'notes': [
            'CC is preserved as-is.',
            'Display season uses SZN_NO + 1.',
            'If SPD/TEC/PWR become zero from display season <=6 onward, classify as SS.',
            'If SPD/TEC/PWR become zero from display season 7 onward, classify as CM.',
            'Otherwise classify as NR.'
        ]
    }
    out['players'] = players_out

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)

    report = {
        'generatedAt': out['generatedAt'],
        'counts': counts,
        'reasonCounts': reason_counts,
        'examples': examples,
    }
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f'Wrote {args.output}')
    print(f'Wrote {args.report}')
    print('counts', counts)


if __name__ == '__main__':
    main()
