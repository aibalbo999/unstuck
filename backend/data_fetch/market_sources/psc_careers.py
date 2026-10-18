"""Full public current-open issuer jobs; source modification is not publication."""
from __future__ import annotations

import base64
from datetime import datetime
from hashlib import sha256
import json
import math
import re
import time
from zoneinfo import ZoneInfo

from search_provider_runtime import SourceResponseError
from .psc_careers_literals import MAX_BYTES, decode_public_callback
from .psc_careers_transport import (DETAIL_API, JOB_ID, LIST_API, LISTING_URL, PROVIDER, PscCareersHttp)

TICKER, LEGAL_NAME, UBN, CUST_ID = '2855.TW', '統一綜合證券股份有限公司', '23218183', '9900000736'
MAX_ROWS, MAX_POSTINGS, MAX_ATTEMPTS = 300, 3, 5
DATE_SEMANTICS = 'source_creation_and_modification_not_first_publication'
MESSAGE = '僅採當時開放且原件可核對的職缺樣本；建立／異動日不推定首次刊登日，也不推論近期新增或擴編。'


def _epoch(value, now, max_age=86400):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0 and 0 <= now - value <= max_age
    except (ValueError, OverflowError):
        return False


def _body(receipt, job_id, now):
    url = DETAIL_API if job_id is not None else LIST_API
    if (not isinstance(receipt, dict) or receipt.get('url') != url or receipt.get('method') != 'POST'
            or receipt.get('request_identity') != {'cust_id': CUST_ID, 'job_id': job_id}
            or not _epoch(receipt.get('fetched_at_epoch'), now)):
        raise ValueError('issuer career receipt identity or age invalid')
    encoded = receipt.get('body_b64')
    if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
        raise ValueError('issuer career receipt size invalid')
    raw = base64.b64decode(encoded, validate=True)
    if not 0 < len(raw) <= MAX_BYTES or sha256(raw).hexdigest() != receipt.get('sha256'):
        raise ValueError('issuer career receipt hash invalid')
    return decode_public_callback(raw)['data']


def _text(value, limit, *, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError('issuer career text invalid')
    return value.strip()


def _date(value, *, day=False):
    pattern = r'\d{4}/\d{2}/\d{2}' + ('' if day else r' \d{2}:\d{2}:\d{2}')
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('issuer career original date invalid')
    return datetime.strptime(value, '%Y/%m/%d' if day else '%Y/%m/%d %H:%M:%S').replace(tzinfo=ZoneInfo('Asia/Taipei'))


def _listing(receipt, now):
    data = _body(receipt, None, now)
    if (not isinstance(data, list) or len(data) != 2 or type(data[0]) is not int
            or not 0 <= data[0] <= MAX_ROWS or not isinstance(data[1], list) or len(data[1]) != data[0]):
        raise ValueError('issuer career listing incomplete or oversized')
    rows, seen, rejected = [], set(), 0
    for row in data[1]:
        if not isinstance(row, dict) or row.get('custId') != CUST_ID:
            raise ValueError('issuer career list employer invalid')
        number = row.get('id')
        if not isinstance(number, str) or not JOB_ID.fullmatch(number) or number in seen:
            raise ValueError('issuer career list id invalid or duplicate')
        seen.add(number)
        if row.get('enable') is not True:
            rejected += 1
            continue
        title = _text(row.get('cleanI18nName'), 200)
        rows.append({'id': number, 'title': title})
    return rows, data[0], rejected


def _posting(receipt, row, now):
    number = row['id']
    value = _body(receipt, number, now)
    if (not isinstance(value, dict) or value.get('id') != number or value.get('custId') != CUST_ID
            or value.get('custNo') != UBN + '000' or value.get('coName') != LEGAL_NAME
            or value.get('enable') is not True or value.get('deleteDate') is not None
            or value.get('closeDate') is not None or value.get('formattedCloseDate') != '無'
            or _text(value.get('job'), 200) != row['title']):
        raise ValueError('issuer career detail identity or open status invalid')
    created, entered, updated = (_date(value.get('formattedCreateDate')),
                                 _date(value.get('formattedInputDate'), day=True),
                                 _date(value.get('formattedUpdateDate')))
    if (created.date() != entered.date() or created > updated
            or updated > datetime.fromtimestamp(receipt['fetched_at_epoch'], ZoneInfo('Asia/Taipei'))):
        raise ValueError('issuer career source dates conflict or future')
    peer = value.get('peer')
    if not isinstance(peer, dict):
        raise ValueError('issuer career description unavailable')
    return {'job_no': number, 'title': row['title'], 'employer': LEGAL_NAME, 'employer_id': UBN + '000',
            'url': LISTING_URL, 'source_url': DETAIL_API, 'is_open': True,
            'description': _text(peer.get('i18nDescription'), 12000),
            'conditions': _text(peer.get('i18nOthers'), 8000, empty=True),
            'employment_type': _text(value.get('roleString'), 80),
            'headcount_text': _text(value.get('needEmpString'), 80, empty=True) or None,
            'salary_text': _text(value.get('salaryString'), 200, empty=True),
            'location': _text(value.get('i18nAddressRegion'), 200),
            'source_created_at': value['formattedCreateDate'], 'source_input_date': value['formattedInputDate'],
            'source_updated_at': value['formattedUpdateDate'], 'published_date': None, 'date_semantics': DATE_SEMANTICS,
            'response_sha256': receipt['sha256'], 'source_receipt_fetched_at_epoch': receipt['fetched_at_epoch']}


def parse_psc_jobs(listing_receipt, detail_receipts, *, now=None):
    now = time.time() if now is None else now
    if not _epoch(now, now) or not isinstance(detail_receipts, list) or not 0 < len(detail_receipts) <= MAX_POSTINGS:
        raise ValueError('issuer career detail sample invalid')
    rows, total, rejected = _listing(listing_receipt, now)
    by_id = {row['id']: row for row in rows}
    jobs, seen = [], set()
    for receipt in detail_receipts:
        identity = receipt.get('request_identity') if isinstance(receipt, dict) else None
        number = identity.get('job_id') if isinstance(identity, dict) else None
        if not isinstance(number, str) or number not in by_id or number in seen:
            raise ValueError('issuer career detail not in verified listing')
        seen.add(number)
        jobs.append(_posting(receipt, by_id[number], now))
    return {'status': 'success', 'ticker': TICKER, 'company_name': LEGAL_NAME, 'official_ubn': UBN,
            'source': PROVIDER, 'source_url': LIST_API, 'listing_url': LISTING_URL,
            'evidence_kind': 'official_company_job_postings', 'query_scope': 'exact_issuer_current_open_postings',
            'coverage_status': 'current_open_posting_sample', 'job_count': None, 'recent_company_job_count': None,
            'current_open_job_count': len(jobs), 'job_postings': jobs, 'listing_total': total,
            'raw_count': total, 'rejected_count': rejected, 'message': MESSAGE,
            'response_sha256': listing_receipt['sha256'],
            'fetched_at_epoch': min(r['fetched_at_epoch'] for r in [listing_receipt, *detail_receipts]),
            'source_record_archive': {'schema': 'psc-careers.v1', 'listing_receipt': listing_receipt,
                                      'detail_receipts': detail_receipts}}


def verified_psc_job_count(value, ticker, legal_name, official_ubn, *, now=None):
    if (ticker != TICKER or legal_name != LEGAL_NAME or official_ubn != UBN
            or not isinstance(value, dict)):
        return 0
    try:
        archive = value.get('source_record_archive')
        if not isinstance(archive, dict) or archive.get('schema') != 'psc-careers.v1':
            return 0
        parsed = parse_psc_jobs(archive.get('listing_receipt'), archive.get('detail_receipts'), now=now)
        if set(value) - (set(parsed) | {'http_request_count', 'component_receipts',
                                       'detail_rejected_count', 'partial_failure_reasons'}):
            return 0
        # JSON identity avoids bool==int and enforces all prompt-facing fields,
        # including original dates and absence of a claimed publication date.
        for key, expected in parsed.items():
            if json.dumps(value.get(key), sort_keys=True, ensure_ascii=True, allow_nan=False) != json.dumps(
                    expected, sort_keys=True, ensure_ascii=True, allow_nan=False):
                return 0
        return len(parsed['job_postings'])
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError):
        return 0


