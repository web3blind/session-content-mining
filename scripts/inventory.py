"""Read-only session inventory by MESSAGE time; not a content review."""
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo


def boundary(value, zone):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(zone))
    return parsed.timestamp()


def inventory(db, profile, start, end, zone):
    lo, hi = boundary(start, zone), boundary(end, zone)
    if hi <= lo:
        raise ValueError('end-exclusive must be after start')
    c = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        cap = c.execute('SELECT COALESCE(MAX(id),0) FROM messages').fetchone()[0]
        unknown = c.execute("SELECT count(*) FROM messages WHERE id<=? AND (timestamp IS NULL OR typeof(timestamp) NOT IN ('integer','real'))", (cap,)).fetchone()[0]
        rows = c.execute('SELECT id,session_id,timestamp,role FROM messages WHERE timestamp>=? AND timestamp<? AND id<=? ORDER BY session_id,timestamp,id', (lo,hi,cap))
        grouped = {}
        for mid, sid, stamp, role in rows:
            entry = grouped.setdefault(sid, {'session_id':sid, 'link':f'@session:{profile}/{sid}', 'messages':[], 'review_status':'pending'})
            entry['messages'].append({'id':mid,'timestamp':stamp,'role':role})
        for sid, entry in grouped.items():
            entry['session_record_exists'] = c.execute('SELECT 1 FROM sessions WHERE id=?', (sid,)).fetchone() is not None
        return {'format':1,'inventory_only':True,'profile':profile,'database':str(Path(db).resolve()),'start_inclusive':start,'end_exclusive':end,'timezone':zone,'start_epoch':lo,'end_epoch':hi,'snapshot_max_message_id':cap,'snapshot_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'unplaced_timestamp_rows':unknown,'session_count':len(grouped),'message_count':sum(len(v['messages']) for v in grouped.values()),'sessions':list(grouped.values())}
    finally:
        c.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('db','profile','start','end-exclusive','timezone','out'):
        p.add_argument('--'+name, required=True)
    a=p.parse_args()
    result=inventory(a.db,a.profile,a.start,a.end_exclusive,a.timezone)
    target=Path(a.out)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:
        target.chmod(0o600)
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ('session_count','message_count','unplaced_timestamp_rows','inventory_only')}))
