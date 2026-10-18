"""Request-bound, original-time progress for checked MOPS announcement bodies.

This is not a cache of derived news records. The caller must reparse the original
against a newly fetched issuer/date index on every use. Only the native transport
can supply the complete-response proof used when qualifying a new entry.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit

import httpx
from cache_backends import InMemoryCache, SqliteCacheBackend
from cache_store import get_cache_backend
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError

RAW_TTL = 1800
MAX_BYTES = 256_000
PREFIX = 'twse-announcement-original:v1:'
CACHE_ERRORS = (OSError, ValueError, TypeError, KeyError, RuntimeError, sqlite3.Error, EOFError, OverflowError)
RECEIPT_KEYS = frozenset({'status','source_url','retrieved_at','http_status','raw_response_sha256',
    'raw_response_path','raw_response_bytes','evidence_kind','historical_point_in_time_verified','finality_guaranteed'})


def request_fingerprint(method, url, *, params=None, data=None, payload=None):
    encoded = json.dumps([method, url, params, data, payload], ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _detail_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    p = urlsplit(url)
    if p.scheme != 'https' or p.fragment:
        return False
    query_text = p.query[1:] if p.query.startswith('&') else p.query
    q = parse_qs(query_text, keep_blank_values=True)
    if p.netloc == 'emops.twse.com.tw' and p.path == '/server-java/t05sr01_1_e':
        if set(q) != {'isNew', 'co_id', 'spoke_date', 'spoke_time', 'seq_no'} or any(len(v) != 1 for v in q.values()):
            return False
        import re
        stamp = q['spoke_time'][0].zfill(6)
        return (q['isNew'][0] == 'Y'
                and re.fullmatch(r'[1-9]\d{3,5}', q['co_id'][0]) is not None
                and re.fullmatch(r'\d{8}', q['spoke_date'][0]) is not None
                and re.fullmatch(r'\d{1,6}', q['spoke_time'][0]) is not None
                and int(stamp[:2]) < 24 and int(stamp[2:4]) < 60 and int(stamp[4:]) < 60
                and re.fullmatch(r'[1-9]\d{0,5}', q['seq_no'][0]) is not None)
    if p.netloc != 'mopsov.twse.com.tw' or p.path != '/mops/web/ajax_t05sr01_1':
        return False
    required = {'COMPANY_ID', 'SPOKE_DATE', 'SPOKE_TIME', 'SEQ_NO'}
    if not required <= set(q) <= required | {'firstin', 'stp', 'step'} or any(len(v) != 1 for v in q.values()):
        return False
    import re
    return (all(re.fullmatch(pattern, q[k][0]) for k, pattern in
                [('COMPANY_ID', r'[1-9]\d{3,5}'), ('SPOKE_DATE', r'\d{8}'),
                 ('SPOKE_TIME', r'\d{1,6}'), ('SEQ_NO', r'[1-9]\d{0,5}')])
            and all(q[k][0] in {'true','1'} for k in {'firstin','stp','step'} & set(q)))


def _number(value):
    try:
        return type(value) in (float, int) and math.isfinite(value)
    except OverflowError:
        return False


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def _stored(key):
    """Read the actual shorter backend expiry without renewing it or a lease."""
    backend = get_cache_backend()
    if isinstance(backend, InMemoryCache):
        with backend._lock:
            entry = backend._entries.get(key)
            return deepcopy(entry) if entry else (None, None)
    if isinstance(backend, SqliteCacheBackend):
        with backend._connection() as conn:
            row = conn.execute('SELECT value, expires_at FROM cache_entries WHERE cache_key = ?', (key,)).fetchone()
        return (json.loads(row[0]), row[1]) if row else (None, None)
    # Unknown backends cannot attest an earlier physical expiry.
    return None, None


def _validate(entry, url, *, deadline, backend_until=None):
    _deadline(deadline)
    fp = request_fingerprint('GET', url)
    if (not _detail_url(url) or not isinstance(entry, dict)
            or set(entry) != {'request_fingerprint','url','method','receipt','fresh_until_epoch'}
            or entry['request_fingerprint'] != fp or entry['url'] != url or entry['method'] != 'GET'):
        raise ValueError('invalid announcement original request')
    proof = entry['receipt']
    if (not isinstance(proof, dict) or set(proof) != RECEIPT_KEYS or proof['status'] != 'archived'
            or proof['source_url'] != url or type(proof['http_status']) is not int or proof['http_status'] != 200
            or proof['evidence_kind'] != 'raw_http_response_bytes'
            or proof['historical_point_in_time_verified'] is not False or proof['finality_guaranteed'] is not False
            or type(proof['raw_response_bytes']) is not int or not 0 < proof['raw_response_bytes'] <= MAX_BYTES):
        raise ValueError('invalid announcement original receipt')
    stamp, until = proof['retrieved_at'], entry['fresh_until_epoch']
    if not _number(stamp) or not _number(until) or not stamp < until <= stamp + RAW_TTL:
        raise ValueError('invalid announcement original time')
    if backend_until is not None:
        if not _number(backend_until):
            raise ValueError('invalid announcement cache expiry')
        until = min(until, backend_until)
    if not stamp <= time.time() < until:
        raise ValueError('expired announcement original')
    body = read_response(proof, max_bytes=MAX_BYTES)
    if len(body) != proof['raw_response_bytes']:
        raise ValueError('announcement original byte count mismatch')
    _deadline(deadline)
    if not stamp <= time.time() < until:
        raise ValueError('expired announcement original')
    result = deepcopy(entry)
    result['fresh_until_epoch'] = until
    return body, result


def read_qualified(url, *, deadline):
    """Misses/corruption never become qualified originals; deadlines are terminal."""
    _deadline(deadline)
    if not _detail_url(url):
        return None
    try:
        entry, expiry = _stored(PREFIX + request_fingerprint('GET', url))
        if entry is None:
            return None
        body, verified = _validate(entry, url, deadline=deadline, backend_until=expiry)
        charset = 'big5' if urlsplit(url).path == '/server-java/t05sr01_1_e' else 'utf-8'
        response = httpx.Response(200, content=body, headers={'content-type':f'text/html; charset={charset}'},
                                  request=httpx.Request('GET', url))
        response.extensions['announcement_original'] = verified
        response.extensions['announcement_cache_hit'] = True
        return response
    except SourceResponseError:
        raise
    except CACHE_ERRORS:
        return None


def qualify(response, *, deadline):
    """Called only after issuer/date/title/body validation; never accepts an injected 200."""
    _deadline(deadline)
    url = str(response.request.url)
    if not _detail_url(url) or response.extensions.get('announcement_cache_hit'):
        return response.extensions.get('announcement_original')
    native = response.extensions.get('announcement_native_response')
    if (not isinstance(native, dict) or set(native) != {'method','url','retrieved_at','complete','http_status_observed','response_sha256'}
            or native['method'] != 'GET' or native['url'] != url or native['complete'] is not True
            or native['http_status_observed'] is not True or response.status_code != 200
            or native['response_sha256'] != hashlib.sha256(response.content).hexdigest()
            or not _number(native['retrieved_at'])):
        return None
    stamp = native['retrieved_at']
    receipt = archive_response(response.content, source_url=url, retrieved_at=stamp, max_bytes=MAX_BYTES)
    entry = {'request_fingerprint':request_fingerprint('GET', url), 'url':url, 'method':'GET',
             'receipt':receipt, 'fresh_until_epoch':stamp + RAW_TTL}
    try:
        _, entry = _validate(entry, url, deadline=deadline)
    except SourceResponseError:
        raise
    except CACHE_ERRORS:
        return None
    # A complete cold original is usable even if optional persistence is unavailable.
    # Stored TTL is floored; read back the actual row so no enclosing cache extends it.
    try:
        ttl = math.floor(entry['fresh_until_epoch'] - time.time())
        if ttl > 0:
            key = PREFIX + entry['request_fingerprint']
            get_cache_backend().set_json(key, entry, ttl_seconds=ttl)
            stored, until = _stored(key)
            if stored == entry:
                _, entry = _validate(stored, url, deadline=deadline, backend_until=until)
    except SourceResponseError:
        raise
    except CACHE_ERRORS:
        pass
    _deadline(deadline)
    _, entry = _validate(entry, url, deadline=deadline)
    response.extensions['announcement_original'] = entry
    return entry


def recheck(entry, *, deadline, cached=False):
    """Final readback preserves a shorter expiry, and a warm row must still exist."""
    body, checked = _validate(entry, entry['url'], deadline=deadline)
    try:
        stored, until = _stored(PREFIX + entry['request_fingerprint'])
    except CACHE_ERRORS:
        stored, until = None, None
    if stored is not None and stored.get('receipt') == entry['receipt']:
        _, current = _validate(stored, entry['url'], deadline=deadline, backend_until=until)
        checked['fresh_until_epoch'] = min(checked['fresh_until_epoch'], current['fresh_until_epoch'])
    elif cached:
        raise ValueError('cached announcement original no longer available')
    _deadline(deadline)
    if time.time() >= checked['fresh_until_epoch']:
        raise ValueError('expired announcement original')
    return checked


def current_admission(entry, *, cached=False):
    """Cheap final-time check of already replayed bytes, not another acquisition.

    A budget-exhausted partial may retain bodies verified before the cutoff, but
    may never hand off an expired body. No parsing or HTTP starts here.
    """
    result = deepcopy(entry)
    try:
        stored, until = _stored(PREFIX + entry['request_fingerprint'])
    except CACHE_ERRORS:
        stored, until = None, None
    reusable = (isinstance(stored, dict) and stored.get('receipt') == entry['receipt']
                and stored.get('request_fingerprint') == entry['request_fingerprint']
                and stored.get('url') == entry['url'] and stored.get('method') == 'GET')
    if reusable:
        values = [result['fresh_until_epoch'], stored.get('fresh_until_epoch'), until]
        if not all(_number(v) for v in values):
            raise ValueError('invalid announcement expiry at handoff')
        result['fresh_until_epoch'] = min(values)
    elif cached:
        raise ValueError('cached original missing at handoff')
    if not result['receipt']['retrieved_at'] <= time.time() < result['fresh_until_epoch']:
        raise ValueError('expired announcement original at handoff')
    return result, reusable
