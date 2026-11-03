"""Exact Lumax IC-distribution leads from complete official source originals.

Membership is observed, undated and segment-only. Current market identities
do not establish whole-company business, size or numeric comparability.
"""
from datetime import date, datetime
import base64
import re
import time
from zoneinfo import ZoneInfo

from official_response_evidence import archive_response, read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp
from .official_company_legal_name import URLS as MASTERS, select_legal_name
from .official_thermal_peer_cohort import (
    ThermalHttp, _page, _compact, _roster, _receipt_current,
)

TARGET = '6192.TW'
LEGAL = '巨路國際股份有限公司'
SHORT = '巨路'
UBN = '14033663'
ISSUER_URL = 'https://ic.tpex.org.tw/company_chain.php?stk_code=6192'
SEGMENT_URL = 'https://ic.tpex.org.tw/introduce.php?ic=D000'
SCOPE = 'semiconductor_distribution_segment'
POLICY = 'official-lumax-ic-distribution-v1'
RECEIPT_KEY = 'ic_distribution_membership_originals'


def _issuer_member(raw):
    page = _page(raw, 25_000)
    headings = [h for h in page.find_all('h4') if _compact(h.get_text()) == '6192巨路所屬產業鏈如下:']
    if len(headings) != 1:
        raise ValueError('ic_target_section_unverified')
    section = headings[0].find_parent('div', class_='content')
    if (section is None or len([h for h in section.find_all('h3')
            if h.get_text(' ', strip=True) == '個體公司所屬產業鏈']) != 1
            or len([h for h in section.find_all('h4') if re.fullmatch(
                r'[0-9]{4}.+所屬產業鏈如下:', _compact(h.get_text()))]) != 1):
        raise ValueError('ic_target_section_ambiguous')
    found = [h for h in section.find_all('h4') if _compact(h.get_text()) == '►半導體>IC通路']
    if len(found) != 1 or len(found[0].find_all('a', href='introduce.php?ic=D000')) != 1:
        raise ValueError('ic_target_membership_unverified')


def _members(raw):
    groups = _page(raw, 500_000).select('div#companyList_DB00[title="IC通路"]')
    if len(groups) != 2 or not any(b.get_text(' ', strip=True) == 'IC通路' for g in groups for b in g.find_all('b')):
        raise ValueError('ic_segment_unverified')
    panels = []
    markets = {'上市': '.TW', '上櫃': '.TWO', '興櫃': 'emerging'}
    for group in groups:
        market, declared, counts, rows = None, {}, {}, []
        # Source table rows are not well nested. Follow its actual heading/link
        # order, not a guessed td/rowspan association or stock-code convention.
        for node in group.descendants:
            if getattr(node, 'name', None) == 'b':
                text = node.get_text(' ', strip=True)
                if text == 'IC通路':
                    continue
                domestic = re.fullmatch(r'本國(上市|上櫃|興櫃)公司\((\d{1,3})家\)', text)
                foreign = re.fullmatch(r'知名外國企業\(\d{1,3}家\)', text)
                if not domestic and not foreign:
                    raise ValueError('ic_market_heading_unverified')
                market = markets[domestic[1]] if domestic else 'foreign'
                if market in declared:
                    raise ValueError('ic_market_heading_duplicated')
                declared[market] = int(domestic[2]) if domestic else None
                counts[market] = 0
            if getattr(node, 'name', None) != 'a':
                continue
            match = re.fullmatch(r'company_basic\.php\?stk_code=([1-9]\d{3})', node.get('href', ''))
            if not match:
                continue
            name = node.get_text(' ', strip=True)
            if market not in {'.TW', '.TWO', 'emerging'} or not name or name != node.get('title'):
                raise ValueError('ic_member_market_or_label_unverified')
            rows.append((match[1], name, market))
            counts[market] += 1
        if (set(declared) != {'.TW', '.TWO', 'emerging', 'foreign'}
                or any(counts[m] != declared[m] for m in ('.TW', '.TWO', 'emerging'))
                or not 1 <= len(rows) <= 2000 or len(rows) != len({r[0] for r in rows})
                or ('6192', SHORT, '.TW') not in rows):
            raise ValueError('ic_complete_membership_unverified')
        panels.append(rows)
    if panels[0] != panels[1]:
        raise ValueError('ic_membership_panels_disagree')
    return [r for r in panels[0] if r[2] in {'.TW', '.TWO'}]


class IcDistributionHttp(ThermalHttp):
    """Share tested receipt lifetimes; keep IC issuer/segment admission separate."""
    def __init__(self, deadline):
        IssuerNewsHttp.__init__(self, deadline)

    @staticmethod
    def route_contract(url):
        if url in MASTERS.values():
            return 2_500_000, {'application/json', 'text/json'}
        if url == ISSUER_URL:
            return 25_000, {'text/html', 'application/xhtml+xml'}
        if url == SEGMENT_URL:
            return 500_000, {'text/html', 'application/xhtml+xml'}
        raise SourceResponseError('transport_url_invalid')

    def _download(self, url, diagnostic):
        value = IssuerNewsHttp._download(self, url, diagnostic)
        raw = base64.b64decode(value['body_b64'], validate=True)
        try:
            if url == ISSUER_URL:
                _issuer_member(raw)
            elif url == SEGMENT_URL:
                _members(raw)
            else:
                _roster(raw, next(suffix for suffix, source in MASTERS.items() if source == url))
        except (ValueError, UnicodeError) as exc:
            diagnostic['error_kind'] = 'ic_original_invalid'
            raise SourceResponseError(diagnostic['error_kind']) from exc
        if time.monotonic() >= self.deadline:
            raise SourceResponseError('timeout')
        return value


