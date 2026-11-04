"""Dated auto-sales-related publisher leads with independent stock identities.

The published category mixes vehicle manufacturers and dealerships. Membership never
proves competition, fine industry, comparable periods, or usable valuations.
"""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
import math
import re
import time

from bs4 import BeautifulSoup

from .moneydj_peer_cohort import _current_identity
from .peer_recovery import current_master_industry_categories

TARGET = '2207.TW'
SHORT = '和泰車'
URL = 'https://m.moneydj.com/z/zh/zha/zh00.djhtm?a=C022010'
TITLE = '同業股價表現-車輛相關-汽車銷售-台股-MoneyDJ理財網'
PROVIDER = 'MoneyDJ published auto-sales-related companies'
POLICY = 'dated-auto-sales-related-company-leads:v1'
SCOPE = 'publisher_auto_sales_related_candidates'
MAX_BYTES = 200_000
LINK = re.compile(r"javascript:Link2Stk\('AS([1-9][0-9]{3})'\);\Z")
HEADERS = ['股票名稱', '最後交易日期', '收盤價', '漲跌', '漲跌幅',
           '近一週報酬', '近一個月報酬', '近二個月報酬', '近三個月報酬', '今年以來報酬']


def parse_page(raw, master_rows, *, today):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or type(today) is not date:
        raise ValueError('auto_sales related original or observation day invalid')
    if _current_identity('2207', master_rows, today) != (SHORT, 'twse'):
        raise ValueError('current auto_sales target identity unverified')
    categories = current_master_industry_categories(TARGET, master_rows, today=today)
    if categories != ['汽車工業']:
        raise ValueError('auto_sales target classification changed')
    text = raw.decode('big5', 'strict')
    if (len(re.findall(r'<html(?:\s[^<>]*)?>', text, re.I)) != 1
            or len(re.findall(r'</html\s*>', text, re.I)) != 1
            or not re.search(r'</html\s*>\s*\Z', text, re.I)):
        raise ValueError('complete auto_sales related original required')
    soup = BeautifulSoup(text, 'html.parser')
    if len(soup.find_all('title')) != 1 or soup.title.get_text(' ', strip=True) != TITLE:
        raise ValueError('auto_sales publisher cohort changed')
    canonical = soup.find_all('link', rel='canonical')
    if len(canonical) != 1 or canonical[0].get('href') not in {
            'https://www.moneydj.com/Z/ZH/ZH0/ZH00/ZH00.djhtm?A=C022010',
            'https://www.moneydj.com/Z/ZH/ZH0/ZH00/ZH00.djhtm?a=C022010'}:
        raise ValueError('auto sales publication identity changed')
    tables = soup.find_all('table', id='oMainTable')
    if len(tables) != 1:
        raise ValueError('auto_sales related table ambiguous')
    table = tables[0]
    headings = table.find_all('tr', id='oScrollMenu')
    if len(headings) != 1 or [''.join(c.get_text().split()) for c in headings[0].find_all('td', recursive=False)] != HEADERS:
        raise ValueError('auto_sales table columns changed')
    titles = table.find_all('td', id='oHeadTitle')
    if len(titles) != 1 or '相關公司股價表現' not in titles[0].get_text():
        raise ValueError('publisher relationship scope unverified')
    calculation = re.findall(r'報酬計算日期：(\d{2}/\d{2})', titles[0].get_text())
    if len(calculation) != 1:
        raise ValueError('auto sales calculation date ambiguous')
    parsed = {}
    for tr in table.find_all('tr', recursive=False):
        if tr.get('id') in ('oScrollHead', 'oScrollMenu'):
            continue
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 10:
            raise ValueError('auto_sales related row incomplete')
        anchors = cells[0].find_all('a', href=True)
        if len(anchors) != 1 or not (link := LINK.fullmatch(anchors[0]['href'])):
            raise ValueError('auto_sales related stock action invalid')
        code = link[1]
        label = re.fullmatch(r'([1-9][0-9]{3})(.+)', anchors[0].get_text(' ', strip=True))
        stamp = date.fromisoformat(cells[1].get_text(strip=True).replace('/', '-'))
        if (not label or label[1] != code or code in parsed
                or not 0 <= (today - stamp).days <= 7 or stamp.strftime('%m/%d') != calculation[0]):
            raise ValueError('auto_sales related stock date or identity invalid')
        parsed[code] = (label[2], stamp)
    if not 2 <= len(parsed) <= 64 or parsed.get('2207', (None,))[0] != SHORT:
        raise ValueError('auto_sales target missing from related table')
    candidates, rejected = [], {}
    for code, (name, stamp) in sorted(parsed.items()):
        if code == '2207':
            continue
        current = _current_identity(code, master_rows, today)
        if current is None or current[0] != name:
            raise ValueError('published and current stock identities disagree')
        symbol = code + ('.TW' if current[1] == 'twse' else '.TWO')
        peer_categories = current_master_industry_categories(symbol, master_rows, today=today)
        if peer_categories != categories:
            rejected['different_exchange_category'] = rejected.get('different_exchange_category', 0) + 1
            continue
        candidates.append({'ticker': symbol, 'name': name, 'identity_status': 'verified_master',
            'comparison_status': 'industry_candidate_only', 'comparison_scope': SCOPE,
            'industry_categories': peer_categories, 'publisher_observed_at': stamp.isoformat(),
            'relationship_basis': 'dated_publisher_related_company_and_current_master',
            'business_comparability_verified_current': False, 'numeric_comparability_verified': False,
            'selection_policy': POLICY, 'identity_source_url': URL})
    return {'candidates': candidates, 'raw_count': len(parsed), 'rejected_reason_counts': rejected,
            'source_url': URL, 'response_sha256': sha256(raw).hexdigest(),
            'relationship_scope': 'published_related_companies_not_competitors_or_valuation_rank'}


