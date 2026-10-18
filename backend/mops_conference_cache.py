"""Reuse complete MOPS year pages, replaying the original selection and age."""
from datetime import datetime, timezone
from hashlib import sha256
import math
import time

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError
from shared_provider_cache import shared_fetch

MAX_BYTES = 2_500_000
EMPTY_SECONDS = 600
CACHE_VERSION = 'mops-conference-original:v1'


def _invalidate(key):
    from cache_store import set_cache_json
    try:set_cache_json('shared_provider:v1:'+sha256(key.encode()).hexdigest(),None,1)
    except Exception:pass


def _stamp(value):
    if type(value) not in (int, float):return None
    try:
        stamp = float(value)
        if math.isfinite(stamp) and 0 < stamp <= time.time():
            datetime.fromtimestamp(stamp, timezone.utc)
            return stamp
    except (OverflowError, ValueError, OSError):pass
    return None


def _codec(raw, text, declared):
    if not isinstance(raw,bytes) or not 0 < len(raw) <= MAX_BYTES:return None
    # The saved decoder must reproduce the exact native text, not guess a new
    # interpretation. The HTTP original remains the evidence, not parsed fields.
    for codec in dict.fromkeys(['utf-8',str(declared or '').lower()]):
        if codec not in {'utf-8','utf8','big5','cp950','iso-8859-1','ascii'}:continue
        try:
            if raw.decode(codec)==text:return codec
        except (UnicodeError, LookupError):pass
    return None


def _replay(payload, symbol, typek, year, month, freshness):
    import official_financials_mops_conference as mops
    if (not isinstance(payload,dict) or payload.get('cacheable') is not True
        or payload.get('symbol') != symbol or payload.get('typek') != typek
        or type(payload.get('year')) is not int or payload['year'] != year
        or payload.get('month') != month
        or payload.get('parser_version') != mops.CONFERENCE_PARSER_VERSION
        or payload.get('codec') not in {'utf-8','utf8','big5','cp950','iso-8859-1','ascii'}):
        raise ValueError('MOPS source envelope invalid')
    receipt=payload.get('receipt');stamp=_stamp(payload.get('fetched_at_epoch'))
    if (not isinstance(receipt,dict) or receipt.get('status')!='archived'
        or receipt.get('source_url')!=mops.MOPS_INVESTOR_CONFERENCE_URL
        or type(receipt.get('http_status')) is not int or receipt['http_status']!=200
        or receipt.get('evidence_kind')!='raw_http_response_bytes'
        or type(receipt.get('raw_response_bytes')) is not int
        or not 0 < receipt['raw_response_bytes'] <= MAX_BYTES
        or stamp is None or _stamp(receipt.get('retrieved_at'))!=stamp):
        raise ValueError('MOPS source receipt invalid')
    raw=read_response(receipt)
    if len(raw)!=receipt['raw_response_bytes']:raise ValueError('MOPS source size differs')
    events=mops.parse_conference_response(raw.decode(payload['codec']),symbol,http_status=200)
    ttl=freshness if events else min(freshness,EMPTY_SECONDS)
    if time.time()-stamp >= ttl:raise ValueError('MOPS original source expired')
    return events,stamp,receipt


def _record_cache(details, count):
    import search_provider_runtime as runtime
    entry={**runtime.current_correlation(),**details,'source':'earnings_call','provider':'MOPS',
           'event_kind':'cache_hit','cache_hit':True,'http_request_sent':False,
           'http_request_count':0,'duration_ms':0,'record_count':count,
           'status':'skipped_fresh_cache' if count else 'degraded_enrichment',
           'message':'沿用已取得的 MOPS 年度原件；非本次 HTTP 取得。'}
    try:runtime.record_source_audit_entries([entry])
    except Exception:pass


