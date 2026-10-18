"""Integer-share source summaries agree across cold, warm and source-only merge."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import time

import pandas as pd
import pytest

NOW = 1791948208.427107
ACQUIRED = NOW - 120
TICKER = '2464.TW'
SOURCE = 'FinMind TaiwanStockInstitutionalInvestorsBuySell'


@pytest.fixture
def saved_source(monkeypatch):
    from official_institutional_source import expected_sessions
    from official_response_evidence import archive_response
    from institutional_observations import summarize_observations
    monkeypatch.setattr(time, 'time', lambda: NOW)
    days = sorted(expected_sessions(TICKER, NOW, 30))
    # Exact formal failure's last-five totals: 32,275 shares (Python round=32.27).
    last_five = [-1512368, 3645363, -2158766, 1596155, -1538109]
    raw, records = [], []
    for n, day in enumerate(days):
        for name, category in [('Foreign_Investor', 'foreign'), ('Investment_Trust', 'investment_trust'),
                               ('Dealer_self', 'dealer')]:
            net = last_five[n - 25] if n >= 25 and category == 'foreign' else 0
            raw.append(dict(date=day, stock_id='2464', name=name, buy=max(net, 0), sell=max(-net, 0)))
            records.append(dict(date=day, category=category, net_buy_shares=net, source=SOURCE, unit='shares'))
    proof = archive_response(json.dumps(raw).encode(), source_url='https://api.finmindtrade.com/api/v4/data',
                             retrieved_at=datetime.fromtimestamp(ACQUIRED, timezone.utc).isoformat(),
                             evidence_kind='sdk_dataframe_json_not_raw_http', http_status=None)
    proof['query'] = {'dataset': 'TaiwanStockInstitutionalInvestorsBuySell', 'data_id': '2464',
                      'start_date': days[0], 'end_date': days[-1]}
    value = summarize_observations(records, TICKER, limit=30)
    value['source_provenance'] = proof
    value['last_5_trading_days_net_buy_thousand_shares'] = 32.28  # Existing pandas-generated warm cache.
    value['preserved_diagnostic'] = {'reason': 'same_saved_epoch', 'values': [1, 2]}
    return value, raw


def install_public_warm(monkeypatch, value, *, conflict=False):
    import shared_provider_cache
    import data_fetch.institutional_provider as provider
    from official_institutional_source import TWSE_FIELDS, _url, _parse_report
    from official_response_evidence import archive_response
    original = deepcopy(value)
    calls = []
    reports = {}
    days = sorted({row['date'] for row in value['daily_category_observations']})[-5:]
    for day in days:
        categories = {r['category']: r['net_buy_shares'] for r in value['daily_category_observations'] if r['date'] == day}
        foreign, trust, dealer = (categories[c] for c in ('foreign', 'investment_trust', 'dealer'))
        if conflict and day == days[-2]:
            foreign += 1
        row = ['2464', '盟立', max(foreign, 0), max(-foreign, 0), foreign, 0, 0, 0,
               max(trust, 0), max(-trust, 0), trust, dealer, max(dealer, 0), max(-dealer, 0), dealer,
               0, 0, 0, foreign + trust + dealer]
        body = json.dumps({'stat': 'OK', 'date': day.replace('-', ''), 'fields': TWSE_FIELDS,
                           'hints': '單位:股', 'data': [row]}).encode()
        proof = archive_response(body, source_url=_url('TWSE', day),
                                 retrieved_at=datetime.fromtimestamp(ACQUIRED, timezone.utc).isoformat())
        report = _parse_report(json.loads(body), 'TWSE', day)
        report.update(raw_evidence=proof, source='TWSE T86', source_url=_url('TWSE', day))
        reports[day] = report

    def cache_only(key, callback, **kwargs):
        assert kwargs['use_cache'] is True
        calls.append(key)
        item = original if key.startswith('institutional:') else reports[key.split(':')[2]]
        return deepcopy(item), {'cache_hit': True, 'stale': False, 'fetched_at_epoch': ACQUIRED}

    monkeypatch.setattr(shared_provider_cache, 'shared_fetch', cache_only)
    monkeypatch.setattr(provider, 'shared_fetch', cache_only)
    import official_institutional_verification
    monkeypatch.setattr(official_institutional_verification, 'attach_cached_verification', lambda v, t: v)
    return original, calls


def public_warm_fetch_and_merge(monkeypatch, value):
    from data_fetch.institutional_provider import fetch_institutional_result
    from data_fetch.types import FetchRequest
    from institutional_source_refresh import merge_institutional_source
    original, calls = install_public_warm(monkeypatch, value)
    result = fetch_institutional_result(FetchRequest.from_ticker(TICKER),
                                       fetch=lambda *_: pytest.fail('warm source must not call SDK'))
    old = {'ticker': TICKER, 'instrument_type': 'EQUITY',
           'company_identity': {'ticker': TICKER, 'stock_id': '2464', 'instrument_type': 'EQUITY'},
           'institutional_trading': deepcopy(original), 'unchanged_analysis_marker': 'old'}
    merged = merge_institutional_source(old, [], result.value, [result.audit], TICKER)
    return original, calls, result, merged


def test_public_warm_sdk_replay_to_exact_source_only_merge_preserves_age(monkeypatch, saved_source):
    from provider_acquisition import observation_kind
    value, _ = saved_source
    # Preserve even a non-sorted original row array; rebuilding must not replace it.
    value['daily_category_observations'].reverse()
    original, calls, result, merged = public_warm_fetch_and_merge(monkeypatch, value)
    assert result.value['last_5_trading_days_net_buy_thousand_shares'] == 32.27
    assert merged['institutional_trading']['daily_category_observations'] == original['daily_category_observations']
    assert result.value['source_provenance'] == original['source_provenance']
    assert result.value['preserved_diagnostic'] == original['preserved_diagnostic']
    assert value == original  # No source-cache object mutation.
    assert result.value['fetched_at_epoch'] == result.audit['fetched_at_epoch'] == ACQUIRED
    assert result.value['cache_hit'] is result.audit['cache_hit'] is True
    assert result.audit['provider_attempts'] == []
    assert result.audit['http_request_sent'] is False
    assert result.audit['coverage_status'] == 'available'
    assert len(calls) == 6
    assert len(merged['institutional_trading']['daily_category_observations']) == 90
    assert observation_kind({'provider': 'FinMind', 'status': result.status,
                             'record_count': result.audit['record_count'], 'message': result.audit['message'],
                             'details': result.audit}) == 'fresh_cache_count'


@pytest.mark.parametrize('sign', [1, -1])
def test_public_cold_producer_uses_same_integer_summary(monkeypatch, saved_source, sign):
    from data_fetch.market_sources import taiwan
    from institutional_observations import summarize_observations
    value, raw = saved_source
    if sign < 0:
        raw = [{**r, 'buy': r['sell'], 'sell': r['buy']} for r in raw]

    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            assert kwargs == {'stock_id': '2464', 'start_date': '2026-08-28', 'end_date': '2026-10-13'}
            return pd.DataFrame(raw)
        def _dispatcher_url(self, _):
            return 'https://api.finmindtrade.com/api/v4/data'

    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    produced = taiwan.fetch_institutional_trading_trend(TICKER)
    rebuilt = summarize_observations(produced['daily_category_observations'], TICKER, limit=30)
    assert produced['last_5_trading_days_net_buy_thousand_shares'] == sign * 32.27
    assert {k: v for k, v in produced.items() if k != 'source_provenance'} == rebuilt
    assert produced['source_provenance']['http_status'] is None
    assert produced['source_provenance']['evidence_kind'] == 'sdk_dataframe_json_not_raw_http'


def test_public_cold_producer_excludes_rows_after_mature_end_date(monkeypatch, saved_source):
    from data_fetch.market_sources import taiwan
    _, raw = saved_source
    raw.append(dict(date='2026-10-14', stock_id='2464', name='Foreign_Investor', buy=999, sell=0))

    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            assert kwargs == {'stock_id': '2464', 'start_date': '2026-08-28', 'end_date': '2026-10-13'}
            # Model an SDK response that includes a provisional row despite the bound query.
            return pd.DataFrame(raw)
        def _dispatcher_url(self, _):
            return 'https://api.finmindtrade.com/api/v4/data'

    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    produced = taiwan.fetch_institutional_trading_trend(TICKER)
    assert produced['latest_date'] == '2026-10-13'
    assert len(produced['daily_category_observations']) == 90
    assert produced['rejected_record_count'] == 0
    assert produced['source_provenance']['response_row_count'] == 91
    assert produced['source_provenance']['excluded_after_end_date_row_count'] == 1


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'bool', 'float', 'wrong_unit', 'wrong_source',
                                   'wrong_date', 'whole_total', 'rejected', 'partial', 'conflict',
                                   'wrong_ticker', 'wrong_endpoint', 'wrong_query', 'wrong_path', 'wrong_hash',
                                   'wrong_end_date', 'wrong_size', 'oversized', 'future', 'balanced_row_tamper'])
def test_warm_summary_never_promotes_invalid_or_unbound_observations(saved_source, damage):
    from institutional_observations import rebuild_cached_primary_summary
    value, _ = saved_source
    rows = value['daily_category_observations']
    if damage == 'missing': rows.pop()
    elif damage == 'duplicate': rows[-1] = deepcopy(rows[0])
    elif damage == 'bool': rows[0]['net_buy_shares'] = False
    elif damage == 'float': rows[0]['net_buy_shares'] = 0.0
    elif damage == 'wrong_unit': rows[0]['unit'] = 'thousand_shares'
    elif damage == 'wrong_source': rows[0]['source'] = 'unknown'
    elif damage == 'wrong_date': rows[0]['date'] = '2099-01-01'
    elif damage == 'whole_total': value['total_net_buy_shares'] += 1
    elif damage == 'rejected': value['rejected_record_count'] = 1
    elif damage == 'partial': value['coverage_status'] = 'partial'
    elif damage == 'conflict': value['official_recovery'] = {'conflicts': [{'date': '2026-10-12'}]}
    elif damage == 'wrong_ticker': value['source_provenance']['query']['data_id'] = '2330'
    elif damage == 'wrong_endpoint': value['source_provenance']['source_url'] = 'https://example.com/data'
    elif damage == 'wrong_query': value['source_provenance']['query']['dataset'] = 'TaiwanStockPrice'
    elif damage == 'wrong_end_date': value['source_provenance']['query']['end_date'] = '2026-10-12'
    elif damage == 'wrong_path': value['source_provenance']['raw_response_path'] = '/tmp/not-the-archive.gz'
    elif damage == 'wrong_hash': value['source_provenance']['raw_response_sha256'] = '0' * 64
    elif damage == 'wrong_size': value['source_provenance']['raw_response_bytes'] += 1
    elif damage == 'oversized': value['source_provenance']['raw_response_bytes'] = 512 * 1024 + 1
    elif damage == 'future': value['source_provenance']['retrieved_at'] = '2099-01-01T00:00:00+00:00'
    elif damage == 'balanced_row_tamper':
        # Same category totals/trend/last10 display, but different original per-day facts.
        rows[0]['net_buy_shares'] += 1
        rows[3]['net_buy_shares'] -= 1
    before = deepcopy(value)
    assert rebuild_cached_primary_summary(value, TICKER, now_epoch=NOW, limit=30) == before
    assert value == before


def test_other_integer_summaries_must_not_be_repaired_even_with_matching_raw(saved_source):
    from institutional_observations import rebuild_cached_primary_summary
    value, _ = saved_source
    value['net_buy_shares_by_category']['foreign'] += 1
    assert rebuild_cached_primary_summary(value, TICKER, now_epoch=NOW, limit=30) == value
    assert value['last_5_trading_days_net_buy_thousand_shares'] == 32.28


def test_warm_source_keeps_official_conflict_and_exact_gate_rejects(monkeypatch, saved_source):
    from data_fetch.institutional_provider import fetch_institutional_result
    from data_fetch.types import FetchRequest
    from institutional_source_refresh import merge_institutional_source
    from fastapi import HTTPException
    value, _ = saved_source
    install_public_warm(monkeypatch, value, conflict=True)
    result = fetch_institutional_result(FetchRequest.from_ticker(TICKER), fetch=lambda *_: pytest.fail('no SDK'))
    assert result.value['official_recovery']['conflicts']
    assert result.audit['coverage_status'] == 'partial'
    old = {'ticker': TICKER, 'instrument_type': 'EQUITY', 'company_identity': {'instrument_type': 'EQUITY'}}
    with pytest.raises(HTTPException) as exc:
        merge_institutional_source(old, [], result.value, [result.audit], TICKER)
    assert exc.value.status_code == 502


@pytest.mark.parametrize('bad_values', [
    {'buy': 1.25}, {'sell': 1.25}, {'buy': True}, {'sell': False},
    {'buy': 1.25, 'sell': 1.25},
])
def test_public_cold_producer_rejects_non_integer_share_rows(monkeypatch, saved_source, bad_values):
    from data_fetch.market_sources import taiwan
    _, raw = saved_source
    raw[0].update(bad_values)

    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            return pd.DataFrame(raw)

    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    produced = taiwan.fetch_institutional_trading_trend(TICKER)
    assert produced['rejected_record_count'] == 1
    assert len(produced['daily_category_observations']) == 89
    assert not any(row['date'] == raw[0]['date'] and row['category'] == 'foreign'
                   for row in produced['daily_category_observations'])


@pytest.mark.parametrize('failure', ['zlib', 'json_recursion'])
def test_warm_archive_parser_failure_keeps_saved_value(monkeypatch, saved_source, failure):
    import zlib
    import official_response_evidence
    from institutional_observations import rebuild_cached_primary_summary
    value, _ = saved_source
    before = deepcopy(value)

    def broken_archive(*args, **kwargs):
        assert kwargs['max_bytes'] == 512 * 1024
        raise zlib.error('corrupt deflate') if failure == 'zlib' else RecursionError('nested JSON')

    monkeypatch.setattr(official_response_evidence, 'read_response', broken_archive)
    assert rebuild_cached_primary_summary(value, TICKER, now_epoch=NOW, limit=30) == before
    assert value == before
