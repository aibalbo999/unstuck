"""A new normal request must not hide optional gaps behind a fresh core cache."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from data_fetch import CallableProvider, FetchRequest, ProviderRegistry, ProviderResult, StockDataService
from data_fetch import workflow
from data_freshness import assess_cached_financial_data, source_is_stale
from fixtures.data_payloads import FRESH_AT_EPOCH, fresh_audited_payload


@pytest.fixture
def cached_request(monkeypatch):
    import data_freshness
    import cache_store
    from cache_backends import InMemoryCache

    clock = [float(FRESH_AT_EPOCH)]
    monkeypatch.setattr(data_freshness.time_module, 'time', lambda: clock[0])
    cache_store.set_cache_backend(InMemoryCache())
    data = fresh_audited_payload(ticker='AAPL', company_name='Apple Inc.')
    data.update(cache_generated_at_epoch=clock[0], market_data_fetched_at_epoch=clock[0])
    data['recent_catalysts'] = [{'title': 'Apple Inc. (AAPL) published results',
                               'date': datetime.fromtimestamp(clock[0], timezone.utc).isoformat(),
                               'link': 'https://www.apple.com/newsroom/fixture-results/'}]
    data['source_freshness']['recent_catalysts'] = {'fetched_at_epoch': clock[0]}
    for source in ('dynamic_peer_metrics', 'pe_river_chart'):
        data['source_freshness'][source] = {'fetched_at_epoch': clock[0]}
    monkeypatch.setattr(workflow, 'get_cache_json', lambda key: deepcopy(data))
    writes = []
    monkeypatch.setattr(workflow, 'cache_financial_payload', lambda value, ticker: writes.append(deepcopy(value)))
    fresh, assessment = assess_cached_financial_data(data, 'AAPL')
    assert fresh, assessment['stale_sources']
    yield data, clock, writes
    cache_store.reset_cache_store_for_tests()


def request_with(provider, *, skip=False, extras=()):
    def unexpected_core(*args):
        pytest.fail('A fresh core must not be acquired again to fill an optional gap')
    registry = ProviderRegistry([CallableProvider('market_data', 'core', unexpected_core), provider, *extras])
    return asyncio.run(StockDataService(registry=registry).fetch_async(
        FetchRequest.from_ticker('AAPL', skip_optional_http=skip, record_provider_sla=False)))


def conference_result(status='success', *, epoch=FRESH_AT_EPOCH, **audit):
    value = {'period': '2026Q1', 'transcript_excerpt': 'Published conference text'} if status == 'success' else {}
    return ProviderResult('earnings_call', 'conference fixture', status, value=value,
                          audit={'source': 'earnings_call', 'provider': 'conference fixture', 'status': status,
                                 'record_count': 2 if value else 0, 'fetched_at_epoch': epoch, **audit})


@pytest.mark.parametrize('initial', ['missing', 'expired'])
def test_normal_request_recovers_missing_or_expired_optional_source(cached_request, initial):
    data, clock, writes = cached_request
    if initial == 'expired':
        data['earnings_call'] = {'period': '2025Q4', 'transcript_excerpt': 'Older conference'}
        data['source_freshness']['earnings_call'] = {'fetched_at_epoch': clock[0] - 40 * 86400}
    assert source_is_stale(data, 'earnings_call', 'AAPL')
    calls = []
    def acquire(request, context):
        calls.append(request)
        assert context['data']['_cache_hit'] is True
        return conference_result()
    healthy_news = CallableProvider('recent_catalysts', 'Free news waterfall',
                                    lambda *args: pytest.fail('Fresh news should stay cached'))
    result = request_with(CallableProvider('earnings_call', 'conference fixture', acquire), extras=(healthy_news,))
    assert len(calls) == 1, 'Fresh market data incorrectly suppressed optional recovery'
    assert calls[0].options.force_refresh is False
    assert result.data['earnings_call'] == conference_result().value
    assert result.data['source_freshness']['earnings_call']['fetched_at_epoch'] == clock[0]
    assert result.data['source_freshness']['market_data']['fetched_at_epoch'] == FRESH_AT_EPOCH
    assert writes and writes[-1]['earnings_call'] == conference_result().value


@pytest.mark.parametrize('skip,healthy', [(True, False), (False, True)])
def test_explicit_skip_and_healthy_source_do_not_fetch(cached_request, skip, healthy):
    data, clock, writes = cached_request
    if healthy:
        data['earnings_call'] = conference_result().value
        data['source_freshness']['earnings_call'] = {'fetched_at_epoch': clock[0]}
    result = request_with(CallableProvider('earnings_call', 'conference fixture',
                          lambda *args: pytest.fail('Unnecessary optional acquisition')), skip=skip)
    assert result.cache_hit
    assert not writes, 'No executed providers must not rewrite the cache or create fetch summaries'


def test_failed_recovery_preserves_old_evidence_and_its_timestamp(cached_request):
    data, clock, writes = cached_request
    old_epoch = clock[0] - 40 * 86400
    old = {'period': '2025Q4', 'transcript_excerpt': 'Older conference'}
    data['earnings_call'] = deepcopy(old)
    data['source_freshness']['earnings_call'] = {'fetched_at_epoch': old_epoch}
    calls = []
    def failed(*args):
        calls.append(True)
        return conference_result('error', epoch=None, error_kind='timeout', http_request_sent=True)
    result = request_with(CallableProvider('earnings_call', 'conference fixture', failed))
    assert len(calls) == 1
    assert result.data['earnings_call'] == old
    assert result.data['source_freshness']['earnings_call']['fetched_at_epoch'] == old_epoch
    audit = [a for a in result.data['source_audit'] if a['source'] == 'earnings_call'][-1]
    assert audit['status'] == 'degraded_enrichment' and audit['stale'] is True
    assert audit['error_kind'] == 'timeout'


def test_repeated_normal_requests_respect_provider_error_backoff(cached_request):
    from shared_provider_cache import shared_fetch
    data, clock, writes = cached_request
    network = []
    def acquire():
        network.append(clock[0])
        raise TimeoutError('temporary source failure')
    def fetch(*args):
        value, meta = shared_fetch('optional-recovery-test', acquire, freshness_seconds=60,
                                  retention_seconds=60, error_retry_seconds=120, lock_wait_seconds=0)
        return conference_result('error', epoch=None, **{k: v for k, v in meta.items()
                                                       if k != 'fetched_at_epoch'})
    provider = CallableProvider('earnings_call', 'conference fixture', fetch)
    for advance in (0, 30):
        clock[0] += advance
        request_with(provider)
    assert network == [FRESH_AT_EPOCH]
    clock[0] += 91
    request_with(provider)
    assert network == [FRESH_AT_EPOCH, FRESH_AT_EPOCH + 121]
