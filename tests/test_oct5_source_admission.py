"""Public boundary checks. Original private-data replay cases remain local."""
from datetime import datetime, date
import pytest
from market_evidence_policy import completed_evidence_session, session_cache_scope
from reporting.trade_price_grid import grid_assessment

@pytest.mark.parametrize('moment,expected', [('2026-10-05T13:38:11+08:00', '2026-10-02'), ('2026-10-05T22:29:59+08:00', '2026-10-02'), ('2026-10-05T22:30:00+08:00', '2026-10-05'), ('2026-10-06T08:00:00+08:00', '2026-10-05')])
def test_maturity_boundary(moment, expected):
    assert completed_evidence_session(datetime.fromisoformat(moment)) == expected

@pytest.mark.parametrize('moment,expected', [('2026-10-05T13:38:11+08:00', ('2026-10-02', 'post_cutoff')), ('2026-10-05T22:29:59+08:00', ('2026-10-02', 'post_cutoff')), ('2026-10-05T22:30:00+08:00', ('2026-10-05', 'post_cutoff'))])
def test_session_cache_scope_uses_publication_maturity_boundary(moment, expected):
    assert session_cache_scope(datetime.fromisoformat(moment)) == expected

def test_missing_6715_metadata_is_unchecked_not_valid():
    r = grid_assessment({'ticker': '6715.TW'}, {'entry_zone': '450', 'target_price': '500', 'stop_loss': '440'})
    assert r['status'] == 'unverified' and r['checked_levels'] == r['invalid_levels'] == [] and (r['instrument_type'] is None)

def test_phase_cache_keys_roll(monkeypatch):
    import data_fetch.market_sources.twse_session_observation as s
    import market_evidence_policy as p
    phase = ['provisional']
    keys = []
    monkeypatch.setattr(p, 'acquisition_phase', lambda *a: phase[0])

    def fake(key, fetch, **kw):
        keys.append((key, kw['freshness_seconds']))
        return (None, {'error_kind': 'test-unavailable'})
    monkeypatch.setattr(s, 'shared_fetch', fake)
    s.official_observation('2330.TW', '2026-10-05')
    phase[0] = 'post_cutoff'
    s.official_observation('2330.TW', '2026-10-05')
    assert keys == [('report-official-session-ohlcv:v4:2026-10-05:provisional', 300), ('report-official-session-ohlcv:v4:2026-10-05:post_cutoff', 21600)]

def test_whole_cache_rechecks_current_date_and_raw_proof(monkeypatch):
    import data_fetch.yfinance_cache_gate as g
    monkeypatch.setattr(g, 'REQUIRED_DATA_SCHEMA_FIELDS', [])
    c = {'ticker': '1301.TW', 'data_schema_version': g.DATA_SCHEMA_VERSION, 'daily_market_data': {'bars': [{'date': '2026-10-02'}], 'as_of': '2026-10-02', 'price_basis_contract': 'market_price_basis.v2', 'history_query': {'expected_completed_session': '2026-10-02'}}}

    def check():
        return g.build_fresh_cache_payload('1301.TW', c, assess_cached=lambda *a: (True, {}), append_cache_audit=lambda *a, **kw: pytest.fail('old payload approved'), now_epoch=datetime.fromisoformat('2026-10-06T08:00:00+08:00').timestamp())
    r, stale, _ = check()
    assert r is None and stale == ['market_data']
    c['daily_market_data']['as_of'] = '2026-10-05'
    c['daily_market_data']['history_query']['expected_completed_session'] = '2026-10-05'
    r, stale, _ = check()
    assert r is None and set(stale) == {'market_data', 'institutional_trading'}

def test_explicit_backtest_end_excludes_provisional_day():
    import pandas as pd
    from market_price_history import fetch_backtest_bars
    calls = []

    class Stock:

        def history(self, **kw):
            calls.append(kw)
            return pd.DataFrame({'Open': [10], 'High': [11], 'Low': [9], 'Close': [10]}, index=pd.to_datetime(['2026-10-02']))
    rows = fetch_backtest_bars('2371.TW', date(2026, 9, 17), date(2026, 10, 5), ticker_factory=lambda _: Stock(), moment=datetime.fromisoformat('2026-10-05T13:38:11+08:00'))
    assert calls[0]['end'] == '2026-10-03' and rows[-1]['date'] == '2026-10-02' and (rows[-1]['observation_provenance']['finality_verified'] is False)

def test_maturity_source_requires_independent_raw_publication_and_price_match(monkeypatch):
    import maturity_source_admission as m
    bars = [{'date': '2026-10-05', 'open': 31.5, 'high': 31.5, 'low': 30.15, 'close': 30.2, 'observation_provenance': {'official_observation': {'open': 31.5, 'high': 31.5, 'low': 30.15, 'close': 30.15}}}]
    assert not m.assess_maturity_source(bars, '2371.TW', '2026-10-05')['eligible']
    monkeypatch.setattr(m, 'price_admission', lambda *a: {'eligible': True, 'raw_evidence': {'status': 'isolated proof fixture'}})
    mismatch = m.assess_maturity_source(bars, '2371.TW', '2026-10-05')
    assert mismatch['reason'] == 'maturity_provider_official_price_mismatch' and mismatch['field'] == 'close'
    bars[0]['close'] = 30.15
    passed = m.assess_maturity_source(bars, '2371.TW', '2026-10-05')
    assert passed['eligible'] and (not passed['finality_guaranteed']) and (not passed['all_historical_bars_verified'])
