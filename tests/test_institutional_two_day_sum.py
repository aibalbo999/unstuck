"""Explicit two-day aggregate uses both dated records, never a lookback proxy."""
import copy
import pytest
from institutional_evidence import institutional_evidence_issues, institutional_evidence_diagnostics


def source():
    return {'ticker': '0050.TW', 'institutional_trading': {
        'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date': '2026-09-22', 'lookback_trading_days': 30,
        'total_net_buy_thousand_shares': 42828.72,
        'daily_total_net_buy_last_10': [
            {'date': '2026-09-17', 'net_buy_thousand_shares': 16136.98},
            {'date': '2026-09-18', 'net_buy_thousand_shares': 11271.71},
        ],
    }}


@pytest.mark.parametrize('number', ['27408.69', '27408'])
def test_two_explicit_days_sum_both_records_with_existing_tolerance(number):
    assert institutional_evidence_issues(f'9/17與9/18法人合計買超約{number}千股。', source()) == []


@pytest.mark.parametrize('text', [
    '9/17與9/18法人合計買超11271.71千股。',  # Last day alone must not pass.
    '9/17與9/18外資合計買超27408.69千股。',
    '9/17與9/18法人合計賣超27408.69千股。',
    '9/17與9/19法人合計買超27408.69千股。',
    '9/17與9/18法人合計買超27408.69千張。',
    '9/17與9/18法人合計買超42828.72千股。',
    '9/16與9/17與9/18法人合計買超27408.69千股。',
    '9/17與9/18法人合計買超27000千股。',
])
def test_wrong_scope_direction_unit_or_total_stays_blocked(text):
    assert institutional_evidence_issues(text, source())


@pytest.mark.parametrize('mutation', ['missing_first', 'duplicate_conflict', 'nonconsecutive'])
def test_aggregate_needs_two_unique_complete_consecutive_dates(mutation):
    data = source();daily = data['institutional_trading']['daily_total_net_buy_last_10']
    text = '9/17與9/18法人合計買超27408.69千股。'
    if mutation == 'missing_first':daily.pop(0)
    if mutation == 'duplicate_conflict':daily.append({'date': '2026-09-17', 'net_buy_thousand_shares': 5})
    if mutation == 'nonconsecutive':daily[0]['date'] = '2026-09-16';text = text.replace('9/17', '9/16')
    assert institutional_evidence_issues(text, data)


def test_both_contributing_records_must_be_visible():
    assert institutional_evidence_issues('9/17與9/18法人合計買超27408.69千股。', source(), allowed_paths=[
        'institutional_trading.daily_total_net_buy_last_10[1].net_buy_thousand_shares'])


def test_wrong_sum_diagnostic_retains_two_day_scope_instead_of_last_day():
    diag = institutional_evidence_diagnostics('9/17與9/18法人合計買超1千股。', source())
    assert diag[0]['window'] == {'kind': 'two_explicit_days', 'dates': ['2026-09-17', '2026-09-18']}
