"""Outer cache must replay institutional receipts, not saved admission flags."""
from copy import deepcopy
from datetime import datetime
import json
import time

import pytest

from fixtures.institutional_cache import NOW, observed
from test_cached_institutional_recovery import cached, run


def install_current_cached_source(cached, damage='provisional'):
    from official_response_evidence import archive_response, read_response
    data, _ = cached
    value, _ = observed()
    official = value['latest_official_observation']
    proof = official['raw_evidence']
    original_acquired = datetime.fromisoformat('2026-10-05T18:00:00+08:00').timestamp()
    if damage == 'provisional':
        official['raw_evidence'] = archive_response(read_response(proof), source_url=proof['source_url'],
            retrieved_at='2026-10-05T10:00:00+00:00', http_status=200)
    elif damage == 'missing':
        official.pop('raw_evidence')
    elif damage == 'corrupt':
        proof['raw_response_sha256'] = '0' * 64
    elif damage == 'future_original':
        proof['retrieved_at'] = '2026-10-06T15:00:00+00:00'
    elif damage == 'other_issuer':
        body = json.loads(read_response(proof)); body['data'][0][0] = '2330'
        official['ticker'] = '2330.TW'
        official['raw_evidence'] = archive_response(json.dumps(body).encode(), source_url=proof['source_url'],
            retrieved_at=proof['retrieved_at'], http_status=200)
    elif damage == 'wrong_date':
        official['date'] = '2026-10-02'
    elif damage == 'wrong_market':
        official['market'] = 'TPEX'
    elif damage == 'malformed':
        value['latest_official_observation'] = ['invalid saved structure']
    elif damage == 'future_source_clock':
        original_acquired = NOW + 60
    value.update(fetched_at_epoch=original_acquired, stale=False)
    # This inherited approval is deliberately stale. It must never authorize a
    # cache hit after the actual original has changed or was acquired too early.
    assert value['latest_session_admission']['eligible'] is True
    data['institutional_trading'] = value
    data['source_freshness']['institutional_trading'] = {'fetched_at_epoch': original_acquired, 'stale': False}
    if damage == 'missing_source_clock':
        data['source_freshness']['institutional_trading'] = {'stale': False}
    return value, original_acquired


@pytest.mark.parametrize('damage', ['provisional', 'missing', 'corrupt', 'future_original',
                                   'other_issuer', 'wrong_date', 'wrong_market', 'malformed',
                                   'future_source_clock', 'missing_source_clock'])
def test_current_day_with_bad_original_recovers_only_institutions(cached, damage):
    from data_fetch.cache_session_alignment import assess_session_aligned_cache
    from data_freshness import assess_cached_financial_data
    data, writes = cached
    install_current_cached_source(cached, damage)
    before = deepcopy(data)
    fresh, assessment = assess_session_aligned_cache(data, '6214.TW',
        assessor=assess_cached_financial_data, now_epoch=NOW)
    assert fresh is False and assessment['stale_sources'] == ['institutional_trading']
    assert assessment['source_freshness']['institutional_trading']['institutional_source_admission']['eligible'] is False
    value, audit = observed()
    result, calls = run(cached, value, audit)
    assert len(calls) == 1 and calls[0].options.force_refresh is False
    assert result.data['institutional_trading'] == value
    assert result.data['source_freshness']['market_data']['fetched_at_epoch'] == NOW
    assert writes and writes[-1]['institutional_trading'] == value
    assert data == before


def test_provisional_original_failure_keeps_values_clock_and_does_not_call_core(cached):
    data, writes = cached
    old, acquired = install_current_cached_source(cached)
    before = deepcopy(data)
    _, audit = observed()
    audit.update(status='error', error_kind='timeout', fetched_at_epoch=None, record_count=0)
    result, calls = run(cached, None, audit)
    assert len(calls) == 1 and not writes
    assert result.data['institutional_trading'] == old
    assert result.data['source_freshness']['institutional_trading']['fetched_at_epoch'] == acquired
    assert result.data['source_freshness']['institutional_trading']['stale']
    assert data == before


def test_actual_post_cutoff_original_ignores_stale_saved_disapproval_and_stays_cached(cached):
    data, writes = cached
    value, audit = observed()
    value['latest_session_admission'] = {'eligible': False, 'reason': 'outdated saved flag'}
    data['institutional_trading'] = value
    data['source_freshness']['institutional_trading'] = {'fetched_at_epoch': NOW - 10, 'stale': False}
    before = deepcopy(data)
    result, calls = run(cached, *observed())
    assert not calls and not writes
    assert result.data['source_freshness']['institutional_trading']['institutional_source_admission']['eligible'] is True
    assert result.data['institutional_trading'] == value and data == before


def test_before_cutoff_provisional_is_displayable_but_not_admitted(cached, monkeypatch):
    from fixtures.official_price_cache import observation
    data, writes = cached
    old, acquired = install_current_cached_source(cached)
    now = datetime.fromisoformat('2026-10-05T22:00:00+08:00').timestamp()
    monkeypatch.setattr(time, 'time', lambda: now)
    data.update(cache_generated_at_epoch=now - 10, market_data_fetched_at_epoch=now - 10)
    for source, entry in data['source_freshness'].items():
        if source != 'institutional_trading':
            entry['fetched_at_epoch'] = now - 10
    data['daily_market_data']['official_observation'] = observation(retrieved_at='2026-10-05T10:00:00+00:00')
    result, calls = run(cached, *observed())
    assert not calls and not writes
    admission = result.data['source_freshness']['institutional_trading']['institutional_source_admission']
    assert admission['eligible'] is False and admission['reason'] == 'official_observation_is_provisional'
    assert result.data['institutional_trading'] == old
    assert result.data['source_freshness']['institutional_trading']['fetched_at_epoch'] == acquired


@pytest.mark.parametrize('failed', [False, True])
def test_provisional_receipt_recovery_keeps_provider_cache_and_backoff(cached, monkeypatch, failed):
    import asyncio
    import official_institutional_source
    from data_fetch import FetchRequest, ProviderRegistry, StockDataService, institutional_provider
    from data_fetch.market_sources import taiwan
    from data_fetch.taiwan_providers import InstitutionalTradingProvider
    data, writes = cached
    old, acquired = install_current_cached_source(cached)
    value, _ = observed()
    callbacks = []
    def primary(ticker):
        callbacks.append(ticker)
        if failed:
            raise TimeoutError('synthetic acquisition failure')
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
        if failed:
            assert not writes and result.data['institutional_trading'] == old
            assert result.data['source_freshness']['institutional_trading']['fetched_at_epoch'] == acquired
        else:
            assert writes and result.data['institutional_trading']['latest_session_admission']['eligible']
            data.update(deepcopy(writes[-1]))
    assert callbacks == ['6214.TW']
