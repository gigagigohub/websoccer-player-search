#!/usr/bin/env python3
import argparse
import datetime as dt
import json


def load_json(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description='Assign categories to iOS source dataset')
    parser.add_argument('--old-data', default='app/data.json')
    parser.add_argument('--new-data', default='app/prepared/players_ios_source_raw.json')
    parser.add_argument('--output', default='app/prepared/players_ios_source_categorized.json')
    parser.add_argument('--report', default='app/prepared/players_ios_source_category_report.json')
    args = parser.parse_args()

    old = load_json(args.old_data)
    new = load_json(args.new_data)

    old_by_id = {int(p['id']): p for p in old.get('players', [])}

    cc_ids = set()
    cm_ids = set()
    ss_ids = set()
    both_flag_ids = set()
    for pid, p in old_by_id.items():
        cat = p.get('category')
        flags = p.get('flags') or {}
        is_cm = bool(flags.get('CM'))
        is_ss = bool(flags.get('SS'))

        if cat == 'CC':
            cc_ids.add(pid)
        if is_cm:
            cm_ids.add(pid)
        if is_ss:
            ss_ids.add(pid)
        if is_cm and is_ss:
            both_flag_ids.add(pid)

    out_players = []
    counts = {'NR': 0, 'CM': 0, 'SS': 0, 'CC': 0, 'CM/SS': 0}
    reasons = {
        'CC_from_existing_category': 0,
        'CMSS_from_existing_flags': 0,
        'SS_from_existing_flags': 0,
        'CM_from_existing_flags': 0,
        'NR_fallback': 0,
    }

    ids_missing_in_old = []

    for p in new.get('players', []):
        pid = int(p['playerId'])

        if pid not in old_by_id:
            ids_missing_in_old.append(pid)

        if pid in cc_ids:
            category = 'CC'
            reason = 'CC_from_existing_category'
            category_membership = ['CC']
        elif pid in both_flag_ids:
            category = 'CM/SS'
            reason = 'CMSS_from_existing_flags'
            category_membership = ['CM', 'SS']
        elif pid in ss_ids:
            category = 'SS'
            reason = 'SS_from_existing_flags'
            category_membership = ['SS']
        elif pid in cm_ids:
            category = 'CM'
            reason = 'CM_from_existing_flags'
            category_membership = ['CM']
        else:
            category = 'NR'
            reason = 'NR_fallback'
            category_membership = ['NR']

        p2 = dict(p)
        p2['category'] = category
        p2['categoryMembership'] = category_membership
        p2['categoryReason'] = reason
        out_players.append(p2)

        counts[category] += 1
        reasons[reason] += 1

    generated_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec='seconds')

    output = dict(new)
    output['generatedAt'] = generated_at
    output['categoryPolicy'] = {
        'priority': [
            'CC_from_existing_category',
            'CMSS_from_existing_flags',
            'SS_from_existing_flags',
            'CM_from_existing_flags',
            'NR_fallback',
        ],
        'notes': [
            'CC is inherited only from existing category=CC.',
            'CM/SS are inferred from existing flags (CM/SS source-site derived).',
            'NA/RT from existing dataset are intentionally not inherited in this pass.',
        ],
    }
    output['players'] = out_players

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False)

    report = {
        'generatedAt': generated_at,
        'inputCounts': {
            'oldPlayers': len(old.get('players', [])),
            'newPlayers': len(new.get('players', [])),
        },
        'categoryCounts': counts,
        'reasonCounts': reasons,
        'idsMissingInOldCount': len(ids_missing_in_old),
        'idsMissingInOldSample': sorted(ids_missing_in_old)[:100],
        'bothFlagIdsCount': len(both_flag_ids),
        'bothFlagIds': sorted(both_flag_ids),
    }
    with open(args.report, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.output}")
    print(f"Wrote {args.report}")


if __name__ == '__main__':
    main()
