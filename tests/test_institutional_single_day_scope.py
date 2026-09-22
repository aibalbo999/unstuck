"""Explicit one-day scope must preserve date, population and numeric boundaries."""
import pytest
from institutional_evidence import institutional_evidence_issues


def source():
    return {'ticker': '2450.TW', 'institutional_trading': {
        'source': 'FinMind TaiwanStockInstitutionalInvestorsBuySell',
        'latest_date': '2026-09-08', 'lookback_trading_days': 1,
        'net_buy_shares_by_category': {'dealer': -89, 'foreign': 0, 'investment_trust': 0},
        'net_buy_thousand_shares_by_category': {'dealer': -0.09, 'foreign': 0, 'investment_trust': 0},
        'total_net_buy_shares': -89,
        'daily_total_net_buy_last_10': [{'date': '2026-09-08', 'net_buy_thousand_shares': -0.09}],
    }}


@pytest.mark.parametrize('text', [
    '法人近一交易日（2026-09-08）合計賣超0.09千股（89股），其中自營商賣超0.09千股。',
    '截至2026-09-08，東訊單日法人合計買賣超為-0.09千股。',
    '截至2026-09-08，自營商單日賣超0.09千股。',
])
def test_retained_correct_single_day_claims_are_supported(text):
    assert institutional_evidence_issues(text, source()) == []


@pytest.mark.parametrize('text', [
    '2026-09-09自營商賣超0.09千股。',
    '近5個交易日自營商賣超0.09千股。',
    '2026-09-08外資賣超0.09千股。',
    '2026-09-08自營商買超0.09千股。',
    '2026-09-08自營商賣超0.09千張。',
    '截至2026-09-08自營商累計賣超0.09千股。',
    '2026-09-07至2026-09-08自營商合計賣超0.09千股。',
])
def test_single_day_fix_does_not_borrow_other_scope_or_value(text):
    assert institutional_evidence_issues(text, source())


def test_single_day_claim_cannot_borrow_multi_day_aggregate():
    data = source()
    data['institutional_trading']['lookback_trading_days'] = 30
    assert institutional_evidence_issues('2026-09-08自營商賣超0.09千股。', data)


def test_visible_catalog_filter_still_applies_to_single_day_equivalence():
    assert institutional_evidence_issues('2026-09-08自營商賣超0.09千股。', source(), allowed_paths=[])
