"""Field-specific applicability with full original replay at each consumer."""
from datetime import datetime
from zoneinfo import ZoneInfo

from .peer_reference_income import APPLICABILITY, TICKER
from .peer_reference_evidence import verified_reference_income
from .peer_reference_transport import spec


def verified_explanation(value, ticker, *, today=None):
    if ticker == '2646.TW':
        from .starair_reference_applicability import verified_explanation as individual_explanation
        return individual_explanation(value, ticker, today=today)
    if ticker != TICKER or not isinstance(value, dict):
        return False
    try:
        derived = verified_reference_income(value.get('source_record_archive'), ticker=ticker,
            observed_at=value.get('observed_at'), today=today)
        if derived is None:
            return False
        from datetime import date
        proof = value['source_record_archive']
        expected = {'reason': APPLICABILITY, 'observed_at': proof['observed_at'],
            'reference_quarter': proof['reference']['reference_quarter'],
            'period_start': derived['period_start'], 'period_end': derived['period_end'],
            'scope': 'consolidated_parent_income', 'currency': 'TWD',
            'source_url': spec('reference', day=date.fromisoformat(proof['observed_at']))['url'],
            'reason_basis': 'derived_from_official_rule_and_period_bound_income; not_a_published_per_row_cause',
            'source_record_archive': proof}
        return value == expected
    except (ValueError, TypeError, KeyError, OverflowError):
        return False


def verified_undefined_pe(row, *, today=None):
    return (isinstance(row, dict) and row.get('pe_ttm') is None
            and verified_explanation(row.get('pe_applicability_evidence'), row.get('ticker'), today=today))


def reassess_reference_applicability(row, *, today=None):
    """No other field, comparison rule, or historical observation is relaxed."""
    from .peers import PEER_METRIC_FIELDS
    today = today or datetime.now(ZoneInfo('Asia/Taipei')).date()
    applicability = row.setdefault('metric_applicability', {})
    applicability['pe_ttm'] = APPLICABILITY if verified_undefined_pe(row, today=today) else 'applicable'
    def inapplicable(field):
        marker = applicability.get(field, 'applicable')
        return ((field == 'pe_ttm' and marker == APPLICABILITY)
                or (field in {'gross_margin_pct', 'asset_turnover', 'ps_ttm'}
                    and marker == 'not_applicable_financial_institution'))
    row['missing_metrics'] = [field for field in PEER_METRIC_FIELDS
                              if row.get(field) is None and not inapplicable(field)]
    row['metrics_status'] = ('complete' if not row['missing_metrics'] else 'partial'
        if any(row.get(field) is not None for field in PEER_METRIC_FIELDS) else 'unavailable')
