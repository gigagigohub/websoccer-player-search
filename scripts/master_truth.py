"""Master-owned corrections and official event ingestion; site JSON is output only."""
import contextlib
import datetime as dt
import fcntl
import json
import sqlite3
from pathlib import Path

TABLES = ('manual_player_category','player_person_identity','manual_player_model',
          'manual_coach_obtainable','manual_scout_event','manual_cm_event',
          'manual_formation_slot','manual_formation_card','manual_change_log')

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

@contextlib.contextmanager
def writer_lock(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'.master-write.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        yield

def init_extra(conn):
    for t in ('manual_formation_slot','manual_formation_card'):
        conn.execute(f'CREATE TABLE IF NOT EXISTS {t} (formation_id INTEGER NOT NULL, slot INTEGER NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(formation_id,slot))')
    conn.execute('CREATE TABLE IF NOT EXISTS manual_change_log (id INTEGER PRIMARY KEY, changed_at TEXT NOT NULL, table_name TEXT NOT NULL, key_json TEXT NOT NULL, before_json TEXT, after_json TEXT, reason TEXT NOT NULL)')

def inherit(conn, source):
    """Copy typed master tables, never reconstruct them from exported site JSON."""
    source=Path(source).resolve()
    old=sqlite3.connect(f'file:{source}?mode=ro',uri=True)
    try:
        existing={r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing=set(TABLES)-existing
        if missing:raise RuntimeError(f'Master correction source lacks tables: {sorted(missing)}')
        for t in TABLES:
            if t not in existing:continue
            schema=old.execute('SELECT sql FROM sqlite_master WHERE name=?',(t,)).fetchone()[0]
            conn.execute(f'DROP TABLE IF EXISTS main.{t}')
            conn.execute(schema)
            rows=old.execute(f'SELECT * FROM {t}').fetchall()
            if rows:conn.executemany(f'INSERT INTO {t} VALUES ('+','.join('?' for _ in rows[0])+')',rows)
        init_extra(conn)
    finally:old.close()

def ensure_player_truth(conn):
    """Fill identities/categories only for newly arrived official players."""
    now=stamp()
    conn.execute('''INSERT OR IGNORE INTO player_person_identity
      (player_id,raw_person_id,canonical_person_id,is_override,source_method,notes,source_file,updated_at)
      SELECT ZPLAYER_ID,ZPERSON_ID,CASE WHEN ZPERSON_ID>0 THEN ZPERSON_ID ELSE ZPLAYER_ID END,0,
      'canonical_from_raw','official default for new player','official core',? FROM ao__ZMOPLAYER''',(now,))
    conn.execute('''INSERT OR IGNORE INTO manual_player_category
      (player_id,category,category_membership_json,retired,retired_reason,is_manual,source_file,source_note)
      SELECT ZPLAYER_ID,CASE WHEN ZRARITY=7 THEN '' ELSE 'NR' END,
      CASE WHEN ZRARITY=7 THEN '[]' ELSE '["NR"]' END,0,'',0,'official core','automatic new-player default'
      FROM ao__ZMOPLAYER''')

def ingest_events(conn, zip_dir):
    """Use ZIP contents for schedules/membership; preserve names corrected in DB."""
    import link_scout_history as scouts
    import link_challenge_history as cm
    previous_ss={pid for (raw,) in conn.execute('SELECT player_ids_json FROM manual_scout_event') for pid in json.loads(raw or '[]')}
    previous_cm={pid for (raw,) in conn.execute('SELECT player_ids_json FROM manual_cm_event') for pid in json.loads(raw or '[]')}
    old_zip=scouts.ZIP_DIR
    try:
        scouts.ZIP_DIR=Path(zip_dir)
        rows=scouts.load_events_from_zips()
    finally:scouts.ZIP_DIR=old_zip
    for eid,r in rows.items():
        old=conn.execute('SELECT version FROM manual_scout_event WHERE event_id=?',(eid,)).fetchone()
        if old and (old[0] or 0)>r['version']:continue
        conn.execute('''INSERT INTO manual_scout_event(event_id,name,start,end,type,version,notes,name_raw,name_source,player_count,player_ids_json,is_manual,source_file)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET
        start=excluded.start,end=excluded.end,type=excluded.type,version=excluded.version,
        notes=excluded.notes,player_count=excluded.player_count,player_ids_json=excluded.player_ids_json''',
        (eid,r['nameRaw'],r['start'],r['end'],r['type'],r['version'],r['notes'],r['nameRaw'],'updatefile',len(r['playerIds']),json.dumps(r['playerIds']),0,str(zip_dir)))
    events,_=cm._build_cm_data(Path(zip_dir))
    for r in events:
        eid=r['eventId'];old=conn.execute('SELECT version FROM manual_cm_event WHERE event_id=?',(eid,)).fetchone()
        if old and (old[0] or 0)>r['version']:continue
        conn.execute('''INSERT INTO manual_cm_event(event_id,name,start,end,mode,version,player_count,player_ids_json,is_manual,source_file)
        VALUES (?,?,?,?,?,?,?,?,0,?) ON CONFLICT(event_id) DO UPDATE SET
        name=CASE WHEN manual_cm_event.is_manual=1 THEN manual_cm_event.name ELSE excluded.name END,
        start=excluded.start,end=excluded.end,mode=excluded.mode,version=excluded.version,
        player_count=excluded.player_count,player_ids_json=excluded.player_ids_json''',
        (eid,r['name'],r['start'],r['end'],r['mode'],r['version'],len(r['playerIds']),json.dumps(r['playerIds']),str(zip_dir)))
    # Reproduce event-derived categories, except explicit corrections and retirement.
    ss={pid for (raw,) in conn.execute('SELECT player_ids_json FROM manual_scout_event') for pid in json.loads(raw or '[]')}
    cms={pid for (raw,) in conn.execute('SELECT player_ids_json FROM manual_cm_event') for pid in json.loads(raw or '[]')}
    protected={json.loads(r[0]).get('player_id') for r in conn.execute("SELECT key_json FROM manual_change_log WHERE table_name='manual_player_category'")}
    new_defaults={r[0] for r in conn.execute("SELECT player_id FROM manual_player_category WHERE source_note='automatic new-player default' AND is_manual=0")}
    for pid in (ss-previous_ss)|(cms-previous_cm)|(new_defaults & (ss|cms)):
        if pid in protected:continue
        row=conn.execute('SELECT category,category_membership_json,retired FROM manual_player_category WHERE player_id=?',(pid,)).fetchone()
        if not row or row[2]:continue
        has_ss=pid in ss or 'SS' in json.loads(row[1] or '[]')
        category=('CM/SS' if has_ss else 'CM') if pid in cms else 'SS'
        membership=['SS'] if category=='SS' else cm._normalize_membership(json.loads(row[1] or '[]'),category)
        conn.execute('UPDATE manual_player_category SET category=?,category_membership_json=? WHERE player_id=?',(category,json.dumps(membership),pid))

def attach_histories(conn, data):
    """Build display histories from the master event tables, not files or CSVs."""
    scout_history={};cm_history={}
    for r in data['scouts']:
        for order,pid in enumerate(r['playerIds'],1):
            scout_history.setdefault(pid,[]).append({**{k:r[k] for k in ('eventId','name','start','end','type','version')},'order':order})
    for r in data['cmEvents']:
        for order,pid in enumerate(r['playerIds'],1):
            cm_history.setdefault(pid,[]).append({**{k:r[k] for k in ('eventId','name','start','end','mode','version')},'order':order})
    for history in (scout_history,cm_history):
        for rows in history.values():rows.sort(key=lambda r:(r.get('start') or '',r['eventId']),reverse=True)
    for p in data['players']:
        for key,h in [('scoutHistory',scout_history),('cmHistory',cm_history)]:
            if p['id'] in h:p[key]=h[p['id']]
            else:p.pop(key,None)

def override_rows(master, table, legacy):
    if master and Path(master).exists():
        c=sqlite3.connect(f'file:{Path(master).resolve()}?mode=ro',uri=True)
        try:
            if c.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
                return [json.loads(r[0]) for r in c.execute(f'SELECT payload_json FROM {table} ORDER BY formation_id,slot')]
        finally:c.close()
    # Pre-migration compatibility for historical WSM only.
    import csv
    if not legacy or not Path(legacy).exists():return []
    with Path(legacy).open() as f:return list(csv.DictReader(f))

def refresh_and_export(app_dir, *, core_root=None, zip_dir=None, master=None, snapshots=None):
    """Compatibility entry for old update commands: commit DB first, then export."""
    import subprocess
    import sys
    from paths import latest_wsm_file
    from build_websoccer_master_db import import_update_core_snapshots, require_player_truth_integrity
    with writer_lock((Path(master) if master else latest_wsm_file()).parent):
        path=Path(master) if master else latest_wsm_file()
        backup=path.parent/'backups'/('update_'+stamp().replace(':','-')+'.sqlite3');backup.parent.mkdir(exist_ok=True)
        with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as source,sqlite3.connect(backup) as dest:source.backup(dest)
        with sqlite3.connect(path) as c:
            init_extra(c)
            if snapshots:
                for snapshot in snapshots:
                    import_update_core_snapshots(c,Path(snapshot))
                    refresh_core_values(c,Path(snapshot))
            elif core_root:
                import_update_core_snapshots(c,Path(core_root))
                refresh_core_values(c,Path(core_root))
            ensure_player_truth(c)
            if zip_dir:ingest_events(c,zip_dir)
            require_player_truth_integrity(c)
        subprocess.run([sys.executable,str(Path(__file__).with_name('export_site_json_from_master_db.py')),'--master-db',str(path),'--out-app-dir',str(app_dir)],check=True)

def refresh_core_values(conn, root):
    """Refresh supplied official fields without touching identity/manual relations."""
    from build_websoccer_master_db import _iter_core_snapshot_payloads
    for _,players,params in _iter_core_snapshot_payloads(Path(root)):
        if players.get('code')!='000':raise ValueError('Unsuccessful core snapshot')
        for row in players.get('players',[]):
            values={'Z'+k.upper():row[k] for k in ('name','fullname','nameruby','age','nation_id','person_id','pos_type','tall','weight','rarity','status','act_szn') if k in row}
            if values:conn.execute('UPDATE ao__ZMOPLAYER SET '+','.join(k+'=?' for k in values)+' WHERE ZPLAYER_ID=?',list(values.values())+[row['player_id']])
            fields={'description_text':'ZDESCRIPTION_TEXT','play_type':'ZPLAY_TYPE','subtitle':'ZSUBTITLE'}
            values={col:row[k] for k,col in fields.items() if k in row}
            if values:conn.execute('UPDATE ao__ZMOPLAYERSINFO SET '+','.join(k+'=?' for k in values)+' WHERE Z_PK=(SELECT ZINFO FROM ao__ZMOPLAYER WHERE ZPLAYER_ID=?)',list(values.values())+[row['player_id']])
        columns={r[1] for r in conn.execute('PRAGMA table_info(ao__ZMOPLAYERSPARAM)')}
        for row in params.get('players_param',[]):
            values={'Z'+k.upper():v for k,v in row.items() if 'Z'+k.upper() in columns and k not in ('player_id','szn_no')}
            if values:conn.execute('UPDATE ao__ZMOPLAYERSPARAM SET '+','.join(k+'=?' for k in values)+' WHERE ZPLAYER_ID=? AND ZSZN_NO=?',list(values.values())+[row['player_id'],row['szn_no']])
