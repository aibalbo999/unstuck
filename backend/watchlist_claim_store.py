"""Atomically lease durable scheduled dispatches, without acknowledging enqueue."""
from __future__ import annotations
from datetime import datetime
import uuid
import watchlist_store
from watchlist_schedule_helpers import slot_due
from watchlist_dispatch_store import dispatch_id, LEASE_SECONDS
TAIPEI=watchlist_store.TAIPEI
DEFAULT_SCHEDULES=watchlist_store.DEFAULT_SCHEDULES

def claim_due_watchlist_items(now: datetime | None=None) -> list[dict]:
    now=now or datetime.now(TAIPEI); today=now.date().isoformat(); now_iso=watchlist_store._now_iso(now)
    claimed=[]
    with watchlist_store._connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        watchlist_store._ensure_legacy_json_migrated(conn)
        items=watchlist_store._read_store_from_conn(conn)['items']
        for item in items:
            if not item.get('enabled'):continue
            for slot in item.get('schedule_slots',[]):
                from nightly_analysis_policy import enabled, domestic
                if enabled() and domestic(item['ticker']) and slot == 'post_market':continue
                if not slot_due(slot,now,schedules=DEFAULT_SCHEDULES):continue
                # Old successful/claimed slots are authoritative; never replay them.
                if (item.get('last_run_dates') or {}).get(slot)==today:continue
                key=dispatch_id(item['ticker'],item['pipeline'],slot,today)
                conn.execute('''INSERT OR IGNORE INTO watchlist_dispatches
                    (dispatch_id,ticker,pipeline,slot,due_date,job_id,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (key,item['ticker'],item['pipeline'],slot,today,key,now_iso,now_iso))
        by_identity={(i['ticker'],i['pipeline']):i for i in items if i.get('enabled')}
        for row in conn.execute('''SELECT * FROM watchlist_dispatches WHERE due_date<=?
                AND state != 'acknowledged' AND (state='pending' OR lease_until<=?)
                ORDER BY due_date,ticker,pipeline,CASE slot WHEN 'pre_market' THEN 0 ELSE 1 END''',(today,now.timestamp())).fetchall():
            item=by_identity.get((row['ticker'],row['pipeline']))
            if not item or row['slot'] not in item.get('schedule_slots',[]):continue
            from nightly_analysis_policy import enabled, domestic
            if enabled() and domestic(item['ticker']) and row['slot']=='post_market':continue
            token=uuid.uuid4().hex
            conn.execute('''UPDATE watchlist_dispatches SET state='leased', lease_token=?,
                lease_until=?, attempts=attempts+1, updated_at=? WHERE dispatch_id=?''',
                (token,now.timestamp()+LEASE_SECONDS,now_iso,row['dispatch_id']))
            claimed.append({**item,'due_slot':row['slot'],'due_label':DEFAULT_SCHEDULES[row['slot']]['label'],
                'due_date':row['due_date'],'dispatch_id':row['dispatch_id'],
                'dispatch_job_id':row['job_id'],'dispatch_token':token})
    return claimed