def _original(receipt, url):
    if not _receipt_current(receipt, url):
        raise ValueError('ic_original_expired_or_unverified')
    raw = read_response(receipt)
    limit, _ = IcDistributionHttp.route_contract(url)
    if not 0 < len(raw) <= limit or type(receipt.get('raw_response_bytes')) is not int or len(raw) != receipt['raw_response_bytes']:
        raise ValueError('ic_original_size_invalid')
    return raw


def _candidates(originals, today):
    if not isinstance(originals, dict) or set(originals) != {*MASTERS.values(), ISSUER_URL, SEGMENT_URL}:
        raise ValueError('ic_original_set_invalid')
    raw = {url: _original(receipt, url) for url, receipt in originals.items()}
    rosters = {suffix: _roster(raw[url], suffix) for suffix, url in MASTERS.items()}
    _issuer_member(raw[ISSUER_URL])
    members = _members(raw[SEGMENT_URL])
    def anchor(code, name, market):
        if sum(code in r['entries'] for r in rosters.values()) != 1:
            return None
        value = select_legal_name(rosters[market], code + market, name, today=today)
        retrieved_day = datetime.fromtimestamp(originals[MASTERS[market]]['retrieved_at'], ZoneInfo('Asia/Taipei')).date()
        if (value and value['official_ubn'] and date.fromisoformat(value['as_of']) <= retrieved_day <= today
                and 0 <= (today - date.fromisoformat(value['as_of'])).days <= 7):
            return value
        return None
    issuer = anchor('6192', SHORT, '.TW')
    if not issuer or issuer['legal_name'] != LEGAL or issuer['official_ubn'] != UBN:
        raise ValueError('ic_current_target_unverified')
    rows = []
    for code, name, market in members:
        ticker = code + market
        if ticker == TARGET:
            continue
        peer = anchor(code, name, market)
        if not peer:
            continue
        rows.append({'name': name, 'ticker': ticker, 'identity_status': 'current_exchange_master_and_official_ic_segment',
            'comparison_status': 'official_segment_candidate', 'comparison_scope': SCOPE,
            'selection_policy': POLICY, 'business_comparability_verified_current': False,
            'membership_effective_date_verified': False, 'numeric_comparability_verified': False,
            'relationship_basis': 'same_undated_tpex_ic_distribution_segment',
            'comparison_limitations': ['undated_segment_membership', 'whole_company_business_mix_not_verified',
                'financial_period_comparability_not_verified', 'publisher_document_order_is_not_economic_rank'],
            'issuer_master_anchor': issuer, 'master_anchor': peer, 'issuer_source_url': ISSUER_URL,
            'segment_source_url': SEGMENT_URL, RECEIPT_KEY: originals})
    return rows


def verified_candidates(records, ticker, *, today):
    try:
        if ticker != TARGET or not isinstance(records, list) or not 1 <= len(records) <= 5 or any(not isinstance(r, dict) for r in records):
            return False
        expected = {r['ticker']: r for r in _candidates(records[0].get(RECEIPT_KEY), today)}
        seen = set()
        for row in records:
            symbol = row.get('ticker')
            if not isinstance(symbol, str) or symbol in seen or symbol not in expected:
                return False
            seen.add(symbol)
            if (any(row.get(k) != v for k, v in expected[symbol].items())
                    or any(row.get(k) is not False for k in ('business_comparability_verified_current',
                        'membership_effective_date_verified', 'numeric_comparability_verified'))):
                return False
        return all(_receipt_current(r, url) for url, r in records[0][RECEIPT_KEY].items())
    except (ValueError, KeyError, TypeError, OSError, EOFError, OverflowError):
        return False


def get_candidates(ticker, *, today):
    if ticker != TARGET:
        return {'candidates': [], 'status': 'not_applicable'}
    http = IcDistributionHttp(time.monotonic() + 12)
    originals = {}
    try:
        for url in (MASTERS['.TWO'], MASTERS['.TW'], ISSUER_URL, SEGMENT_URL):
            raw = http.get(url)
            part = http.components[-1]
            receipt = archive_response(raw, source_url=url, retrieved_at=part['fetched_at_epoch'],
                evidence_kind=part['evidence_kind'], http_status=200 if part['http_status_observed'] else None)
            receipt.update(fresh_until_epoch=part['fresh_until_epoch'], http_status_observed=part['http_status_observed'])
            originals[url] = receipt
        rows = _candidates(originals, today)
        if not all(_receipt_current(r, u) for u, r in originals.items()):
            raise SourceResponseError('cache_receipt_expired')
        if time.monotonic() >= http.deadline:
            raise SourceResponseError('timeout')
        return {'candidates': rows, 'status': 'success' if rows else 'no_qualified_current_members',
                'candidate_order_policy': 'publisher_document_order_only_not_economic_rank',
                'cache_hit': all(c.get('cache_hit') is True for c in http.components),
                'http_request_count': http.http_request_count, 'components': http.components}
    except Exception as exc:
        return {'candidates': [], 'status': 'official_ic_originals_unavailable',
                'error_kind': getattr(exc, 'error_kind', type(exc).__name__),
                'http_request_count': http.http_request_count, 'components': http.components}
