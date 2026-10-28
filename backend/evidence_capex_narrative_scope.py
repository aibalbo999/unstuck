"""Resolve explicit purchase components without guessing a bare CapEx meaning."""
from decimal import Decimal, ROUND_HALF_UP
import re

from financial_claim_context import CONDITIONAL, PROJECTION, THRESHOLD
from financial_money_claims import _target_revenue_scope

_NUMBER = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
_FOREIGN_OR_SCOPE = re.compile(
    r'同業|同儕|合併|集團|分部|部門|產品|美元|美金|USD|US\$|CNY|人民幣|RMB|'
    r'港元|港幣|HKD|日圓|日元|JPY|歐元|EUR|韓元|KRW|餘額|流入', re.I)
_PERIOD = r'TTM(?:期間)?(?:[（(](?P<start>20\d{2}-\d{2}-\d{2})至(?P<end>20\d{2}-\d{2}-\d{2})[）)])?'
_PREFIX_COMPONENTS = re.compile(
    r'(?P<owner>.*?)(?:官方個別(?:財報)?)?' + _PERIOD
    + r'購置不動產、廠房及設備[（(]PPE[）)]支出為(?P<ppe>' + _NUMBER + r')億元[，,]'
    r'加計無形資產購置(?P<intangible>' + _NUMBER + r')億元後[，,]總$', re.I)
_POSTFIX_PERIOD = re.compile(r'(?:在)?(?P<owner>.*?)(?:官方個別(?:財報)?)?' + _PERIOD + r'[，,]總$', re.I)
_POSTFIX_COMPONENTS = re.compile(
    r'[（(]含PPE(?P<ppe>' + _NUMBER + r')億元與無形資產(?P<intangible>' + _NUMBER + r')億元[）)]'
    r'(?:[，,]這是為了確保未來產能領先)?$', re.I)


def _rounded_component(literal: str, raw: int) -> bool:
    if type(raw) is not int or raw > 0 or len(literal) > 64:
        return False
    precision = len(literal.partition('.')[2])
    if precision > 20:
        return False
    value = Decimal(literal.replace(',', ''))
    expected = -Decimal(raw) / Decimal('100000000')
    return (value >= 0 and (value != 0 or raw == 0)
            and value == expected.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP))


def resolve_capex_narrative_scope(claim: dict, data: dict) -> dict | None:
    """Return only a proved definition/period, never validate the reported total.

    The caller must send the unchanged total, unit and direction through the
    ordinary CapEx checker. The original claim and its text remain immutable.
    Exact archived projection replay is required even for a matching narrative.
    """
    if not claim.get('financial_capex') or not claim.get('financial_actual', True):
        return None
    prefix = re.sub(r'[*`\s]', '', str(claim.get('financial_period_text') or ''))
    suffix = re.sub(r'[*`\s]', '', str(claim.get('financial_amount_suffix') or ''))
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    scoped = prefix + heading + parent + str(claim.get('unit') or '') + str(claim.get('financial_capex_link') or '')
    if (_FOREIGN_OR_SCOPE.search(scoped + suffix) or claim.get('foreign_currency_declared')
            or any(pattern.search(scoped) for pattern in (CONDITIONAL, PROJECTION, THRESHOLD))):
        return None
    if parent and not _target_revenue_scope(data, parent, heading):
        return None
    prefix = re.sub(r'^[-+]?資本支出與投資效率[:：]', '', prefix)
    match = _PREFIX_COMPONENTS.fullmatch(prefix)
    if match:
        if suffix:
            return None
        components = match
    else:
        match = _POSTFIX_PERIOD.fullmatch(prefix)
        components = _POSTFIX_COMPONENTS.fullmatch(suffix)
        if match is None or components is None:
            return None
    if not _target_revenue_scope(data, match['owner'], heading):
        return None
    from official_financial_projection import read_official_financial_projection
    projection = read_official_financial_projection(data)
    if projection is None:
        return None
    fact = projection['facts']
    if match['start'] and (match['start'], match['end']) != (fact['period_start'], fact['period_end']):
        return None
    raw = fact['cashflows']['ttm']
    evidence = {}
    for token, field in (('ppe', 'ppe_purchase'), ('intangible', 'intangible_purchase')):
        value = raw.get(field)
        if not _rounded_component(components[token], value):
            return None
        evidence[field] = {'source_signed_raw_twd': value,
            'reported_outflow_100million_twd': components[token],
            'display_precision': len(components[token].partition('.')[2]),
            'source_path': 'data.official_financial_projection.facts.cashflows.ttm.' + field,
            'rounding': 'ROUND_HALF_UP', 'amount_convention': 'cash_purchase_outflow_magnitude'}
    return {'financial_period_text': '官方個別TTM(' + fact['period_start'] + '至' + fact['period_end'] + ')',
            'financial_capex_definition': 'ppe_and_intangible_purchase',
            'period_start': fact['period_start'], 'period_end': fact['period_end'],
            'period_binding': 'explicit_dated_ttm' if match['start'] else 'selected_official_ttm_contract',
            'reporting_scope': 'individual', 'currency': 'TWD',
            'component_evidence': evidence, 'total_amount_verified': False}
