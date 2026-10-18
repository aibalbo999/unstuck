"""A dated secondary series is a reference, not a period assignment to old info."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from urllib.parse import urlencode

import pytest

from official_response_evidence import archive_response, read_response
from report_reader_assets import reader_observations


def reference():
    ticker = '5314.TWO'
    url = 'https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/'+ticker
    fields = {'trailingFreeCashFlow': 468978000., 'trailingOperatingCashFlow': 533937000.,
              'trailingCapitalExpenditure': -64959000.}
    payload = {'timeseries': {'error': None, 'result': [
        {'meta': {'symbol': [ticker], 'type': [field]}, field: [
            {'asOfDate': '2026-06-30', 'periodType': 'TTM', 'currencyCode': 'TWD',
             'reportedValue': {'raw': value}}]} for field, value in fields.items()]}}
    url += '?'+urlencode({'symbol': ticker, 'type': ','.join(fields), 'period1': 1672531200, 'period2': 1792300000})
    proof = archive_response(json.dumps(payload).encode(), source_url=url,
        retrieved_at=datetime.now(timezone.utc).isoformat())
    return {'schema': 'yahoo-cash-flow-period-review:v1', 'ticker': ticker, 'series_receipt': proof}


def test_explicit_ttm_reference_never_overwrites_or_dates_an_undated_negative_scalar():
    data = {'ticker': '5314.TWO', 'financial_currency': 'TWD', 'free_cash_flow_raw': -25623500}
    snapshot = {'data': data, '_reader_cash_flow_review': reference()}
    before = deepcopy(snapshot)
    cash = reader_observations(snapshot)['evidence_gaps']['cash_flow']
    result = cash.get('period_reference') or {}
    assert result.get('status') == 'dated_series_original_replayed'
    assert result['period_end'] == '2026-06-30' and result['period_type'] == 'TTM'
    assert result['free_cash_flow'] == 468978000
    assert result['raw_scalar_matches_series'] is False
    assert result['complete_capex_verified'] is False and result['report_scope_verified'] is False
    assert cash['raw_scalar_period_verified'] is False and cash['raw_scalar'] == -25623500
    assert snapshot == before


def test_money_unit_rejection_does_not_claim_the_raw_scalar_has_a_verified_ttm_period():
    from financial_money_claims import financial_money_claim_issues
    issues = financial_money_claim_issues('TTM自由現金流為0.256235億元。',
        {'financial_currency': 'TWD', 'free_cash_flow_raw': -25623500})
    assert issues
    assert '同期間來源' not in issues[0]
    assert '期間未核實' in issues[0]


@pytest.mark.parametrize('problem', ['symbol', 'currency', 'period', 'missing', 'duplicate', 'math',
                                    'positive_capex', 'future', 'hash', 'request_symbol'])
def test_incomplete_corrupt_or_incomparable_period_reference_fails_closed(problem):
    from report_fcf_period_evidence import cash_flow_period_reference
    review = reference()
    proof = review['series_receipt']
    payload = json.loads(read_response(proof))
    entries = payload['timeseries']['result']
    point = entries[0]['trailingFreeCashFlow'][0]
    if problem == 'symbol': entries[0]['meta']['symbol'] = ['OTHER.TW']
    elif problem == 'currency': point['currencyCode'] = 'USD'
    elif problem == 'period': point['periodType'] = '3M'
    elif problem == 'missing': entries.pop()
    elif problem == 'duplicate': entries[0]['trailingFreeCashFlow'].append(deepcopy(point))
    elif problem == 'math': point['reportedValue']['raw'] += 1
    elif problem == 'positive_capex': entries[2]['trailingCapitalExpenditure'][0]['reportedValue']['raw'] *= -1
    elif problem == 'future': point['asOfDate'] = '2099-06-30'
    if problem == 'hash': proof['raw_response_sha256'] = '0'*64
    elif problem == 'request_symbol': proof['source_url'] = proof['source_url'].replace('symbol=5314.TWO', 'symbol=OTHER.TW')
    else:
        review['series_receipt'] = archive_response(json.dumps(payload).encode(), source_url=proof['source_url'],
            retrieved_at=proof['retrieved_at'])
    result = cash_flow_period_reference({'ticker': '5314.TWO', 'financial_currency': 'TWD'}, review)
    assert result['status'] == 'unverified'
    assert result['raw_scalar_period_verified'] is False


def test_even_an_equal_scalar_does_not_prove_a_period_or_complete_capex():
    from report_fcf_period_evidence import cash_flow_period_reference
    result = cash_flow_period_reference({'ticker': '5314.TWO', 'financial_currency': 'TWD',
        'free_cash_flow_raw': 468978000}, reference())
    assert result['raw_scalar_matches_series'] is True
    assert result['raw_scalar_period_verified'] is False
    assert result['report_scope_verified'] is False and result['complete_capex_verified'] is False
    assert 'raw_response_path' not in json.dumps(result)


def test_missing_currency_on_both_sides_is_not_verified_by_equality():
    from report_fcf_period_evidence import cash_flow_period_reference
    review = reference()
    proof = review['series_receipt']
    payload = json.loads(read_response(proof))
    for entry in payload['timeseries']['result']:
        for key, points in entry.items():
            if key != 'meta':
                for point in points:
                    point.pop('currencyCode')
    review['series_receipt'] = archive_response(json.dumps(payload).encode(), source_url=proof['source_url'],
        retrieved_at=proof['retrieved_at'])
    assert cash_flow_period_reference({'ticker': '5314.TWO'}, review)['status'] == 'unverified'
