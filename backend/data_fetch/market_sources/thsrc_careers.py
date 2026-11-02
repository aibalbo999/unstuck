"""THSRC-linked anonymous public jobs, replayed without evaluating JavaScript."""
from __future__ import annotations

import base64
from datetime import datetime
from hashlib import sha256
import json
import re
import time
import unicodedata
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from search_provider_runtime import SourceResponseError
from .psc_careers import _date, _epoch, _text
from .psc_careers_literals import MAX_BYTES, decode_public_callback

TICKER, SHORT, LEGAL, UBN, CUST_ID = '2633.TW', '台灣高鐵', '台灣高速鐵路股份有限公司', '16446274', '1900000134'
PROVIDER = 'THSRC official public careers'
INDEX_URL = 'https://www.thsrc.com.tw/ArticleContent/923049a0-10dd-4c2f-927b-66e470c9c16e'
LISTING_URL = 'https://ehrweb.104.com.tw/job.do?uno=16446274'
BASE_API = 'https://ehrweb.104.com.tw/dwr/call/plaincall/normalAjaxService.'
LIST_API, DETAIL_API = BASE_API + 'searchJobs.dwr', BASE_API + 'getJobDetailByCustId.dwr'
JOB_ID = re.compile(r'[1-9]\d{9,24}')
MAX_ROWS, MAX_POSTINGS, MAX_ATTEMPTS = 300, 3, 5
MESSAGE = '僅採官方連結招募站當時開放且原件可核對的個別職缺樣本；清單筆數不是招聘人數，建立／異動日不代表首次刊登或近期擴編。'


def request_identity(key):
    if key in ('index', 'tenant'):
        return (INDEX_URL if key == 'index' else LISTING_URL), 'GET', None
    if key != 'listing' and (not isinstance(key, str) or not JOB_ID.fullmatch(key)):
        raise ValueError('invalid THSRC career component')
    number = None if key == 'listing' else key
    return (LIST_API if number is None else DETAIL_API), 'POST', {'cust_id': CUST_ID, 'job_id': number}


def receipt_body(receipt, key, now):
    url, method, identity = request_identity(key)
    if (not isinstance(receipt, dict) or receipt.get('url') != url or receipt.get('method') != method
            or receipt.get('request_identity') != identity
            or not _epoch(receipt.get('fetched_at_epoch'), now, max_age=1800)
            or receipt.get('http_status') != 200 or receipt.get('response_complete') is not True):
        raise ValueError('THSRC original identity, HTTP completion or age invalid')
    encoded = receipt.get('body_b64')
    if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
        raise ValueError('THSRC original size invalid')
    raw = base64.b64decode(encoded, validate=True)
    if (not 0 < len(raw) <= MAX_BYTES or sha256(raw).hexdigest() != receipt.get('sha256')
            or type(receipt.get('response_bytes')) is not int or receipt['response_bytes'] != len(raw)):
        raise ValueError('THSRC original incomplete or hash invalid')
    return raw


def verify_links(index, tenant, now):
    first = BeautifulSoup(receipt_body(index, 'index', now), 'html.parser')
    title = first.title.get_text(' ', strip=True) if first.title else ''
    if '甄選流程' not in title or SHORT not in title or not any(
            a.get('href') == LISTING_URL and a.get_text(strip=True) == '我要應徵' for a in first.select('a[href]')):
        raise ValueError('THSRC official career link unavailable')
    second = BeautifulSoup(receipt_body(tenant, 'tenant', now), 'html.parser')
    if not second.title or second.title.get_text(strip=True) != '職務訊息 - ' + LEGAL + ' - 招募管理系統':
        raise ValueError('THSRC recruiter employer title invalid')
    ids = re.findall(r'\bvar\s+Job\s*=\s*\{\s*custId\s*:\s*(\d+)\s*,',
                     '\n'.join(s.get_text() for s in second.find_all('script')))
    if ids != [CUST_ID]:
        raise ValueError('THSRC public recruiter tenant invalid')


def listing_rows(receipt, now):
    data = decode_public_callback(receipt_body(receipt, 'listing', now))['data']
    if (not isinstance(data, list) or len(data) != 2 or type(data[0]) is not int
            or not 0 <= data[0] <= MAX_ROWS or not isinstance(data[1], list) or len(data[1]) != data[0]):
        raise ValueError('THSRC listing incomplete or oversized')
    rows, seen = [], set()
    for row in data[1]:
        if not isinstance(row, dict) or row.get('custId') != CUST_ID:
            raise ValueError('THSRC list employer invalid')
        number = row.get('id')
        if not isinstance(number, str) or not JOB_ID.fullmatch(number) or number in seen:
            raise ValueError('THSRC list identity invalid or duplicate')
        seen.add(number)
        if row.get('enable') is True:
            rows.append({'id': number, 'title': _text(row.get('cleanI18nName'), 200)})
    return rows, data[0]


