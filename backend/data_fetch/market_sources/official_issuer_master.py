"""One private, complete TWSE CSV observation shared by issuer transports.

Only the master is reusable. Issuer HTML/PDF policies and identity parsers remain
with their callers. Archives prove original acquisition, never a new HTTP call.
"""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import base64
import csv
import io
import json
import math
import re
import sqlite3
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from cache_store import get_cache_json, set_cache_json, get_cache_backend
from cache_backends import InMemoryCache, SqliteCacheBackend, LocalRedisCache
from redis.exceptions import RedisError
from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError, scope_key
from shared_provider_cache import _shared_lock
from .issuer_news_transport import PROVIDER as HTTP_PROVIDER
from .tcfhc_conference_transport import RECEIPT_FIELDS as BASE_FIELDS

MASTER_URL = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
POLICY = 'twse-whole-issuer-master-identity-v1'
RAW_TTL = 1800
MAX_BYTES = 2_500_000
LOCK_DIGEST = sha256((POLICY + ':GET:' + MASTER_URL).encode()).hexdigest()
CACHE_KEY = 'shared_provider:v1:' + LOCK_DIGEST
ADMISSION_KEY = 'official-issuer-master-admission:v1:' + LOCK_DIGEST
HOST_KEY = scope_key(HTTP_PROVIDER, endpoint='mopsfin.twse.com.tw')
META_FIELDS = {'http_status','effective_url','num_redirects','size_download','content_type',
               'content_length','method','proxy_used','cache_control','content_encoding',
               'wire_bytes','wire_sha256','decoded_bytes','decoded_sha256','age'}
RECEIPT_FIELDS = BASE_FIELDS | {'fresh_until_epoch','request_body','response_metadata',
                               'acquisition_manifest','retrieval_policy','reusable'}
ARCHIVE_FIELDS = BASE_FIELDS - {'http_status_observed','request_method','response_complete','cache_hit'}
STORAGE_ERRORS = (OSError, sqlite3.Error, RedisError)
JSON_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
JSON_POLICY = 'twse-whole-issuer-master-json-v1'
FALLBACK_ERRORS = frozenset({'timeout','transport_error','server_error','cooldown'})


class _NoReusableMaster(Exception):
    """A cache-only selection miss; never a failed provider observation."""


def _parameters(url):
    if url not in (MASTER_URL, JSON_URL): raise ValueError('master URL invalid')
    policy = POLICY if url == MASTER_URL else JSON_POLICY
    digest = sha256((policy + ':GET:' + url).encode()).hexdigest()
    return policy, digest, 'shared_provider:v1:' + digest, 'official-issuer-master-admission:v1:' + digest


def _storage_for(url):
    return _stored() if url == MASTER_URL else _stored(url)


def _valid_metadata(meta, raw, url):
    if url == MASTER_URL: return valid_metadata(meta, raw)
    from .official_issuer_master_json import valid_metadata as validate
    return validate(meta, raw)


def _validate_body(raw, stamp, url):
    if url == MASTER_URL: return validate_csv(raw, stamp)
    from .official_issuer_master_json import parse_rows
    return parse_rows(raw, stamp)



def _number(value):
    try: return type(value) in (int, float) and math.isfinite(value)
    except OverflowError: return False


def _check(deadline):
    if time.monotonic() >= deadline: raise SourceResponseError('timeout')


def master_metadata(metadata, raw, headers):
    """Called only after native identity transport validation, never on a hit."""
    return {**metadata, 'content_encoding':headers.get('content-encoding','identity').lower(),
            'wire_bytes':len(raw), 'decoded_bytes':len(raw),
            'wire_sha256':sha256(raw).hexdigest(), 'decoded_sha256':sha256(raw).hexdigest(),
            'age':headers.get('age')}


