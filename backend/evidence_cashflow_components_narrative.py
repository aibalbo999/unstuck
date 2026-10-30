"""Bind a complete, explicitly dated cash-flow sentence to replayed originals.

This recognizer consumes the whole sentence and checks every component. It
never borrows an undated vendor value, an adjacent period, or a parent issuer.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

_NUMBER = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'


def complete_cashflow_components(claim, data, projection, *, scale):
    from financial_money_claims import _target_revenue_scope
    if scale != 100000000 or claim.get('unit') not in {'億元', '億'}:
        return False
    raw = str(claim.get('raw_text') or '')
    if not 1 <= len(raw) <= 2000 or claim.get('scenario_projection'):
        return False
    heading = str(claim.get('financial_heading') or '')
    parent = re.sub(r'[*`\s]', '', str(claim.get('financial_parent_context') or ''))
    # This parent is a section label, not a hidden issuer/period declaration.
    if parent not in {'', '-現金流表現與流動性限制：', '現金流表現與流動性限制：'}:
        return False
    from evidence_financial_amounts import _native_mode_a_structural_headings
    native_headings = _native_mode_a_structural_headings(data)
    def structural(value):
        return value in native_headings or re.fullmatch(
            r'#{1,6}\s*(?:[一二三四五六七八九十]{1,3}、)?主要風險因子', value) is not None
    ancestors = claim.get('_financial_heading_ancestors')
    if (type(ancestors) is not list or len(ancestors) > 6
            or any(type(value) is not str or not structural(value) for value in ancestors)
            or (heading and (not ancestors or ancestors[-1] != heading))
            or (not heading and ancestors)):
        return False
    forbidden = r'合併|集團|同業|同儕|未來|預估|預測|假設|情境|美元|美金|USD|CNY|人民幣|港元|HKD|JPY|日圓|EUR|歐元'
    if re.search(forbidden, ''.join(str(claim.get(k) or '') for k in (
            'financial_period_text', 'financial_owner_text', 'financial_amount_suffix')), re.I):
        return False
    text = re.sub(r'[*`\s]', '', raw)
    pattern = (r'-?官方個別TTM現金流為(?P<direction>淨流入|淨流出)：依據官方個別財務報表'
               r'（期間為(?P<start>20\d{2}-\d{2}-\d{2})至(?P<end>20\d{2}-\d{2}-\d{2})，'
               r'來源：(?:data\.)?cash_flow\.official_reference），(?P<owner>[^，。：；（）]{2,80})'
               r'營業現金流為(?P<ocf>'+_NUMBER+r')億元新臺幣，'
               r'購置不動產廠房設備與無形資產支出分別為(?P<ppe>'+_NUMBER+r')億元及'
               r'(?P<intangible>'+_NUMBER+r')億元，計算之個別TTM自由現金流為'
               r'(?P<fcf>'+_NUMBER+r')億元新臺幣（(?P<billion>'+_NUMBER+r')billion_twd）。')
    match = re.fullmatch(pattern, text)
    if not match or not _target_revenue_scope(data, match['owner'], ''):
        return False
    fact = projection['facts']
    if (match['start'], match['end']) != (fact['period_start'], fact['period_end']):
        return False
    cash = fact['cashflows']['ttm']
    def exact_display(literal, expected, divisor):
        if len(literal) > 64:
            return False
        normalized = literal.replace(',', '')
        precision = len(normalized.partition('.')[2])
        if precision > 20:
            return False
        return Decimal(normalized) == (Decimal(str(expected))/Decimal(divisor)).quantize(
            Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    try:
        for name, key in [('ocf','operating_cash_flow'), ('ppe','ppe_purchase'),
                          ('intangible','intangible_purchase'), ('fcf','free_cash_flow')]:
            if not exact_display(match[name], cash[key], 100000000):
                return False
        if (Decimal(str(cash['operating_cash_flow'])) + Decimal(str(cash['ppe_purchase']))
                + Decimal(str(cash['intangible_purchase'])) != Decimal(str(cash['free_cash_flow']))):
            return False
        if Decimal(match['fcf'].replace(',','')) != Decimal(str(claim['reported_value'])):
            return False
        if not exact_display(match['billion'], cash['free_cash_flow'], 1000000000):
            return False
        if (cash['free_cash_flow'] < 0) != (match['direction'] == '淨流出') or cash['free_cash_flow'] == 0:
            return False
    except (InvalidOperation, ValueError, TypeError, KeyError):
        return False
    return True