def posting(receipt, row, now):
    number = row['id']
    value = decode_public_callback(receipt_body(receipt, number, now))['data']
    if (not isinstance(value, dict) or value.get('id') != number or value.get('custId') != CUST_ID
            or value.get('custNo') != UBN + '000' or value.get('coName') != LEGAL
            or value.get('enable') is not True or value.get('deleteDate') is not None
            or value.get('closeDate') is not None or value.get('formattedCloseDate') != '無'):
        raise ValueError('THSRC detail employer or open status invalid')
    title = _text(value.get('job'), 200)
    # The real publisher renders full-width parentheses only in its clean list.
    # Preserve both spellings; no fuzzy matching or removal of words/numbers.
    if unicodedata.normalize('NFKC', title) != unicodedata.normalize('NFKC', row['title']):
        raise ValueError('THSRC list/detail title conflict')
    created, entered, updated = (_date(value.get('formattedCreateDate')),
                                 _date(value.get('formattedInputDate'), day=True),
                                 _date(value.get('formattedUpdateDate')))
    if (created.date() != entered.date() or created > updated
            or updated > datetime.fromtimestamp(receipt['fetched_at_epoch'], ZoneInfo('Asia/Taipei'))):
        raise ValueError('THSRC source dates invalid or future')
    peer = value.get('peer')
    if not isinstance(peer, dict):
        raise ValueError('THSRC job description missing')
    return {'job_no': number, 'title': title, 'listing_title': row['title'], 'employer': LEGAL,
            'employer_id': UBN + '000', 'url': LISTING_URL, 'source_url': DETAIL_API, 'is_open': True,
            'description': _text(peer.get('i18nDescription'), 12000),
            'conditions': _text(peer.get('i18nOthers'), 8000, empty=True),
            'employment_type': _text(value.get('roleString'), 80),
            'headcount_text': _text(value.get('needEmpString'), 80, empty=True) or None,
            'salary_text': _text(value.get('salaryString'), 200, empty=True),
            'location': _text(value.get('i18nAddressRegion'), 200),
            'source_created_at': value['formattedCreateDate'], 'source_input_date': value['formattedInputDate'],
            'source_updated_at': value['formattedUpdateDate'], 'published_date': None,
            'date_semantics': 'source_creation_and_modification_not_first_publication',
            'response_sha256': receipt['sha256'], 'source_receipt_fetched_at_epoch': receipt['fetched_at_epoch']}


def parse_jobs(receipts, *, now=None):
    now = time.time() if now is None else now
    if not isinstance(receipts, list) or not 4 <= len(receipts) <= 3 + MAX_POSTINGS:
        raise ValueError('THSRC original chain incomplete')
    index, tenant, listing, *details = receipts
    verify_links(index, tenant, now)
    rows, total = listing_rows(listing, now)
    by_id, seen, jobs = {row['id']: row for row in rows}, set(), []
    for detail in details:
        identity = detail.get('request_identity') if isinstance(detail, dict) else None
        number = identity.get('job_id') if isinstance(identity, dict) else None
        if not isinstance(number, str) or number not in by_id or number in seen:
            raise ValueError('THSRC detail not in current listing or duplicate')
        seen.add(number); jobs.append(posting(detail, by_id[number], now))
    return {'status': 'success', 'ticker': TICKER, 'company_name': LEGAL, 'official_ubn': UBN,
            'source': PROVIDER, 'source_url': INDEX_URL, 'listing_url': LISTING_URL,
            'evidence_kind': 'official_company_job_postings', 'query_scope': 'exact_issuer_current_open_postings',
            'coverage_status': 'current_open_posting_sample', 'job_count': None, 'recent_company_job_count': None,
            'current_open_job_count': len(jobs), 'job_postings': jobs, 'listing_total': total,
            'raw_count': total, 'message': MESSAGE, 'response_sha256': listing['sha256'],
            'fetched_at_epoch': min(r['fetched_at_epoch'] for r in receipts),
            'source_record_archive': {'schema': 'thsrc-careers.v1', 'receipts': receipts}}


def verified_job_count(value, ticker, legal_name, official_ubn, *, now=None):
    if ticker != TICKER or legal_name != LEGAL or official_ubn != UBN or not isinstance(value, dict):
        return 0
    try:
        archive = value.get('source_record_archive')
        if not isinstance(archive, dict) or archive.get('schema') != 'thsrc-careers.v1': return 0
        parsed = parse_jobs(archive.get('receipts'), now=now)
        if set(value) - (set(parsed) | {'http_request_count', 'component_receipts', 'partial_failure_reasons'}): return 0
        if any(json.dumps(value.get(k), sort_keys=True, allow_nan=False) != json.dumps(v, sort_keys=True, allow_nan=False)
               for k, v in parsed.items()): return 0
        return len(parsed['job_postings'])
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError, OSError):
        return 0


