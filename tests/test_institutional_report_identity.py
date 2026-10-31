"""Frozen independent counterexamples and adjacent metadata identity boundaries."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from institutional_report_status import build_institutional_report_status
from test_institutional_report_status import context


COUNTEREXAMPLES = json.loads((Path(__file__).parent / 'fixtures/institutional_status_review_counterexamples.json').read_text())['cases']


@pytest.mark.parametrize('case', COUNTEREXAMPLES, ids=lambda row: row['case'])
def test_frozen_reviewer_counterexample(case):
    context = deepcopy(case['context'])
    result = build_institutional_report_status(context)
    assert result['status'] == case['expected_status']
    assert result['query_status'] == 'unknown'
    assert result['official_publication_status'] == 'unknown'
    assert context == case['context']


def project(value):
    return build_institutional_report_status(value)


def inst(value):
    return value['data']['institutional_trading']


@pytest.mark.parametrize('key,value', [('data_id', '2330'), ('dataset', 'TaiwanStockPrice'),
                                      ('data_id', None), ('dataset', None), ('data_id', 2855)])
def test_primary_query_identity_must_be_explicit_and_match(key, value):
    c = context(); i = inst(c); i['official_recovery']['reports'] = []
    i['source_provenance']['query'][key] = value
    assert project(c)['status'] == 'insufficient_evidence'


def test_primary_mismatch_cannot_be_hidden_by_good_official_response():
    c = context(); inst(c)['source_provenance']['query']['data_id'] = '2330'
    assert project(c)['query_status'] == 'unknown'


@pytest.mark.parametrize('key,value', [('dataset', None), ('data_id', None), ('data_id', 2855)])
def test_present_but_unbound_primary_is_not_hidden_by_good_official_response(key, value):
    c = context(); inst(c)['source_provenance']['query'][key] = value
    p = project(c)
    assert p['status'] == 'insufficient_evidence' and p['identity_binding'] == 'unknown'


@pytest.mark.parametrize('value', [{}, []])
def test_present_empty_or_malformed_primary_record_is_not_an_absent_source(value):
    c = context(); inst(c)['source_provenance'] = value
    assert project(c)['identity_binding'] == 'unknown'


@pytest.mark.parametrize('location', ['data', 'daily', 'inst', 'audit', 'primary', 'provenance'])
def test_present_container_tickers_cannot_disagree(location):
    c = context(); d = c['data']; i = inst(c); audit = d['source_audit'][0]
    destination = {'data': d, 'daily': d['daily_market_data'], 'inst': i, 'audit': audit,
                   'primary': audit['primary_acquisition'], 'provenance': i['source_provenance']}[location]
    destination['ticker'] = '2330.TW'
    assert project(c)['status'] == 'insufficient_evidence'
    assert 'container_ticker_conflict' in project(c)['identity_limitations']


@pytest.mark.parametrize('url', [
    'https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20260615&selectType=ALLBUT0999',
    'https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20260616&date=20260615&selectType=ALLBUT0999',
    'https://www.twse.com.tw.evil.test/rwd/zh/fund/T86?response=json&date=20260616&selectType=ALLBUT0999',
    'http://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20260616&selectType=ALLBUT0999',
    'https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20260616&selectType=other',
    'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?date=2026/06/16&type=Daily&sect=EW&response=json',
])
def test_invalid_official_raw_endpoint_cannot_be_masked_by_primary_or_request_url(url):
    c = context(); inst(c)['official_recovery']['reports'][0]['raw_evidence']['source_url'] = url
    p = project(c)
    assert p['status'] == 'insufficient_evidence' and p['query_status'] == 'unknown'


@pytest.mark.parametrize('fault', ['missing_source', 'missing_raw_url', 'unknown_source', 'wrong_row_ticker', 'wrong_row_market', 'wrong_raw_ticker', 'wrong_raw_date'])
def test_official_identity_fields_are_checked_consistently(fault):
    c = context(); row = inst(c)['official_recovery']['reports'][0]
    if fault == 'missing_source': row.pop('source')
    elif fault == 'missing_raw_url': row['raw_evidence'].pop('source_url')
    elif fault == 'unknown_source': row['source'] = 'TWSE guessed source'
    elif fault == 'wrong_row_ticker': row['ticker'] = '2330.TW'
    elif fault == 'wrong_row_market': row['market'] = 'TPEX'
    elif fault == 'wrong_raw_ticker': row['raw_evidence']['ticker'] = '2330.TW'
    elif fault == 'wrong_raw_date': row['raw_evidence']['date'] = '2026-06-15'
    assert project(c)['status'] == 'insufficient_evidence'


def latest_context():
    c = context(observed='2026-06-16', official='available'); i = inst(c)
    row = i['official_recovery']['reports'][0]
    i['latest_official_observation'] = {'ticker': '2855.TW', 'market': 'TWSE', 'date': row['date'],
        'source_url': row['source_url'], 'raw_evidence': deepcopy(row['raw_evidence'])}
    i['official_recovery']['reports'] = []; i.pop('source_provenance')
    return c


def test_bound_legacy_latest_receipt_can_date_current_rows():
    assert project(latest_context())['status'] == 'available_provisional'


@pytest.mark.parametrize('field,value', [('ticker', '2330.TW'), ('ticker', None), ('market', 'TPEX'),
                                       ('market', None), ('source_url', 'https://unknown.test/data')])
def test_fallback_uses_the_same_identity_and_endpoint_boundaries(field, value):
    c = latest_context(); inst(c)['latest_official_observation'][field] = value
    assert project(c)['status'] == 'insufficient_evidence'


def test_bad_fallback_is_not_hidden_by_good_recovery_row():
    c = context(observed='2026-06-16', official='available')
    bad = latest_context()['data']['institutional_trading']['latest_official_observation']
    bad['ticker'] = '2330.TW'; inst(c)['latest_official_observation'] = bad
    assert project(c)['status'] == 'insufficient_evidence'


def test_twse_mirror_keeps_known_market_and_date_binding():
    c = context(); row = inst(c)['official_recovery']['reports'][0]
    row['source_url'] = row['raw_evidence']['source_url'] = row['source_url'].replace('www.twse', 'wwwc.twse')
    assert project(c)['status'] == 'no_current_rows'


@pytest.mark.parametrize('api', ['daily', 'openapi'])
def test_explicit_tpex_endpoints_bind_saved_date_without_borrowing_twse(api):
    c = context(observed='2026-06-16', official='available'); c['ticker'] = '6543.TWO'; i = inst(c)
    i.pop('source_provenance'); row = i['official_recovery']['reports'][0]
    row['source'] = 'TPEx dailyTrade' if api == 'daily' else 'TPEx institutional OpenAPI'
    url = 'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?date=2026/06/16&type=Daily&sect=EW&response=json' if api == 'daily' else 'https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading'
    row['source_url'] = row['raw_evidence']['source_url'] = url
    assert project(c)['status'] == 'available_provisional'
