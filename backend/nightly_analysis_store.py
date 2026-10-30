"""Durable overnight scope, prepared inputs and idempotent dispatch ownership."""
from contextlib import contextmanager, closing
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

TABLE = 'nightly_analysis_work_v1'


def path():
    from runtime_paths import current_runtime_paths
    return Path(current_runtime_paths().task_db)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


@contextmanager
def connection():
    conn = sqlite3.connect(path(), timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS nightly_analysis_sessions_v1 (session_date TEXT PRIMARY KEY, scope_json TEXT NOT NULL, created_at TEXT NOT NULL)')
        conn.execute(f'''CREATE TABLE IF NOT EXISTS {TABLE} (
          job_id TEXT PRIMARY KEY, session_date TEXT NOT NULL, ticker TEXT NOT NULL,
          pipeline TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt REAL NOT NULL DEFAULT 0, lease_token TEXT, lease_until REAL NOT NULL DEFAULT 0,
          data_json TEXT, data_sha256 TEXT, evidence_json TEXT, last_error TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(session_date,ticker,pipeline))''')
        conn.commit()
        with conn:
            yield conn
    finally:
        conn.close()


def read_rows(session=None, *, job_id=None, pending=False):
    if not path().exists():
        return []
    with closing(sqlite3.connect(path().resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
            return []
        fields = 'job_id' if pending else '*'
        sql = f'SELECT {fields} FROM {TABLE}'
        conditions, params = [], []
        if session:
            conditions.append('session_date=?'); params.append(session)
        if job_id:
            conditions.append('job_id=?'); params.append(job_id)
        if pending:
            conditions.append("state != 'dispatched'")
        if conditions:
            sql += ' WHERE ' + ' AND '.join(conditions)
        return [dict(r) for r in conn.execute(sql, params)]


def get_work(job_id):
    rows = read_rows(job_id=job_id)
    return rows[0] if rows else None


def pending_job_ids():
    return {r['job_id'] for r in read_rows(pending=True)}



def session_recorded(session):
    if not path().exists():
        return False
    with closing(sqlite3.connect(path().resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='nightly_analysis_sessions_v1'").fetchone():
            return False
        return conn.execute('SELECT 1 FROM nightly_analysis_sessions_v1 WHERE session_date=?', (session,)).fetchone() is not None


def seed(session, items, now):
    if session_recorded(session):
        return
    from nightly_analysis_policy import domestic, session_open, session_state
    candidates = [i for i in items if i.get('enabled') and 'post_market' in i.get('schedule_slots', []) and domestic(i['ticker'])]
    if any(session_state(session, i['ticker']) == 'unknown' for i in candidates):
        return 'waiting_calendar'
    scope = sorted({(i['ticker'], i['pipeline']) for i in items if i.get('enabled')
                    and 'post_market' in i.get('schedule_slots', []) and domestic(i['ticker'])
                    and session_open(session, i['ticker'])})
    if not scope:
        return 'no_open_scope'
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        inserted = conn.execute('INSERT OR IGNORE INTO nightly_analysis_sessions_v1 VALUES (?,?,?)',
                                (session, encoded(scope), now.isoformat())).rowcount
        if not inserted:
            return
        for ticker, pipeline in scope:
            job_id = uuid.uuid5(uuid.NAMESPACE_URL, f'stock-agent/nightly/v1/{session}/{ticker}/{pipeline}').hex
            conn.execute(f'INSERT INTO {TABLE} (job_id,session_date,ticker,pipeline,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                         (job_id, session, ticker, pipeline, now.isoformat(), now.isoformat()))


def claim(session, now):
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(f"SELECT * FROM {TABLE} WHERE session_date=? AND state IN ('pending','prepared') AND next_attempt<=? AND lease_until<=? AND (data_json IS NOT NULL OR attempts<6) ORDER BY ticker,pipeline LIMIT 1", (session, now.timestamp(), now.timestamp())).fetchone()
        if not row:
            return None
        token = uuid.uuid4().hex
        conn.execute(f'UPDATE {TABLE} SET lease_token=?,lease_until=?,updated_at=? WHERE job_id=?',
                     (token, now.timestamp()+600, now.isoformat(), row['job_id']))
        return {**dict(row), 'lease_token': token}


def update_owned(item, now, **values):
    allowed = {'state','attempts','next_attempt','data_json','data_sha256','evidence_json','last_error','lease_token','lease_until'}
    if not set(values) <= allowed:
        raise ValueError('unknown nightly state field')
    values['updated_at'] = now.isoformat()
    with connection() as conn:
        changed = conn.execute(f"UPDATE {TABLE} SET " + ','.join(k+'=?' for k in values) + ' WHERE job_id=? AND lease_token=? AND lease_until>?',
                               (*values.values(), item['job_id'], item['lease_token'], now.timestamp())).rowcount
    return bool(changed)
