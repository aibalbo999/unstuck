"""A matching arithmetic window is not exchange-session or source proof."""
from copy import deepcopy
from datetime import date, timedelta

from short_term_technical_indicators import calculate_technical_indicators
from technical_reasoning import sma_reasoning_checks
from reporting.content_credibility_observations import evaluate_observation_credibility
import pytest


def market_data(*, polluted=False):
    start = date(2026, 8, 3)
    bars = []
    for offset in range(40):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        close = 40.0 + len(bars)
        bars.append(dict(date=day.isoformat(), open=close, high=close, low=close,
                         close=close, volume=1000.0))
    if polluted:
        bars.append(dict(date='2026-10-23', open=90., high=90., low=90., close=90., volume=0.))
    daily = dict(ticker='2356.TW', bars=bars, as_of=bars[-1]['date'], source='saved-provider',
                 price_adjustment_basis='same_adjusted_basis')
    return dict(ticker='2356.TW', current_price=bars[-1]['close'], daily_market_data=daily,
                technical_indicators=calculate_technical_indicators(daily))


def test_closed_day_cannot_be_verified_by_same_window_and_hash():
    data = market_data(polluted=True)
    before = deepcopy(data)
    check = sma_reasoning_checks('收盤價高於5日線。', data)[0]
    assert check['status'] == 'unverifiable'
    assert check['arithmetic_status'] == 'verified'
    assert check['verification_scope'] == 'saved_window_arithmetic'
    assert check['session_integrity']['eligible'] is False
    assert data == before


def test_bad_session_never_hides_a_saved_window_arithmetic_contradiction():
    check = sma_reasoning_checks('收盤價低於5日線。', market_data(polluted=True))[0]
    assert check['status'] == check['arithmetic_status'] == 'mismatch'
    assert check['session_integrity']['eligible'] is False
    assert check['reason'] == 'same_window_sma_relation'


def test_unknown_quarantined_observation_is_not_hidden_by_clean_remaining_rows():
    data = market_data()
    data['daily_market_data']['quarantined_session_rows'] = [
        {'date':'2026-08-05', 'state':'unknown'}]
    check = sma_reasoning_checks('收盤價高於5日線。', data)[0]
    assert check['status'] == 'unverifiable'
    assert check['arithmetic_status'] == 'verified'


def test_valid_calculation_does_not_claim_independent_prices_or_pit():
    check = sma_reasoning_checks('收盤價高於5日線。', market_data())[0]
    assert check['status'] == 'verified'
    assert check['verification_scope'] == 'saved_window_arithmetic'
    assert check['session_integrity']['eligible'] is True
    assert check['independent_primary_source_verified'] is False
    assert check['historical_point_in_time_verified'] is False


def test_missing_market_identity_cannot_borrow_tw_calendar():
    data = market_data()
    data.pop('ticker'); data['daily_market_data'].pop('ticker')
    assert sma_reasoning_checks('收盤價高於5日線。', data)[0]['status'] == 'unverifiable'


def test_quality_blocks_invalid_full_history_even_if_last_price_matches():
    data = market_data(polluted=True)
    result = evaluate_observation_credibility({}, {'generated_at':'2026-10-23T18:00:00+08:00'}, data, 'v4')
    assert 'v4_market_session_integrity_invalid' in {x['id'] for x in result['blocking_issues']}
    assert result['session_integrity']['rejected_dates'] == ['2026-10-23']


def test_annual_series_cannot_assign_raw_fcf_period():
    data = market_data()
    data.update(financial_currency='TWD', free_cash_flow_raw=4_079_718_000,
                years=['2025'], fcf_history=[4.079718],
                financial_history_basis={'statement_schema':'financial_holding_audited_annual.v1'})
    result = evaluate_observation_credibility({}, {}, data, 'v4')
    warning = next(x for x in result['warnings'] if x['id'] == 'v4_raw_fcf_period_unverified')
    assert warning['details']['selected_field']['period_status'] == 'unverified'
    assert warning['details']['annual_series']['raw_scalar_period_verified'] is False
    assert warning['details']['annual_series']['source_path'] == 'data.fcf_history'


def test_verified_selected_official_fcf_keeps_preserved_quote_unverified():
    from test_official_financial_projection import projected
    data = projected()
    before = deepcopy(data)
    result = evaluate_observation_credibility({}, {}, data, 'v4')
    scope = result['fcf_scope']
    assert scope['selected_field']['period_status'] == 'verified'
    assert scope['selected_field']['source_replay_status'] == 'official_originals_and_selection_replayed'
    assert scope['selected_field']['period_start'] == '2025-07-01'
    assert scope['selected_field']['period_end'] == '2026-06-30'
    assert scope['selected_field']['unit'] == 'TWD'
    assert scope['preserved_quote']['period_status'] == 'unverified'
    assert scope['preserved_quote']['value'] == -461411616
    assert 'v4_preserved_quote_fcf_period_unverified' in {x['id'] for x in result['warnings']}
    assert data == before


@pytest.mark.parametrize('damage', ['source', 'selected_value', 'scope', 'annual_substitution'])
def test_fcf_scope_never_qualifies_from_flags_hash_or_annual_numbers(damage):
    from test_official_financial_projection import projected
    data = projected()
    if damage == 'source':
        data['official_financial_projection']['reference']['quarterly_document']['raw_receipt']['raw_response_path'] = '/missing-original.gz'
    elif damage == 'selected_value':
        data['free_cash_flow_raw'] += 1
    elif damage == 'scope':
        data['official_financial_projection']['facts']['report_scope'] = 'consolidated'
    else:
        data.pop('official_financial_projection')
        data['years'] = ['2025']; data['fcf_history'] = [data['free_cash_flow_raw'] / 1e9]
    result = evaluate_observation_credibility({}, {}, data, 'v4')
    assert result['fcf_scope']['selected_field']['period_status'] == 'unverified'
    assert 'v4_raw_fcf_period_unverified' in {x['id'] for x in result['warnings']}
