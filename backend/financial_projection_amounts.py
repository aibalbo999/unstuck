"""Unit consistency of explicitly named deterministic Forward-EPS projections."""
import re

from financial_cross_checks import build_financial_cross_checks
from financial_money_claims import _AMOUNT, _FOREIGN, _SCALES, _amount_matches, _finite, signed_amount_number


def forward_cross_check_money_issues(text, data):
    """Compare named tool projections, never certify them as realized results."""
    if str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}:
        return []
    inputs = [data.get(key) for key in ('shares_raw', 'forward_eps', 'profit_margin_raw')]
    if any(isinstance(value, bool) for value in inputs):
        return []
    values = build_financial_cross_checks(data)
    issues = []
    for raw in str(text or '').splitlines():
        line = re.sub(r'[*`\s]', '', raw).replace('−', '-')
        if ('cross_checks' not in line or not re.search(r'ForwardEPS', line, re.I)
                or re.search(r'同業|同儕|其他公司|錯誤示例|誤寫|不採用', line) or _FOREIGN.search(line)):
            continue
        for match in _AMOUNT.finditer(line):
            if not re.search(r'隱含$', line[max(0, match.start()-15):match.start()]):
                continue
            metric = match['metric']
            field = {'淨利': 'forward_eps_implied_net_income_billion_twd',
                     '營收': 'forward_eps_implied_revenue_billion_twd'}.get(metric)
            expected = _finite(values.get(field)) if field else None
            if expected is None:
                continue
            unit = match['unit'].lower()
            scale = _SCALES.get(unit.removesuffix('元'), _SCALES.get(unit))
            if scale and not _amount_matches(signed_amount_number(match), scale, expected * 1e9, False, 0):
                issues.append(f'推算金額單位紅線：cross_checks.{field} 為 {expected:g} billion_twd，'
                              f'即 {expected * 10:g}億元，不是原文「{match.group()}」；'
                              '只核對同一 Forward EPS 推算的金額單位，不代表已實現營收或淨利。')
    return issues
