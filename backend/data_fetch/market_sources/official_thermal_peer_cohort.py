"""Current identities in an observed thermal segment, not valuation equivalence.

The exchange segment has no membership effective date. Keep complete originals
and their retrieval times; whole-company business mix remains unverified.
"""
from datetime import date, datetime
import base64
from hashlib import sha256
import math
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp
from .official_company_legal_name import URLS as MASTERS, parse_roster, select_legal_name

TARGET = '3324.TWO'
POLICY = 'official-thermal-segment-v1'
SCOPE = 'thermal_management_segment'
ISSUER_URL = 'https://ic.tpex.org.tw/company_chain.php?stk_code=3324'
SEGMENT_URL = 'https://ic.tpex.org.tw/introduce.php?ic=F000'
SEGMENT = '散熱片、風扇馬達、散熱模組'
IDENTITIES = {
    TARGET: ('雙鴻', '雙鴻科技股份有限公司', '16619628'),
    '3017.TW': ('奇鋐', '奇鋐科技股份有限公司', '86427715'),
    '3338.TW': ('泰碩', '泰碩電子股份有限公司', '89858152'),
    '6230.TW': ('尼得科超眾', '尼得科超眾科技股份有限公司', '34005476'),
    '2421.TW': ('建準', '建準電機工業股份有限公司', '81448796'),
    '3483.TWO': ('力致', '力致科技股份有限公司', '16266820'),
}
PEERS = tuple(ticker for ticker in IDENTITIES if ticker != TARGET)
RECEIPT_KEY = 'thermal_membership_originals'
SHARED_KIND = 'cached_complete_source_payload_verified_by_digest'


def _page(raw, limit):
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= limit:
        raise ValueError('thermal_page_size_invalid')
    return BeautifulSoup(raw.decode('utf-8', errors='strict'), 'html.parser')


def _compact(value):
    return re.sub(r'\s+', '', value)


def _issuer_member(raw):
    page = _page(raw, 25_000)
    headings = [h for h in page.find_all('h4')
                if _compact(h.get_text()) == '3324雙鴻所屬產業鏈如下:']
    if len(headings) != 1:
        raise ValueError('thermal_target_section_unverified')
    section = headings[0].find_parent('div', class_='content')
    if (section is None
            or len([h for h in section.find_all('h3') if h.get_text(' ', strip=True) == '個體公司所屬產業鏈']) != 1
            or len([h for h in section.find_all('h4') if re.fullmatch(
                r'[0-9]{4}.+所屬產業鏈如下:', _compact(h.get_text()))]) != 1):
        raise ValueError('thermal_target_section_ambiguous')
    matches = [h for h in section.find_all('h4')
               if _compact(h.get_text()) == '►電腦及週邊設備>' + SEGMENT]
    if len(matches) != 1 or len(matches[0].find_all('a', href='introduce.php?ic=F000')) != 1:
        raise ValueError('thermal_target_membership_unverified')


def _members(raw):
    groups = _page(raw, 500_000).select(f'div#companyList_FB00[title="{SEGMENT}"]')
    if len(groups) != 2 or not any(b.get_text(' ', strip=True) == SEGMENT
                                 for group in groups for b in group.find_all('b')):
        raise ValueError('thermal_segment_unverified')
    panels = []
    for group in groups:
        found = {}
        for link in group.find_all('a', href=True):
            match = re.fullmatch(r'company_basic\.php\?stk_code=([1-9]\d{3})', link['href'])
            if match:
                found.setdefault(match[1], []).append((link.get_text(' ', strip=True), link.get('title')))
        if found.get('3324') != [('雙鴻', '雙鴻')]:
            raise ValueError('thermal_target_absent_from_segment')
        panels.append(found)
    return [ticker for ticker in PEERS
            if all(panel.get(ticker[:4]) == [(IDENTITIES[ticker][0], IDENTITIES[ticker][0])]
                   for panel in panels)]


def _roster(raw, suffix):
    roster = parse_roster(raw, suffix)
    if len(roster['entries']) < (800 if suffix == '.TW' else 700):
        raise ValueError('thermal_master_incomplete')
    return roster


