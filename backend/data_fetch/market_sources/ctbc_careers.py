"""Recent open CTBC Holding postings from its public Workday career UI.

The issuer's Careers page links this site. Its hiringCompany filter separates
2891 from bank/insurance subsidiaries. The public UI's unauthenticated listing
and individual JSON responses are used without browser tokens or login. An
Apply button or an old search-engine copy alone never proves an open vacancy.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import html
import json
import math
import os
import re
import time
import unicodedata
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from bounded_curl_process import collect_capped_process

PROVIDER = 'CTBC Holding official Workday careers'
TICKER = '2891.TW'
LEGAL_NAME = '中國信託金融控股股份有限公司'
SOURCE_EMPLOYER = '中國信託金融控股公司'
COMPANY_ID = '1e73f5b107d8012217d8aa3be2e00000'
HOST = 'https://ctbcholding.wd3.myworkdayjobs.com'
CAREER_URL = HOST + '/zh-TW/External?hiringCompany=' + COMPANY_ID
API_BASE = HOST + '/wday/cxs/ctbcholding/External'
API_URL = API_BASE + '/jobs'
MAX_BYTES = 1_000_000
MAX_ROWS = 20
MAX_POSTINGS = 10
DIGEST = re.compile(r'[0-9a-f]{64}')
JOB_PATH = re.compile(r'/job/(?:Taipei/)?(?P<slug>[A-Za-z0-9_-]{0,200}_(?P<req>JR\d+)(?:-\d+)?)')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
DATE_PARTS = r'(\d{4})[-./年](\d{1,2})[-./月](\d{1,2})(?:日)?'
REQUEST = json.dumps({'appliedFacets': {'hiringCompany': [COMPANY_ID]},
                      'limit': MAX_ROWS, 'offset': 0, 'searchText': ''}, separators=(',', ':')).encode('ascii')


def _today(epoch: float) -> date:
    return datetime.fromtimestamp(epoch, ZoneInfo('Asia/Taipei')).date()


def _date(value) -> date:
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError('invalid posting date')
    return date.fromisoformat(value)


def _job_path(value: str):
    if not isinstance(value, str):
        raise ValueError('invalid job path')
    match = JOB_PATH.fullmatch(value)
    if not match:
        raise ValueError('invalid job path')
    return match


def _public_path(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('invalid public URL')
    parts = urlsplit(value)
    if (parts.scheme != 'https' or parts.netloc != 'ctbcholding.wd3.myworkdayjobs.com'
            or parts.query or parts.fragment or not parts.path.startswith('/External/job/')):
        raise ValueError('invalid public URL')
    path = parts.path[len('/External'):]
    _job_path(path)
    return path


def _download(url: str, deadline: float, request: bytes | None = None) -> bytes:
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK') == '1':
        raise RuntimeError('network disabled for tests')
    if request is not None:
        if url != API_URL or request != REQUEST:
            raise ValueError('invalid listing request')
    elif not url.startswith(API_BASE + '/job/'):
        raise ValueError('invalid job request')
    else:
        _job_path(url[len(API_BASE):])
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError('career acquisition deadline')
    argv = ['/usr/bin/curl', '--disable', '--silent', '--show-error', '--fail-with-body',
            '--max-time', str(min(4, remaining)), '--connect-timeout', '3',
            '--max-filesize', str(MAX_BYTES), '--proto', '=https', '--max-redirs', '0',
            '--retry', '0', '-H', 'Accept: application/json']
    if request is not None:
        argv += ['-H', 'Content-Type: application/json', '--data-binary', request.decode('ascii')]
    argv.append(url)
    parts, rc, error = collect_capped_process(argv, deadline, body_limit=MAX_BYTES)
    if error or rc != 0 or not 0 < len(parts['body']) <= MAX_BYTES:
        raise RuntimeError(error or 'career HTTP response unavailable')
    return parts['body']


def _payload(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('invalid career response size')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('invalid career response shape')
    return result


def _candidates(raw: bytes) -> tuple[list[dict], int]:
    payload = _payload(raw)
    total, rows, facets = payload.get('total'), payload.get('jobPostings'), payload.get('facets')
    if (type(total) is not int or not 0 <= total <= 5000 or not isinstance(rows, list)
            or len(rows) != min(MAX_ROWS, total) or not isinstance(facets, list)):
        raise ValueError('invalid or incomplete career listing')
    companies = [value for facet in facets if isinstance(facet, dict)
                 and facet.get('facetParameter') == 'hiringCompany'
                 and isinstance(facet.get('values'), list) for value in facet['values']
                 if isinstance(value, dict) and value.get('id') == COMPANY_ID]
    if (len(companies) != 1 or companies[0].get('descriptor') != SOURCE_EMPLOYER
            or type(companies[0].get('count')) is not int or companies[0]['count'] != total):
        raise ValueError('holding company facet unverified')
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid job listing row')
        match = _job_path(row.get('externalPath'))
        title = row.get('title')
        if (not isinstance(title, str) or not 1 <= len(title.strip()) <= 200
                or row.get('bulletFields') != [match['req']] or match['req'] in seen):
            raise ValueError('invalid or duplicate job identity')
        seen.add(match['req'])
    return rows[:MAX_POSTINGS], total


def _closing_date(description: str, today: date) -> str | None:
    text = unicodedata.normalize('NFKC', html.unescape(re.sub(r'<[^>]*>', '', description)))
    if re.search(r'(?:已|現已).{0,8}(?:截止|關閉|結束)|(?:招募|招聘|徵才|申請|投遞|收件|應徵|履歷)(?:現已|目前已|已)?(?:停止|暫停|關閉|結束|額滿)|(?:applications?|recruitment).{0,20}(?:closed|ended)|no longer accepting', text, re.I):
        raise ValueError('closed job description')
    markers = list(re.finditer(r'截止|deadline|(?:申請|投遞|招募|報名|履歷|招聘|徵才|應徵|收件)(?:期限|期間)|applications?\s+(?:closes?|ends?)(?:\s+(?:on|by))?', text, re.I))
    dates = []
    for marker in markers:
        tail = text[marker.end():]
        match = re.match(r'[^\d]{0,24}' + DATE_PARTS, tail)
        if not match:
            raise ValueError('ambiguous closing date')
        end = date(*(int(value) for value in match.groups()))
        if marker.group().endswith('期間'):
            bound = re.match(r'\s*(?:至|到|~|–|—|-)\s*' + DATE_PARTS, tail[match.end():])
            if not bound:
                raise ValueError('ambiguous application period')
            start, end = end, date(*(int(value) for value in bound.groups()))
            if start > end or today < start:
                raise ValueError('application period not open')
        if end < today:
            raise ValueError('expired closing date')
        dates.append(end)
    return min(dates).isoformat() if dates else None


def _posting(raw: bytes, candidate: dict, *, fetched_at_epoch: float) -> dict:
    payload = _payload(raw)
    info, employer = payload.get('jobPostingInfo'), payload.get('hiringOrganization')
    path = candidate['externalPath']
    match = _job_path(path)
    if (not isinstance(info, dict) or not isinstance(employer, dict)
            or employer.get('name') != SOURCE_EMPLOYER or info.get('title') != candidate['title']
            or info.get('jobReqId') != match['req'] or info.get('jobPostingId') != match['slug']
            or info.get('jobPostingSiteId') != 'External'
            or info.get('canApply') is not True or info.get('posted') is not True
            or _public_path(info.get('externalUrl')) != path):
        raise ValueError('job employer, availability or identity unverified')
    published, today = _date(info.get('startDate')), _today(fetched_at_epoch)
    if not 0 <= (today - published).days <= 30:
        raise ValueError('job not recently posted')
    description = info.get('jobDescription')
    if not isinstance(description, str) or not 10 <= len(description) <= 100_000:
        raise ValueError('job description unavailable')
    closing_date = _closing_date(description, today)
    return {'title': info['title'], 'url': info['externalUrl'], 'job_no': match['req'],
            'employer': LEGAL_NAME, 'source_employer': SOURCE_EMPLOYER, 'company_id': COMPANY_ID,
            'posted_date': published.isoformat(), 'closing_date': closing_date,
            'can_apply': True, 'posted': True, 'source_url': API_BASE + path,
            'response_sha256': sha256(raw).hexdigest(), 'response_bytes': len(raw),
            'fetched_at_epoch': fetched_at_epoch}


def fetch_official_ctbc_jobs(ticker: str) -> dict:
    unavailable = {'status': 'unavailable', 'ticker': ticker, 'company_name': LEGAL_NAME,
                   'job_count': None, 'current_open_job_count': None, 'job_postings': [],
                   'source': PROVIDER, 'source_url': API_URL, 'reason_code': 'official_career_unverified'}
    if ticker != TICKER:
        return {**unavailable, 'reason_code': 'issuer_not_supported'}
    deadline = time.monotonic() + 12
    try:
        raw = _download(API_URL, deadline, REQUEST)
        candidates, total = _candidates(raw)
        jobs, rejected = [], 0
        for candidate in candidates:
            # This source label only excludes an already old candidate. Any
            # accepted job still needs its individual absolute startDate.
            if candidate.get('postedOn') in ('Posted 30+ Days Ago', '超過 30 天前刊登'):
                rejected += 1
                continue
            try:
                body = _download(API_BASE + candidate['externalPath'], deadline)
                jobs.append(_posting(body, candidate, fetched_at_epoch=time.time()))
            except (RuntimeError, ValueError, TypeError, KeyError, OverflowError):
                rejected += 1
        if not jobs:
            return {**unavailable, 'reason_code': 'no_verified_recent_open_issuer_postings', 'rejected_count': rejected}
        return {'status': 'success', 'ticker': TICKER, 'company_name': LEGAL_NAME,
                'company_id': COMPANY_ID, 'job_count': None, 'current_open_job_count': len(jobs),
                'job_postings': jobs, 'evidence_kind': 'official_company_job_postings',
                'query_scope': 'exact_issuer_recent_open_postings', 'source': PROVIDER,
                'source_url': API_URL, 'listing_url': CAREER_URL,
                'response_sha256': sha256(raw).hexdigest(), 'response_bytes': len(raw),
                'fetched_at_epoch': time.time(), 'issuer_listing_count': total,
                'rejected_count': rejected, 'raw_count': len(candidates),
                'coverage_status': 'recent_open_posting_sample',
                'message': '只計入金控本體近30天刊登、逐筆仍可應徵的官方原件樣本；非集團或全站職缺總數。'}
    except (RuntimeError, ValueError, TypeError, KeyError, OverflowError):
        return unavailable


def _fresh_epoch(value, now) -> bool:
    if type(value) not in (int, float) or type(now) not in (int, float):
        return False
    try:
        return math.isfinite(value) and math.isfinite(now) and 0 <= now-value <= 86400
    except (OverflowError, ValueError):
        return False


def verified_ctbc_job_count(value: dict, ticker: str, legal_name: str, *, now: float | None = None) -> int:
    now = time.time() if now is None else now
    if (not isinstance(value, dict) or ticker != TICKER or legal_name != LEGAL_NAME
            or value.get('status') != 'success' or value.get('ticker') != TICKER
            or value.get('company_name') != LEGAL_NAME or value.get('company_id') != COMPANY_ID
            or value.get('source') != PROVIDER or value.get('source_url') != API_URL
            or value.get('listing_url') != CAREER_URL or value.get('job_count') is not None
            or value.get('evidence_kind') != 'official_company_job_postings'
            or value.get('query_scope') != 'exact_issuer_recent_open_postings'
            or not DIGEST.fullmatch(str(value.get('response_sha256') or ''))):
        return 0
    rows, count, fetched = value.get('job_postings'), value.get('current_open_job_count'), value.get('fetched_at_epoch')
    if (not _fresh_epoch(fetched, now)
            or not isinstance(rows, list) or not 0 < len(rows) <= MAX_POSTINGS
            or type(count) is not int or count != len(rows)):
        return 0
    try:
        today, ids = _today(now), set()
        for row in rows:
            if not isinstance(row, dict):
                return 0
            path = _public_path(row.get('url'))
            match = _job_path(path)
            fetched = row.get('fetched_at_epoch')
            if (row.get('job_no') != match['req'] or match['req'] in ids
                    or row.get('employer') != LEGAL_NAME or row.get('source_employer') != SOURCE_EMPLOYER
                    or row.get('company_id') != COMPANY_ID or row.get('can_apply') is not True
                    or row.get('posted') is not True or row.get('source_url') != API_BASE + path
                    or not isinstance(row.get('title'), str) or not 1 <= len(row['title'].strip()) <= 200
                    or not DIGEST.fullmatch(str(row.get('response_sha256') or ''))
                    or type(row.get('response_bytes')) is not int or not 0 < row['response_bytes'] <= MAX_BYTES
                    or not _fresh_epoch(fetched, now)
                    or not 0 <= (today - _date(row.get('posted_date'))).days <= 30
                    or (row.get('closing_date') is not None and _date(row['closing_date']) < today)):
                return 0
            ids.add(match['req'])
    except (ValueError, TypeError, KeyError, OverflowError, OSError):
        return 0
    return len(ids)
