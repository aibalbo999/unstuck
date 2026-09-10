import asyncio
from types import SimpleNamespace

import pytest

from data_fetch import FetchResult, FetchRequest, StockDataService
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import ProviderResult
from watchlist_radar_data import RadarDataCache, trigger_sources


def test_source_plan_keeps_unknown_conditions_full_and_disabled_out():
    assert trigger_sources([{'type': 'vix_above'}, {'type': 'foreign_sell_streak'}]) == ('institutional_trading', 'macro_indicators')
    assert trigger_sources([{'type': 'daily_screener'}, {'type': 'vix_above', 'enabled': False}]) == ()
    assert trigger_sources([{'type': 'report_catalyst', 'trigger_condition': '月營收低於5億元'}]) == ('full',)
    assert trigger_sources([{'type': 'revenue_record_high'}]) == ('market_data', 'monthly_revenue')


def test_cache_shares_requests_expires_and_never_reuses_failed_or_prior_day_data():
    tick = [0.0]
    calls = []
    fail = [False]
    class Service:
        async def fetch_async(self, request):
            calls.append(request)
            await asyncio.sleep(0)
            assert request.options.force_refresh is True
            return FetchResult(request=request, data={'error': 'bad'} if fail[0] else {'ticker': request.ticker, 'value': len(calls)})
    service = Service()
    cache = RadarDataCache(clock=lambda: tick[0])
    async def fetch(day='2026-09-09'):
        return await cache.fetch(service, '5314.TWO', ('full',), day)
    async def concurrent():
        return await asyncio.gather(fetch(), fetch())
    assert asyncio.run(concurrent())[0]['value'] == 1
    tick[0] = 899
    assert asyncio.run(fetch())['value'] == 1
    tick[0] = 901
    assert asyncio.run(fetch())['value'] == 2
    assert asyncio.run(fetch('2026-09-10'))['value'] == 3
    tick[0] += 901
    fail[0] = True
    with pytest.raises(RuntimeError):
        asyncio.run(fetch('2026-09-10'))
    with pytest.raises(RuntimeError):
        asyncio.run(fetch('2026-09-10'))
    assert len(calls) == 4  # failure cooldown, not stale success
    tick[0] += 61
    fail[0] = False
    assert asyncio.run(fetch('2026-09-10'))['value'] == 5


def test_selective_provider_fetch_avoids_financial_and_news_and_preserves_audit():
    calls = []
    class Provider:
        primary_source_provider = True
        def __init__(self, source): self.source = source
        def supports(self, request): return True
        async def fetch_async(self, request, context=None):
            calls.append(self.source)
            return ProviderResult(self.source, 'test', 'success', {'indicators': {'vix': {'value': 35}}}, {'source': self.source, 'status': 'success'})
    service = StockDataService(registry=ProviderRegistry([Provider('macro_indicators'), Provider('market_data'), Provider('news')]))
    result = asyncio.run(service.fetch_radar_async(FetchRequest.from_ticker('6409.TW', record_provider_sla=False), ('macro_indicators',)))
    assert calls == ['macro_indicators']
    assert result.data['macro_indicators']['indicators']['vix']['value'] == 35
    assert result.source_audit[0]['source'] == 'macro_indicators'


def test_radar_log_scope_propagates_into_threads_and_restores(monkeypatch):
    import runtime_logging as log
    lines = []
    monkeypatch.setattr(log, 'get_runtime_logger', lambda: SimpleNamespace(info=lines.append))
    async def run():
        with log.runtime_log_scope('背景雷達 5314.TWO'):
            await asyncio.to_thread(log.log_runtime_message, '核心資料完成')
        log.log_runtime_message('分析仍在執行')
    asyncio.run(run())
    assert lines == ['[背景雷達 5314.TWO] 核心資料完成', '分析仍在執行']


