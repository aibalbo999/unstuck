"""Request-bound original POST bytes with existing MOPS admission and raw TTL."""
import base64
from hashlib import sha256
import math
import time
from uuid import uuid4

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, remember_success
from shared_provider_cache import shared_fetch
from mops_material_transport import BODY_LIMIT, INDEX_LIMIT, validate_response_metadata
from data_fetch.market_sources.issuer_news_transport import PROVIDER as HTTP_PROVIDER

RAW_TTL = 1800
GUARD = scope_key('MOPS', endpoint='mopsov_investor_conference')
PREFIX = 'mops-material-original:v1:'
REQUEST_FIELDS = ('ticker', 'symbol', 'url', 'method', 'request_body', 'request_sha256', 'format')


def request_identity(spec):
    return {k: spec[k] for k in REQUEST_FIELDS}


def cache_key(spec):
    return PREFIX + spec['ticker'] + ':' + spec['request_sha256']


def _check(deadline, owns=None):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')
    if owns is not None and not owns():
        raise SourceResponseError('lease_lost')


def _epoch(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 < value <= time.time()


def _saved_value(spec, raw, stamp):
    from cache_store import get_cache_json
    row = get_cache_json('shared_provider:v1:' + sha256(cache_key(spec).encode()).hexdigest())
    if not isinstance(row, dict) or set(row) != {'value', 'fetched_at_epoch', 'fresh_until_epoch', 'retained_until_epoch'}:
        raise ValueError('original observation missing')
    value = row['value']
    if (not isinstance(value, dict) or set(value) != {'request', 'body_b64', 'sha256', 'fetched_at_epoch', 'response_metadata'}
            or value['request'] != request_identity(spec) or value['sha256'] != sha256(raw).hexdigest()
            or value['fetched_at_epoch'] != stamp or not _epoch(stamp) or time.time()-stamp >= RAW_TTL
            or not validate_response_metadata(value['response_metadata'], raw, spec)):
        raise ValueError('original identity or metadata differs')
    limit = INDEX_LIMIT if spec['format'] == 'html' else BODY_LIMIT
    if (not 0 < len(raw) <= limit or not isinstance(value['body_b64'], str)
            or len(value['body_b64']) > (limit+2)//3*4 or base64.b64decode(value['body_b64'], validate=True) != raw):
        raise ValueError('original bytes differ')
    if (any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in ('fetched_at_epoch','fresh_until_epoch','retained_until_epoch'))
            or not stamp <= row['fetched_at_epoch'] <= time.time()
            or not row['fetched_at_epoch'] < row['fresh_until_epoch'] <= row['retained_until_epoch']):
        raise ValueError('original observation time invalid')
    expiry = min(row['fresh_until_epoch'], stamp+RAW_TTL)
    if time.time() >= expiry:
        raise ValueError('original expired')
    return value, expiry


def original_bytes(receipt, spec):
    if (not isinstance(receipt, dict) or receipt.get('status') != 'archived'
            or receipt.get('source_url') != spec['url'] or receipt.get('request') != request_identity(spec)
            or type(receipt.get('http_status')) is not int or receipt['http_status'] != 200
            or receipt.get('http_status_observed') is not True or receipt.get('response_complete') is not True
            or receipt.get('request_method') != spec['method'] or type(receipt.get('cache_hit')) is not bool
            or receipt.get('evidence_kind') != 'raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified') is not False or receipt.get('finality_guaranteed') is not False):
        raise ValueError('original POST receipt invalid')
    raw = read_response(receipt,max_bytes=INDEX_LIMIT if spec['format']=='html' else BODY_LIMIT)
    if type(receipt.get('raw_response_bytes')) is not int or len(raw) != receipt['raw_response_bytes']:
        raise ValueError('original archived bytes invalid')
    value, expiry = _saved_value(spec, raw, receipt.get('retrieved_at'))
    if receipt.get('fresh_until_epoch') != expiry or receipt.get('response_metadata') != value['response_metadata']:
        raise ValueError('original receipt not bound to stored observation')
    return raw


def _guard(spec, deadline, owns):
    from cache_store import get_cache_json
    _check(deadline, owns)
    keys = [GUARD, scope_key(HTTP_PROVIDER, endpoint='mopsov.twse.com.tw'),
            PREFIX+'admission:'+spec['request_sha256']]
    try:
        for key in keys:
            state = get_cache_json(key)
            if state is None:
                continue
            if not isinstance(state, dict):
                raise ValueError('guard malformed')
            for field in ('retry_at', 'next_request_at'):
                until = state.get(field, 0)
                if type(until) not in (int,float) or not math.isfinite(until) or until < 0:
                    raise ValueError('guard time malformed')
                if until > time.time():
                    raise SourceResponseError('cooldown' if field == 'retry_at' else 'request_pacing')
        row = get_cache_json('shared_provider:v1:'+sha256(cache_key(spec).encode()).hexdigest())
        if isinstance(row,dict) and row.get('error_kind'):
            until = row.get('retry_after_epoch')
            if type(until) not in (int,float) or not math.isfinite(until):
                raise ValueError('cache failure time malformed')
            if until > time.time():
                raise SourceResponseError('cooldown')
    except SourceResponseError:
        raise
    except Exception as exc:
        raise SourceResponseError('guard_storage_unavailable') from exc
    _check(deadline, owns)


