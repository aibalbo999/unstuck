"""Verify explicitly dated individual income against qualified archived originals.

This separate source never replaces an undated vendor scalar, supplies TTM EPS,
or upgrades freshness, historical availability, trust, or valuation permission.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata

_DATE = re.compile(r'20\d{2}-\d{2}-\d{2}')
_CURRENCY = re.compile(r'TWD|NTD|新[臺台]幣', re.I)
_INCOMPATIBLE = re.compile(
    r'合併|集團|分部|部門|產品|同業|同儕|競爭|peer|competitor|consolidated|group|'
    r'美元|美金|USD|US\$|CNY|RMB|人民幣|HKD|港元|港幣|JPY|日圓|日元|'
    r'EUR|歐元|GBP|英鎊|AUD|澳幣|CHF|瑞郎|KRW|韓元|'
    r'每股|EPS|股數|股本|預估|預測|預期|假設|情境|未來|如果|倘若|forecast|estimate', re.I)


def _identity(facts):
    # Only source-established names are eligible. Caller aliases must not turn
    # an unrelated issuer into the owner of these replayed monetary facts.
    aliases = ['大東電'] if (facts['ticker'] == '1623.TW'
                         and facts['issuer_name'] == '大東電業廠股份有限公司') else []
    return {'ticker': facts['ticker'], 'company_name': facts['issuer_name'],
            'company_identity': {'allowed_aliases': aliases}}


def _context_matches(text, identity):
    """Only structural headings/preambles may surround this explicit clause."""
    from financial_money_claims import _PERIOD, _target_revenue_scope
    # These exact debate stance labels identify a speaker position only.
    # Issuer/year/FX/forecast qualifiers and every ancestor retain their gates.
    if re.fullmatch(r'\s*(?:🐻\s*空頭|🐂\s*多頭)\s*[:：]?\s*', text):
        return True
    # Agent 2's native prompt mandates this exact structural section name.
    # Match the whole heading; issuer, year, currency and forecast qualifiers
    # in headings or surrounding prose must still pass the existing checks.
    if re.fullmatch(r'\s*##\s*二、\s*獲利趨勢深析\s*', text):
        return True
    if re.fullmatch(r'\s*#{1,6}\s*(?:[一二三四五六七八九十\d]+[、.]\s*)?'
                    r'折現現金流[（(]DCF[）)]估值解讀\s*', text, re.I):
        return True
    if re.fullmatch(r'\s*#{1,6}\s*現金流與獲利品質分析\s*', text):
        return True
    if re.fullmatch(r'\s*##\s*Round\s*(?:1\s*[:：]\s*基本面與護城河|2\s*[:：]\s*財務與估值|3\s*[:：]\s*近期催化劑)\s*', text):
        return True
    if re.fullmatch(r'\s*#{1,6}\s*(?:(?:[一二三四五六七八九十]+)[、.]\s*)?(?:獲利趨勢深析|自由現金流分析|已觀測財務與歷史反證|企業體質總結|成長潛力總評)\s*',text):
        return True
    text = re.sub(r'Agent\s*\d+|角色\s*\d+', '', text, flags=re.I)
    if _PERIOD.search(text):
        return False
    text = re.sub(r'財務|資本結構|分析|淨利|獲利|現金流|風險|摘要|資料|如下|與|及', '', text)
    return _target_revenue_scope(identity, text, '')


def _native_report_title(text, facts):
    if (facts['ticker']=='1623.TW' and facts['issuer_name']=='大東電業廠股份有限公司'
            and re.fullmatch(r'\s*# 1623\.TW（大東電）投資銀行等級估值解讀報告\s*',text)):
        return True
    title = re.fullmatch(r'\s*#\s+' + re.escape(facts['ticker'])
                         + r'\s+(.+?) - 華爾街深度研究報告\s*', text)
    if title is None:
        return False
    normalize = lambda value: ' '.join(unicodedata.normalize('NFKC', value).split()).casefold()
    names = {normalize(facts['issuer_name']), '大東電'}
    if facts.get('issuer_english_name'):
        names.add(normalize(facts['issuer_english_name']))
    parts = [normalize(value) for value in title[1].split(' / ')]
    return 1 <= len(parts) <= 2 and all(value in names for value in parts)


def _native_moat_income_scope(claim, facts, data):
    """Bind the complete observed cashflow bullet, including consumed amounts.

    A structural competitive-moat title grants no financial scope by itself.
    Every owner, period, currency and other monetary fact must bind to replayed
    originals. The current income is compared by the ordinary mismatch gate.
    """
    from official_financial_projection import read_official_financial_projection
    from evidence_official_financial_claims import _ttm_display_matches
    if not isinstance(data, dict) or claim.get('unit') != '億元':
        return False
    clean = lambda value: re.sub(r'[*`\s]', '', str(value or ''))
    ancestors = claim.get('_financial_heading_ancestors')
    names = [facts['issuer_name']]
    if facts['ticker'] == '1623.TW' and facts['issuer_name'] == '大東電業廠股份有限公司':
        names.append('大東電')
    wrapper = '## 護城河逐項證據'
    heading = '#### 6. 競爭優勢持久性總結'
    if (not isinstance(ancestors, list) or len(ancestors) not in (3, 4)
            or ancestors[-3] != wrapper or ancestors[-1] != heading
            or claim.get('financial_heading') != heading
            or (len(ancestors) == 4 and not _native_report_title(ancestors[0], facts))
            or ancestors[-2] not in [f'### {name} ({facts["ticker"]}) 競爭護城河評估報告' for name in names]
            or clean(claim.get('financial_parent_context'))):
        return False
    raw = str(claim.get('raw_text') or '')
    if not re.match(r'^\* \*\*現金流觀察：\*\*', raw):
        return False
    number = r'[+-]?\d+(?:\.\d+)?'
    pattern = (r'現金流觀察：(?P<issuer>' + '|'.join(map(re.escape, names))
        + r')官方個別TTM（' + re.escape(facts['period_start']) + r'至'
        + re.escape(facts['period_end']) + r'）淨利為(?P<income>' + number
        + r')億元新臺幣；同期間營業現金流為(?P<ocf>' + number
        + r')億元新臺幣，CapEx（PPE及無形資產取得支出）合計(?P<capex>' + number
        + r')億元新臺幣，自由現金流為(?P<fcf>' + number
        + r')億元新臺幣（來源：data.cash_flow.official_reference、'
        + r'data.cash_flow.official_income_facts及其source_documents）。')
    match = re.fullmatch(pattern, clean(raw))
    if not match:
        return False
    prefix = clean(raw).split('淨利為', 1)[0]
    if (clean(claim.get('financial_period_text')) != prefix
            or clean(claim.get('financial_amount_suffix')) != '新臺幣'
            or clean(claim.get('financial_owner_text')) != prefix + '為新臺幣'):
        return False
    try:
        if Decimal(match['income']) != Decimal(str(claim['reported_value'])):
            return False
        selected = read_official_financial_projection(data)
        if selected is None:
            return False
        source = selected['facts']
        if any(source.get(key) != facts.get(key) for key in ('period_start', 'period_end', 'currency', 'report_scope', 'ticker')):
            return False
        cf = source['cashflows']['ttm']
        return all(_ttm_display_matches(match[key], value) for key, value in (
            ('ocf', cf['operating_cash_flow']),
            ('capex', -(cf['ppe_purchase'] + cf['intangible_purchase'])),
            ('fcf', cf['free_cash_flow'])))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return False


def _bound_scope(claim, facts, data=None):
    if _native_moat_income_scope(claim, facts, data):
        return True
    from financial_money_claims import _target_revenue_scope
    prefix = str(claim.get('financial_period_text') or '')
    suffix = str(claim.get('financial_amount_suffix') or '')
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    owner = str(claim.get('financial_owner_text') or '')
    if _INCOMPATIBLE.search(prefix + suffix + heading + parent + owner):
        return False
    trailing_currency = re.match(r'^\s*(?:TWD|NTD|新[臺台]幣)(?![A-Za-z])', suffix, re.I)
    if (not re.search(r'個別', prefix)
            or not (_CURRENCY.search(prefix + str(claim.get('unit') or '')) or trailing_currency)
            or _DATE.findall(prefix) != [facts['period_start'], facts['period_end']]):
        return False
    identity = _identity(facts)
    finding = re.match(r'^\s*-\s*發現\s*[:：]\s*', prefix)
    if finding is not None:
        # Only the exact native dated-evidence memo wrapper may be removed.
        # Its ancestor scopes remain binding; a peer/year/FX heading cannot
        # be hidden by a nested neutral evidence heading.
        ancestors = claim.get('_financial_heading_ancestors')
        if (heading != '## 證據時點與來源'
                or not re.match(r'^\s*-\s+\*\*發現\*\*[:：]', str(claim.get('raw_text') or ''))
                or not isinstance(ancestors, list) or not ancestors
                or ancestors[-1] != heading
                or any(not isinstance(value, str) or _INCOMPATIBLE.search(value)
                       or (value != heading and not _native_report_title(value, facts) and not _context_matches(value, identity))
                       for value in ancestors)):
            return False
        prefix = prefix[finding.end():]
        heading = ''
    if (re.fullmatch(r'\s*#{1,6}\s*現金流與獲利品質分析\s*', heading)
            or re.fullmatch(r'\s*##\s*Round\s*(?:1\s*[:：]\s*基本面與護城河|2\s*[:：]\s*財務與估值|3\s*[:：]\s*近期催化劑)\s*', heading)):
        # The native neutral subsection is structural, not an issuer/period.
        # Retain every ancestor scope so a peer, FX or fiscal heading cannot
        # be hidden by nesting this neutral heading.
        ancestors = claim.get('_financial_heading_ancestors')
        if (not isinstance(ancestors, list) or not ancestors or ancestors[-1] != heading
                or any(not isinstance(value, str) or _INCOMPATIBLE.search(value)
                       or (not re.fullmatch(r'\s*##\s*六、\s*成長潛力總評\s*', value)
                           and not _native_report_title(value, facts) and not _context_matches(value, identity))
                       for value in ancestors)):
            return False
    if (heading == '## 一頁式摘要' or re.fullmatch(r'\s*#{1,6}\s*(?:(?:[一二三四五六七八九十]+)[、.]\s*)?(?:獲利趨勢深析|自由現金流分析|已觀測財務與歷史反證|企業體質總結|成長潛力總評)\s*',heading)):
        # Only the native wrapper is neutral. Every inherited title must still
        # bind to names replayed from both official originals, never caller aliases.
        ancestors = claim.get('_financial_heading_ancestors')
        if (not isinstance(ancestors, list) or not ancestors or ancestors[-1] != heading
                or any(not isinstance(value, str) or _INCOMPATIBLE.search(value)
                       or (value != heading and not _native_report_title(value, facts)
                           and not _native_report_title(value, facts) and not _context_matches(value, identity)) for value in ancestors)):
            return False
    elif not _context_matches(heading, identity):
        return False
    if not _context_matches(parent, identity):
        return False
    # No other year/period or arbitrary owner/prose is discarded. Both dates
    # must be present in this very claim, not inherited from another amount.
    remaining = _DATE.sub('', prefix)
    remaining = re.sub(r'TTM|近十二個月|近12個月|官方|個別|財務報表|財報|報表|'
                       r'幣別|期間|涵蓋|起訖|截至|至|TWD|NTD|新[臺台]幣', '', remaining, flags=re.I)
    if re.search(r'20\d{2}|年度|全年|單季|季度|[上下]半年|YTD|LTM', remaining, re.I):
        return False
    if not _target_revenue_scope(identity, remaining, '', require_explicit=True):
        return False
    if trailing_currency:
        suffix = suffix[trailing_currency.end():]
    # Only this bounded public derived-source citation is admitted. A source
    # path itself supplies no evidence and cannot qualify a different owner.
    source_year = str(facts['period_start'])[:4]
    current_year = str(facts['period_end'])[:4]
    quarter = str((int(str(facts['period_end'])[5:7]) + 2) // 3)
    chain = (r'(?:完整雙原件鏈|完整\s*FY' + re.escape(source_year)
             + r'\s*[＋+]\s*' + re.escape(current_year) + r'Q' + quarter
             + r'\s*官方個別雙原件鏈|(?:的|之)\s*FY' + re.escape(source_year)
             + r'\s*全年與\s*' + re.escape(current_year) + r'Q' + quarter
             + r'\s*官方個別雙原件鏈|(?:的|之)\s*完整\s*FY' + re.escape(source_year)
             + r'\s*與\s*' + re.escape(current_year) + r'Q' + quarter
             + r'\s*(?:官方個別)?雙原件鏈)')
    suffix = re.sub(r'[（(]\s*來源\s*[:：]\s*(?:data\.)?cash_flow\.'
                    r'official_income_facts(?:\.source_documents(?:\[(?:\*)?\](?:\.url)?)?)?'
                    r'\s*(?:[，,]\s*)?(?:' + chain + r')?\s*[）)]', '', suffix)
    return not re.sub(r'[\s，,。;；()（）]', '', suffix)


def official_income_claim(claim, data, *, scale, tolerance_pct):
    """Return a dated official-income check, or no applicable qualified source.

    Scope failures remain unknown in the caller. They must never borrow the
    official amount merely because the numeric value happens to be nearby.
    """
    if claim.get('financial_metric') not in {'淨利', '稅後淨利'}:
        return None
    if (claim.get('financial_actual') is False or claim.get('foreign_currency_declared')
            or claim.get('financial_scope_unbound')):
        return None
    from official_income_prompt import official_income_prompt_facts
    facts = official_income_prompt_facts(data)
    if (facts is None or facts.get('currency') != 'TWD' or facts.get('report_scope') != 'individual'
            or facts.get('monetary_amount_unit') != 'TWD' or not _bound_scope(claim, facts, data)):
        return None
    try:
        raw = facts['net_income_ttm_raw']
        precision = claim.get('financial_display_precision', len(str(claim['reported_value']).partition('.')[2]))
        if (type(raw) is not int or type(precision) is not int or not 0 <= precision <= 20
                or type(claim['reported_value']) not in (int, float)):
            return None
        reported = Decimal(str(claim['reported_value']))
        divisor = Decimal(str(scale)); tolerance = Decimal(str(tolerance_pct))
        if not all(value.is_finite() for value in (reported, divisor, tolerance)) or divisor <= 0 or tolerance < 0:
            return None
        expected = Decimal(raw) / divisor
        rounded = expected.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        difference = abs(reported - expected) / max(abs(expected), Decimal('1e-12')) * 100
        matches = reported * expected >= 0 and (reported == rounded or difference <= tolerance)
    except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
        return None
    return {
        'status': 'verified' if matches else 'mismatch',
        'verification_reason_code': 'official_income_fact_matched' if matches else 'official_income_fact_mismatch',
        'verification_scope': 'replayed_official_income_fact', 'candidate_count': 1,
        'matched_path': 'official_income_prompt_facts(data).net_income_ttm_raw',
        'matched_value': float(expected), 'diff_pct': round(float(difference), 4),
        'financial_source_path': 'data.official_financial_projection.reference',
        'financial_period_verified': True,
        'financial_period': facts['period_start'] + '/' + facts['period_end'],
        'financial_report_scope': 'individual', 'financial_currency': 'TWD',
        'financial_definition': '個別本期損益（prior_annual + current_ytd - prior_ytd）',
        'financial_period_formula': facts['net_income_ttm_formula'],
        'source_value': raw, 'source_unit': 'TWD',
        'expected_value_raw_twd': raw, 'reported_value_raw_twd': float(reported * divisor),
        'independent_primary_source_verified': True,
        'financial_source_documents': facts['source_documents'],
        'capture_boundary': facts['capture_boundary'], 'freshness_status': facts['freshness_status'],
        'historical_pit_verified': False, 'native_acquisition': False,
        'ttm_eps_verified': False, 'share_count_bridge_verified': False,
        'five_year_history_verified': False,
    }