_ARCHIVE_FIELDS = {'status', 'source_url', 'retrieved_at', 'http_status', 'raw_response_sha256',
                   'raw_response_path', 'raw_response_bytes', 'evidence_kind',
                   'historical_point_in_time_verified', 'finality_guaranteed'}


def _original(receipt, url, limit, age, now):
    from official_response_evidence import read_response
    if (not isinstance(receipt, dict) or set(receipt) != _ARCHIVE_FIELDS
            or receipt.get('status') != 'archived' or receipt.get('source_url') != url
            or type(receipt.get('http_status')) is not int or receipt['http_status'] != 200
            or receipt.get('evidence_kind') != 'raw_http_response_bytes'
            or receipt.get('historical_point_in_time_verified') is not False
            or receipt.get('finality_guaranteed') is not False
            or type(receipt.get('retrieved_at')) not in (int, float)
            or not math.isfinite(receipt['retrieved_at'])
            or not 0 <= now - receipt['retrieved_at'] < age):
        raise ValueError('auto_sales source original identity or freshness invalid')
    raw = read_response(receipt, max_bytes=limit)
    if type(receipt.get('raw_response_bytes')) is not int or not 0 < len(raw) == receipt['raw_response_bytes'] <= limit:
        raise ValueError('auto_sales complete source body missing')
    return raw


def _master(receipt, now):
    from .stock_identity_master import URL as MASTER_URL, MAX_BYTES as MASTER_LIMIT, FRESH_SECONDS, parse_master
    return parse_master(_original(receipt, MASTER_URL, MASTER_LIMIT, FRESH_SECONDS, now))


