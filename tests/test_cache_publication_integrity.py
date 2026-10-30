"""Independent observation clocks and provisional publication, with no network."""
from copy import deepcopy
from datetime import datetime

import pandas as pd
import pytest


def epoch(stamp='2026-10-27T18:00:00+08:00'):
    return datetime.fromisoformat(stamp).timestamp()


def payload(day='2026-10-27'):
    return {
        'ticker': '2356.TW', 'instrument_type': 'EQUITY',
        'daily_market_data': {'ticker': '2356.TW', 'as_of': day, 'source': 'fixture',
                              'bars': [{'date': day, 'open': 63, 'high': 63,
                                        'low': 63, 'close': 63, 'volume': 0}]},
        'institutional_trading': {'latest_date': day},
    }


def fresh_assessor(data, ticker, **kwargs):
    return True, {'stale_sources': [], 'source_freshness': {
        source: {'is_fresh': True, 'stale': False, 'fetched_at_epoch': 123}
        for source in ('market_data', 'institutional_trading')}}


def test_policy_separates_completed_and_mature_evidence_dates():
    from market_evidence_policy import acquisition_session_scope
    before = acquisition_session_scope(datetime.fromtimestamp(epoch(), __import__('zoneinfo').ZoneInfo('Asia/Taipei')))
    assert before['latest_completed_session'] == '2026-10-27'
    assert before['mature_evidence_session'] == '2026-10-22'
    assert before['acquisition_phase'] == 'provisional'
    assert before['finality_guaranteed'] is False
    after = acquisition_session_scope(datetime.fromisoformat('2026-10-27T22:30:00+08:00'))
    assert after['latest_completed_session'] == after['mature_evidence_session'] == '2026-10-27'
    assert after['acquisition_phase'] == 'post_cutoff'


@pytest.mark.parametrize('day', ['2026-10-22', '2026-10-23', '2026-10-28', None, 'bad'])
def test_recent_market_acquisition_cannot_hide_wrong_or_missing_session(day):
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    data = payload(day); original = deepcopy(data)
    fresh, result = assess_session_aligned_cache(data, '2356.TW', assessor=fresh_assessor, now_epoch=epoch())
    assert not fresh and 'market_data' in result['stale_sources']
    assert result['source_freshness']['market_data']['expected_session'] == '2026-10-27'
    assert result['source_freshness']['market_data']['fetched_at_epoch'] == 123
    assert data == original


def test_legitimate_current_zero_volume_is_not_discarded():
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    fresh, result = assess_session_aligned_cache(payload(), '2356.TW', assessor=fresh_assessor, now_epoch=epoch())
    assert fresh and result['stale_sources'] == []


@pytest.mark.parametrize('day', ['2026-10-22', '2026-10-28', None, 'invalid'])
def test_institutional_observation_clock_independent_of_fresh_market(day):
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    data = payload(); data['institutional_trading']['latest_date'] = day
    fresh, result = assess_session_aligned_cache(data, '2356.TW', assessor=fresh_assessor, now_epoch=epoch())
    assert not fresh and result['stale_sources'] == ['institutional_trading']
    assert result['source_freshness']['market_data']['is_fresh']
    assert result['source_freshness']['institutional_trading']['expected_session'] == '2026-10-27'


def test_unknown_calendar_does_not_leave_cache_fresh(monkeypatch):
    from data_fetch import cache_session_alignment as module
    monkeypatch.setattr(module, 'acquisition_session_scope', lambda moment, **kwargs: {
        'latest_completed_session': None, 'mature_evidence_session': None,
        'acquisition_phase': 'unknown'})
    fresh, result = module.assess_session_aligned_cache(payload(), '2356.TW', assessor=fresh_assessor, now_epoch=epoch())
    assert not fresh
    assert set(result['stale_sources']) == {'market_data', 'institutional_trading'}


def test_explicit_other_market_retains_its_existing_policy():
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    data = payload(); data['ticker'] = 'AAPL'
    assert assess_session_aligned_cache(data, 'AAPL', assessor=fresh_assessor, now_epoch=epoch()) == fresh_assessor(data, 'AAPL')


def test_finmind_query_can_read_published_today_before_cutoff(monkeypatch):
    import time
    from data_fetch.market_sources import taiwan
    calls = []
    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame([{'stock_id': '2356', 'date': '2026-10-27', 'name': name,
                                  'buy': 10, 'sell': 5} for name in
                                 ('Foreign_Investor', 'Investment_Trust', 'Dealer_self')])
    monkeypatch.setattr(time, 'time', lambda: epoch())
    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    result = taiwan.fetch_institutional_trading_trend('2356.TW')
    assert calls[0]['end_date'] == '2026-10-27'
    assert result['latest_date'] == '2026-10-27'
    assert result['publication_observation']['acquisition_phase'] == 'provisional'
    assert result['publication_observation']['eligible'] is False