def _cache_policy(meta):
    text = meta['cache_control']
    if not isinstance(text, str): raise ValueError('master cache policy invalid')
    tokens = [p.strip().lower() for p in text.split(',') if p.strip()]
    fields = {}
    for token in tokens:
        name, _, value = token.partition('=')
        if name in fields: raise ValueError('duplicate master cache directive')
        fields[name] = value.strip('"')
    age = meta['age']
    if age is not None and (not isinstance(age,str) or not re.fullmatch(r'\d{1,10}',age)):
        raise ValueError('invalid master Age')
    maximum = fields.get('max-age')
    if maximum is not None and not re.fullmatch(r'\d{1,10}',maximum):
        raise ValueError('invalid master max-age')
    remaining = max(0, int(maximum) - int(age or 0)) if maximum is not None else RAW_TTL
    reusable = not {'no-cache','no-store'} & fields.keys() and remaining > 0
    # A must-revalidate/no-store response is still a new usable acquisition.
    # Its validation budget is separate from permission to serve a cache hit.
    return bool(reusable), min(RAW_TTL, remaining) if reusable else RAW_TTL


def valid_metadata(meta, raw):
    if not isinstance(raw,bytes) or not 0 < len(raw) <= MAX_BYTES: return False
    digest = sha256(raw).hexdigest()
    try:
        _cache_policy(meta)
        return (isinstance(meta,dict) and set(meta)==META_FIELDS
                and type(meta['http_status']) is int and meta['http_status']==200
                and meta['effective_url']==MASTER_URL and meta['method']=='GET'
                and type(meta['num_redirects']) is int and meta['num_redirects']==0
                and type(meta['proxy_used']) is int and meta['proxy_used']==0
                and _number(meta['size_download']) and meta['size_download']==len(raw)
                and meta['content_type'] in {'text/csv','application/csv','application/octet-stream'}
                and (meta['content_length'] is None or type(meta['content_length']) is int and meta['content_length']==len(raw))
                and meta['content_encoding'] in {'','identity'}
                and type(meta['wire_bytes']) is int and meta['wire_bytes']==len(raw)
                and type(meta['decoded_bytes']) is int and meta['decoded_bytes']==len(raw)
                and meta['wire_sha256']==meta['decoded_sha256']==digest)
    except (KeyError,ValueError,TypeError): return False


def validate_csv(raw, retrieved_at):
    """Whole response shape first; callers still select exact issuer identity."""
    if not isinstance(raw,bytes) or not 0 < len(raw) <= MAX_BYTES: raise ValueError('master size invalid')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig','strict')), strict=True)
    rows = list(reader); fields = reader.fieldnames
    required = {'公司代號','公司名稱','公司簡稱','營利事業統一編號','英文簡稱','網址','出表日期'}
    if (not fields or len(fields)!=len(set(fields)) or not required<=set(fields)
            or not 500<=len(rows)<=2000 or any(None in row or any(v is None for v in row.values()) for row in rows)):
        raise ValueError('master complete CSV shape invalid')
    codes = [row['公司代號'] for row in rows]
    if len(set(codes))!=len(codes) or any(not re.fullmatch(r'\d{4,6}',code) for code in codes):
        raise ValueError('master issuer codes invalid')
    days = {row['出表日期'] for row in rows}
    if len(days)!=1 or not re.fullmatch(r'\d{7}',next(iter(days))): raise ValueError('master date invalid')
    s=next(iter(days)); day=date(int(s[:3])+1911,int(s[3:5]),int(s[5:]))
    original_day=datetime.fromtimestamp(retrieved_at,ZoneInfo('Asia/Taipei')).date()
    if not 0 <= (original_day-day).days <= 14: raise ValueError('master date outside original window')


def _stored(url=MASTER_URL):
    """Read physical TTL without touching it; no fallback to a renewed epoch."""
    _,_,cache_key,_=_parameters(url)
    backend=get_cache_backend()
    if isinstance(backend,InMemoryCache):
        with backend._lock: return deepcopy(backend._entries.get(cache_key,(None,None)))
    if isinstance(backend,SqliteCacheBackend):
        with backend._connection() as conn:
            row=conn.execute('SELECT value,expires_at FROM cache_entries WHERE cache_key=?',(cache_key,)).fetchone()
        return (json.loads(row[0]),row[1]) if row else (None,None)
    if isinstance(backend,LocalRedisCache):
        observed=time.time()
        with backend._redis.pipeline(transaction=True) as pipe:
            payload,ttl=pipe.get(backend._cache_key(cache_key)).pttl(backend._cache_key(cache_key)).execute()
        if payload is None: return None,None
        if type(ttl) is not int or ttl<=0: raise ValueError('master physical TTL unavailable')
        return json.loads(payload),observed+ttl/1000
    raise ValueError('master physical TTL unsupported')