def get_original(spec, downloader, *, deadline, owns, diagnostic, force_refresh=False, use_cache=True, parser=None):
    """Return validated bytes (or parser result) and their original receipt.

    Recovery requires a successful content parser and this call's native HTTP;
    downloading bytes or replaying an original is not a source recovery.
    """
    from cache_store import get_cache_json, set_cache_json
    diagnostic.update(url=spec['url'], request_method=spec['method'], request_sha256=spec['request_sha256'],
                      http_request_sent=False, http_request_count=0)
    _check(deadline, owns)
    if force_refresh or not use_cache:
        _guard(spec, deadline, owns)
    failures = []
    native_started = []
    def acquire_native():
        _guard(spec, deadline, owns)
        key = PREFIX+'admission:'+spec['request_sha256']
        marker = {'token': uuid4().hex, 'retry_at': time.time()+120}
        try:
            set_cache_json(key, marker, ttl_seconds=120)
            if get_cache_json(key) != marker:
                raise SourceResponseError('lease_lost')
        except SourceResponseError:
            raise
        except Exception as exc:
            raise SourceResponseError('guard_storage_unavailable') from exc
        _check(deadline, owns)
        request_started_at = time.time()
        native_started.append(request_started_at)
        try:
            raw = downloader(diagnostic)
            diagnostic['http_request_count'] = int(diagnostic.get('http_request_sent') is True)
            stamp = time.time()
            _check(deadline, owns)
            if not validate_response_metadata(diagnostic.get('response_metadata'), raw, spec):
                raise SourceResponseError('transport_metadata_invalid')
            value = {'request': request_identity(spec), 'body_b64': base64.b64encode(raw).decode('ascii'),
                     'sha256': sha256(raw).hexdigest(), 'fetched_at_epoch': stamp,
                     'response_metadata': diagnostic['response_metadata']}
            try:
                if get_cache_json(key) == marker:
                    set_cache_json(key, {**marker, 'retry_at': 0}, ttl_seconds=1)
            except Exception:
                diagnostic['admission_release_failed'] = True
            _check(deadline, owns)
            return value
        except SourceResponseError as exc:
            diagnostic['http_request_count'] = int(diagnostic.get('http_request_sent') is True)
            failures.append(exc)
            if diagnostic.get('http_request_sent') is True and owns():
                try:
                    remember_failure(GUARD, exc)
                except Exception:
                    diagnostic['failure_guard_write_failed'] = True
            raise
    def acquire():
        # shared_fetch reduces exceptions to a class name. Preserve the first
        # actual guard/admission cause even when no HTTP request was made.
        try:
            return acquire_native()
        except SourceResponseError as exc:
            if not failures:failures.append(exc)
            raise
    def ttl(value):
        stamp = value.get('fetched_at_epoch')
        if not _epoch(stamp) or time.time()-stamp >= RAW_TTL:
            raise SourceResponseError('original_expired')
        remaining = math.floor(stamp+RAW_TTL-time.time())
        if remaining < 1:
            raise SourceResponseError('original_expired')
        return remaining
    value, meta = shared_fetch(cache_key(spec), acquire, freshness_seconds=RAW_TTL, retention_seconds=RAW_TTL,
                              result_ttl=ttl, error_retry_seconds=120, force_refresh=force_refresh or not use_cache,
                              lock_wait_seconds=0)
    _check(deadline, owns)
    diagnostic['cache_hit'] = bool(meta.get('cache_hit'))
    if meta.get('error_kind') or meta.get('stale'):
        if failures:
            raise failures[0]
        raise SourceResponseError('cooldown' if meta.get('error_kind') == 'SourceResponseError' else meta.get('error_kind') or 'stale_receipt')
    try:
        limit = INDEX_LIMIT if spec['format'] == 'html' else BODY_LIMIT
        encoded = value['body_b64']
        if not isinstance(encoded,str) or len(encoded) > (limit+2)//3*4:
            raise ValueError('invalid raw envelope')
        raw = base64.b64decode(encoded,validate=True)
        saved, expiry = _saved_value(spec,raw,value['fetched_at_epoch'])
        if saved != value:
            raise ValueError('observation replaced')
        receipt = archive_response(raw,source_url=spec['url'],retrieved_at=value['fetched_at_epoch'],
                                   http_status=200,max_bytes=limit)
        receipt.update(request=request_identity(spec),request_method=spec['method'],response_complete=True,http_status_observed=True,
                       cache_hit=bool(meta.get('cache_hit')),fresh_until_epoch=expiry,response_metadata=value['response_metadata'])
        if original_bytes(receipt,spec) != raw:
            raise ValueError('archived original differs')
    except Exception as exc:
        _check(deadline, owns)
        raise SourceResponseError('cache_receipt_invalid') from exc
    _check(deadline, owns)
    diagnostic.update(fetched_at_epoch=receipt['retrieved_at'],original_receipt=receipt,
                      original_http_status_observed=True,http_status=200)
    parsed = parser(raw, receipt) if parser is not None else raw
    _check(deadline, owns)
    if parser is not None and native_started and diagnostic.get('http_request_sent') is True and not receipt['cache_hit']:
        remember_success(GUARD, request_started_at=native_started[0])
    _check(deadline, owns)
    return parsed, receipt
