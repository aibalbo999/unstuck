"""Bounded, exact-parent KGI Workday evidence, retaining complete source bodies."""
from __future__ import annotations

import base64
from datetime import datetime
from hashlib import sha256
import json
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from .ctbc_careers import _closing_date, _date, _fresh_epoch

TICKER = '2883.TW'
LEGAL = '凱基金融控股股份有限公司'
SHORT = '凱基金'
UBN = '70827383'
EMPLOYER = LEGAL + ' KGI Financial Holding Co., Ltd.'
COMPANY_ID = '39d77424bb861000fb161fa41a5e0000'
PROVIDER = 'KGI Financial Holding official Workday careers'
HOST = 'https://cdfh.wd3.myworkdayjobs.com'
API_BASE = HOST + '/wday/cxs/cdfh/External'
API_URL = API_BASE + '/jobs'
LISTING_URL = HOST + '/zh-TW/External?hiringCompany=' + COMPANY_ID
REQUEST = {'appliedFacets': {'hiringCompany': [COMPANY_ID]}, 'limit': 20, 'offset': 0, 'searchText': ''}
MAX_BYTES = 500_000
MAX_POSTINGS = 3
PATH = re.compile(r'/job/(?:-Guochang-Building/|-KGIFH-Building/)?(?P<slug>[A-Za-z0-9_-]{1,200}_(?P<req>JR\d+)(?:-\d+)?)')
MESSAGE = '僅採金控本體近30天來源日期且當時可應徵的逐筆樣本；不代表招聘人數、全站總數或首次刊登日期。'


def _path(value):
    match = PATH.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError('invalid issuer job path')
    return match


def detail_url(path):
    return API_BASE + '/job/' + _path(path)['slug']


def _body(receipt, url, now, *, listing=False):
    if (not isinstance(receipt, dict) or receipt.get('url') != url
            or receipt.get('method') != ('POST' if listing else 'GET')
            or receipt.get('request_json') != (REQUEST if listing else None)
            or not _fresh_epoch(receipt.get('fetched_at_epoch'), now)):
        raise ValueError('invalid issuer job receipt identity or age')
    encoded = receipt.get('body_b64')
    if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
        raise ValueError('invalid issuer job receipt size')
    raw = base64.b64decode(encoded, validate=True)
    if not 0 < len(raw) <= MAX_BYTES or sha256(raw).hexdigest() != receipt.get('sha256'):
        raise ValueError('invalid issuer job receipt hash')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('invalid issuer job payload')
    return value


def _listing(receipt, now):
    data = _body(receipt, API_URL, now, listing=True)
    total, rows, facets = data.get('total'), data.get('jobPostings'), data.get('facets')
    if (type(total) is not int or not 0 <= total <= 5000 or not isinstance(rows, list)
            or len(rows) != min(20, total) or not isinstance(facets, list)):
        raise ValueError('incomplete issuer listing')
    companies = [v for f in facets if isinstance(f, dict) and f.get('facetParameter') == 'hiringCompany'
                 and isinstance(f.get('values'), list) for v in f['values']
                 if isinstance(v, dict) and v.get('id') == COMPANY_ID]
    if (len(companies) != 1 or companies[0].get('descriptor') != EMPLOYER
            or type(companies[0].get('count')) is not int or companies[0]['count'] != total):
        raise ValueError('issuer company filter unverified')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid job row')
        identity = _path(row.get('externalPath'))
        if (row.get('bulletFields') != [identity['req']] or identity['req'] in seen
                or not isinstance(row.get('title'), str) or not 1 <= len(row['title'].strip()) <= 200):
            raise ValueError('duplicate or invalid job identity')
        seen.add(identity['req'])
    return rows, total


def _posting(receipt, row, now):
    path = row['externalPath']; identity = _path(path)
    payload = _body(receipt, detail_url(path), now)
    info, employer = payload.get('jobPostingInfo'), payload.get('hiringOrganization')
    if (not isinstance(info, dict) or not isinstance(employer, dict)
            or employer.get('name') != EMPLOYER or payload.get('userAuthenticated') is not False
            or info.get('title') != row['title'] or info.get('jobReqId') != identity['req']
            or info.get('jobPostingId') != identity['slug'] or info.get('jobPostingSiteId') != 'External'
            or info.get('canApply') is not True or info.get('posted') is not True
            or info.get('externalUrl') != HOST + '/External' + path):
        raise ValueError('issuer job identity or open status unverified')
    posted = _date(info.get('startDate'))
    description = info.get('jobDescription')
    if not isinstance(description, str) or not 10 <= len(description) <= 100_000:
        raise ValueError('job description unavailable')
    for stamp in (receipt['fetched_at_epoch'], now):
        today = datetime.fromtimestamp(stamp, ZoneInfo('Asia/Taipei')).date()
        if not 0 <= (today - posted).days <= 30:
            raise ValueError('job outside recent source-date window')
        closing = _closing_date(description, today)
    description_text = BeautifulSoup(description, 'html.parser').get_text(' ', strip=True)
    if not description_text or len(description_text) > 16000:
        raise ValueError('job description unavailable or oversized')
    return {'job_no': identity['req'], 'title': info['title'], 'employer': LEGAL,
            'source_employer': EMPLOYER, 'company_id': COMPANY_ID, 'url': info['externalUrl'],
            'source_url': detail_url(path), 'description': description_text,
            'source_start_date': posted.isoformat(), 'published_date': None,
            'date_semantics': 'source_startDate_not_independently_verified_first_publication',
            'closing_date': closing, 'can_apply': True, 'posted': True, 'headcount': None,
            'response_sha256': receipt['sha256'], 'source_receipt_fetched_at_epoch': receipt['fetched_at_epoch']}