def _manifest_bytes(receipt):
    return json.dumps({k:v for k,v in receipt.items() if k!='acquisition_manifest'},
                      sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()


def _seal(receipt):
    receipt['acquisition_manifest']=archive_response(_manifest_bytes(receipt),source_url=receipt['source_url'],
        retrieved_at=receipt['retrieved_at'],evidence_kind='private_acquisition_manifest',http_status=None)
    if receipt['acquisition_manifest'].get('status')!='archived': raise ValueError('master manifest unavailable')
    return receipt


def _age_valid(receipt, max_age, observed):
    stamp=receipt.get('retrieved_at'); expiry=receipt.get('fresh_until_epoch')
    return (_number(stamp) and _number(expiry) and 0<stamp<expiry<=stamp+RAW_TTL
            and 0<=observed-stamp<max_age and (max_age>RAW_TTL or observed<expiry))


def _row_expiry(row, physical, receipt, observed):
    if not isinstance(row,dict) or set(row)!={'receipt','fetched_at_epoch','fresh_until_epoch'}:
        raise ValueError('master shared row invalid')
    original=row['receipt']
    if (not isinstance(original,dict) or not _number(physical)
            or not _number(row['fresh_until_epoch']) or not _number(row['fetched_at_epoch'])
            or row['fetched_at_epoch']!=receipt['retrieved_at']
            or original.get('retrieved_at')!=receipt['retrieved_at']
            or original.get('raw_response_sha256')!=receipt['raw_response_sha256']
            or original.get('source_url')!=receipt['source_url'] or original.get('reusable') is not True
            or original.get('cache_hit') is not False
            or original.get('response_metadata')!=receipt['response_metadata']
            or not row['fetched_at_epoch']<row['fresh_until_epoch']<=original['fresh_until_epoch']):
        raise ValueError('master shared row identity or epoch mismatch')
    expiry=min(physical,row['fresh_until_epoch'],original['fresh_until_epoch'])
    if not observed<expiry: raise ValueError('master shared row expired')
    return expiry


def original_bytes(receipt, *, max_age=86400):
    now=time.time()
    url=receipt.get('source_url') if isinstance(receipt,dict) else None
    policy,_,_,_=_parameters(url)
    fields=RECEIPT_FIELDS | ({'wire_original'} if url==JSON_URL else set())
    if (not isinstance(receipt,dict) or set(receipt)!=fields or receipt.get('retrieval_policy')!=policy
            or receipt.get('status')!='archived' or receipt.get('source_url')!=url
            or type(receipt.get('cache_hit')) is not bool or type(receipt.get('reusable')) is not bool
            or receipt.get('request_method')!='GET' or receipt.get('request_body') is not None
            or receipt.get('response_complete') is not True or receipt.get('http_status_observed') is not True
            or type(receipt.get('http_status')) is not int or receipt['http_status']!=200
            or receipt.get('evidence_kind')!=('decoded_http_response_bytes' if url==JSON_URL else 'raw_http_response_bytes')
            or receipt.get('historical_point_in_time_verified') is not False or receipt.get('finality_guaranteed') is not False
            or not _age_valid(receipt,max_age,now)): raise ValueError('master receipt invalid')
    raw=read_response(receipt,max_bytes=MAX_BYTES)
    if type(receipt['raw_response_bytes']) is not int or len(raw)!=receipt['raw_response_bytes'] or not _valid_metadata(receipt['response_metadata'],raw,url):
        raise ValueError('master original metadata mismatch')
    _validate_body(raw,receipt['retrieved_at'],url)
    if url==JSON_URL:
        from .official_issuer_master_json import verify_wire
        verify_wire(receipt,raw)
    proof=receipt['acquisition_manifest']
    if (not isinstance(proof,dict) or set(proof)!=ARCHIVE_FIELDS or proof.get('status')!='archived'
            or proof.get('source_url')!=url or not _number(proof.get('retrieved_at'))
            or proof['retrieved_at']!=receipt['retrieved_at'] or proof.get('http_status') is not None
            or proof.get('evidence_kind')!='private_acquisition_manifest'
            or proof.get('historical_point_in_time_verified') is not False or proof.get('finality_guaranteed') is not False
            or type(proof.get('raw_response_bytes')) is not int): raise ValueError('master manifest invalid')
    manifest=read_response(proof,max_bytes=16384)
    if len(manifest)!=proof['raw_response_bytes'] or manifest!=_manifest_bytes(receipt): raise ValueError('master manifest mismatch')
    if max_age<=RAW_TTL and receipt['cache_hit']:
        row,physical=_storage_for(url)
        expiry=_row_expiry(row,physical,receipt,time.time())
        if receipt['fresh_until_epoch']>expiry: raise ValueError('master stored deadline shortened')
    if not live_or_historical_expiry_valid(receipt,max_age): raise ValueError('master expired at replay handoff')
    return raw


def live_or_historical_expiry_valid(receipt, max_age, observed=None):
    # Callers use this after their final deadline check. Keep it pure: original
    # readback checks the shared row earlier and seals the shorter deadline.
    now=time.time() if observed is None else observed
    return _age_valid(receipt,max_age,now)


def _guard(url=MASTER_URL):
    _,_,_,admission_key=_parameters(url)
    host_key=scope_key(HTTP_PROVIDER,endpoint='mopsfin.twse.com.tw' if url==MASTER_URL else 'openapi.twse.com.tw')
    legacy_admission = [prefix+'-conference-admission:v1:GET:'+sha256(MASTER_URL.encode()).hexdigest()
                        for prefix in ('gce','allis')]
    legacy_raw = ['shared_provider:v1:'+sha256((prefix+'-conference-raw:v1:GET:'+MASTER_URL).encode()).hexdigest()
                  for prefix in ('gce','allis')]
    if url != MASTER_URL: legacy_admission=[];legacy_raw=[]
    blocked_kind=None
    for key in (admission_key,host_key,*legacy_admission,*legacy_raw):
        try: state=get_cache_json(key)
        except Exception as exc: raise SourceResponseError('guard_storage_unavailable') from exc
        if state is None: continue
        if not isinstance(state,dict): raise SourceResponseError('guard_storage_unavailable')
        for field in ('retry_at','next_request_at','retry_after_epoch'):
            value=state.get(field,0)
            if not _number(value) or value<0: raise SourceResponseError('guard_storage_unavailable')
            if value>time.time():
                kind=state.get('error_kind')
                if kind and (not isinstance(kind,str) or kind not in FALLBACK_ERRORS):
                    raise SourceResponseError(kind if isinstance(kind,str) else 'guard_storage_unavailable',status_code=state.get('http_status'))
                if state.get('fallback_eligible') is False:
                    raise SourceResponseError('guard_storage_unavailable')
                if field=='next_request_at': blocked_kind='request_pacing'
                elif blocked_kind is None: blocked_kind='cooldown'
    if blocked_kind: raise SourceResponseError(blocked_kind)


def get_receipt(*, deadline, download, diagnostic, url=MASTER_URL, cached_only=False):
    """Validate the shared original; cache-only misses return None without GET."""
    policy,digest,cache_key,admission_key=_parameters(url)
    diagnostic.update(url=url,http_request_sent=False,cache_hit=False,request_method='GET',request_body=None)
    marker=None
    try:
        _check(deadline)
        with _shared_lock(digest,min(1.,max(0.,deadline-time.monotonic()))) as acquired:
            _check(deadline)
            if not acquired: raise SourceResponseError('single_flight_busy')
            try: row,physical=_storage_for(url)
            except STORAGE_ERRORS: row,physical=None,None
            _check(deadline)
            if row is not None and _number(physical) and physical<=time.time(): row=None
            if row is not None:
                receipt=deepcopy(row.get('receipt')) if isinstance(row,dict) else None
                if (not isinstance(receipt,dict) or receipt.get('source_url')!=url
                        or receipt.get('retrieval_policy')!=policy):
                    raise ValueError('master cache endpoint/profile mismatch')
                # Invalid stored bytes are not permission to fetch outside the guard.
                raw=original_bytes(receipt,max_age=86400)
                expiry=min(row['fresh_until_epoch'],physical,receipt['fresh_until_epoch'])
                if time.time()<expiry:
                    _row_expiry(row,physical,receipt,time.time())
                    if physical<min(row['fresh_until_epoch'],receipt['fresh_until_epoch']):
                        # Redis TTL is read with subsecond round-trip jitter.
                        # A conservative fixed cutoff cannot renew on reread.
                        expiry=min(expiry,math.floor(physical))
                    receipt.update(cache_hit=True,fresh_until_epoch=expiry)
                    _seal(receipt)
                    raw=original_bytes(receipt,max_age=RAW_TTL)
                else: row=None
            if row is None:
                if cached_only: raise _NoReusableMaster()
                _guard(url);_check(deadline)
                marker={'token':uuid4().hex,'retry_at':time.time()+120,'fallback_eligible':False}
                try:
                    set_cache_json(admission_key,marker,ttl_seconds=120)
                    if get_cache_json(admission_key)!=marker: raise SourceResponseError('lease_lost')
                except SourceResponseError: raise
                except Exception as exc: raise SourceResponseError('guard_storage_unavailable') from exc
                _check(deadline)
                value=download(url,diagnostic);stamp=time.time();_check(deadline)
                if (not isinstance(value,dict) or value.get('url')!=url
                        or value.get('request_method')!='GET' or value.get('request_body') is not None): raise ValueError('master native request mismatch')
                encoded=value.get('body_b64')
                if not isinstance(encoded,str) or len(encoded)>(MAX_BYTES+2)//3*4: raise ValueError('master body invalid')
                raw=base64.b64decode(encoded,validate=True)
                if sha256(raw).hexdigest()!=value.get('sha256') or not _valid_metadata(value.get('response_metadata'),raw,url): raise ValueError('master native metadata mismatch')
                _validate_body(raw,stamp,url);_check(deadline)
                reusable,seconds=_cache_policy(value['response_metadata'])
                receipt=archive_response(raw,source_url=url,retrieved_at=stamp,evidence_kind='decoded_http_response_bytes' if url==JSON_URL else 'raw_http_response_bytes')
                receipt.update(http_status_observed=True,request_method='GET',request_body=None,response_complete=True,
                    cache_hit=False,fresh_until_epoch=stamp+seconds,response_metadata=value['response_metadata'],retrieval_policy=policy,reusable=reusable)
                if url==JSON_URL:
                    from .official_issuer_master_json import archive_wire
                    receipt['wire_original']=archive_wire(value,stamp)
                _seal(receipt);original_bytes(receipt,max_age=RAW_TTL);_check(deadline)
                if reusable:
                    saved={'receipt':deepcopy(receipt),'fetched_at_epoch':stamp,'fresh_until_epoch':receipt['fresh_until_epoch']}
                    try:
                        set_cache_json(cache_key,saved,ttl_seconds=max(1,math.ceil(receipt['fresh_until_epoch']-time.time())))
                    except Exception: diagnostic['success_cache_write_failed']=True
                    else:
                        try: current,until=_storage_for(url)
                        except STORAGE_ERRORS: diagnostic['success_cache_readback_failed']=True
                        else:
                            _check(deadline)
                            if current!=saved: raise ValueError('master cache write readback mismatch')
                            expiry=_row_expiry(current,until,receipt,time.time())
                            if expiry<receipt['fresh_until_epoch']:
                                receipt['fresh_until_epoch']=min(expiry,math.floor(until));_seal(receipt)
                    if diagnostic.get('success_cache_write_failed') or diagnostic.get('success_cache_readback_failed'):
                        receipt['reusable']=False;_seal(receipt)
                try:
                    if get_cache_json(admission_key)==marker: set_cache_json(admission_key,{**marker,'retry_at':0},ttl_seconds=1)
                except Exception: diagnostic['admission_release_failed']=True
            _check(deadline)
            raw=original_bytes(receipt,max_age=RAW_TTL)
        _check(deadline)
        if receipt['cache_hit']:
            # Include shared-row I/O and archive readback after lock cleanup;
            # then only pure clock checks remain at the handoff boundary.
            raw=original_bytes(receipt,max_age=RAW_TTL)
        _check(deadline)
        if not live_or_historical_expiry_valid(receipt,RAW_TTL): raise SourceResponseError('original_expired')
        _check(deadline)
        diagnostic.update(cache_hit=receipt['cache_hit'],fetched_at_epoch=receipt['retrieved_at'],
                          original_receipt=receipt,original_http_status_observed=True)
        if not receipt['cache_hit']: diagnostic['http_status']=200
        return raw,receipt
    except _NoReusableMaster:
        # Include lock cleanup in the deadline even when no original exists.
        _check(deadline)
        return None
    except Exception as original:
        # Preserve the cause across attempts. An opaque new reservation must
        # never turn a 403/429 or invalid original into an allowed fallback.
        if marker is not None and time.monotonic()<deadline:
            kind=original.error_kind if isinstance(original,SourceResponseError) else 'original_unverified'
            failed={**marker,'error_kind':kind,'http_status':getattr(original,'status_code',None),
                    'fallback_eligible':kind in FALLBACK_ERRORS}
            try:
                if get_cache_json(admission_key)==marker and marker['retry_at']>time.time():
                    set_cache_json(admission_key,failed,ttl_seconds=max(1,math.ceil(marker['retry_at']-time.time())))
            except Exception: diagnostic['failure_guard_write_failed']=True
        diagnostic.pop('original_receipt',None)
        if time.monotonic()>=deadline: raise SourceResponseError('timeout') from original
        if isinstance(original,SourceResponseError): raise
        raise SourceResponseError('cache_receipt_invalid' if not diagnostic.get('http_request_sent') else 'original_unverified') from original


def _warm_master(http):
    """Select verified existing originals without authorizing any download."""
    primary = {}
    try:
        value = get_receipt(deadline=http.deadline, download=http.download_original,
                            diagnostic=primary, cached_only=True)
    except SourceResponseError as exc:
        primary.update(error_kind=exc.error_kind, status='error')
        http.components.append(primary)
        raise
    if value is not None:
        http.components.append(primary)
        return value

    # A reusable fallback cannot hide a known terminal primary refusal. Keep
    # recoverable cooldown evidence, but do not manufacture a failed CSV GET.
    primary_blocked = False
    try:
        _guard(MASTER_URL)
        _check(http.deadline)
    except SourceResponseError as exc:
        primary.update(error_kind=exc.error_kind, status='error')
        _check(http.deadline)
        if exc.error_kind not in FALLBACK_ERRORS:
            http.components.append(primary)
            raise
        primary_blocked = True

    try:
        guard = getattr(http, 'warm_fallback_guard', None)
        if guard is not None: guard()
        _check(http.deadline)
    except SourceResponseError as exc:
        primary.update(error_kind=exc.error_kind, status='error')
        http.components.append(primary)
        raise

    fallback = {'fallback_from':MASTER_URL} if primary_blocked else {}
    try:
        value = get_receipt(deadline=http.deadline, download=http.download_original,
                            diagnostic=fallback, url=JSON_URL, cached_only=True)
    except SourceResponseError as exc:
        if primary_blocked: http.components.append(primary)
        fallback.update(error_kind=exc.error_kind, status='error')
        http.components.append(fallback)
        raise
    if value is not None:
        if primary_blocked: http.components.append(primary)
        http.components.append(fallback)
    return value


def request_master(http):
    """Reuse complete originals first; cold acquisition remains CSV then JSON."""
    warm = _warm_master(http)
    if warm is not None: return warm
    diagnostic={};http.components.append(diagnostic)
    try:
        return get_receipt(deadline=http.deadline,download=http.download_original,diagnostic=diagnostic)
    except SourceResponseError as exc:
        diagnostic.update(error_kind=exc.error_kind,status='error')
        _check(http.deadline)
        if exc.error_kind not in FALLBACK_ERRORS: raise
    fallback={'fallback_from':MASTER_URL};http.components.append(fallback)
    try:
        return get_receipt(deadline=http.deadline,download=http.download_original,diagnostic=fallback,url=JSON_URL)
    except SourceResponseError as exc:
        fallback.update(error_kind=exc.error_kind,status='error')
        raise
