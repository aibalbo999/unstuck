"""A stale institutional source must not force healthy core data to refetch."""
import asyncio
from copy import deepcopy
import time

import pytest

from data_fetch import CallableProvider, FetchRequest, ProviderRegistry, ProviderResult, StockDataService
from data_fetch import workflow
from data_freshness import assess_cached_financial_data
from fixtures.data_payloads import fresh_audited_payload
from fixtures.institutional_cache import NOW, observed


@pytest.fixture
def cached(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    monkeypatch.setattr(time, 'time', lambda: NOW)
    cache_store.set_cache_backend(InMemoryCache())
    data = fresh_audited_payload(ticker='6214.TW', company_name='精誠')
    data.update(instrument_type='EQUITY', company_identity={
        'ticker': '6214.TW', 'stock_id': '6214', 'instrument_type': 'EQUITY'},
        cache_generated_at_epoch=NOW, market_data_fetched_at_epoch=NOW)
    for source in ('market_data', 'financial_statements', 'monthly_revenue',
                   'dynamic_peer_metrics', 'pe_river_chart', 'twse_official'):
        data['source_freshness'][source] = {'fetched_at_epoch': NOW}
    data['source_audit'] = []
    data['institutional_trading'] = {'latest_date': '2026-10-02', 'stale': True,
                                    'original_limited_observation': True}
    data['source_freshness']['institutional_trading'] = {'fetched_at_epoch': NOW - 86400, 'stale': True}
    fresh, assessment = assess_cached_financial_data(data, '6214.TW')
    assert not fresh and assessment['stale_sources'] == ['institutional_trading'], assessment
    monkeypatch.setattr(workflow, 'get_cache_json', lambda key: deepcopy(data))
    writes = []
    monkeypatch.setattr(workflow, 'cache_financial_payload', lambda value, ticker: writes.append(deepcopy(value)))
    yield data, writes
    cache_store.reset_cache_store_for_tests()


def run(cached, value, audit, *, force=False, extras=(), core=None, skip=True):
    calls = []
    def acquire(request, context):
        from provider_correlation import current_audit_correlation
        calls.append(request)
        return ProviderResult('institutional_trading', 'FinMind', audit['status'],
                              value=deepcopy(value), audit={**deepcopy(audit), **current_audit_correlation()})
    def forbidden(*args):
        pytest.fail('Healthy market and financial data should not be fetched to update institutions')
    service = StockDataService(registry=ProviderRegistry([
        CallableProvider('market_data', 'core', core or forbidden),
        CallableProvider('institutional_trading', 'FinMind', acquire), *extras]))
    result = asyncio.run(service.fetch_async(FetchRequest.from_ticker(
        '6214.TW', force_refresh=force, skip_optional_http=skip, record_provider_sla=False)))
    return result, calls


def test_new_normal_request_recovers_institutions_without_full_core_fetch(cached):
    data, writes = cached
    value, audit = observed()
    before = deepcopy(data)
    result, calls = run(cached, value, audit)
    assert len(calls) == 1 and calls[0].options.force_refresh is False
    assert result.data['institutional_trading'] == value
    assert assess_cached_financial_data(result.data, '6214.TW')[0]
    for field in ('current_price', 'years', 'revenue_history', 'earnings_call'):
        assert result.data.get(field) == before.get(field)
    assert result.data['source_freshness']['market_data']['fetched_at_epoch'] == NOW
    assert writes and writes[-1]['institutional_trading'] == value
    assert data == before, 'The input cache must not be mutated in place'


@pytest.mark.parametrize('failure', ['timeout', 'partial', 'wrong_identity', 'corrupt_evidence'])
def test_failed_or_unverified_recovery_keeps_old_values_and_age(cached, failure):
    data, writes = cached
    value, audit = observed()
    if failure == 'timeout':
        value = None
        audit.update(status='error', error_kind='timeout', record_count=0, fetched_at_epoch=None)
    elif failure == 'partial':
        value['daily_category_observations'].pop()
    elif failure == 'wrong_identity':
        value['latest_official_observation']['ticker'] = '2330.TW'
    else:
        value['latest_official_observation']['raw_evidence']['raw_response_sha256'] = '0' * 64
    result, calls = run(cached, value, audit)
    assert len(calls) == 1
    assert result.data['institutional_trading'] == data['institutional_trading']
    assert result.data['source_freshness']['institutional_trading']['fetched_at_epoch'] == NOW - 86400
    assert not assess_cached_financial_data(result.data, '6214.TW')[0]
    assert not writes, 'An unsuccessful replacement must not extend the shared payload cache'
    last = [a for a in result.source_audit if a['source'] == 'institutional_trading'][-1]
    assert last['status'] in {'error', 'degraded_enrichment'}
    assert last.get('error_kind') == ('timeout' if failure == 'timeout' else 'institutional_recovery_validation_failed')


@pytest.mark.parametrize('cause', ['market_expired', 'force', 'identity_conflict'])
def test_other_core_requirements_still_use_normal_full_fetch(cached, cause):
    data, _ = cached
    if cause == 'market_expired':
        data['market_data_fetched_at_epoch'] = NOW - 86400 * 10
        data['source_freshness']['market_data']['fetched_at_epoch'] = NOW - 86400 * 10
    elif cause == 'identity_conflict':
        data['company_identity']['ticker'] = '2330.TW'
    core_calls = []
    def core(*args):
        core_calls.append(True)
        return ProviderResult('market_data', 'core', 'error', value={'error': 'source unavailable'})
    value, audit = observed()
    result, calls = run(cached, value, audit, force=cause == 'force', core=core)
    assert core_calls == [True] and not calls


def test_optional_gaps_are_still_acquired_after_institutional_recovery(cached):
    calls = []
    def conference(request, context):
        calls.append(True)
        return ProviderResult('earnings_call', 'conference fixture', 'success',
                              value={'transcript_excerpt': 'Current conference text'},
                              audit={'source': 'earnings_call', 'provider': 'conference fixture',
                                     'status': 'success', 'record_count': 1, 'fetched_at_epoch': NOW})
    result, institution = run(cached, *observed(), skip=False, extras=(
        CallableProvider('earnings_call', 'conference fixture', conference),))
    assert len(institution) == 1 and calls == [True]
    assert result.data['earnings_call']['transcript_excerpt'] == 'Current conference text'


@pytest.mark.parametrize('failed', [False, True])
def test_actual_institutional_provider_keeps_cache_and_error_backoff(cached, monkeypatch, failed):
    from data_fetch.taiwan_providers import InstitutionalTradingProvider
    from data_fetch import institutional_provider
    from data_fetch.market_sources import taiwan
    import official_institutional_source
    data, writes = cached
    value, _ = observed()
    calls = []
    def primary(ticker):
        calls.append(ticker)
        if failed:
            raise TimeoutError('source temporarily unavailable')
        return deepcopy(value)
    monkeypatch.setattr(taiwan, 'fetch_institutional_trading_trend', primary)
    monkeypatch.setattr(institutional_provider, 'call_provider_with_resilience',
                        lambda provider, fn, args, kwargs: fn(*args, **kwargs))
    monkeypatch.setattr(official_institutional_source, 'recover_institutional_observations',
                        lambda ticker, primary, **kwargs: (primary, {}))
    service = StockDataService(registry=ProviderRegistry([InstitutionalTradingProvider()]))
    for _ in range(2):
        result = asyncio.run(service.fetch_async(FetchRequest.from_ticker(
            '6214.TW', skip_optional_http=True, record_provider_sla=False)))
        if not failed:
            assert result.data['institutional_trading']['latest_session_admission']['eligible']
            assert assess_cached_financial_data(result.data, '6214.TW')[0]
            assert writes
            data.update(deepcopy(writes[-1]))
        else:
            assert not writes
            assert result.data['institutional_trading'] == data['institutional_trading']
    assert calls == ['6214.TW'], 'A second request must respect primary cache or error backoff'
