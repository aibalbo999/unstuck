"""Public monthly collectors share actual observations, never acquisition time."""
from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest

from data_fetch.types import FetchRequest


@pytest.fixture
def monthly(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import taiwan
    from data_fetch import yfinance_extractors
    from data_fetch.taiwan_providers import MonthlyRevenueProvider

    cache_store.set_cache_backend(InMemoryCache())
    state = {'now': 1791878400.0, 'calls': [], 'amount': 100000000, 'failure': False}
    monkeypatch.setattr('time.time', lambda: state['now'])

    class Loader:
        def taiwan_stock_month_revenue(self, **kwargs):
            state['calls'].append(kwargs)
            if state['failure']:
                raise ValueError('fixture monthly fetch failed')
            return pd.DataFrame([
                {'stock_id': kwargs['stock_id'], 'revenue_year': 2026,
                 'revenue_month': month, 'revenue': 0 if month == 4 else state['amount']}
                for month in range(4, 10)])

    monkeypatch.setattr(taiwan, 'DataLoader', Loader)
    # A cache check must not initiate a real exchange fallback.
    monkeypatch.setattr('data_fetch.market_sources.official_monthly_revenue.fetch_official_monthly_revenue',
                        lambda ticker: {'value': [], 'audit': {'source': 'monthly_revenue',
                            'provider': 'fixture official', 'status': 'unavailable', 'record_count': 0}})

    def fetch(entry='market', ticker='2330.TW', **kwargs):
        if entry == 'provider':
            r = MonthlyRevenueProvider().fetch(FetchRequest.from_ticker(ticker, **kwargs))
            return r.value, r.audit
        helper = taiwan if entry == 'market' else yfinance_extractors
        return helper.fetch_monthly_revenue_records(ticker, Loader, **kwargs)

    state['fetch'] = fetch
    state['loader'] = Loader
    yield state
    cache_store.reset_cache_store_for_tests()


@pytest.mark.parametrize('entry', ['market', 'legacy', 'provider'])
def test_repeated_monthly_read_uses_one_sdk_call_and_original_epoch(monthly, entry):
    first, audit = monthly['fetch'](entry)
    original = deepcopy(first)
    monthly['now'] += 60
    second, warm = monthly['fetch'](entry)
    assert len(monthly['calls']) == 1
    assert second == original and len(second) == 6
    assert warm['status'] == 'skipped_fresh_cache'
    assert warm['cache_hit'] is True and warm['stale'] is False
    assert warm['fetched_at_epoch'] == audit['fetched_at_epoch']
    assert warm['http_request_sent'] is False and warm['http_request_count'] == 0
    assert warm['provider_attempt_count'] == 0 and warm['provider_attempts'] == []
    second.clear()
    assert monthly['fetch'](entry)[0] == original


def test_core_and_typed_provider_share_same_ticker_observation(monthly):
    first, _ = monthly['fetch']('legacy')
    for entry in ['market', 'provider']:
        value, audit = monthly['fetch'](entry)
        assert value == first and audit['status'] == 'skipped_fresh_cache'
    assert len(monthly['calls']) == 1
    monthly['fetch']('provider', ticker='2317.TW')
    assert len(monthly['calls']) == 2


@pytest.mark.parametrize('entry', ['market', 'legacy', 'provider'])
def test_force_refresh_replaces_shared_observation_then_normal_reuses_it(monthly, entry):
    first, old = monthly['fetch'](entry)
    monthly['now'] += 20
    monthly['amount'] = 300000000
    forced, new = monthly['fetch'](entry, force_refresh=True)
    assert len(monthly['calls']) == 2 and forced != first
    assert new['status'] == 'success' and new['fetched_at_epoch'] > old['fetched_at_epoch']
    monthly['now'] += 20
    reused, audit = monthly['fetch'](entry)
    assert reused == forced and len(monthly['calls']) == 2
    assert audit['fetched_at_epoch'] == new['fetched_at_epoch']


def test_expired_observation_is_refetched_and_zero_is_retained(monthly):
    first, old = monthly['fetch']()
    monthly['now'] += 1801
    monthly['amount'] = 200000000
    value, audit = monthly['fetch']()
    assert len(monthly['calls']) == 2 and value != first
    assert value[0] == '2026年4月: NT$0.00億'
    assert audit['status'] == 'success' and audit['fetched_at_epoch'] > old['fetched_at_epoch']


def test_failed_force_does_not_serve_old_observation_as_fresh(monthly):
    monthly['fetch']()
    monthly['now'] += 20
    monthly['failure'] = True
    value, failed = monthly['fetch'](force_refresh=True)
    assert value == [] and failed['status'] == 'error'
    attempts = len(monthly['calls'])
    monthly['now'] += 1
    value, cooldown = monthly['fetch']()
    assert value == [] and len(monthly['calls']) == attempts
    assert cooldown['status'] == 'unavailable'
    assert cooldown['event_kind'] == 'local_block'
    assert cooldown['http_request_sent'] is False


def test_core_payload_keeps_monthly_epoch_and_does_not_emit_fake_fresh_fetch(monthly):
    from data_fetch.yfinance_payload import finalize_and_cache_legacy_payload
    from data_fetch.service import StockDataService
    from provider_correlation import correlation_scope
    value, cold = monthly['fetch']('legacy')
    monthly['now'] += 60
    with correlation_scope(replace=True, ticker='2330.TW', fetch_id='monthly-warm-core-test'):
        value, warm = monthly['fetch']('legacy')
        data = {'ticker': '2330.TW', 'instrument_type': 'EQUITY',
                'recent_monthly_revenue': value, 'source_audit': [], 'current_price': 123.0}
        result = finalize_and_cache_legacy_payload(
            data=data, ticker='2330.TW', original_cache_key='fixture-monthly-core',
            provider=SimpleNamespace(name='fixture market'), fetch_started_epoch=monthly['now'],
            skip_optional_http=True, enrichment_audit=[], fmp_quote_audit=None,
            monthly_revenue_audit=warm, finmind_financial_fallback_audit=None)
        built = StockDataService()._build_result(
            FetchRequest.from_ticker('2330.TW', record_provider_sla=False), result, 0)
    assert built.data['source_freshness']['monthly_revenue']['fetched_at_epoch'] == cold['fetched_at_epoch']
    entries = [a for a in built.source_audit if a['source'] == 'monthly_revenue']
    assert len(entries) == 1 and entries[0]['status'] == 'skipped_fresh_cache'
    assert entries[0]['fetch_id'] == 'monthly-warm-core-test'
    assert entries[0]['http_request_count'] == 0


def test_concurrent_readers_share_one_sdk_observation(monthly):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: monthly['fetch'](), range(6)))
    assert len(monthly['calls']) == 1
    assert sum(a['status'] == 'success' for _, a in results) == 1
    assert sum(a['status'] == 'skipped_fresh_cache' for _, a in results) == 5
    assert all(value == results[0][0] for value, _ in results)