def _manifest(context):
    return json.dumps({k: v for k, v in context.items() if k != 'receipt_manifest'},
                      ensure_ascii=True, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def replay_context(context, *, today, now=None):
    from official_response_evidence import read_response
    now = time.time() if now is None else now
    if (not isinstance(context, dict) or set(context) != {'policy', 'ticker', 'publication_receipt', 'master_receipt', 'receipt_manifest'}
            or context['policy'] != POLICY or context['ticker'] != TARGET
            or type(now) not in (int, float) or not math.isfinite(now)):
        raise ValueError('auto_sales original context invalid')
    rows = _master(context['master_receipt'], now)
    raw = _original(context['publication_receipt'], URL, MAX_BYTES, 1800, now)
    manifest = context['receipt_manifest']
    encoded = _manifest(context)
    if (not isinstance(manifest, dict) or set(manifest) != _ARCHIVE_FIELDS
            or manifest.get('status') != 'archived' or manifest.get('source_url') != URL
            or manifest.get('http_status') is not None
            or manifest.get('retrieved_at') != context['publication_receipt']['retrieved_at']
            or manifest.get('evidence_kind') != 'private_acquisition_manifest'
            or manifest.get('historical_point_in_time_verified') is not False
            or manifest.get('finality_guaranteed') is not False
            or type(manifest.get('raw_response_bytes')) is not int or manifest['raw_response_bytes'] != len(encoded)
            or read_response(manifest, max_bytes=16384) != encoded):
        raise ValueError('auto_sales original metadata manifest invalid')
    return parse_page(raw, rows, today=today)


def _context(raw, stamp, master_receipt):
    from official_response_evidence import archive_response
    value = {'policy': POLICY, 'ticker': TARGET,
             'publication_receipt': archive_response(raw, source_url=URL, retrieved_at=stamp, http_status=200, max_bytes=MAX_BYTES),
             'master_receipt': deepcopy(master_receipt)}
    value['receipt_manifest'] = archive_response(_manifest(value), source_url=URL,
        retrieved_at=stamp, evidence_kind='private_acquisition_manifest', http_status=None)
    return value


def get_candidates(ticker, master_rows, *, today, transport=None):
    """One normal raw-source path; current master must already be available."""
    from .issuer_news_transport import IssuerNewsHttp
    from source_audit import build_source_audit_entry
    if ticker != TARGET:
        return {'candidates': [], 'status': 'not_applicable'}
    started = time.time()
    http = None
    parsed = {}
    context = None
    error = None
    try:
        metadata = getattr(master_rows, 'identity_master_metadata', {})
        receipt = metadata.get('raw_receipt') if isinstance(metadata, dict) else None
        if _master(receipt, started) != list(master_rows):
            raise ValueError('auto_sales master rows differ from complete original')
        # Fail before requesting a publisher if the exact target is not current.
        if _current_identity('2207', master_rows, today) != (SHORT, 'twse'):
            raise ValueError('auto_sales target identity unverified')
        class AutoSalesHttp(IssuerNewsHttp):
            @staticmethod
            def route_contract(url):
                if url != URL:
                    raise ValueError('unqualified auto_sales related URL')
                return MAX_BYTES, {'text/html', 'application/xhtml+xml'}
        http = transport or AutoSalesHttp(time.monotonic() + 8)
        raw = http.get(URL)
        diagnostic = http.components[-1]
        stamp = diagnostic.get('fetched_at_epoch')
        if (type(stamp) not in (int, float) or not math.isfinite(stamp)
                or not 0 <= time.time() - stamp < 1800):
            raise ValueError('auto_sales publisher original epoch missing or expired')
        context = _context(raw, stamp, receipt)
        parsed = replay_context(context, today=today)
    except Exception as exc:
        error = getattr(exc, 'error_kind', type(exc).__name__)
    components = deepcopy(http.components) if http is not None else []
    sent = sum(c.get('http_request_sent') is True for c in components)
    cache_hit = bool(components) and not sent and all(c.get('cache_hit') is True for c in components)
    candidates = [] if error else [dict(c, auto_sales_related_originals=deepcopy(context)) for c in parsed['candidates']]
    status = 'error' if error else 'skipped_fresh_cache' if candidates and cache_hit else 'success' if candidates else 'unavailable'
    audit = build_source_audit_entry('peer_discovery', PROVIDER, status,
        started_at_epoch=started, finished_at_epoch=time.time(),
        fetched_at_epoch=components[-1].get('fetched_at_epoch') if components else None,
        record_count=len(candidates), cache_hit=cache_hit, stale=False, error_kind=str(error or ''),
        message='汽車銷售相關公司候選；競爭關係、整體業務及財期可比性尚未驗證。')
    audit.update(selection_policy=POLICY, source_url=URL, http_request_sent=bool(sent),
        http_request_count=sent, component_statuses=components,
        event_kind='http_request' if sent else 'cache_hit' if cache_hit else 'local_block',
        response_sha256=parsed.get('response_sha256'), raw_count=parsed.get('raw_count', 0),
        rejected_reason_counts=parsed.get('rejected_reason_counts', {}))
    return {'candidates': candidates, 'status': status, 'source_audit': audit}


def verified_candidates(records, ticker, *, today):
    if ticker != TARGET or not isinstance(records, list) or not records:
        return False
    seen = set()
    try:
        for record in records:
            if (not isinstance(record, dict) or record.get('comparison_scope') != SCOPE
                    or record.get('comparison_status') != 'business_industry_matched'
                    or record.get('ticker') in seen):
                return False
            seen.add(record['ticker'])
            parsed = replay_context(record.get('auto_sales_related_originals'), today=today)
            expected = {c['ticker']: c for c in parsed['candidates']}.get(record['ticker'])
            if expected is None or any(record.get(k) != v for k, v in expected.items() if k != 'comparison_status'):
                return False
    except (ValueError, TypeError, KeyError, OSError, OverflowError):
        return False
    return True