def test_selective_market_monthly_and_calendar_have_evaluator_fields():
    import pandas as pd
    from watchlist_triggers import evaluate_watchlist_triggers
    calls = []
    class Stock:
        calendar = {'Earnings Date': [__import__('datetime').datetime(2026, 9, 10)]}
        def history(self, **kwargs):
            calls.append('history')
            return pd.DataFrame({'Close': [110, 109, 108, 107, 100], 'Volume': [1, 2, 3, 4, 20]}, index=pd.date_range('2026-09-01', periods=5))
    class Provider:
        primary_source_provider = True
        def __init__(self, source): self.source = source
        def supports(self, request): return True
        async def fetch_async(self, request, context=None):
            calls.append(self.source)
            value = {'kind': 'yfinance_snapshot', 'stock': Stock(), 'info': {}, 'is_valid': True} if self.source == 'market_data' else ['2026年6月: NT$5億', '2026年7月: NT$6億', '2026年8月: NT$7億']
            return ProviderResult(self.source, 'test', 'success', value, {'source': self.source, 'status': 'success'})
    service = StockDataService(registry=ProviderRegistry([Provider('market_data'), Provider('monthly_revenue')]))
    result = asyncio.run(service.fetch_radar_async(FetchRequest.from_ticker('6409.TW', record_provider_sla=False), ('market_data', 'monthly_revenue')))
    assert calls == ['market_data', 'history', 'monthly_revenue']
    events = evaluate_watchlist_triggers({'ticker': '6409.TW', 'pipeline': 'v1', 'triggers': [{'type': 'price_below_sma', 'period': 5}, {'type': 'revenue_record_high'}]}, result.data, evaluation_date='2026-09-09')
    assert len(events) == 2 and all(event['matched'] for event in events)
    result = asyncio.run(service.fetch_radar_async(FetchRequest.from_ticker('6409.TW', record_provider_sla=False), ('event_calendar',)))
    assert 'event_calendar' in result.data


def test_monitor_rechecks_false_condition_after_ttl_on_same_day(monkeypatch):
    import watchlist_service as service
    tick = [0]
    calls = []
    class Data:
        _watchlist_radar_cache = RadarDataCache(clock=lambda: tick[0])
        async def fetch_async(self, request):
            calls.append(request)
            return FetchResult(request=request, data={'macro_indicators': {'indicators': {'vix': {'value': 20 if len(calls) == 1 else 35}}}})
    monkeypatch.setattr(service, '_sync_store_config', lambda: None)
    monkeypatch.setattr(service, 'list_watchlist', lambda: {'items': [{'ticker': 'TEST', 'enabled': True, 'pipeline': 'v1', 'triggers': [{'type': 'vix_above', 'threshold': 30}]}]})
    monkeypatch.setattr(service.time, 'sleep', lambda _: None)
    from datetime import datetime
    kwargs = dict(data_service=Data(), now=datetime(2026, 9, 9, 16, 0, tzinfo=service.TAIPEI), create_job=lambda *a: 'job-test', find_active_job=lambda *a: {}, task_queue=SimpleNamespace(enqueue=lambda *a, **kw: None), run_stock_analysis_job=lambda *a: None)
    assert asyncio.run(service.monitor_watchlist_triggers(**kwargs))['queued'] == []
    tick[0] = 301
    assert len(asyncio.run(service.monitor_watchlist_triggers(**kwargs))['queued']) == 1
    assert len(calls) == 2


def test_stale_fallback_does_not_become_fresh_radar_data():
    class Service:
        async def fetch_async(self, request):
            return FetchResult(request=request, data={'ticker': request.ticker, '_cache_hit': True, 'data_freshness': {'stale_sources': ['market_data']}})
    with pytest.raises(RuntimeError):
        asyncio.run(RadarDataCache().fetch(Service(), 'TEST', ('full',), '2026-09-09'))


def test_empty_calendar_or_swallowed_provider_error_is_not_success():
    from data_fetch.radar import _market_fields
    class Stock:
        @property
        def calendar(self): raise RuntimeError('provider timeout')
    with pytest.raises(RuntimeError, match='日曆'):
        _market_fields({'stock': Stock(), 'info': {}}, calendar=True)


def test_mixed_full_trigger_obeys_fastest_source_ttl_and_refreshes_canonical_cache():
    tick = [0]
    calls = []
    class Service:
        async def fetch_radar_async(self, request, sources):
            calls.append(request)
            assert request.options.force_refresh is True
            return FetchResult(request=request, data={'ticker': request.ticker})
    service = Service()
    sources = trigger_sources([{'type': 'report_catalyst'}, {'type': 'vix_above'}])
    cache = RadarDataCache(clock=lambda: tick[0])
    asyncio.run(cache.fetch(service, 'TEST', sources, '2026-09-09'))
    tick[0] = 301
    asyncio.run(cache.fetch(service, 'TEST', sources, '2026-09-09'))
    assert len(calls) == 2