def test_calendar_month_change_does_not_reuse_previous_query_namespace(monthly):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monthly['now'] = datetime(2026, 10, 31, 23, 59, tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
    monthly['fetch']()
    monthly['now'] += 120
    _, audit = monthly['fetch']()
    assert len(monthly['calls']) == 2 and audit['cache_hit'] is False


def test_forced_fetch_keeps_provider_admission_guard(monthly, monkeypatch):
    import source_audit
    from provider_resilience import ProviderRateLimitOpenError
    monthly['fetch']()

    def blocked(*args, **kwargs):
        raise ProviderRateLimitOpenError('fixture provider quota remains blocked')

    monkeypatch.setattr(source_audit, 'call_provider_with_resilience', blocked)
    value, audit = monthly['fetch'](force_refresh=True)
    assert value == [] and len(monthly['calls']) == 1
    assert audit['status'] == 'unavailable'
    assert audit['provider_admission_blocked'] is True
    assert audit['http_request_sent'] is False


def test_normal_core_quote_updates_preserve_monthly_age_and_force_really_fetches(monthly, monkeypatch):
    from test_data_fetch_fixtures import FakeProvider, _patch_common_fetch_dependencies
    from data_fetch import yfinance_core_fetch as core
    _patch_common_fetch_dependencies(monkeypatch, resolved_ticker='2330.TW')
    monkeypatch.setattr(core.time_module, 'time', lambda: monthly['now'])
    monkeypatch.setattr(core, 'DataLoader', monthly['loader'])
    provider = FakeProvider('2330.TW')
    first = core.fetch_stock_data('2330.TW', skip_optional_http=True, market_data_provider=provider)
    assert 'error' not in first
    monthly['now'] += 120
    second = core.fetch_stock_data('2330.TW', skip_optional_http=True, market_data_provider=provider)
    assert 'error' not in second and len(monthly['calls']) == 1
    assert second['recent_monthly_revenue'] == first['recent_monthly_revenue']
    assert second['source_freshness']['monthly_revenue']['fetched_at_epoch'] == first['source_freshness']['monthly_revenue']['fetched_at_epoch']
    assert second['source_freshness']['market_data']['fetched_at_epoch'] == monthly['now']
    monthly['amount'] = 200000000
    monthly['now'] += 120
    third = core.fetch_stock_data('2330.TW', skip_optional_http=True, market_data_provider=provider, force_refresh=True)
    assert 'error' not in third and len(monthly['calls']) == 2
    assert third['recent_monthly_revenue'] != first['recent_monthly_revenue']
    assert third['source_freshness']['monthly_revenue']['fetched_at_epoch'] == monthly['now']
