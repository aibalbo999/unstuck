"""Typed checks for explicit EPS/price/P-E calculations in narrative text.

These receipts verify arithmetic and fiscal basis, not the valuation conclusion.
No replacement value is written into historical/model prose.
"""
import re
import math

_NUMBER = r'(?<![\d.,])([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?!\d|[.,]\d)'
_CALC = re.compile(r'(?:EPS|每股盈餘)[^\d\n+\-]{0,16}' + _NUMBER +
    r'(?:(?!EPS|每股盈餘)[^\n]){0,70}?(?:股價|現價)[^\d\n+\-]{0,12}' + _NUMBER +
    r'[^\n]{0,60}?(?P<ttm>TTM\s*)?(?:P/E|本益比)[^\d\n+\-]{0,16}' + _NUMBER, re.I)

def derived_pe_claims(markdown, snapshot):
    data = snapshot.get('data') or {}
    result = []
    for line_number, line in enumerate(str(markdown).splitlines(), 1):
        if line.lstrip().startswith(('#', '|', '```')):
            continue
        for match in _CALC.finditer(line):
            # Only a stated relation, not a list of independent observations.
            if not re.search(r'計算|對應|除以|÷|/\s*EPS', match.group(), re.I):
                continue
            eps, price, pe = (float(match.group(index).replace(',', '')) for index in (1, 2, 4))
            expected = price / eps if eps != 0 else None
            annual = re.search(r'(20\d{2})\s*年\s*$', line[:match.start()], re.I)
            reasons = []
            if expected is None or not math.isfinite(expected):
                reasons.append('undefined_pe_division')
            elif abs(pe - expected) > max(abs(expected) * .01, .01):
                reasons.append('pe_arithmetic_mismatch')
            if match.group('ttm') and annual:
                reasons.append('annual_eps_used_for_ttm_pe')
            basis = 'annual:' + annual.group(1) if annual else 'ttm' if match.group('ttm') else 'unspecified'
            eps_path = 'data.trailing_eps' if basis == 'ttm' else ''
            source_eps = data.get('trailing_eps') if eps_path else None
            if basis == 'ttm' and isinstance(source_eps, (int, float)) and not isinstance(source_eps, bool):
                if abs(eps - source_eps) > max(abs(source_eps) * .01, .01):
                    reasons.append('ttm_eps_snapshot_mismatch')
            source_currency = str(data.get('currency') or '').upper()
            eps_currency = str(data.get('financial_currency') or '').upper()
            declared_eps = match.group()[match.start(1) - match.start():match.end(1) - match.start() + 12]
            declared_price = match.group()[max(0, match.start(2) - match.start() - 8):match.end(2) - match.start() + 8]
            def declared_currency(text):
                return 'USD' if re.search(r'美元|USD|US\$', text, re.I) else 'TWD' if re.search(r'新台幣|TWD|NT\$', text, re.I) else ''
            if declared_currency(declared_eps) and eps_currency and declared_currency(declared_eps) != eps_currency:
                reasons.append('declared_eps_currency_mismatch')
            if declared_currency(declared_price) and source_currency and declared_currency(declared_price) != source_currency:
                reasons.append('declared_price_currency_mismatch')
            units_bound = bool(source_currency and eps_currency and source_currency == eps_currency)
            if source_currency and eps_currency and source_currency != eps_currency:
                reasons.append('price_eps_currency_mismatch')
            status = 'mismatch' if reasons else 'verified' if basis != 'unspecified' and units_bound else 'unverifiable'
            result.append({'label': 'P/E 衍生算式與盈餘期間', 'reported_value': pe,
                'claim_type': 'derived_calculation', 'unit': 'x', 'line_number': line_number,
                'raw_text': line, 'status': status,
                'verification_reason_code': reasons[0] if reasons else 'derived_arithmetic_consistent' if basis != 'unspecified' and units_bound else 'derived_units_or_period_unbound',
                'verification_scope': 'arithmetic_and_period_consistency', 'basis': basis,
                'arithmetic_inputs': {'price_per_share': price, 'eps_per_share': eps},
                'units_bound': units_bound, 'price_currency': source_currency, 'eps_currency': eps_currency,
                'calculated_value': expected, 'issues': reasons,
                'source_eps_path': eps_path, 'source_eps': source_eps,
                'candidate_count': 0})
    return result