class ThermalHttp(IssuerNewsHttp):
    @staticmethod
    def route_contract(url):
        if url in MASTERS.values():
            return 2_500_000, {'application/json', 'text/json'}
        if url == ISSUER_URL:
            return 25_000, {'text/html', 'application/xhtml+xml'}
        if url == SEGMENT_URL:
            return 500_000, {'text/html', 'application/xhtml+xml'}
        raise SourceResponseError('transport_url_invalid')

    def get(self, url):
        from cache_store import get_cache_json
        raw = super().get(url)
        component = self.components[-1]
        shared = component.get('evidence_kind') == SHARED_KIND
        key = 'official-company-roster:v2:.TW' if shared else 'issuer-news-raw:v1:' + url
        cached = get_cache_json('shared_provider:v1:' + sha256(key.encode()).hexdigest())
        if not isinstance(cached, dict) or cached.get('error_kind'):
            raise SourceResponseError('cache_receipt_invalid')
        stamp, until = cached.get('fetched_at_epoch'), cached.get('fresh_until_epoch')
        value = cached.get('value')
        digest = value.get('response_sha256' if shared else 'sha256') if isinstance(value, dict) else None
        ttl = 86400 if shared else 1800
        if (shared and url != MASTERS['.TW'] or stamp != component.get('fetched_at_epoch')
                or digest != sha256(raw).hexdigest() or not _current_window(stamp, until, ttl)):
            raise SourceResponseError('cache_receipt_invalid')
        component.update(fresh_until_epoch=min(until, stamp + ttl),
                         evidence_kind=SHARED_KIND if shared else 'raw_http_response_bytes',
                         http_status_observed=not shared)
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return raw

    def _download(self, url, diagnostic):
        value = super()._download(url, diagnostic)
        raw = base64.b64decode(value['body_b64'], validate=True)
        try:
            if url == ISSUER_URL:
                _issuer_member(raw)
            elif url == SEGMENT_URL:
                _members(raw)
            else:
                _roster(raw, next(suffix for suffix, source in MASTERS.items() if source == url))
        except (ValueError, UnicodeError) as exc:
            diagnostic['error_kind'] = 'thermal_original_invalid'
            raise SourceResponseError(diagnostic['error_kind']) from exc
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return value


def _current_window(stamp, until, ttl):
    now = time.time()
    return (type(stamp) in (int, float) and type(until) in (int, float)
            and math.isfinite(stamp) and math.isfinite(until)
            and 0 < stamp <= now < min(until, stamp + ttl)
            and 0 < until - stamp <= ttl + 1)


def _receipt_current(receipt, url):
    if not isinstance(receipt, dict):
        return False
    shared = receipt.get('evidence_kind') == SHARED_KIND
    provenance_valid = ((url == MASTERS['.TW'] and receipt.get('http_status') is None
                         and receipt.get('http_status_observed') is False) if shared else
                        (receipt.get('evidence_kind') == 'raw_http_response_bytes'
                         and receipt.get('http_status') == 200
                         and receipt.get('http_status_observed') is True))
    return (provenance_valid and receipt.get('status') == 'archived' and receipt.get('source_url') == url
            and _current_window(receipt.get('retrieved_at'), receipt.get('fresh_until_epoch'),
                                86400 if shared else 1800))


def _original(receipt, url):
    if not _receipt_current(receipt, url):
        raise ValueError('thermal_original_expired_or_unverified')
    raw = read_response(receipt)
    limit, _ = ThermalHttp.route_contract(url)
    if (not 0 < len(raw) <= limit or type(receipt.get('raw_response_bytes')) is not int
            or receipt['raw_response_bytes'] != len(raw)):
        raise ValueError('thermal_original_size_invalid')
    return raw