def verified_psc_issuer_receipt(receipt, ticker, short_name, *, now=None):
    """Do not reuse a historical issuer identity as a current employer anchor."""
    from .official_company_legal_name import verified_legal_name_from_evidence, verified_official_ubn_from_evidence
    now = time.time() if now is None else now
    if (ticker != TICKER or short_name != '統一證' or not isinstance(receipt, dict)
            or not _epoch(receipt.get('fetched_at_epoch'), now)
            or verified_legal_name_from_evidence(receipt, ticker, short_name) != LEGAL_NAME
            or verified_official_ubn_from_evidence(receipt, ticker, short_name) != UBN):
        return False
    try:
        observed = datetime.strptime(receipt.get('as_of'), '%Y-%m-%d').date()
        return 0 <= (datetime.fromtimestamp(now, ZoneInfo('Asia/Taipei')).date() - observed).days <= 14
    except (ValueError, TypeError, OverflowError):
        return False


def fetch_official_psc_jobs(ticker, legal_name, official_ubn):
    unavailable = {'status': 'unavailable', 'ticker': ticker, 'source': PROVIDER, 'source_url': LIST_API,
                   'company_name': LEGAL_NAME, 'job_count': None, 'current_open_job_count': None,
                   'recent_company_job_count': None, 'job_postings': [], 'reason_code': 'official_career_unverified'}
    if ticker != TICKER or legal_name != LEGAL_NAME or official_ubn != UBN:
        return {**unavailable, 'reason_code': 'issuer_not_supported', 'http_request_count': 0}
    http = PscCareersHttp(time.monotonic() + 20)
    rejected, failures = 0, []
    try:
        listing = http.get_receipt()
        rows, _, _ = _listing(listing, time.time())
        receipts = []
        for row in rows[:MAX_ATTEMPTS]:
            try:
                receipt = http.get_receipt(row['id'])
                _posting(receipt, row, time.time())
                receipts.append(receipt)
            except SourceResponseError as exc:
                failures.append(str(exc.error_kind)); break
            except (ValueError, TypeError, UnicodeError):
                rejected += 1
            if len(receipts) >= MAX_POSTINGS or time.monotonic() >= http.deadline:
                break
        if not receipts:
            raise ValueError('no verified current open issuer details')
        result = parse_psc_jobs(listing, receipts)
        if time.monotonic() >= http.deadline:
            raise SourceResponseError('timeout')
    except (SourceResponseError, ValueError, TypeError, UnicodeError) as exc:
        result = {**unavailable, 'reason_code': getattr(exc, 'error_kind', 'official_career_unverified')}
    return {**result, 'http_request_count': http.http_request_count, 'component_receipts': http.components,
            'detail_rejected_count': rejected, 'partial_failure_reasons': failures,
            'message': MESSAGE}