def parse_jobs(listing_receipt, detail_receipts, *, now=None):
    now = time.time() if now is None else now
    rows, total = _listing(listing_receipt, now)
    if not isinstance(detail_receipts, list) or not 0 < len(detail_receipts) <= MAX_POSTINGS:
        raise ValueError('invalid detail sample')
    indexed = {detail_url(row['externalPath']): row for row in rows}
    jobs, seen = [], set()
    for receipt in detail_receipts:
        url = receipt.get('url') if isinstance(receipt, dict) else None
        if not isinstance(url, str) or url not in indexed or url in seen:
            raise ValueError('detail not in verified issuer listing')
        seen.add(url); jobs.append(_posting(receipt, indexed[url], now))
    return {'status': 'success', 'ticker': TICKER, 'company_name': LEGAL, 'official_ubn': UBN,
            'source': PROVIDER, 'source_url': API_URL, 'listing_url': LISTING_URL,
            'evidence_kind': 'official_company_job_postings', 'query_scope': 'exact_issuer_recent_open_postings',
            'coverage_status': 'recent_open_posting_sample', 'job_count': None, 'recent_company_job_count': None,
            'current_open_job_count': len(jobs), 'job_postings': jobs, 'listing_total': total,
            'raw_count': len(rows), 'message': MESSAGE, 'response_sha256': listing_receipt['sha256'],
            'fetched_at_epoch': min(r['fetched_at_epoch'] for r in [listing_receipt, *detail_receipts]),
            'source_record_archive': {'schema': 'kgi-careers.v1', 'listing_receipt': listing_receipt,
                                      'detail_receipts': detail_receipts}}


def verified_job_count(value, ticker, legal_name, ubn, *, now=None):
    if ticker != TICKER or legal_name != LEGAL or ubn != UBN or not isinstance(value, dict):
        return 0
    try:
        archive = value.get('source_record_archive')
        if not isinstance(archive, dict) or archive.get('schema') != 'kgi-careers.v1':
            return 0
        parsed = parse_jobs(archive.get('listing_receipt'), archive.get('detail_receipts'), now=now)
        if set(value) - (set(parsed) | {'http_request_count', 'component_receipts',
                                       'detail_rejected_count', 'partial_failure_reasons'}):
            return 0
        for key, expected in parsed.items():
            if json.dumps(value.get(key), sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
                return 0
        return len(parsed['job_postings'])
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError, OSError):
        return 0


def verified_issuer(receipt, ticker, short_name, *, now=None):
    from .official_company_legal_name import verified_legal_name_from_evidence, verified_official_ubn_from_evidence
    now = time.time() if now is None else now
    try:
        return (ticker == TICKER and short_name == SHORT and isinstance(receipt, dict)
                and _fresh_epoch(receipt.get('fetched_at_epoch'), now)
                and verified_legal_name_from_evidence(receipt, ticker, short_name) == LEGAL
                and verified_official_ubn_from_evidence(receipt, ticker, short_name) == UBN
                and 0 <= (datetime.fromtimestamp(now, ZoneInfo('Asia/Taipei')).date() - _date(receipt.get('as_of'))).days <= 14)
    except (ValueError, TypeError, OverflowError, OSError):
        return False


def fetch_official_jobs(ticker, legal_name, ubn):
    from .kgi_careers_transport import KgiCareersHttp
    unavailable = {'status': 'unavailable', 'ticker': ticker, 'source': PROVIDER, 'source_url': API_URL,
                   'company_name': LEGAL, 'job_count': None, 'current_open_job_count': None,
                   'job_postings': [], 'reason_code': 'official_career_unverified'}
    if ticker != TICKER or legal_name != LEGAL or ubn != UBN:
        return {**unavailable, 'reason_code': 'issuer_not_supported', 'http_request_count': 0}
    http = KgiCareersHttp(time.monotonic() + 12)
    rejected, failures = 0, []
    try:
        listing = http.get_receipt()
        rows, _ = _listing(listing, time.time())
        receipts = []
        for row in rows[:10]:
            if row.get('postedOn') in ('Posted 30+ Days Ago', '超過 30 天前刊登'):
                rejected += 1
                continue
            try:
                receipt = http.get_receipt(row['externalPath'])
                _posting(receipt, row, time.time()); receipts.append(receipt)
            except SourceResponseError as exc:
                failures.append(str(exc.error_kind)); break
            except (ValueError, TypeError, UnicodeError):
                rejected += 1
            if len(receipts) >= MAX_POSTINGS or time.monotonic() >= http.deadline:
                break
        result = parse_jobs(listing, receipts)
        if time.monotonic() >= http.deadline:
            raise SourceResponseError('timeout')
    except (SourceResponseError, ValueError, TypeError, UnicodeError, OverflowError) as exc:
        result = {**unavailable, 'reason_code': getattr(exc, 'error_kind', 'official_career_unverified')}
    return {**result, 'http_request_count': http.http_request_count, 'component_receipts': http.components,
            'detail_rejected_count': rejected, 'partial_failure_reasons': failures}