def fetch_cached_events(ticker, *, year, month=None, limit, force_refresh=False, diagnostics=None):
    import official_financials_mops_conference as mops
    from config import SOURCE_FRESHNESS_MAX_AGE_SECONDS
    symbol,typek=mops._mops_symbol_and_type(ticker)
    if symbol is None:return []
    year=int(year) if year is not None else mops.date.today().year
    month=int(month) if month is not None else None
    if month is not None and not 1 <= month <= 12:raise ValueError('invalid MOPS conference month')
    freshness=max(1,min(86400,int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get('earnings_call',86400))))
    key=f'{CACHE_VERSION}:{mops.CONFERENCE_PARSER_VERSION}:{symbol}:{typek}:{year}'
    if month is not None:key+=f':{month:02d}'
    captured={};failure=[]
    def acquire():
        try:
            events=mops._fetch_uncached_events(ticker,year=year,month=month,limit=limit,source_capture=captured)
        except SourceResponseError as exc:
            failure.append(exc);raise
        codec=_codec(captured.get('raw'),captured.get('text'),captured.get('encoding'))
        if codec is None or captured.get('http_status')!=200:
            return {'cacheable':False,'events':events,'fetched_at_epoch':captured.get('fetched_at_epoch')}
        try:
            receipt=archive_response(captured['raw'],source_url=mops.MOPS_INVESTOR_CONFERENCE_URL,
                                     retrieved_at=captured['fetched_at_epoch'],http_status=200)
        except (OSError,EOFError,ValueError) as error:
            captured['cache_warning_kind']=type(error).__name__
            receipt={'status':'unavailable'}
        if receipt.get('status')!='archived':
            return {'cacheable':False,'events':events,'fetched_at_epoch':captured['fetched_at_epoch']}
        return {'cacheable':True,'symbol':symbol,'typek':typek,'year':year,'month':month,
                'parser_version':mops.CONFERENCE_PARSER_VERSION,'codec':codec,'receipt':receipt,
                'fetched_at_epoch':captured['fetched_at_epoch'],'has_events':bool(captured['records'])}
    options={'freshness_seconds':freshness,
             'result_ttl':lambda p:freshness if p.get('cacheable') and p.get('has_events') else min(freshness,EMPTY_SECONDS) if p.get('cacheable') else 1,
             'lock_wait_seconds':0}
    value,meta=shared_fetch(key,acquire,force_refresh=force_refresh,**options)
    if (not meta.get('error_kind') and not meta.get('stale') and meta.get('cache_hit') and
            isinstance(value,dict) and value.get('cacheable') is False):
        # An unarchivable response can be returned by its native call, but is
        # never accepted on a later warm call. Recovery keeps the same lock and
        # provider guards and records its actual transport/time below.
        _invalidate(key)
        value,meta=shared_fetch(key,acquire,force_refresh=True,**options)
    if meta.get('error_kind') or meta.get('stale'):
        if failure:
            exc=failure[0]
        else:
            details={**meta,'http_request_sent':False,'http_request_count':0}
            from search_provider_runtime import record_observation, cooldown_state, scope_key
            blocked=cooldown_state(scope_key('MOPS',endpoint='mopsov_investor_conference'))
            record_observation('MOPS',time.monotonic(),outcome='cooldown',source='earnings_call',details=details,sent=False)
            kind=('single_flight_busy' if meta.get('error_kind')=='single_flight_busy' else
                  blocked.get('error_kind') or ('stale_source' if meta.get('stale') else 'cooldown'))
            exc=SourceResponseError(kind,status_code=blocked.get('http_status'),parser_version=mops.CONFERENCE_PARSER_VERSION)
            exc.diagnostic.update(http_request_sent=False,http_request_count=0)
        exc.diagnostic.update({k:v for k,v in meta.items() if k!='error_kind'},
                              cache_error_kind=meta.get('error_kind') or 'stale_source')
        raise exc
    if isinstance(value,dict) and value.get('cacheable') is False:
        events,stamp,receipt=value['events'],value['fetched_at_epoch'],None
    else:
        try:events,stamp,receipt=_replay(value,symbol,typek,year,month,freshness)
        except (ValueError,TypeError,KeyError,OverflowError,OSError,EOFError,UnicodeError,SourceResponseError) as error:
            if not meta.get('cache_hit') and isinstance(captured.get('records'),list):
                # The real HTTP response already passed the native parser. A
                # local readback failure cannot turn that acquisition into an
                # empty result or HTTP0; only this cache copy is discarded.
                _invalidate(key)
                events,stamp,receipt=captured['records'],captured['fetched_at_epoch'],None
                captured['cache_warning_kind']=type(error).__name__
            else:
                exc=SourceResponseError('original_unverified',parser_version=mops.CONFERENCE_PARSER_VERSION)
                exc.diagnostic.update(cache_hit=bool(meta.get('cache_hit')),http_request_sent=False,
                                      http_request_count=0,fetched_at_epoch=None)
                raise exc from error
    selected=events[:max(1,int(limit or 3))]
    details={'cache_hit':bool(meta.get('cache_hit')),'stale':False,'fetched_at_epoch':stamp,
             'status':('skipped_fresh_cache' if meta.get('cache_hit') else 'success') if selected else 'degraded_enrichment',
             'outcome':'results' if selected else 'valid_empty','record_count':len(selected),
             'http_request_sent':not meta.get('cache_hit'),'http_request_count':0 if meta.get('cache_hit') else 1,
             'source_query_year':year,'source_query_month':month,'source_symbol':symbol,
             'parser_version':mops.CONFERENCE_PARSER_VERSION}
    if receipt:details['raw_http_receipt']=receipt
    if captured.get('cache_warning_kind'):details['cache_warning_kind']=captured['cache_warning_kind']
    if diagnostics is not None:diagnostics.update(details)
    if meta.get('cache_hit'):_record_cache(details,len(selected))
    return selected
