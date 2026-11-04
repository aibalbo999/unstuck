"""Replay complete portal originals and their independent, unrenewed owners."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import math
import time
from urllib.parse import urlsplit

from official_response_evidence import archive_response, read_response
from .tigerair_yes123 import (TICKER, SHORT, LEGAL, UBN, PROVIDER, PAGE, ARTICLE,
    PROFILE, MAX_BYTES, MAX_POSTINGS, TTL, TZ, canonical_detail_url,
    parse_mapping, parse_listing, parse_detail, _json)

RAW_PREFIX = 'tigerair-yes123-raw:v1:'
SCHEMA = 'tigerair-yes123-http.v1'
# TWSE's historical listing table names 6757 as 台灣虎航-創 (112.08.15).
# https://www.twse.com.tw/rwd/zh/company/newlisting?response=html
# Only this exact saved label is compatible; every accepted source still
# replays the current full roster with SHORT, LEGAL, UBN and registered site.
SAVED_SHORT = '台灣虎航-創'
ARCHIVE_FIELDS = {'status', 'source_url', 'retrieved_at', 'http_status',
    'raw_response_sha256', 'raw_response_path', 'raw_response_bytes', 'evidence_kind',
    'historical_point_in_time_verified', 'finality_guaranteed'}


def allowed_url(url):
    if url in (PAGE, ARTICLE, PROFILE):
        return url
    return canonical_detail_url(url)


def _manifest(receipt):
    return json.dumps({k: v for k, v in receipt.items() if k != 'metadata_manifest'},
                      sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode()


def native_receipt(raw, url, stamp, transport):
    """Only the bounded native consumer calls this after complete curl checks."""
    allowed_url(url)
    expected = {'http_status': 200, 'http_status_observed': True,
        'response_complete': True, 'http_request_sent': True, 'return_code': 0,
        'ssl_verify_result': 0, 'proxy_used': 0, 'num_redirects': 0,
        'response_bytes': len(raw)}
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES
            or type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0
            or not isinstance(transport, dict) or transport != expected
            or any(type(transport[k]) is not type(v) for k, v in expected.items())):
        raise ValueError('yes123 native complete transport unverified')
    receipt = {'schema': SCHEMA, 'url': url, 'method': 'GET', 'encoding': 'utf-8',
        'fetched_at_epoch': stamp, 'native_transport': deepcopy(transport),
        'raw_receipt': archive_response(raw, source_url=url, retrieved_at=stamp,
                                        http_status=200, max_bytes=MAX_BYTES)}
    receipt['metadata_manifest'] = archive_response(_manifest(receipt), source_url=url,
        retrieved_at=stamp, http_status=None, evidence_kind='private_acquisition_manifest')
    return receipt


def _archived(proof, url, stamp, kind, status, limit):
    if (not isinstance(proof, dict) or set(proof) != ARCHIVE_FIELDS
            or proof.get('status') != 'archived' or proof.get('source_url') != url
            or proof.get('retrieved_at') != stamp or proof.get('evidence_kind') != kind
            or proof.get('http_status') != status or type(proof.get('http_status')) is not type(status)
            or proof.get('historical_point_in_time_verified') is not False
            or proof.get('finality_guaranteed') is not False):
        raise ValueError('yes123 original identity or metadata invalid')
    raw = read_response(proof, max_bytes=limit)
    if type(proof.get('raw_response_bytes')) is not int or not 0 < len(raw) == proof['raw_response_bytes'] <= limit:
        raise ValueError('yes123 full original bytes missing')
    return raw


def receipt_body(receipt, url, now):
    from cache_store import get_cache_json
    allowed_url(url)
    if (not isinstance(receipt, dict) or set(receipt) != {'schema', 'url', 'method', 'encoding',
            'fetched_at_epoch', 'native_transport', 'raw_receipt', 'metadata_manifest'}
            or receipt.get('schema') != SCHEMA or receipt.get('url') != url
            or receipt.get('method') != 'GET' or receipt.get('encoding') != 'utf-8'):
        raise ValueError('yes123 exact original receipt missing')
    stamp = receipt['fetched_at_epoch']
    if (type(stamp) not in (int, float) or type(now) not in (int, float)
            or not math.isfinite(stamp) or not math.isfinite(now) or not 0 <= now - stamp < TTL):
        raise ValueError('yes123 original expired or future')
    raw = _archived(receipt['raw_receipt'], url, stamp, 'raw_http_response_bytes', 200, MAX_BYTES)
    transport = {'http_status': 200, 'http_status_observed': True,
        'response_complete': True, 'http_request_sent': True, 'return_code': 0,
        'ssl_verify_result': 0, 'proxy_used': 0, 'num_redirects': 0,
        'response_bytes': len(raw)}
    if (receipt['native_transport'] != transport
            or any(type(receipt['native_transport'].get(k)) is not type(v) for k, v in transport.items())
            or _archived(receipt['metadata_manifest'], url, stamp,
                'private_acquisition_manifest', None, 16384) != _manifest(receipt)):
        raise ValueError('yes123 native receipt metadata changed')
    saved = get_cache_json('shared_provider:v1:' + sha256((RAW_PREFIX + url).encode()).hexdigest())
    if not isinstance(saved, dict) or saved.get('error_kind') or saved.get('value') != receipt:
        raise ValueError('yes123 independent original owner missing or changed')
    start, end = saved.get('fetched_at_epoch'), saved.get('fresh_until_epoch')
    if (type(start) not in (int, float) or type(end) not in (int, float)
            or not math.isfinite(start) or not math.isfinite(end)
            or not 0 <= start - stamp <= 5 or not start <= now < end
            or not 0 < end - start <= TTL + 1):
        raise ValueError('yes123 owner observation window invalid')
    return raw


def valid_context(data):
    if not isinstance(data, dict) or data.get('ticker') != TICKER or data.get('quote_type') != 'EQUITY':
        return False
    i = data.get('company_identity')
    if (not isinstance(i, dict) or i.get('ticker') != TICKER or i.get('official_name') not in (SHORT, SAVED_SHORT)
            or i.get('instrument_type') != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quoteType'))
            or any(v not in (None, '', '6757') for v in (data.get('stock_id'), i.get('stock_id')))
            or i.get('legal_name') not in (None, '', LEGAL) or i.get('official_ubn') not in (None, '', UBN)):
        return False
    english = i.get('english_names', [])
    name = data.get('company_name')
    return (isinstance(english, list) and all(isinstance(v, str) for v in english)
            and isinstance(name, str) and bool(name.strip())
            and all(p.strip() and p.strip() in {SHORT, SAVED_SHORT, LEGAL, *english} for p in name.split(' / ')))


def verified_issuer(evidence, *, now=None):
    from cache_store import get_cache_json
    from runtime_paths import current_runtime_paths
    from .official_company_legal_name import (parse_roster, select_legal_name,
        verified_legal_name_from_evidence, verified_official_ubn_from_evidence,
        URLS, MAX_BYTES as MASTER_LIMIT)
    now = time.time() if now is None else now
    try:
        stamp = evidence['fetched_at_epoch']
        if (type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 <= now - stamp < 86400
                or verified_legal_name_from_evidence(evidence, TICKER, SHORT) != LEGAL
                or verified_official_ubn_from_evidence(evidence, TICKER, SHORT) != UBN):
            return False
        digest = evidence['response_sha256']
        raw = read_response({'raw_response_sha256': digest, 'raw_response_path': str(
            current_runtime_paths().cache_dir / 'official-response-evidence' / (digest + '.gz'))}, max_bytes=MASTER_LIMIT)
        rows = _json(raw)
        roster = parse_roster(raw, '.TW')
        if len(roster['entries']) < 800:
            return False
        selected = select_legal_name(roster, TICKER, SHORT, today=datetime.fromtimestamp(now, TZ).date())
        if not selected or any(evidence.get(k) != selected.get(k) for k in (
                'ticker', 'legal_name', 'official_short_name', 'official_ubn', 'as_of', 'source_url', 'response_sha256')):
            return False
        issuer = [r for r in rows if str(r.get('公司代號')) == '6757']
        if len(issuer) != 1:
            return False
        p = urlsplit(str(issuer[0].get('網址') or ''))
        if (p.scheme not in {'http', 'https'} or p.netloc not in {'www.tigerairtw.com', 'tigerairtw.com'}
                or p.path not in {'', '/'} or p.query or p.fragment):
            return False
        key = 'shared_provider:v1:' + sha256(b'official-company-roster:v2:.TW').hexdigest()
        saved = get_cache_json(key)
        return (isinstance(saved, dict) and not saved.get('error_kind') and saved.get('value') == roster
                and saved.get('fetched_at_epoch') == stamp
                and type(saved.get('fresh_until_epoch')) in (int, float)
                and math.isfinite(saved['fresh_until_epoch']) and now < saved['fresh_until_epoch']
                and 0 < saved['fresh_until_epoch'] - stamp <= 86401
                and evidence.get('source_url') == URLS['.TW'])
    except (ValueError, TypeError, KeyError, OSError, OverflowError, AttributeError, UnicodeError, RecursionError):
        return False


def parse_receipts(receipts, *, now):
    if not isinstance(receipts, list) or not 4 <= len(receipts) <= 3 + MAX_POSTINGS:
        raise ValueError('yes123 complete selected receipt set missing')
    parse_mapping(receipt_body(receipts[0], PAGE, now), receipt_body(receipts[1], ARTICLE, now))
    listing = parse_listing(receipt_body(receipts[2], PROFILE, now))
    if len(receipts) != 3 + len(listing['selected']):
        raise ValueError('yes123 selected posting originals incomplete')
    jobs = [parse_detail(receipt_body(r, c['url'], now), c,
                        observed_at=r['fetched_at_epoch'], now=now)
            for c, r in zip(listing['selected'], receipts[3:])]
    return {'status': 'partial', 'source': PROVIDER, 'source_url': PROFILE,
        'ticker': TICKER, 'company_name': LEGAL, 'official_ubn': UBN,
        'evidence_kind': 'official_linked_portal_posting_samples',
        'verified_sample_job_count': len(jobs), 'current_open_job_count': None,
        'job_count': None, 'job_postings': jobs,
        'observed_first_page_jobs': listing['observed_first_page_jobs'],
        'publisher_page_count': listing['page_count'], 'observed_pages': 1,
        'first_publication_verified': False, 'employer_deadline_verified': False,
        'fetched_at_epoch': min(r['fetched_at_epoch'] for r in receipts),
        'response_sha256': sha256('|'.join(r['raw_receipt']['raw_response_sha256'] for r in receipts).encode()).hexdigest(),
        'source_record_archive': {'schema': 'tigerair-yes123.v1', 'receipts': deepcopy(receipts)},
        'message': '官網連出的yes123精確雇主公開職缺樣本；日期為平台更新與平台有效期，首次刊登日、雇主截止、全公司職缺及招聘總人數仍未知。'}


def verified_job_count(value, data, issuer, *, now=None):
    live_clock = now is None
    now = time.time() if now is None else now
    try:
        if not valid_context(data) or not verified_issuer(issuer, now=now):
            return 0
        archive = value['source_record_archive']
        if set(archive) != {'schema', 'receipts'} or archive['schema'] != 'tigerair-yes123.v1':
            return 0
        expected = parse_receipts(archive['receipts'], now=now)
        if json.dumps(value, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
            return 0
        finished = time.time() if live_clock else now
        if not verified_issuer(issuer, now=finished) or parse_receipts(archive['receipts'], now=finished) != expected:
            return 0
        return expected['verified_sample_job_count']
    except (ValueError, TypeError, KeyError, OSError, OverflowError, AttributeError, UnicodeError, RecursionError):
        return 0
