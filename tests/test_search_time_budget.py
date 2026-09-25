"""A search's total deadline spans providers and fallback queries."""
import asyncio
from datetime import datetime, timezone, timedelta
import time

import pytest
import external_search_providers as search


@pytest.fixture
def configured(monkeypatch):
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(search, 'async_client', Client)
    monkeypatch.setattr(search, '_provider_configured', lambda provider: True)
    monkeypatch.setattr(search, '_provider_order', lambda: ['google_news_rss', 'gdelt', 'yahoo_rss'])


def record(number):
    return search.SearchResult('台積電營收展望 ' + str(number), '台積電營收更新',
                               'https://publisher.test/' + str(number), 'Publisher',
                               (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), 'google_news_rss')


def test_catalyst_queries_share_one_deadline_and_keep_earlier_evidence(configured, monkeypatch):
    now = [100.0]
    monkeypatch.setenv('WEB_SEARCH_TOTAL_TIMEOUT_SECONDS', '2')
    monkeypatch.setattr(search, 'monotonic', lambda: now[0], raising=False)
    monkeypatch.setattr(search, '_provider_order', lambda: ['google_news_rss', 'gdelt'])
    calls = []
    async def fetch(client, provider, query, **kwargs):
        calls.append((provider, query))
        now[0] += 0.8
        return [record(len(calls))]
    monkeypatch.setattr(search, '_fetch_provider_results', fetch)
    diagnostics = {}
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        '2330.TW', '台積電', {'official_name': '台積電'}, diagnostics=diagnostics))
    assert len(calls) == 3  # second query has only the original budget remainder
    assert calls[0][1] != calls[-1][1]
    assert 'https://publisher.test/1' in {r['link'] for r in result}
    assert diagnostics['search_budget_exhausted'] is True


def test_direct_waterfall_without_deadline_gets_bounded_default(configured, monkeypatch):
    now = [100.0]
    monkeypatch.setenv('WEB_SEARCH_TOTAL_TIMEOUT_SECONDS', '1')
    monkeypatch.setattr(search, 'monotonic', lambda: now[0], raising=False)
    calls = []
    async def fetch(client, provider, query, **kwargs):
        calls.append(provider)
        now[0] += 2
        return [record(1)]
    monkeypatch.setattr(search, '_fetch_provider_results', fetch)
    result = asyncio.run(search.fetch_web_search_results_async('台積電'))
    assert calls == ['google_news_rss']
    assert result[0].link == 'https://publisher.test/1'


def test_slow_provider_is_cancelled_at_total_deadline_and_keeps_partial_results(configured, monkeypatch):
    calls = []
    stopped = []
    async def fetch(client, provider, query, **kwargs):
        calls.append(provider)
        if len(calls) == 1:
            return [record(1)]
        try:
            await asyncio.sleep(10)
        finally:
            stopped.append(provider)
    monkeypatch.setattr(search, '_fetch_provider_results', fetch)
    started = time.monotonic()
    result = asyncio.run(search.fetch_web_search_results_async('台積電', deadline=started + 0.05))
    assert time.monotonic() - started < 0.5
    assert calls == ['google_news_rss', 'gdelt']
    assert stopped == ['gdelt']
    assert result[0].link == 'https://publisher.test/1'


def test_caller_cancellation_propagates_without_starting_next_provider(configured, monkeypatch):
    calls = []
    async def scenario():
        entered = asyncio.Event()
        async def fetch(client, provider, query, **kwargs):
            calls.append(provider)
            entered.set()
            await asyncio.sleep(10)
        monkeypatch.setattr(search, '_fetch_provider_results', fetch)
        task = asyncio.create_task(search.fetch_alternative_search_catalysts_async('2330.TW', '台積電', {}))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert calls == ['google_news_rss']


@pytest.mark.parametrize('configured_seconds, spent', [('100000', 61), ('nan', 31), ('invalid', 31), ('-5', 2)])
def test_total_budget_configuration_is_finite_and_bounded(configured, monkeypatch, configured_seconds, spent):
    now = [100.0]
    monkeypatch.setenv('WEB_SEARCH_TOTAL_TIMEOUT_SECONDS', configured_seconds)
    monkeypatch.setattr(search, 'monotonic', lambda: now[0])
    calls = []
    async def fetch(*args, **kwargs):
        calls.append(1)
        now[0] += spent
        return []
    monkeypatch.setattr(search, '_fetch_provider_results', fetch)
    assert asyncio.run(search.fetch_web_search_results_async('台積電')) == []
    assert calls == [1]


def test_expired_catalyst_deadline_returns_audited_empty_without_http(configured, monkeypatch):
    calls = []
    async def fetch(*args, **kwargs):
        calls.append(1)
        return [record(1)]
    monkeypatch.setattr(search, '_fetch_provider_results', fetch)
    audit = {}
    result = asyncio.run(search.fetch_alternative_search_catalysts_async(
        '2330.TW', '台積電', {}, diagnostics=audit, deadline=time.monotonic() - 1))
    assert result == [] and not calls
    assert audit['search_budget_exhausted'] is True
    assert audit['raw_count'] == audit['usable_count'] == 0