def valid_context(data):
    if not isinstance(data, dict) or not isinstance(data.get('company_identity'), dict): return False
    identity = data['company_identity']
    english = identity.get('english_names', [])
    if not isinstance(english, list) or any(not isinstance(v, str) for v in english): return False
    name = data.get('company_name')
    return (data.get('ticker') == TICKER and identity.get('ticker') == TICKER
            and identity.get('official_name') == SHORT and identity.get('legal_name') in (None, '', LEGAL)
            and data.get('quote_type') == identity.get('instrument_type') == 'EQUITY'
            and all(data.get(k) in (None, '', 'EQUITY') for k in ('quoteType', 'instrument_type'))
            and all(v in (None, '', '2633') for v in (data.get('stock_id'), identity.get('stock_id')))
            and identity.get('official_ubn') in (None, '', UBN)
            and isinstance(name, str) and bool(name.strip())
            and all(part.strip() in {SHORT, LEGAL, *english} for part in name.split(' / ')))


def verified_issuer(receipt, *, now=None):
    """Replay the actual current TWSE roster, including this issuer's web host."""
    from urllib.parse import urlsplit
    from runtime_paths import current_runtime_paths
    from official_response_evidence import read_response
    from .official_company_legal_name import (verified_legal_name_from_evidence,
        verified_official_ubn_from_evidence, parse_roster, select_legal_name, MAX_BYTES as MASTER_MAX)
    now = time.time() if now is None else now
    try:
        if (not isinstance(receipt, dict) or not _epoch(receipt.get('fetched_at_epoch'), now)
                or verified_legal_name_from_evidence(receipt, TICKER, SHORT) != LEGAL
                or verified_official_ubn_from_evidence(receipt, TICKER, SHORT) != UBN): return False
        digest = receipt['response_sha256']
        raw = read_response({'raw_response_sha256': digest, 'raw_response_path': str(
            current_runtime_paths().cache_dir / 'official-response-evidence' / (digest + '.gz'))}, max_bytes=MASTER_MAX)
        def pairs(items):
            value = {}
            for key, item in items:
                if key in value: raise ValueError('duplicate roster field')
                value[key] = item
            return value
        rows = json.loads(raw, object_pairs_hook=pairs)
        roster = parse_roster(raw, '.TW')
        if len(roster['entries']) < 800: return False
        selected = select_legal_name(roster, TICKER, SHORT, today=datetime.fromtimestamp(now, ZoneInfo('Asia/Taipei')).date())
        if not selected or any(selected.get(k) != receipt.get(k) for k in (
                'ticker', 'legal_name', 'official_short_name', 'as_of', 'official_ubn', 'source_url', 'response_sha256')): return False
        matched = [row for row in rows if str(row.get('公司代號')) == '2633']
        if len(matched) != 1: return False
        website = str(matched[0].get('網址') or '').strip()
        return urlsplit(website if '://' in website else 'https://' + website).hostname in {'thsrc.com.tw', 'www.thsrc.com.tw'}
    except (ValueError, TypeError, KeyError, OverflowError, OSError, UnicodeError, AttributeError, RecursionError):
        return False


def fetch_jobs():
    from .thsrc_careers_transport import ThsrcCareersHttp
    http, failures = ThsrcCareersHttp(time.monotonic() + 20), []
    try:
        index, tenant = http.get_receipt('index'), http.get_receipt('tenant')
        verify_links(index, tenant, time.time())
        listing = http.get_receipt('listing'); rows, _ = listing_rows(listing, time.time())
        details = []
        for row in rows[:MAX_ATTEMPTS]:
            try:
                detail = http.get_receipt(row['id']); posting(detail, row, time.time()); details.append(detail)
            except SourceResponseError:
                raise
            except (ValueError, TypeError, UnicodeError) as exc:
                failures.append(str(exc)); continue
            if len(details) == MAX_POSTINGS: break
        value = parse_jobs([index, tenant, listing, *details])
        if time.monotonic() >= http.deadline: raise SourceResponseError('timeout')
    except (SourceResponseError, ValueError, TypeError, UnicodeError, OverflowError) as exc:
        value = {'status': 'unavailable', 'ticker': TICKER, 'source': PROVIDER,
                 'job_count': None, 'current_open_job_count': None, 'job_postings': [],
                 'reason_code': getattr(exc, 'error_kind', 'official_career_unverified')}
    return {**value, 'http_request_count': http.http_request_count, 'component_receipts': http.components,
            'partial_failure_reasons': failures}
