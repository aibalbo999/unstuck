"""Verify an explicitly named product amount against a qualified archived cell."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
import re

from financial_money_claims import _FOREIGN, _SCALES, _target_revenue_scope, _annual_owner_scope

_PRODUCT = r'(?:特高壓電纜(?:\s*[（(]\s*Extra-high\s+Voltage\s+Cables\s*[）)])?|Extra-high\s+Voltage\s+Cables)'
_PREFIX = re.compile(r'(?P<owner>.*?)\s*(?P<year>20\d{2})\s*年(?:度)?\s*'
                     r'(?P<quarter>Q[1-4])?\s*' + _PRODUCT + r'\s*$', re.I)
_SCOPE = re.compile(r'合併|集團|個別|財報|審計|查核|consolidated|audited|standalone', re.I)
_SUFFIX = re.compile(r'\s*(?:[，,]\s*(?:營收)?(?:佔比|占比)(?:為)?\s*[+-]?\d+(?:\.\d+)?\s*%)?\s*$')


def official_segment_amount(claim: dict, data: dict, *, tolerance_pct: float) -> dict | None:
    """No caller facts, issuer totals, inferred mix amounts or live acquisition."""
    reference = data.get('official_segment_reference')
    reference_path = 'data.official_segment_reference'
    if reference is None:
        from data_fetch.market_sources.tewc_segment_reference import SCHEMA
        earnings_call = data.get('earnings_call')
        receipt = earnings_call.get('tewc_conference_receipt') if isinstance(earnings_call, dict) else None
        if isinstance(receipt, dict):
            reference = {'schema': SCHEMA, 'ticker': data.get('ticker'), 'conference_receipt': receipt}
            reference_path = 'data.earnings_call.tewc_conference_receipt'
    if not isinstance(reference, dict) or str(data.get('financial_currency') or '').upper() not in {'TWD', 'NTD'}:
        return None
    prefix = str(claim.get('financial_period_text') or '')
    heading = str(claim.get('financial_heading') or '')
    parent = str(claim.get('financial_parent_context') or '')
    suffix = str(claim.get('financial_amount_suffix') or '')
    if (not claim.get('financial_actual', True) or claim.get('foreign_currency_declared')
            or _FOREIGN.search(prefix + heading + parent + suffix)
            or _SCOPE.search(prefix + suffix + heading + parent) or not _SUFFIX.fullmatch(suffix)):
        return None
    prefix = re.sub(r'^\s*(?:[-*]\s*)?數據依據\s*[:：]\s*', '', prefix)
    prefix = re.sub(r'^\s*根據公司法說會簡報\s*[（(]\s*原頁\s*14\s*[）)]\s*[，,]\s*', '', prefix)
    match = _PREFIX.fullmatch(prefix)
    if not match or not _target_revenue_scope(data, match['owner'], heading):
        return None
    if not _annual_owner_scope(data, parent, match['owner']):
        return None
    period = match['year'] + (match['quarter'] or '').upper()
    if period not in {'2025', '2026Q1'}:
        return None
    unit = str(claim.get('unit') or '').lower()
    scale = _SCALES.get(unit.removesuffix('元'), _SCALES.get(unit))
    value = claim.get('reported_value')
    if scale is None or type(value) not in (int, float) or not math.isfinite(value):
        return None
    from data_fetch.market_sources.tewc_segment_reference import replay_segment_reference
    replay = replay_segment_reference(reference, data.get('ticker'))
    if (replay.get('status') != 'issuer_presentation_cells_verified'
            or replay.get('ticker') != data.get('ticker')
            or replay.get('report_scope') != 'issuer_presentation_product'
            or replay.get('audited') is not False):
        return None
    fact = replay['facts'][period]
    expected = fact['net_operating_revenue_twd']
    if fact['currency'] != 'TWD' or type(expected) is not int:
        return None
    reported = Decimal(str(value)) * Decimal(str(scale))
    precision = claim.get('financial_display_precision', 0)
    rounded = (Decimal(expected) / Decimal(str(scale))).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    diff = abs(reported - expected) / max(abs(expected), 1) * 100
    matched = reported * expected >= 0 and (diff <= Decimal(str(tolerance_pct)) or Decimal(str(value)) == rounded)
    doc = replay['document']
    return {'status': 'verified' if matched else 'mismatch',
        'verification_reason_code': 'matched_official_product_cell' if matched else 'official_product_amount_mismatch',
        'verification_scope': 'archived_issuer_presentation_product_cell_consistency',
        'candidate_count': 1, 'matched_path': f'{reference_path}.replayed.facts.{period}.net_operating_revenue_twd',
        'matched_value': expected / scale, 'diff_pct': round(float(diff), 4),
        'financial_period': period, 'financial_period_start': fact['period_start'], 'financial_period_end': fact['period_end'],
        'financial_currency': 'TWD', 'financial_reporting_scope': replay['report_scope'],
        'source_value': expected, 'source_unit': 'twd', 'source_audited': False,
        'reported_value_raw_twd': float(reported), 'expected_value_raw_twd': expected,
        'source_url': doc['source_url'], 'source_raw_response_sha256': doc['raw_response_sha256'],
        'source_acquired_at': datetime.fromtimestamp(doc['original_retrieved_at'], tz=timezone.utc).isoformat(),
        'source_row': fact['provenance']['source_row'], 'source_column': fact['provenance']['source_column'],
        'source_page_number': fact['provenance']['page_number'],
        'historical_point_in_time_verified': False, 'native_acquisition': False,
        'source_freshness_status': 'not_revalidated', 'independent_primary_source_verified': True}
