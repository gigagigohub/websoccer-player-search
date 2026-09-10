#!/usr/bin/env python3
"""Reject site-only corrections; fix the master and regenerate instead."""
import argparse,json,sqlite3
from pathlib import Path
from paths import latest_wsm_file
from export_site_json_from_master_db import build_players,build_coaches,build_scouts,build_cm_events,collect_player_image_ids,collect_scout_button_event_ids


def validate(app_dir,master):
    app_dir=Path(app_dir)
    with sqlite3.connect(f'file:{Path(master).resolve()}?mode=ro',uri=True) as c:
        players=build_players(c,{},collect_player_image_ids(app_dir));coaches=build_coaches(c,{})
        scouts=build_scouts(c,collect_scout_button_event_ids(app_dir));events=build_cm_events(c)
    errors=[]
    groups=[('data.json','players',players,('category','categoryMembership','retired','retiredReason','personId','personIdRaw','personIdManualOverride','modelPlayer','modelPlayerManual','modelPlayerSourceMethod','modelPlayerSourceNote')),
            ('coaches_data.json','coaches',coaches,('obtainable','formationObtainableIds','depth4FormationIds'))]
    for file,key,expected,fields in groups:
        actual={r['id']:r for r in json.loads((app_dir/file).read_text())[key]}
        if set(actual)!={r['id'] for r in expected}:errors.append(file+': ID set mismatch')
        for row in expected:
            for field in fields:
                if actual.get(row['id'],{}).get(field)!=row.get(field):errors.append(f'{file}: {row["id"]} {field}')
    actual_data=json.loads((app_dir/'data.json').read_text())
    for name,expected in [('scouts',scouts),('cmEvents',events)]:
        if actual_data.get(name)!=expected:errors.append(name+': master event metadata mismatch')
    if errors:raise RuntimeError('Site-only/master-mismatched corrections; use register_master_correction.py and regenerate: '+', '.join(errors[:20]))
    return {'players':len(players),'coaches':len(coaches)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app-dir',type=Path,required=True);p.add_argument('--master-db',type=Path);a=p.parse_args();print(validate(a.app_dir,a.master_db or latest_wsm_file()))
if __name__=='__main__':main()
