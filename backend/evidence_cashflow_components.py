"""Exact operating cash-effect claims; no substitution with total OCF or FCF."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

LABELS = {
    '存貨變動現金影響': 'inventories',
    '應收帳款變動現金影響': 'receivables',
    '營業資產淨變動現金影響': 'operating_assets',
    '營業負債淨變動現金影響': 'operating_liabilities',
    '營業資產及負債淨變動現金影響': 'operating_assets_and_liabilities',
}


def component_reference_text(facts):
    """Standalone paragraph references omit receipts and never assert business motives."""
    prefix = (f"{facts['issuer_name']}官方個別財報 TWD TTM"
              f"（{facts['period_start']} 至 {facts['period_end']}）")
    return {label: prefix + label + '為 ' + format(Decimal(facts['components'][key]['ttm_twd']) / Decimal(100000000), 'f') + ' 億元。'
            for label, key in LABELS.items() if key in facts['components']}


def check_component_claim(claim, data, scale, tolerance_pct):
    from official_cashflow_components import read_official_cashflow_components
    from evidence_official_income_claims import _bound_scope
    key = LABELS.get(claim.get('financial_metric'))
    if key is None:
        return None
    unknown = {'status': 'unverifiable', 'verification_reason_code': 'official_cashflow_component_scope_unbound',
               'candidate_count': 0, 'matched_path': '', 'matched_value': None,
               'independent_primary_source_verified': False}
    facts = read_official_cashflow_components(data)
    if (facts is None or key not in facts['components'] or not claim.get('financial_actual', True)
            or claim.get('foreign_currency_declared') or claim.get('financial_scope_unbound')
            or not _bound_scope(claim, facts, data)):
        return unknown
    try:
        raw = facts['components'][key]['ttm_twd']
        precision = claim['financial_display_precision']
        if type(raw) is not int or type(precision) is not int or not 0 <= precision <= 20:
            return unknown
        reported, divisor, tolerance = [Decimal(str(v)) for v in (claim['reported_value'], scale, tolerance_pct)]
        if not all(v.is_finite() for v in (reported, divisor, tolerance)) or divisor <= 0 or tolerance < 0:
            return unknown
        expected = Decimal(raw) / divisor
        rounded = expected.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        difference = abs(reported - expected) / max(abs(expected), Decimal('1e-12')) * 100
        matched = reported * expected >= 0 and (reported == rounded or difference <= tolerance)
    except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
        return unknown
    return {'status': 'verified' if matched else 'mismatch', 'candidate_count': 1,
            'verification_reason_code': 'official_cashflow_component_matched' if matched else 'official_cashflow_component_mismatch',
            'verification_scope': 'replayed_official_cashflow_component',
            'matched_path': 'read_official_cashflow_components(data).components.' + key + '.ttm_twd',
            'matched_value': float(expected), 'diff_pct': float(difference),
            'expected_value_raw_twd': raw, 'financial_currency': 'TWD', 'financial_report_scope': 'individual',
            'financial_period': facts['period_start'] + '/' + facts['period_end'],
            'document_sha256': facts['document_sha256'], 'independent_primary_source_verified': True,
            'native_acquisition': False, 'historical_pit_verified': False,
            'underlying_business_motive': 'unverified'}