def _candidates(originals, today):
    if not isinstance(originals, dict) or set(originals) != {*MASTERS.values(), ISSUER_URL, SEGMENT_URL}:
        raise ValueError('thermal_original_set_invalid')
    raw = {url: _original(receipt, url) for url, receipt in originals.items()}
    rosters = {suffix: _roster(raw[url], suffix) for suffix, url in MASTERS.items()}
    identities = {}
    for ticker, (short, legal, ubn) in IDENTITIES.items():
        suffix = '.TWO' if ticker.endswith('.TWO') else '.TW'
        anchor = select_legal_name(rosters[suffix], ticker, short, today=today)
        retrieved_day = datetime.fromtimestamp(originals[MASTERS[suffix]]['retrieved_at'], ZoneInfo('Asia/Taipei')).date()
        if (anchor and anchor['legal_name'] == legal and anchor['official_ubn'] == ubn
                and date.fromisoformat(anchor['as_of']) <= retrieved_day <= today
                and 0 <= (today - date.fromisoformat(anchor['as_of'])).days <= 7):
            identities[ticker] = anchor
    if TARGET not in identities:
        raise ValueError('thermal_current_target_unverified')
    _issuer_member(raw[ISSUER_URL])
    members = _members(raw[SEGMENT_URL])
    rows = []
    for ticker in PEERS:
        if ticker not in members or ticker not in identities:
            continue
        rows.append({
            'name': IDENTITIES[ticker][0], 'ticker': ticker,
            'identity_status': 'current_exchange_master_and_official_thermal_segment',
            'comparison_status': 'official_segment_candidate', 'comparison_scope': SCOPE,
            'selection_policy': POLICY, 'business_comparability_verified_current': False,
            'membership_effective_date_verified': False, 'numeric_comparability_verified': False,
            'relationship_basis': 'same_undated_tpex_thermal_segment',
            'comparison_limitations': ['undated_segment_membership', 'whole_company_business_mix_not_verified',
                                       'financial_period_comparability_not_verified'],
            'issuer_master_anchor': identities[TARGET], 'master_anchor': identities[ticker],
            'issuer_source_url': ISSUER_URL, 'segment_source_url': SEGMENT_URL,
            RECEIPT_KEY: originals,
        })
    return rows


def verified_thermal_candidate(record, ticker, *, today):
    return verified_thermal_candidates([record], ticker, today=today)


def verified_thermal_candidates(records, ticker, *, today):
    """One original readback for a batch; no per-row page downloads or reparse."""
    try:
        if (ticker != TARGET or not isinstance(records, list) or not 1 <= len(records) <= 5
                or any(not isinstance(row, dict) for row in records)):
            return False
        expected_by_ticker = {row['ticker']: row for row in _candidates(records[0].get(RECEIPT_KEY), today)}
        seen = set()
        for record in records:
            symbol = record.get('ticker')
            if not isinstance(symbol, str) or symbol in seen or symbol not in expected_by_ticker:
                return False
            seen.add(symbol)
            expected = expected_by_ticker[symbol]
            if (any(record.get(key) != value for key, value in expected.items())
                    or any(record.get(key) is not False for key in (
                        'business_comparability_verified_current', 'membership_effective_date_verified',
                        'numeric_comparability_verified'))):
                return False
        # Parsing must not extend an almost-expired original's admission time.
        for url, receipt in records[0][RECEIPT_KEY].items():
            if not _receipt_current(receipt, url):
                return False
        return True
    except (ValueError, KeyError, TypeError, OSError, EOFError, OverflowError):
        pass
    return False


def get_official_thermal_candidates(ticker, *, today):
    if ticker != TARGET:
        return {'candidates': [], 'status': 'not_applicable'}
    deadline = time.monotonic() + 12
    http = ThermalHttp(deadline)
    originals = {}
    try:
        for url in (MASTERS['.TWO'], MASTERS['.TW'], ISSUER_URL, SEGMENT_URL):
            raw = http.get(url)
            component = http.components[-1]
            originals[url] = archive_response(raw, source_url=url,
                retrieved_at=component['fetched_at_epoch'], evidence_kind=component['evidence_kind'],
                http_status=200 if component['http_status_observed'] else None)
            originals[url].update(fresh_until_epoch=component['fresh_until_epoch'],
                                  http_status_observed=component['http_status_observed'])
            if time.monotonic() >= deadline:
                raise SourceResponseError('timeout')
        rows = _candidates(originals, today)
        if not all(_receipt_current(receipt, url) for url, receipt in originals.items()):
            raise SourceResponseError('cache_receipt_expired')
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        return {'candidates': rows, 'status': 'success' if rows else 'no_verified_members',
                'cache_hit': all(c.get('cache_hit') is True for c in http.components),
                'http_request_count': http.http_request_count, 'components': http.components}
    except Exception as exc:
        return {'candidates': [], 'status': 'official_thermal_originals_unavailable',
                'error_kind': getattr(exc, 'error_kind', type(exc).__name__),
                'http_request_count': http.http_request_count, 'components': http.components}
