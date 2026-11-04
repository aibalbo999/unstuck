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
    if (raw.get('document_kind') == 'mops_major_announcement' or 'original_evidence' in raw
            or str(raw.get('document_id') or '').startswith('mops-json:')):
        from mops_document_bridge import validate_document
        verified = validate_document(raw)
        if any(doc.get(k) != v for k,v in verified.items() if k not in {'original_evidence','original_body_sha256'}):
            raise ValueError('Indexed MOPS document differs from its complete original')
        doc.update(original_evidence=verified['original_evidence'],original_body_sha256=verified['original_body_sha256'])
    # A changed monthly discovery index is acquisition provenance, not a new
    # revision of an otherwise unchanged original announcement body.
    semantic = {key: value for key, value in doc.items() if key not in {'retrieved_at_epoch','original_evidence'}}
    revision = hashlib.sha256(json.dumps(semantic, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return doc, published_epoch, revision


def _ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS source_documents (
        ticker TEXT NOT NULL, source_type TEXT NOT NULL, document_id TEXT NOT NULL,
        revision_sha256 TEXT NOT NULL, published_epoch REAL, retrieved_at_epoch REAL NOT NULL,
        last_observed_at_epoch REAL NOT NULL, search_text TEXT NOT NULL, document_json TEXT NOT NULL,
        PRIMARY KEY (ticker, source_type, document_id, revision_sha256))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS source_document_observations (
        ticker TEXT NOT NULL, source_type TEXT NOT NULL, document_id TEXT NOT NULL,
        revision_sha256 TEXT NOT NULL, original_body_sha256 TEXT NOT NULL,
        acquired_at_epoch REAL NOT NULL, content_fingerprint TEXT NOT NULL, document_json TEXT NOT NULL,
        PRIMARY KEY (ticker,source_type,document_id,original_body_sha256,acquired_at_epoch))''')
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
        except (ValueError, TypeError, KeyError, OverflowError, OSError):
            rejected += 1
    if not rows:
        return {'accepted': 0, 'rejected': rejected}
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=5) as conn:
        _ensure_schema(conn)
        for row in rows:
            doc=json.loads(row[-1]);fingerprint=None
            if 'original_evidence'in doc:
                from mops_document_bridge import document_revision_fingerprint
                fingerprint=document_revision_fingerprint(doc)
                prior=conn.execute("SELECT document_json,revision_sha256,published_epoch,retrieved_at_epoch FROM source_documents WHERE ticker=? AND source_type=? AND document_id=? ORDER BY last_observed_at_epoch DESC,rowid DESC",row[:3]).fetchall()
                for raw,revision,published,acquired in prior:
                    try:
                        old,old_published,rebuilt=_normalize(json.loads(raw),acquired)
                        if (tuple(old[k]for k in ('ticker','source_type','document_id'))!=row[:3]
                                or rebuilt!=revision or old_published!=published or old['retrieved_at_epoch']!=acquired):
                            continue
                        if document_revision_fingerprint(old)!=fingerprint:continue
                        # Keep the immutable first version and its original proof.
                        row=(*row[:3],revision,*row[4:])
                        break
                    except (ValueError,TypeError,KeyError,OverflowError,OSError):
                        continue
            conn.execute('''INSERT INTO source_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, source_type, document_id, revision_sha256) DO UPDATE SET
                last_observed_at_epoch=excluded.last_observed_at_epoch
                WHERE excluded.last_observed_at_epoch > source_documents.last_observed_at_epoch''',row)
            if fingerprint is not None:
                conn.execute('''INSERT INTO source_document_observations VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT DO NOTHING''',(*row[:4],doc['original_body_sha256'],
                        doc['retrieved_at_epoch'],fingerprint,json.dumps(doc,ensure_ascii=False,sort_keys=True)))
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
        SELECT document_json, last_observed_at_epoch, document_id, revision_sha256, source_type, published_epoch, retrieved_at_epoch FROM latest WHERE ''' + ' AND '.join(conditions) + '''
        ORDER BY published_epoch DESC, document_id ASC LIMIT ?'''
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3) as conn:
        try:
            rows = conn.execute(query, values).fetchall()
            has_observations=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_document_observations'").fetchone()
            observations={}
            if has_observations:
                for _,observed,document_id,revision,source_type,_,_ in rows:
                    observations[(source_type,document_id,revision)]=conn.execute(
                        'SELECT original_body_sha256,acquired_at_epoch,content_fingerprint,document_json FROM source_document_observations WHERE ticker=? AND source_type=? AND document_id=? AND revision_sha256=? AND acquired_at_epoch=?',
                        (ticker,source_type,document_id,revision,observed)).fetchall()
        except sqlite3.OperationalError as exc:
            if 'no such table: source_documents' in str(exc):
                return []
            raise
    documents = []
    for raw, observed, document_id, revision, source_type, published, acquired in rows:
        try:
            doc, actual_published, rebuilt_revision = _normalize(json.loads(raw),observed)
            if (doc['ticker']!=ticker or doc['document_id']!=document_id or doc['source_type']!=source_type
                    or rebuilt_revision!=revision or actual_published!=published or doc['retrieved_at_epoch']!=acquired):
                continue
            result=dict(doc,last_observed_at_epoch=observed)
            latest=observations.get((source_type,document_id,revision),[])
            if 'original_evidence'in doc:
                from mops_document_bridge import document_revision_fingerprint
                content_fingerprint=document_revision_fingerprint(doc)
                # Old rows without this table retain their original proof. A
                # newer observation must have its own complete proof at that time.
                if observed>acquired and not latest:raise ValueError('Latest original observation missing')
                if latest:
                    if len(latest)!=1:raise ValueError('Ambiguous latest original observation')
                    body_hash,stamp,fingerprint,observation_json=latest[0]
                    observation,_,_=_normalize(json.loads(observation_json),stamp)
                    if (tuple(observation[k]for k in ('ticker','source_type','document_id'))!=(ticker,source_type,document_id)
                            or observation['retrieved_at_epoch']!=stamp or stamp!=observed
                            or observation['original_body_sha256']!=body_hash
                            or document_revision_fingerprint(observation)!=fingerprint or fingerprint!=content_fingerprint):
                        raise ValueError('Latest original observation differs from version')
                    result['last_observation']={k:observation[k]for k in ('retrieved_at_epoch','original_body_sha256','original_evidence')}
            documents.append(result)
        except (ValueError,TypeError,KeyError,OverflowError,OSError):
            continue  # Keep the stored evidence; an unverifiable latest row cannot roll back to an old revision.
    return documents
