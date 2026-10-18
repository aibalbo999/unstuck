"""Durable per-slot dispatch intents; legacy completed dates are never backfilled."""
from __future__ import annotations
from datetime import datetime
import uuid

LEASE_SECONDS = 600

def init_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS watchlist_dispatches (
        dispatch_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, pipeline TEXT NOT NULL,
        slot TEXT NOT NULL, due_date TEXT NOT NULL, job_id TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending', lease_token TEXT,
        lease_until REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
        receipt_job_id TEXT, receipt_kind TEXT, error_kind TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(ticker, pipeline, slot, due_date)
    )''')

def dispatch_id(ticker, pipeline, slot, due_date):
    return uuid.uuid5(uuid.NAMESPACE_URL, f'stock-agent/watchlist/{_store()._db_path().resolve()}/{ticker}/{pipeline}/{slot}/{due_date}').hex

def _store():
    import watchlist_store
    return watchlist_store

def renew(item, now=None):
    store=_store(); now=now or datetime.now(store.TAIPEI)
    with store._connect() as conn:
        cur=conn.execute('''UPDATE watchlist_dispatches SET lease_until=?, updated_at=?
            WHERE dispatch_id=? AND state='leased' AND lease_token=?''',
            (now.timestamp()+LEASE_SECONDS,store._now_iso(now),item['dispatch_id'],item['dispatch_token']))
        return cur.rowcount==1

def release(item, error_kind, now=None):
    store=_store(); now=now or datetime.now(store.TAIPEI)
    with store._connect() as conn:
        conn.execute('''UPDATE watchlist_dispatches SET state='pending', lease_token=NULL,
            lease_until=0, error_kind=?, updated_at=?
            WHERE dispatch_id=? AND state='leased' AND lease_token=?''',
            (str(error_kind)[:100],store._now_iso(now),item['dispatch_id'],item['dispatch_token']))

def acknowledge(item, receipt_job_id, receipt_kind, now=None):
    store=_store(); now=now or datetime.now(store.TAIPEI); now_iso=store._now_iso(now)
    with store._connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        cur=conn.execute('''UPDATE watchlist_dispatches SET state='acknowledged',
            receipt_job_id=?, receipt_kind=?, lease_token=NULL, lease_until=0,
            error_kind=NULL, updated_at=?
            WHERE dispatch_id=? AND state='leased' AND lease_token=?''',
            (receipt_job_id,receipt_kind,now_iso,item['dispatch_id'],item['dispatch_token']))
        if cur.rowcount!=1:return False
        current=store._select_item(conn,item['ticker'],item['pipeline'])
        if current:
            dates=dict(current.get('last_run_dates') or {})
            dates[item['due_slot']]=max(dates.get(item['due_slot']) or '',item['due_date'])
            current.update(last_run_dates=dates,updated_at=now_iso)
            store._replace_item_row(conn,current);store._touch_store(conn,now_iso)
        return True

def pending_job_ids():
    store=_store()
    with store._connect() as conn:
        return {row['job_id'] for row in conn.execute("SELECT job_id FROM watchlist_dispatches WHERE state != 'acknowledged'")}
