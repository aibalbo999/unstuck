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
    data['daily_market_data'] = {'ticker': '6214.TW', 'as_of': '2026-10-05',
        'source': 'synthetic dated market fixture', 'bars': [
            {'date': '2026-10-05', 'open': 100, 'high': 100, 'low': 100,
             'close': 100, 'volume': 0}]}
    from fixtures.official_price_cache import observation
    data['daily_market_data']['official_observation'] = observation()
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


def test_provisional_official_publication_is_returned_separately_without_cache_write(cached, monkeypatch):
    from datetime import datetime
    from market_evidence_policy import publication_observation
    from report_source_admission import institutional_admission
    data, writes = cached
    value, audit = observed()
    moment = datetime.fromisoformat('2026-10-05T22:00:00+08:00')
    now = moment.timestamp()
    monkeypatch.setattr(time, 'time', lambda: now)
    data.update(cache_generated_at_epoch=now, market_data_fetched_at_epoch=now)
    for source in data['source_freshness']:
        data['source_freshness'][source]['fetched_at_epoch'] = now if source != 'institutional_trading' else now - 86400
    old_institution = deepcopy(data['institutional_trading'])
    old_clock = data['source_freshness']['institutional_trading']['fetched_at_epoch']
    proof = value['latest_official_observation']['raw_evidence']
    proof['retrieved_at'] = '2026-10-05T14:00:00+00:00'
    value['publication_observation'] = publication_observation(
        '2026-10-05', moment=moment, provider='TWSE T86', retrieved_at=proof['retrieved_at'],
        raw_evidence=proof, ticker='6214.TW')
    value['latest_session_admission'] = institutional_admission(value, '2026-10-05')
    value.update(stale=True, coverage_status='partial', fetched_at_epoch=now)
    audit.update(status='degraded_enrichment', stale=True, coverage_status='partial',
                 fetched_at_epoch=now, latest_session_admission=value['latest_session_admission'])
    result, calls = run(cached, value, audit)
    assert len(calls) == 1 and not writes
    assert result.data['institutional_trading'] == old_institution
    assert result.data['source_freshness']['institutional_trading']['fetched_at_epoch'] == old_clock
    visible = result.data['institutional_publication_observation']
    assert visible['status'] == 'available_provisional'
    assert visible['observed_date'] == '2026-10-05'
    assert visible['retrieved_at'] == proof['retrieved_at']
    assert visible['raw_evidence'] == proof
    assert visible['eligible'] is visible['canonical_source_replaced'] is False


def test_market_cutoff_rechecks_provisional_price_through_outer_workflow(cached, monkeypatch):
    from datetime import datetime
    from fixtures.official_price_cache import observation
    data, writes = cached
    value, audit = observed()
    data['institutional_trading'] = value
    before_cutoff = datetime.fromisoformat('2026-10-05T22:29:00+08:00').timestamp()
    original_clock = before_cutoff - 60
    data.update(cache_generated_at_epoch=original_clock, market_data_fetched_at_epoch=original_clock)
    for item in data['source_freshness'].values():
        item.update(fetched_at_epoch=original_clock, stale=False)
    old_price = observation(retrieved_at='2026-10-05T10:00:00+00:00')
    data['daily_market_data']['official_observation'] = old_price
    monkeypatch.setattr(time, 'time', lambda: before_cutoff)
    retained, calls = run(cached, value, audit)
    assert not calls and not writes
    assert retained.data['source_freshness']['market_data']['price_source_admission']['eligible'] is False

    monkeypatch.setattr(time, 'time', lambda: before_cutoff + 120)
    core_calls = []
    def core(*args):
        core_calls.append(True)
        return ProviderResult('market_data', 'core', 'error', value={'error': 'temporary failure'})
    fallback, institution_calls = run(cached, value, audit, core=core)
    assert core_calls == [True] and not institution_calls
    assert fallback.data['daily_market_data']['official_observation'] == old_price
    market = fallback.data['source_freshness']['market_data']
    assert market['fetched_at_epoch'] == original_clock and market['stale']
    assert market['price_source_admission']['reason'] == 'official_price_observation_is_provisional'
    assert not writes

    data['daily_market_data']['official_observation'] = observation(retrieved_at='2026-10-05T14:30:30+00:00')
    # At 22:31 the institutional fixture's default 22:45 receipt would be in
    # the future. Model a real already-acquired post-cutoff original instead.
    from official_response_evidence import archive_response, read_response
    institution_proof = value['latest_official_observation']['raw_evidence']
    value['latest_official_observation']['raw_evidence'] = archive_response(
        read_response(institution_proof), source_url=institution_proof['source_url'],
        retrieved_at='2026-10-05T14:30:30+00:00', http_status=200)
    healthy, calls = run(cached, value, audit)
    assert not calls and not writes
    assert healthy.data['source_freshness']['market_data']['price_source_admission']['eligible'] is True
    assert healthy.data['source_freshness']['market_data']['fetched_at_epoch'] == original_clock


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'future', 'malformed'])
def test_market_cutoff_missing_or_invalid_price_proof_uses_core_not_institution_only(cached, damage):
    data, writes = cached
    value, audit = observed()
    data['institutional_trading'] = value
    data['source_freshness']['institutional_trading'].update(fetched_at_epoch=NOW, stale=False)
    official = data['daily_market_data']['official_observation']
    if damage == 'missing':
        official.pop('raw_evidence')
    elif damage == 'corrupt':
        official['raw_evidence']['raw_response_sha256'] = '0' * 64
    elif damage == 'future':
        official['raw_evidence']['retrieved_at'] = '2026-10-06T15:00:00+00:00'
    else:
        data['daily_market_data']['official_observation'] = 'invalid saved structure'
    before = deepcopy(data)
    core_calls = []
    def core(*args):
        core_calls.append(True)
        return ProviderResult('market_data', 'core', 'error', value={'error': 'temporary failure'})
    result, calls = run(cached, value, audit, core=core)
    assert core_calls == [True] and not calls and not writes
    assert result.data['source_freshness']['market_data']['stale'] is True
    assert data == before
