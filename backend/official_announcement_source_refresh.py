"""Bounded, network-free admission of ordinary issuer announcement originals.

The native acquisition retains request-bound indexes and checked detail bytes.
Each source-only boundary reparses those bytes through the original collector;
this module never issues an HTTP request, renews a cache, or changes source time.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
import time
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import HTTPException
from official_response_evidence import archive_response, read_response
from data_fetch.market_sources import twse_announcement_progress as progress
from data_fetch.market_sources.twse_history_transport import IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL

TICKER = '2851.TW'
# Legacy v1 packets retain their original, fixed issuer contract. New issuers
# require v2 raw index/body replay against the report's saved equity identity.
ISSUERS = {
    '2851.TW': '中再保', '1216.TW': '統一', '2308.TW': '台達電',
    '2881.TW': '富邦金', '2882.TW': '國泰金', '2885.TW': '元大金',
    '2891.TW': '中信金', '4763.TW': '材料*-KY', '6214.TW': '精誠',
    '9945.TW': '潤泰新', '2812.TW': '台中銀',
}


def supports(ticker):
    from data_fetch.market_sources.mops_json_company_history import TICKERS
    return (isinstance(ticker, str) and re.fullmatch(r'[1-9]\d{3,5}\.TW', ticker) is not None
            and not ticker.startswith('91') and ticker not in TICKERS)

PROVIDER = 'TWSE company announcement history'
POLICY = 'ordinary-announcement-originals-v1'
DYNAMIC_POLICY = 'ordinary-announcement-originals-v2'
LOCAL_REPLAY_SECONDS = 2.
IDENTITY_FIELDS = ('ticker','stock_id','company_name','company_identity','instrument_type','quote_type','quoteType')
BASE_KEYS = {'request_fingerprint','url','method','receipt','fresh_until_epoch'}


def validate_context(data, ticker):
    from news_record_utils import clean_text
    if not isinstance(data, dict) or not supports(ticker) or data.get('ticker') != ticker:
        raise ValueError('ordinary announcement ticker mismatch')
    identity = data.get('company_identity')
    name = identity.get('official_name') if isinstance(identity, dict) else None
    if (not isinstance(identity, dict) or identity.get('ticker') != ticker
            or identity.get('stock_id') != ticker.split('.')[0]
            or data.get('stock_id') not in (None, '', ticker.split('.')[0])
            or not isinstance(name, str) or not 0 < len(name) <= 256 or clean_text(name) != name
            or re.search(r'-DR(?:\b|$)', name, re.IGNORECASE)
            or ticker in ISSUERS and name != ISSUERS[ticker]
            or identity.get('instrument_type') != 'EQUITY'
            or any(identity.get(k) not in (None, '', 'EQUITY') for k in ('quote_type','quoteType'))
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type','quote_type','quoteType'))):
        raise ValueError('ordinary announcement identity mismatch')
    forbidden = identity.get('forbidden_aliases', [])
    if (not isinstance(forbidden, (list, tuple)) or any(not isinstance(x, str)
            or clean_text(x).strip().strip('*').strip() == name.strip('*').strip() for x in forbidden)):
        raise ValueError('ordinary announcement forbidden identity')
    legal = identity.get('legal_name')
    if legal is not None and (not isinstance(legal, str) or not 0 < len(legal) <= 256 or clean_text(legal) != legal):
        raise ValueError('ordinary announcement legal identity invalid')


def _check(deadline):
    progress._deadline(deadline)


def _request(method, url, kwargs, *, ticker=TICKER):
    request = {'method':method, 'url':url, 'params':kwargs.get('params'),
               'data':kwargs.get('data'), 'payload':kwargs.get('json')}
    if (not supports(ticker) or url not in {IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL}
            or method != ('GET' if url in {IIH_URL, IIH_EN_URL} else 'POST')):
        raise ValueError('unrecognized ordinary announcement index')
    # Public issuer/date parameters only. Exact values are matched against the
    # collector's independently regenerated request during consumer replay.
    allowed = ({'code'} if url in {IIH_URL, IIH_EN_URL} else
               {'step','RADIO_CM','TYPEK','CO_MARKET','CO_ID','PRO_ITEM','SUBJECT','SDATE','EDATE','lang','AN'}
               if url == EZ_URL else {'companyId','year','month','firstDay','lastDay'})
    key = 'params' if url in {IIH_URL, IIH_EN_URL} else 'data' if url == EZ_URL else 'payload'
    values = request[key]
    if (not isinstance(values, dict) or set(values) != allowed
            or any(not isinstance(v, str) or len(v) > 32 for v in values.values())
            or any(request[k] is not None for k in {'params','data','payload'}-{key})
            or values.get('code', values.get('CO_ID', values.get('companyId'))) != ticker.split('.')[0]):
        raise ValueError('invalid public index parameters')
    return request


def _fingerprint(request):
    return progress.request_fingerprint(request['method'], request['url'], params=request['params'],
                                        data=request['data'], payload=request['payload'])


def _target(request):
    return request['url'] + ('?' + urlencode(request['params']) if request['params'] else '')


def _read_index(entry, deadline, *, ticker=TICKER):
    _check(deadline)
    if not isinstance(entry, dict) or set(entry) != {'request','request_fingerprint','receipt','fresh_until_epoch'}:
        raise ValueError('index receipt shape')
    req = entry['request']
    if not isinstance(req, dict) or set(req) != {'method','url','params','data','payload'}:
        raise ValueError('index request shape')
    _request(req['method'], req['url'], {'params':req['params'], 'data':req['data'], 'json':req['payload']}, ticker=ticker)
    if entry['request_fingerprint'] != _fingerprint(req):
        raise ValueError('index request fingerprint')
    proof = entry['receipt']
    limit = 2_000_000 if req['url'] == EZ_URL else 256_000
    if (not isinstance(proof, dict) or set(proof) != progress.RECEIPT_KEYS
            or proof['status'] != 'archived' or proof['source_url'] != _target(req)
            or type(proof['http_status']) is not int or proof['http_status'] != 200
            or proof['evidence_kind'] != 'raw_http_response_bytes'
            or proof['historical_point_in_time_verified'] is not False or proof['finality_guaranteed'] is not False
            or type(proof['raw_response_bytes']) is not int or not 0 < proof['raw_response_bytes'] <= limit):
        raise ValueError('index original metadata')
    _fresh(entry)
    body = read_response(proof, max_bytes=limit)
    if len(body) != proof['raw_response_bytes']:
        raise ValueError('index original bytes')
    _fresh(entry)
    _check(deadline)
    return body


def _fresh(entry):
    stamp, until = entry['receipt']['retrieved_at'], entry['fresh_until_epoch']
    if (not progress._number(stamp) or not progress._number(until)
            or not 0 < stamp < until <= stamp + progress.RAW_TTL or not stamp <= time.time() < until):
        raise ValueError('expired announcement original')


def archive_index_response(response, method, url, kwargs, *, deadline, ticker=TICKER):
    """Only the completed native transport may create a new index receipt."""
    _check(deadline)
    req = _request(method, url, kwargs, ticker=ticker)
    marker = response.extensions.get('announcement_index_native_response')
    if (not isinstance(marker, dict) or set(marker) != {'method','url','retrieved_at','complete','http_status_observed','response_sha256','request_fingerprint'}
            or marker['method'] != method or marker['url'] != _target(req)
            or marker['request_fingerprint'] != _fingerprint(req) or marker['complete'] is not True
            or marker['http_status_observed'] is not True or type(response.status_code) is not int
            or response.status_code != 200 or not progress._number(marker['retrieved_at'])
            or marker['response_sha256'] != hashlib.sha256(response.content).hexdigest()):
        raise ValueError('index native original unavailable')
    limit = 2_000_000 if url == EZ_URL else 256_000
    proof = archive_response(response.content, source_url=_target(req), retrieved_at=marker['retrieved_at'], max_bytes=limit)
    entry = {'request':req, 'request_fingerprint':_fingerprint(req), 'receipt':proof,
             'fresh_until_epoch':marker['retrieved_at']+progress.RAW_TTL}
    _read_index(entry, deadline, ticker=ticker)
    return entry


def bundle(indexes, *, cutoff, coverage, ticker=TICKER):
    return {'policy':POLICY if ticker in ISSUERS else DYNAMIC_POLICY, 'ticker':ticker, 'selection_cutoff':cutoff.isoformat(),
            'coverage_status':coverage, 'indexes':deepcopy(indexes)}


def _verify_dynamic_identity(index_map, data):
    """Bind optional IIH names from raw bytes, never from packet assertions.

    The normal parser independently binds every admitted row's code/name to
    its exact listed-company detail header. EZ-only replay has that same
    binding, but cannot establish a non-null saved legal name.
    """
    from data_fetch.market_sources.twse_company_history import _english_iih_name, _iih_names
    identity = data['company_identity']
    legal_seen = False
    for item, raw in index_map.values():
        source_url = item['request']['url']
        if source_url == IIH_EN_URL:
            payload = json.loads(raw)
            name = _english_iih_name(payload, identity['stock_id'])
            english_names = identity.get('english_names')
            if (not isinstance(english_names, list) or not english_names
                    or not any(isinstance(candidate, str) and candidate.strip().casefold() == name.casefold()
                               for candidate in english_names)):
                raise ValueError('native IIH English name mismatch')
            legal_seen = True  # English name + exact company code bind this route when only the English index was used.
            continue
        if source_url != IIH_URL:
            continue
        payload = json.loads(raw)
        short, legal = _iih_names(payload, identity['stock_id'])
        if short is not None and short != identity['official_name']:
            raise ValueError('native IIH short name mismatch')
        if identity.get('legal_name') is not None:
            if legal != identity['legal_name']:
                raise ValueError('native IIH legal name mismatch')
            legal_seen = True
    if identity.get('legal_name') is not None and not legal_seen:
        raise ValueError('native legal identity unavailable')


def _final(entries, deadline, *, warm=False, aggregate_until=None):
    expiries = []
    for entry in entries:
        _fresh(entry)
        until = entry['fresh_until_epoch']
        if 'url' in entry:
            base = {k:entry[k] for k in BASE_KEYS}
            current, _ = progress.current_admission(base, cached=warm or entry['cache_hit'])
            until = min(until, current['fresh_until_epoch'])
            if aggregate_until is not None and aggregate_until > until:
                raise ValueError('aggregate exceeds physical original expiry')
        expiries.append((entry['receipt']['retrieved_at'], until))
    # Later reads can consume an earlier original's remaining lifetime. All
    # adopted originals must be fresh at this same final handoff instant.
    _check(deadline)
    handed_off_at = time.time()
    if any(not stamp <= handed_off_at < until for stamp, until in expiries):
        raise ValueError('announcement original expired before common handoff')
    _check(deadline)


def _replay_records_equal(rebuilt, records):
    # Old cache values retain their old shape; do not retroactively certify
    # them. A partial/present binding still requires full exact replay equality.
    from official_event_identity import FIELDS
    if len(rebuilt) != len(records):
        return False
    comparable = []
    for new, old in zip(rebuilt, records):
        item = dict(new)
        if not any(field in old for field in FIELDS):
            for field in FIELDS:
                item.pop(field, None)
        comparable.append(item)
    return comparable == records


def verify_value(records, audit, data, *, deadline, producer=False):
    """Reconstruct at the original cutoff, then admit under current original TTL."""
    from data_fetch.market_sources.twse_company_history import fetch_recent_company_announcements
    ticker = data.get('ticker') if isinstance(data, dict) else None
    validate_context(data, ticker)
    _check(deadline)
    if (not isinstance(records, list) or not 1 <= len(records) <= 64 or any(not isinstance(r, dict) for r in records)
            or not isinstance(audit, dict) or audit.get('provider') != PROVIDER or audit.get('source') != 'recent_catalysts'
            or audit.get('status') not in {'success','degraded_enrichment','skipped_fresh_cache'}
            or type(audit.get('record_count')) is not int or audit['record_count'] != len(records)
            or audit.get('stale') is True or not progress._number(audit.get('fetched_at_epoch'))
            or not 0 < audit['fetched_at_epoch'] <= time.time()
            or type(audit.get('http_request_count')) is not int or not 0 <= audit['http_request_count'] <= 69
            or audit.get('http_request_sent') is not (audit['http_request_count'] > 0)):
        raise ValueError('ordinary announcement audit invalid')
    archive = audit.get('source_record_archive')
    if not isinstance(archive, list) or len(archive) != len(records)+1:
        raise ValueError('ordinary announcement archive missing')
    packet = archive[-1]
    if (not isinstance(packet, dict) or set(packet) != {'policy','ticker','selection_cutoff','coverage_status','indexes'}
            or packet['policy'] not in {POLICY, DYNAMIC_POLICY} or packet['ticker'] != ticker
            or packet['policy'] == POLICY and ticker not in ISSUERS
            or packet['coverage_status'] not in {'partial','window_complete'}
            or packet['coverage_status'] != audit.get('coverage_status')
            or audit['status'] == 'success' and packet['coverage_status'] != 'window_complete'):
        raise ValueError('ordinary announcement packet invalid')
    cutoff = datetime.fromisoformat(packet['selection_cutoff'])
    if cutoff.tzinfo is None or not 0 < cutoff.timestamp() <= time.time():
        raise ValueError('ordinary announcement cutoff invalid')
    indexes = packet['indexes']
    if not isinstance(indexes, list) or not 1 <= len(indexes) <= 5:
        raise ValueError('ordinary announcement index count')
    index_map, body_map = {}, {}
    for item in indexes:
        raw = _read_index(item, deadline, ticker=ticker)
        if item['request_fingerprint'] in index_map or not cutoff.timestamp() <= item['receipt']['retrieved_at'] <= cutoff.timestamp()+20:
            raise ValueError('duplicate or mistimed index')
        index_map[item['request_fingerprint']] = (item, raw)
    if packet['policy'] == DYNAMIC_POLICY:
        _verify_dynamic_identity(index_map, data)
    warm = audit.get('cache_hit') is True and audit['http_request_count'] == 0
    checked_bodies = []
    for item in archive[:-1]:
        if (not isinstance(item, dict) or set(item) != BASE_KEYS|{'cache_hit','reusable'}
                or type(item['cache_hit']) is not bool or type(item['reusable']) is not bool
                or item['url'] in body_map):
            raise ValueError('ordinary announcement detail receipt shape')
        base = {k:item[k] for k in BASE_KEYS}
        checked = progress.recheck(base, deadline=deadline, cached=warm or item['cache_hit'])
        checked_bodies.append({**checked, 'cache_hit':item['cache_hit'], 'reusable':item['reusable']})
        raw = read_response(checked['receipt'], max_bytes=progress.MAX_BYTES)
        body_map[item['url']] = (item, raw)
    minimum_body_stamp = min(item['receipt']['retrieved_at'] for item in archive[:-1])
    if audit.get('body_fetched_at_epoch') != minimum_body_stamp:
        raise ValueError('body observation epoch mismatch')
    stamp = audit['fetched_at_epoch']
    # Cold callback completion is not the body observation epoch. Its native
    # chain below remains usable without optional aggregate persistence; the
    # guard publishes only original body time. A warm callback's unequal stamp
    # still needs its exact saved aggregate, never a substituted current time.
    native_attempt = producer and not warm and audit['http_request_count'] > 0
    if stamp != minimum_body_stamp and not native_attempt:
        key = 'shared_provider:v1:'+hashlib.sha256(f'twse-company-announcements:v3:{ticker}'.encode()).hexdigest()
        try:
            aggregate, aggregate_until = progress._stored(key) if producer else (None, None)
        except progress.CACHE_ERRORS:
            aggregate, aggregate_until = None, None
        pair = aggregate.get('value') if isinstance(aggregate,dict) else None
        if (not producer or not isinstance(pair,(list,tuple)) or len(pair)!=2
                or pair[0] != records or not isinstance(pair[1],dict)
                or pair[1].get('source_record_archive') != archive
                or aggregate.get('fetched_at_epoch') != stamp
                or not progress._number(aggregate_until) or not time.time() < aggregate_until):
            raise ValueError('component observation epoch mismatch')
    observations = audit.get('request_observations')
    if (not isinstance(observations, list) or len(observations) > 69
            or any(not isinstance(o,dict) or type(o.get('http_request_count')) is not int
                   or o['http_request_count'] not in {0,1} for o in observations)
            or sum(o['http_request_count'] for o in observations) != audit['http_request_count']):
        raise ValueError('native HTTP observation count mismatch')
    old = sum(item['cache_hit'] for item in archive[:-1])
    historical_counts = (old, len(records)-old, old==len(records))
    expected_counts = (len(records), 0, True) if warm else historical_counts
    supplied_counts = (audit.get('detail_cache_hit_count'),audit.get('detail_new_body_count'),audit.get('body_cache_hit'))
    if (any(type(v) is not int for v in supplied_counts[:2]) or type(supplied_counts[2]) is not bool
            or supplied_counts != expected_counts and not (producer and warm and supplied_counts == historical_counts)):
        raise ValueError('body acquisition count mismatch')
    partial_attempt = (not warm and packet['coverage_status']=='partial'
                       and audit['status']=='degraded_enrichment' and audit['http_request_count']>0
                       and audit.get('cache_hit') is False and audit.get('event_kind')=='aggregate')
    if expected_counts[2] and not partial_attempt and (audit.get('cache_hit') is not True
            or audit.get('event_kind') != 'cache_hit' or audit['status'] == 'success'):
        raise ValueError('old bodies cannot become new acquisition')
    if not warm:
        for item in indexes:
            req = item['request']
            if not any(o.get('url') == req['url'] and o.get('method') == req['method']
                    and o.get('request_fingerprint') == item['request_fingerprint']
                    and o.get('status') == 'success' and o.get('response_complete') is True
                    and o.get('http_status_observed') is True and type(o.get('http_status')) is int
                    and o['http_status'] == 200 and o['http_request_count'] == 1
                    and o.get('response_sha256') == item['receipt']['raw_response_sha256']
                    and o.get('response_bytes') == item['receipt']['raw_response_bytes']
                    and o.get('response_retrieved_at_epoch') == item['receipt']['retrieved_at'] for o in observations):
                raise ValueError('index lacks its native acquisition observation')
        for item in archive[:-1]:
            if item['cache_hit']:
                continue
            if (not cutoff.timestamp() <= item['receipt']['retrieved_at'] <= cutoff.timestamp()+20
                    or not any(o.get('url') == item['url'] and o.get('method') == 'GET'
                        and o.get('request_fingerprint') == item['request_fingerprint']
                        and o.get('status') == 'success' and o.get('response_complete') is True
                        and o.get('http_status_observed') is True and o.get('http_status') == 200
                        and o['http_request_count'] == 1
                        and o.get('response_sha256') == item['receipt']['raw_response_sha256']
                        and o.get('response_retrieved_at_epoch') == item['receipt']['retrieved_at']
                        and o.get('response_bytes') == item['receipt']['raw_response_bytes'] for o in observations)):
                raise ValueError('new body lacks its native acquisition observation')
    used_indexes, used_bodies = set(), set()

    def replay(method, url, **kwargs):
        _check(deadline)
        if url in {IIH_URL, IIH_EN_URL, EZ_URL, JSON_URL}:
            req = _request(method, url, kwargs, ticker=ticker)
            fp = _fingerprint(req)
            if fp not in index_map:
                raise ValueError('saved index unavailable')
            used_indexes.add(fp)
            raw = index_map[fp][1]
        else:
            if method != 'GET' or url not in body_map:
                raise ValueError('saved body unavailable')
            used_bodies.add(url)
            raw = body_map[url][1]
        charset = 'big5' if urlsplit(url).path == '/server-java/t05sr01_1_e' else 'utf-8'
        return httpx.Response(200, content=raw, headers={'content-type':f'text/html; charset={charset}'},
                              request=httpx.Request(method, url))

    rebuilt, diagnostic = fetch_recent_company_announcements(ticker, now=cutoff,
        get=lambda url, **kw: replay('GET',url,**kw), post=lambda url, **kw: replay('POST',url,**kw))
    _check(deadline)
    def has_identity_prefix(record):
        identity = data['company_identity']
        stock_id = ticker.split('.')[0]
        if record.get('issuer_identity_basis') == 'TWSE company ID + MOPS detail header':
            return record['text'].startswith(f"{identity['official_name']}（{stock_id}） ")
        if record.get('issuer_identity_basis') != 'TWSE English company ID + English MOPS detail header':
            return False
        prefix, separator, _ = record['text'].partition(f"（{stock_id}） ")
        return bool(separator and isinstance(identity.get('english_names'), list)
                    and any(isinstance(name, str) and name.strip().casefold() == prefix.casefold()
                            for name in identity['english_names']))

    if used_indexes != set(index_map):
        raise ValueError('ordinary announcement replay did not consume every archived index')
    if used_bodies != set(body_map):
        raise ValueError('ordinary announcement replay did not consume every archived detail')
    if not _replay_records_equal(rebuilt, records):
        raise ValueError('ordinary announcement replay record mismatch')
    if any(not has_identity_prefix(r) or r['content_truncated'] for r in rebuilt):
        raise ValueError('ordinary announcement replay identity or content mismatch')
    if packet['coverage_status'] == 'window_complete' and diagnostic['coverage_status'] != 'window_complete':
        raise ValueError('ordinary announcement replay coverage mismatch')
    entries = [*indexes, *checked_bodies]
    expiry = audit.get('progress_fresh_until_epoch')
    if not progress._number(expiry) or not time.time() < expiry <= min(e['fresh_until_epoch'] for e in entries):
        raise ValueError('ordinary announcement aggregate expiry mismatch')
    _final(entries, deadline, warm=warm, aggregate_until=expiry)
    return entries


def guard_result(result, data):
    from data_fetch.types import ProviderResult
    if result.status not in {'success','degraded_enrichment','skipped_fresh_cache'} or not result.value:
        return result
    deadline = time.monotonic()+LOCAL_REPLAY_SECONDS
    try:
        if result.audit.get('status') != result.status:
            raise ValueError('ordinary announcement status mismatch')
        entries = verify_value(result.value, result.audit, data, deadline=deadline, producer=True)
        result.audit['fetched_at_epoch'] = result.audit['body_fetched_at_epoch']
        # An aggregate cache hit reuses all body observations, irrespective of
        # the historical cold counts preserved inside its saved raw archive.
        if result.audit.get('cache_hit') is True and result.audit['http_request_count'] == 0:
            result.audit.update(body_cache_hit=True, detail_new_body_count=0, detail_cache_hit_count=len(result.value))
        _final(entries, deadline, warm=result.audit.get('cache_hit') is True and result.audit['http_request_count']==0,
               aggregate_until=result.audit['progress_fresh_until_epoch'])
        return result
    except Exception as exc:
        audit = {**result.audit, 'status':'error','record_count':0,'coverage_status':'partial',
                 'error_kind':getattr(exc,'error_kind','original_unverified'),
                 'message':'公告完整原件核對未完成；保留原快照。','progress_resume_possible':False}
        return ProviderResult('recent_catalysts',PROVIDER,'error',value=[],audit=audit,duration_ms=result.duration_ms)


def merge_source(old_data, old_audits, value, audits, ticker):
    from source_content_selection import select_company_records
    from news_freshness_policy import apply_news_freshness
    from report_source_refresh import _reassess_original_freshness
    deadline = time.monotonic()+LOCAL_REPLAY_SECONDS
    try:
        validate_context(old_data, ticker)
        if not isinstance(audits, list) or len(audits) != 1 or not audits[0].get('fetch_id'):
            raise ValueError('ordinary announcement acquisition receipt missing')
        entries = verify_value(value, audits[0], old_data, deadline=deadline)
        context = {k:deepcopy(old_data[k]) for k in IDENTITY_FIELDS if k in old_data}
        accepted, _ = select_company_records(value, context, cutoff=time.time())
        if len(accepted) != len(value):
            raise ValueError('ordinary announcement current window/issuer mismatch')
        buckets = ('recent_catalysts','additional_recent_catalysts','historical_catalysts','unverified_catalysts','identity_rejected_catalysts')
        previous = [r for k in buckets for r in (old_data.get(k) or []) if isinstance(r,dict)]
        merged = deepcopy(old_data)
        archive = deepcopy(merged.get('source_record_archive') or [])
        original_entry = {'source':'recent_catalysts','provider':PROVIDER,'originals':deepcopy(audits[0]['source_record_archive'])}
        if original_entry not in archive:
            archive.append(original_entry)
        old_provider = [a for a in old_audits if a.get('source')=='recent_catalysts' and a.get('provider')==PROVIDER]
        if old_provider:
            archive.append({'source':'recent_catalysts','reason':'superseded_component_audits','audits':deepcopy(old_provider)})
        merged['source_record_archive'] = archive
        apply_news_freshness(context, records=[*accepted,*previous], cutoff=time.time())
        for key in (*buckets,'news_selection'):
            merged[key] = deepcopy(context[key])
        merged['source_audit'] = [deepcopy(a) for a in old_audits if a not in old_provider]+deepcopy(audits)
        _reassess_original_freshness(merged,ticker,'recent_catalysts',audits)
        _final(entries, deadline, warm=audits[0].get('cache_hit') is True and audits[0]['http_request_count']==0,
               aggregate_until=audits[0]['progress_fresh_until_epoch'])
        return merged
    except Exception as exc:
        raise HTTPException(status_code=502, detail='公告完整原件、身分或期限未通過核對；原快照保持') from exc
