"""Local, revision-preserving index of acquired public company documents.

Search never performs HTTP or invokes a model. Publication time and original
acquisition time remain distinct; rereading a cache does not renew either one.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import re
import sqlite3
import time
from collections.abc import Mapping
from datetime import datetime, time as day_time, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from runtime_paths import current_runtime_paths

SOURCE_TYPES = frozenset({'official_disclosure', 'company_ir'})
_ZONE = ZoneInfo('Asia/Taipei')
_TICKER = re.compile(r'^[0-9]{4,6}\.(?:TW|TWO)$')
_TEXT_LIMIT = 60000


def _database_path() -> Path:
    return current_runtime_paths().operational_db


def _date_epoch(value, *, end_of_day=False):
    if value is None or value == '':
        return None
    raw = str(value).strip()
    parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    if len(raw) == 10:
        parsed = datetime.combine(parsed.date(), day_time(), _ZONE)
        if end_of_day:
            return (parsed + timedelta(days=1)).timestamp() - 0.000001
    elif parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_ZONE)
    return parsed.timestamp()


def _ticker(value):
    ticker = str(value or '').strip().upper()
    if not _TICKER.fullmatch(ticker):
        raise ValueError('A qualified Taiwan ticker is required')
    return ticker


def _public_url(value):
    raw = str(value or '').strip()
    parsed = urlsplit(raw)
    host = (parsed.hostname or '').lower()
    if (len(raw) > 4096 or parsed.scheme not in {'http', 'https'} or not host
            or parsed.username or parsed.password or host == 'localhost'
            or host.endswith(('.localhost', '.local')) or '.' not in host):
        raise ValueError('A public source URL is required')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('A public source URL is required')
    return raw


def _normalize(raw, observed_at):
    if not isinstance(raw, Mapping):
        raise ValueError('Invalid document')
    source_type = str(raw.get('source_type') or '')
    if source_type not in SOURCE_TYPES:
        raise ValueError('Invalid document source type')
    published_at = raw.get('published_at') or None
    published_epoch = _date_epoch(published_at)
    event_date = raw.get('event_date') or None
    _date_epoch(event_date)
    acquired = float(raw.get('retrieved_at_epoch', observed_at))
    if not math.isfinite(acquired) or acquired <= 0 or acquired > time.time() + 300:
        raise ValueError('Invalid acquisition time')
    doc = {'ticker': _ticker(raw.get('ticker')), 'source_type': source_type,
           'url': _public_url(raw.get('url')), 'published_at': published_at,
           'event_date': event_date, 'retrieved_at_epoch': acquired}
    for key, limit in (('document_id', 256), ('title', 1000), ('source', 256),
                       ('document_kind', 80)):
        value = str(raw.get(key) or '').strip()
        if not value or len(value) > limit:
            raise ValueError(f'Invalid {key}')
        doc[key] = value
    full_text = str(raw.get('text') or '')
    summary = str(raw.get('summary') or '')
    doc.update(text=full_text[:_TEXT_LIMIT], summary=summary[:4000],
               content_truncated=bool(raw.get('content_truncated')) or len(full_text) > _TEXT_LIMIT
                                 or len(summary) > 4000,
               coverage_status='text_available' if full_text.strip() else 'metadata_only')
    # This hash always describes the exact stored text, not a clipped provider body.
    doc['content_sha256'] = hashlib.sha256(doc['text'].encode('utf-8')).hexdigest()
    semantic = {key: value for key, value in doc.items() if key != 'retrieved_at_epoch'}
    revision = hashlib.sha256(json.dumps(semantic, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return doc, published_epoch, revision


def _ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS source_documents (
        ticker TEXT NOT NULL, source_type TEXT NOT NULL, document_id TEXT NOT NULL,
        revision_sha256 TEXT NOT NULL, published_epoch REAL, retrieved_at_epoch REAL NOT NULL,
        last_observed_at_epoch REAL NOT NULL, search_text TEXT NOT NULL, document_json TEXT NOT NULL,
        PRIMARY KEY (ticker, source_type, document_id, revision_sha256))''')
    conn.execute('''CREATE INDEX IF NOT EXISTS source_documents_ticker_date
                    ON source_documents(ticker, source_type, published_epoch DESC)''')


def upsert_source_documents(documents, *, observed_at_epoch=None) -> dict:
    """Add acquired revisions without changing unrelated operational tables."""
    observed_at = float(observed_at_epoch if observed_at_epoch is not None else time.time())
    if not math.isfinite(observed_at) or observed_at <= 0:
        raise ValueError('Invalid observation time')
    if not isinstance(documents, (list, tuple)) or len(documents) > 10000:
        raise ValueError('Expected at most 10000 documents')
    rows, rejected = [], 0
    for raw in documents:
        try:
            doc, published, revision = _normalize(raw, observed_at)
            rows.append((doc['ticker'], doc['source_type'], doc['document_id'], revision, published,
                         doc['retrieved_at_epoch'], doc['retrieved_at_epoch'],
                         '\n'.join(doc[key] for key in ('title', 'summary', 'text')),
                         json.dumps(doc, ensure_ascii=False, sort_keys=True)))
        except (ValueError, TypeError, OverflowError):
            rejected += 1
    if not rows:
        return {'accepted': 0, 'rejected': rejected}
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=5) as conn:
        _ensure_schema(conn)
        conn.executemany('''INSERT INTO source_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, source_type, document_id, revision_sha256) DO UPDATE SET
            last_observed_at_epoch=excluded.last_observed_at_epoch
            WHERE excluded.last_observed_at_epoch > source_documents.last_observed_at_epoch''', rows)
    return {'accepted': len(rows), 'rejected': rejected}


def search_source_documents(ticker, *, text='', kinds=(), since=None, until=None, limit=20) -> list:
    """Return latest acquired revisions; dated queries exclude unknown publication dates."""
    ticker = _ticker(ticker)
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    if not isinstance(text, str) or len(text) > 200:
        raise ValueError('text must be at most 200 characters')
    if isinstance(kinds, str) or any(kind not in SOURCE_TYPES for kind in kinds):
        raise ValueError('Invalid source type filter')
    start, end = _date_epoch(since), _date_epoch(until, end_of_day=True)
    if start is not None and end is not None and start > end:
        raise ValueError('since must not be after until')
    path = _database_path()
    if not path.exists():
        return []
    conditions = ['version_rank=1', '(published_epoch IS NULL OR published_epoch<=?)']
    values = [ticker, time.time()]
    if kinds:
        conditions.append('source_type IN (' + ','.join('?' for _ in kinds) + ')')
        values.extend(kinds)
    if text.strip():
        conditions.append('instr(lower(search_text), lower(?)) > 0')
        values.append(text.strip())
    for op, bound in (('>=', start), ('<=', end)):
        if bound is not None:
            conditions.append(f'published_epoch {op} ?')
            values.append(bound)
    values.append(limit)
    query = '''WITH latest AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY source_type, document_id
            ORDER BY last_observed_at_epoch DESC, rowid DESC) AS version_rank
        FROM source_documents WHERE ticker=?)
        SELECT document_json, last_observed_at_epoch FROM latest WHERE ''' + ' AND '.join(conditions) + '''
        ORDER BY published_epoch DESC, document_id ASC LIMIT ?'''
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3) as conn:
        try:
            rows = conn.execute(query, values).fetchall()
        except sqlite3.OperationalError as exc:
            if 'no such table: source_documents' in str(exc):
                return []
            raise
    return [dict(json.loads(raw), last_observed_at_epoch=observed) for raw, observed in rows]
