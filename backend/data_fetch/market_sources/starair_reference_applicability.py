"""Individual issuer field applicability; no numeric P/E is synthesized."""
from datetime import datetime
from zoneinfo import ZoneInfo
from .starair_reference_income import APPLICABILITY, TICKER
from .starair_reference_evidence import verified_reference_income
from .starair_reference_spec import spec


def verified_explanation(value, ticker, *, today=None):
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
            'scope': 'individual_issuer_income', 'currency': 'TWD',
            'source_url': spec('reference', day=date.fromisoformat(proof['observed_at']))['url'],
            'reason_basis': 'derived_from_official_rule_and_period_bound_income; not_a_published_per_row_cause',
            'source_record_archive': proof}
        return value == expected
    except (ValueError, TypeError, KeyError, OverflowError):
        return False
