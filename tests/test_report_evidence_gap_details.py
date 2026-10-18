"""Recovered evidence must not relabel unknown scope or historical availability."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from report_evidence_gap_details import evidence_gap_details
from official_response_evidence import archive_response
from official_institutional_source import TWSE_FIELDS, _url


def institutional_data():
    day = '2026-10-02'
    row = ['1301', '台塑'] + ['0'] * 17
    row[4], row[10], row[11], row[14], row[18] = '1234', '-100', '20', '20', '1154'
    raw = json.dumps({'stat': 'OK', 'date': '20261002', 'fields': TWSE_FIELDS,
                      'hints': '單位：股', 'data': [row]}).encode()
    receipt = archive_response(raw, source_url=_url('TWSE', day),
                               retrieved_at=datetime.now(timezone.utc).isoformat())
    return {'ticker': '1301.TW', 'institutional_trading': {
        'latest_date': day, 'observation_dates': [day],
        'daily_category_observations': [
            {'date': day, 'category': category, 'unit': 'shares',
             'net_buy_shares': value, 'source': 'FinMind'}
            for category, value in [('foreign', 1234), ('investment_trust', -100), ('dealer', 20)]],
        'official_recovery': {'reports': [{'date': day, 'raw_evidence': receipt}]}}}


def test_all_three_institutional_categories_are_compared_but_never_claim_pit():
    data = institutional_data()
    before = deepcopy(data)
    result = evidence_gap_details(data)['institutional']
    assert result['status'] == 'matched_saved_dates'
    assert result['matched_values'] == 3
    assert result['official_totals_shares']['foreign'] == 1234
    assert result['historical_pit_verified'] is False
    assert result['prediction_verified'] is False
    assert data == before


@pytest.mark.parametrize('problem', ['missing_day', 'duplicate', 'mismatch', 'invalid_hash'])
def test_missing_conflicting_and_changed_institutional_evidence_stays_visible(problem):
    data = institutional_data()
    inst = data['institutional_trading']
    if problem == 'missing_day':
        inst['observation_dates'].append('2026-10-01')
        inst['daily_category_observations'].append({
            'date': '2026-10-01', 'category': 'foreign', 'unit': 'shares',
            'net_buy_shares': 0, 'source': 'FinMind'})
    elif problem == 'duplicate':
        inst['daily_category_observations'].append(deepcopy(inst['daily_category_observations'][0]))
    elif problem == 'mismatch':
        inst['daily_category_observations'][0]['net_buy_shares'] += 1
    else:
        inst['official_recovery']['reports'][0]['raw_evidence']['raw_response_sha256'] = '0' * 64
    result = evidence_gap_details(data)['institutional']
    assert result['status'] != 'matched_saved_dates'
    assert result['issues']
    assert result['historical_pit_verified'] is False


def test_verified_public_annual_fcf_does_not_overwrite_or_date_yahoo_scalar():
    captured_value = pytest.importorskip('test_mops_public_annual_financial').captured_value
    value = captured_value()
    fields = ('years', 'revenue_history', 'net_income_history', 'gross_profit_history',
              'operating_income_history', 'fcf_history', 'total_assets_history', 'total_equity_history')
    data = {key: deepcopy(value[key]) for key in fields}
    data.update(ticker='3443.TW', free_cash_flow_raw=-999,
                source_audit=[dict(value, source='financial_statements', status='success',
                                   provider='TWSE MOPS public annual JSON')])
    before = deepcopy(data)
    result = evidence_gap_details(data)['cash_flow']
    assert result['status'] == 'annual_originals_verified'
    assert result['period_end'] == '2025-12-31'
    assert result['free_cash_flow_twd'] == -2313966000
    assert result['raw_scalar_period_verified'] is False
    assert result['raw_scalar'] == -999
    assert data == before
    data['source_audit'][0]['raw_twd_by_year']['2025']['intangible_purchase'] = None
    assert evidence_gap_details(data)['cash_flow']['status'] != 'annual_originals_verified'


def test_cached_annual_receipts_can_be_replayed_without_calling_them_new_acquisition():
    captured_value = pytest.importorskip('test_mops_public_annual_financial').captured_value
    value = captured_value()
    data = deepcopy(value)
    data['source_audit'] = [dict(value, source='financial_statements', status='skipped_fresh_cache',
                                provider='TWSE MOPS public annual JSON')]
    before = deepcopy(data)
    assert evidence_gap_details(data)['cash_flow']['status'] == 'annual_originals_verified'
    assert data == before


def test_individual_originals_keep_their_own_scope_instead_of_becoming_consolidated():
    fetch = pytest.importorskip('test_ordinary_individual_annual').fetch
    from data_fetch.annual_financial_source_provider import project_source_value
    result, _ = fetch()
    data = project_source_value(result['value'], '2646.TW')
    data.update(ticker='2646.TW', source_audit=[])
    detail = evidence_gap_details(data)['cash_flow']
    assert detail['status'] == 'annual_originals_verified'
    assert detail['scope'] == 'individual'


def test_audited_pdf_bridge_keeps_its_native_receipts_and_recomputed_fcf():
    Http = pytest.importorskip('test_cal_annual_bridge').Http
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_histories, PROVIDER
    value = fetch_bridge_histories('2610.TW', transport=Http())
    data = deepcopy(value)
    data['source_audit'] = [dict(value, source='financial_statements', status='success', provider=PROVIDER)]
    detail = evidence_gap_details(data)['cash_flow']
    assert detail['status'] == 'annual_originals_verified'
    assert detail['free_cash_flow_twd'] == value['raw_twd_by_year']['2025']['free_cash_flow']


def test_volume_difference_remains_unresolved_even_with_a_verified_official_note():
    from report_evidence_fixtures import daily, official_payload
    data = daily()
    official = data['official_observation']
    payload = official_payload()
    payload['tables'][0]['data'][0][-1] = '1,000'
    raw = json.dumps(payload).encode()
    proof = archive_response(raw,
        source_url='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20261002&type=ALL&response=json',
        retrieved_at=datetime.now(timezone.utc).isoformat())
    official['raw_evidence'] = proof
    data['provider_raw_observation']['volume'] += 100
    result = evidence_gap_details({'ticker': '1301.TW', 'daily_market_data': data})['volume']
    assert result['status'] == 'different'
    assert result['delta_shares'] == 100
    assert result['cross_provider_comparable'] is False
    assert result['same_provider_ratio_policy']


def test_tpex_original_uses_tpex_schema_and_exact_categories_not_twse_population():
    from official_institutional_source import TPEX_FIELDS
    data = institutional_data()
    data['ticker'] = '1301.TWO'
    row = ['1301', '測試'] + ['0'] * 22
    row[4], row[10], row[13], row[16], row[22], row[23] = '1234', '1234', '-100', '20', '20', '1154'
    proof = archive_response(json.dumps({'stat': 'ok', 'date': '20261002',
        'tables': [{'fields': TPEX_FIELDS, 'data': [row]}]}).encode(),
        source_url=_url('TPEX', '2026-10-02'), retrieved_at=datetime.now(timezone.utc).isoformat())
    data['institutional_trading']['official_recovery']['reports'][0]['raw_evidence'] = proof
    result = evidence_gap_details(data)['institutional']
    assert result['status'] == 'matched_saved_dates'
    assert result['matched_values'] == 3


def test_archived_prior_source_can_fill_a_date_without_changing_current_provider_rows():
    data = institutional_data()
    prior = deepcopy(data['institutional_trading'])
    data['institutional_trading']['official_recovery']['reports'] = []
    data['source_record_archive'] = [{'source': 'institutional_trading', 'record': prior}]
    assert evidence_gap_details(data)['institutional']['status'] == 'matched_saved_dates'


def test_bad_saved_metadata_fails_closed_without_breaking_the_reader():
    data = institutional_data()
    data['financial_currency'] = ['not-a-currency']
    data['institutional_trading']['daily_category_observations'][0]['category'] = []
    result = evidence_gap_details(data)
    assert result['cash_flow']['raw_scalar_currency'] is None
    assert result['institutional']['status'] != 'matched_saved_dates'


def test_old_acquisition_failure_is_separate_from_new_valid_numeric_evidence():
    data = institutional_data()
    valid = deepcopy(data['institutional_trading']['official_recovery']['reports'][0])
    data['institutional_trading']['official_recovery']['reports'][0]['raw_evidence'] = {}
    result = evidence_gap_details(data, [valid])['institutional']
    assert result['status'] == 'matched_saved_dates'
    assert result['prior_receipt_issues']


def test_only_the_conflicting_category_is_unverified_not_other_matching_values():
    from official_response_evidence import read_response
    data = institutional_data()
    report = deepcopy(data['institutional_trading']['official_recovery']['reports'][0])
    payload = json.loads(read_response(report['raw_evidence']))
    payload['data'][0][10], payload['data'][0][18] = '-99', '1155'
    report['raw_evidence'] = archive_response(json.dumps(payload).encode(),
        source_url=_url('TWSE', report['date']), retrieved_at=datetime.now(timezone.utc).isoformat())
    result = evidence_gap_details(data, [report])['institutional']
    assert result['status'] == 'partial'
    assert result['matched_values'] == 2
    assert result['conflicts'][0]['category'] == 'investment_trust'


@pytest.mark.parametrize('market', ['TW', 'TWO'])
def test_normal_report_history_uses_the_exact_exchange_adapter(monkeypatch, market):
    import pandas as pd
    from types import SimpleNamespace
    from datetime import date
    from data_fetch.yfinance_enrichment_extractors import extract_market_history_bundle
    from data_fetch.market_sources import twse_session_observation as twse
    from data_fetch.market_sources import tpex_session_observation as tpex
    calls = []
    for name, adapter in [('TW', twse), ('TWO', tpex)]:
        monkeypatch.setattr(adapter, 'official_observation',
            lambda ticker, day, name=name: calls.append((name, ticker, day)) or {'status': 'unavailable'})
    frame = pd.DataFrame({'Open': [100.], 'High': [101.], 'Low': [99.],
        'Close': [100.], 'Adj Close': [100.], 'Volume': [1000.]}, index=pd.to_datetime(['2026-10-16']))
    stock = SimpleNamespace(ticker='3324.'+market, history=lambda **kwargs: frame)
    extract_market_history_bundle(stock, as_of=date(2026, 10, 17))
    if market == 'TWO':
        assert calls[-1] == (market, '3324.'+market, '2026-10-16')
    else:
        # Older standalone checkouts have no TWSE enrichment; do not invent it.
        assert calls in ([], [('TW', '3324.TW', '2026-10-16')])
    assert sum(item[0] == 'TWO' for item in calls) == (market == 'TWO')


def test_tpex_volume_supplement_preserves_lots_and_never_splices_old_share_series():
    from report_evidence_fixtures import tpex_payload
    from data_fetch.market_sources.tpex_session_observation import parse_observation, source_url
    payload = tpex_payload()
    row = parse_observation(payload, '3324.TWO', '2026-10-07')
    proof = archive_response(json.dumps(payload).encode(), source_url=source_url('3324.TWO', '2026-10-07'),
                             retrieved_at=datetime.now(timezone.utc).isoformat())
    official = {**row, 'ticker': '3324.TWO', 'status': 'observed', 'raw_evidence': proof}
    bar = {**row, 'volume': 2721000}
    data = {'ticker': '3324.TWO', 'daily_market_data': {'as_of': row['date'], 'bars': [bar],
        'source': 'yfinance', 'provider_raw_observation': {**bar, 'ticker': '3324.TWO', 'volume_unit': 'shares'},
        'official_observation': {'status': 'not_applicable', 'ticker': '3324.TWO'}}}
    before = deepcopy(data)
    detail = evidence_gap_details(data, supplemental_volume=official)['volume']
    assert detail['official_original_verified'] is True
    assert detail['status'] == 'unit_mismatch'
    assert detail['official_unit'] == 'lots'
    assert detail.get('delta_shares') is None
    assert detail['cross_provider_comparable'] is False
    assert data == before


def test_market_comparison_never_subtracts_lots_from_shares_and_keeps_a_quality_warning():
    from report_evidence_fixtures import daily
    from market_price_reconciliation import reconcile
    from report_exchange_volume import evaluate_volume_units
    value = daily()
    value['official_observation']['volume_unit'] = 'lots'
    value['official_observation']['volume'] = 1
    result = reconcile(value)
    assert result['volume']['status'] == 'unit_mismatch'
    assert result['volume']['delta'] is None
    assert result['cross_provider_flow_normalization_allowed'] is False
    details = evaluate_volume_units({'daily_market_data': value}, 'v4')
    assert any(row['id']=='v4_volume_scope_mismatch' for row in details['warnings'])


def test_missing_optional_annual_projector_is_explicitly_unverified(monkeypatch):
    import builtins
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'data_fetch.annual_financial_source_provider':
            raise ModuleNotFoundError(name=name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    result = evidence_gap_details({'ticker': '2330.TW'})['cash_flow']
    assert result['status'] == 'unverified'
    assert '核對器' in result['reason']


def test_public_credibility_gate_keeps_mixed_units_warning():
    from report_evidence_fixtures import daily
    from reporting.content_credibility import evaluate_content_credibility
    value = daily()
    value['official_observation']['volume_unit'] = 'lots'
    result = evaluate_content_credibility({}, {'pipeline': 'v4', 'data': {'daily_market_data': value}})
    assert sum(row['id'] == 'v4_volume_scope_mismatch' for row in result['warnings']) == 1


@pytest.mark.parametrize('value', [None, [], 'unknown'])
def test_missing_or_malformed_daily_metadata_does_not_break_units_check(value):
    from report_exchange_volume import evaluate_volume_units
    result = evaluate_volume_units({'daily_market_data': value}, 'v4')
    assert not result['warnings'] and not result['blocking_issues']