def test_official_recovery_observes_today_but_cannot_admit_before_cutoff(monkeypatch):
    import official_institutional_source as official
    import shared_provider_cache
    from report_source_admission import institutional_admission
    calls = []
    def fetch(market, day, timeout, **kwargs):
        calls.append(day)
        return {'rows': {'2356': {'foreign': 1, 'investment_trust': 2, 'dealer': 3}},
                'source': 'TWSE T86', 'raw_evidence': {'status': 'archived',
                  'evidence_kind': 'raw_http_response_bytes',
                  'retrieved_at': '2026-10-27T10:00:00+00:00'}}
    monkeypatch.setattr(official, '_fetch_report', fetch)
    monkeypatch.setattr(shared_provider_cache, 'shared_fetch', lambda key, fn, **kwargs: (
        fn(), {'cache_hit': False, 'fetched_at_epoch': epoch()}))
    value, diagnostics = official.recover_institutional_observations(
        '2356.TW', {}, now_epoch=epoch(), limit=30, include_provisional=True)
    assert calls[0] == '2026-10-27' and len(calls) <= official.MAX_REPORTS
    assert '2026-10-23' not in calls
    assert value['latest_date'] == '2026-10-27'
    assert value['latest_official_observation']['acquisition_phase'] == 'provisional'
    assert not institutional_admission(value, '2026-10-27')['eligible']
    assert diagnostics['publication_observation']['status'] == 'available_provisional'


def test_unknown_calendar_blocks_primary_acquisition(monkeypatch):
    from data_fetch.market_sources import taiwan
    import official_institutional_source as official
    class Loader:
        def taiwan_stock_institutional_investors(self, **kwargs):
            pytest.fail('No known calendar must not become a fabricated query bound')
    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    monkeypatch.setattr(official, 'expected_sessions', lambda *a, **kw: [])
    assert taiwan.fetch_institutional_trading_trend('2356.TW') == {}


def test_acquisition_cache_reuses_provisional_receipt_but_rechecks_cutoff_and_calendar(monkeypatch):
    import cache_store
    import time
    import official_institutional_source as official
    import market_evidence_policy as policy
    from cache_backends import InMemoryCache
    from data_fetch import institutional_provider as provider
    from data_fetch.types import FetchRequest
    now = [epoch()]; version = ['fixture-calendar-v1']; calls = []
    monkeypatch.setattr(time, 'time', lambda: now[0])
    monkeypatch.setattr(policy, 'calendar_cache_token', lambda *args: version[0])
    monkeypatch.setattr(provider, 'call_provider_with_resilience', lambda p, fn, args, kw: fn(*args, **kw))
    monkeypatch.setattr(official, 'recover_institutional_observations', lambda ticker, value, **kw: (value, {}))
    def fetch(ticker):
        calls.append(ticker)
        return {'latest_date': '2026-10-27', 'source': 'synthetic', 'observation_dates': ['2026-10-27']}
    cache_store.set_cache_backend(InMemoryCache())
    try:
        request = FetchRequest.from_ticker('2356.TW')
        first = provider.fetch_institutional_result(request, fetch=fetch)
        now[0] += 60
        warm = provider.fetch_institutional_result(request, fetch=fetch)
        assert len(calls) == 1
        assert first.audit['fetched_at_epoch'] == warm.audit['fetched_at_epoch']
        assert not warm.value['latest_session_admission']['eligible']
        now[0] = epoch('2026-10-27T22:30:00+08:00')
        mature = provider.fetch_institutional_result(request, fetch=fetch)
        assert len(calls) == 2 and mature.audit['cache_key'] != warm.audit['cache_key']
        version[0] = 'fixture-calendar-v2'
        revised = provider.fetch_institutional_result(request, fetch=fetch)
        assert len(calls) == 3 and revised.audit['cache_key'] != mature.audit['cache_key']
        assert not revised.value['latest_session_admission']['eligible'], 'Clock alone cannot create official proof'
    finally:
        cache_store.reset_cache_store_for_tests()


def test_published_observation_is_visible_without_replacing_canonical_source():
    from data_fetch.cached_institutional_recovery import _provisional_publication
    proof = {'status': 'archived', 'evidence_kind': 'raw_http_response_bytes',
             'retrieved_at': '2026-10-27T10:00:00+00:00', 'raw_response_sha256': 'fixture-only'}
    value = {'latest_date': '2026-10-27',
        'publication_observation': {'status': 'available_provisional', 'observed_date': '2026-10-27',
                                    'provider': 'TWSE T86'},
        'latest_official_observation': {'date': '2026-10-27', 'ticker': '2356.TW', 'market': 'TWSE',
                                        'raw_evidence': proof, 'categories': {'foreign': 1}}}
    original = deepcopy(value)
    observed = _provisional_publication(value, '2356.TW')
    assert observed['canonical_source_replaced'] is observed['eligible'] is False
    assert observed['retrieved_at'] == proof['retrieved_at']
    assert observed['raw_evidence'] == proof
    assert value == original
    value['latest_official_observation']['ticker'] = '2330.TW'
    assert _provisional_publication(value, '2356.TW') is None


@pytest.mark.parametrize('day', ['2026-10-24', '2026-10-26'])
def test_sourced_special_opening_is_consistent_across_acquisition_and_window(monkeypatch, day):
    import market_calendar_store as calendars
    from official_institutional_source import expected_sessions
    from data_fetch.institutional_provider import institutional_window_status
    exception = {'state': 'open', 'reason': 'official_special_opening_fixture',
                 'published_date': '2026-10-22', 'source_url': 'https://www.twse.com.tw/test-only-opening',
                 'scope': 'synthetic exchange calendar evidence', 'exchanges': ['TWSE']}
    monkeypatch.setitem(calendars.BUILTIN_SESSION_EXCEPTIONS[('tw', 2026)], day, exception)
    days = expected_sessions('2356.TW', epoch(day+'T23:00:00+08:00'), 3, include_provisional=True)
    assert days[0] == day
    assert institutional_window_status(sorted(days), '2356.TW', 3) == 'complete'
