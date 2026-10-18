"""Normal provider reads must advance partial originals without extending their age."""
import pytest

from data_fetch.types import FetchRequest


@pytest.fixture
def clock(monkeypatch):
    import cache_store
    import shared_provider_cache
    from cache_backends import InMemoryCache
    now = [1000.0]
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(shared_provider_cache.time, 'time', lambda: now[0])
    yield now
    cache_store.reset_cache_store_for_tests()


def receipt(*, complete=False, expires=2800.0, resume=True):
    return ([{'text': 'verified original'}], {
        'status': 'success' if complete else 'degraded_enrichment',
        'coverage_status': 'window_complete' if complete else 'partial',
        'progress_resume_possible': resume and not complete,
        'progress_fresh_until_epoch': expires,
        'progress_remaining_seconds': expires - 1000,
        'http_request_sent': True, 'http_request_count': 3,
        'request_observations': [{'method': 'GET', 'http_status': 200}],
    })


def test_normal_reads_resume_partial_before_verified_originals_expire(clock, monkeypatch):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    calls = []
    def acquire(self, ticker):
        calls.append(ticker)
        return receipt(complete=len(calls) > 1)
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', acquire)
    provider = TwseCompanyHistoryProvider()
    request = FetchRequest.from_ticker('2851.TW')
    first = provider.fetch(request)
    clock[0] += 30
    warm = provider.fetch(request)
    assert calls == ['2851.TW']
    assert warm.audit['http_request_sent'] is False
    clock[0] += 31
    resumed = provider.fetch(request)
    assert len(calls) == 2, 'Partial aggregate cache prevented missing-original recovery'
    assert first.status == 'degraded_enrichment' and resumed.status == 'success'


def test_cached_observation_reports_zero_current_http_and_no_replayed_attempts(clock, monkeypatch):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', lambda *a: receipt(complete=True))
    provider = TwseCompanyHistoryProvider()
    cold = provider.fetch(FetchRequest.from_ticker('2851.TW'))
    warm = provider.fetch(FetchRequest.from_ticker('2851.TW'))
    assert warm.status == 'skipped_fresh_cache'
    assert warm.audit['fetched_at_epoch'] == cold.audit['fetched_at_epoch']
    assert warm.audit['http_request_count'] == 0
    assert warm.audit['request_observations'] == []


def test_completed_aggregate_does_not_extend_replayed_original_expiry(clock, monkeypatch):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    calls = []
    def acquire(*args):
        calls.append(clock[0])
        return receipt(complete=True, expires=1010 if len(calls) == 1 else 2811)
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', acquire)
    provider = TwseCompanyHistoryProvider()
    request = FetchRequest.from_ticker('2851.TW')
    provider.fetch(request)
    clock[0] = 1011
    assert provider.fetch(request).audit['cache_hit'] is False
    assert calls == [1000, 1011]


@pytest.mark.parametrize('resume', [False, None, 'true'])
def test_no_qualified_progress_keeps_existing_partial_backoff(clock, monkeypatch, resume):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    calls = []
    def acquire(*args):
        calls.append(1)
        result = receipt(resume=False)
        result[1]['progress_resume_possible'] = resume
        return result
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', acquire)
    provider = TwseCompanyHistoryProvider()
    provider.fetch(FetchRequest.from_ticker('2851.TW'))
    clock[0] += 61
    provider.fetch(FetchRequest.from_ticker('2851.TW'))
    assert calls == [1]


def test_expired_retained_original_is_not_returned_when_recovery_fails(clock, monkeypatch):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    calls = []
    def acquire(*args):
        calls.append(1)
        if len(calls) > 1:
            raise TimeoutError()
        return receipt(complete=True, expires=1010)
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', acquire)
    provider = TwseCompanyHistoryProvider()
    request = FetchRequest.from_ticker('2851.TW')
    provider.fetch(request)
    clock[0] = 1011
    result = provider.fetch(request)
    assert len(calls) == 2
    assert result.value == []
    assert result.status != 'success' and result.audit['stale'] is True


def test_failed_original_details_survive_ledger_without_body_or_query_secrets(clock):
    import json
    import sqlite3
    import provider_sla
    from provider_acquisition import observation_kind
    provider_sla.record_source_audit_entries([{
        'source': 'recent_catalysts', 'provider': 'TWSE company announcement history',
        'status': 'degraded_enrichment', 'record_count': 1,
        'http_request_sent': True, 'http_request_count': 2,
        'progress_resume_possible': True, 'progress_missing_count': 1,
        'request_observations': [{
            'url': 'https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?secret=DO_NOT_SAVE',
            'method': 'GET', 'status': 'error', 'error_kind': 'timeout',
            'http_status': 200, 'http_request_sent': True, 'http_request_count': 1,
            'elapsed_seconds': 4.0, 'remaining_seconds': 6.0,
            'response_complete': False, 'response_bytes': 130,
            'request_fingerprint': 'a' * 64,
            'body': 'DO_NOT_SAVE', 'headers': {'Authorization': 'DO_NOT_SAVE'},
        }],
        'source_record_archive': [{'body': 'DO_NOT_SAVE'}],
    }])
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        text, = db.execute('SELECT details_json FROM provider_sla_events ORDER BY id DESC LIMIT 1').fetchone()
    details = json.loads(text)
    assert 'DO_NOT_SAVE' not in text and 'source_record_archive' not in details
    assert details['http_request_count'] == 2
    attempt, = details['request_observations']
    assert attempt['error_kind'] == 'timeout' and attempt['http_status'] == 200
    assert attempt['url'] == 'https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1'
    assert attempt['response_complete'] is False
    assert observation_kind({'provider': 'TWSE company announcement history',
        'status': 'degraded_enrichment', 'record_count': 1, 'message': '',
        'details': details}) == 'degraded_count'


def test_attempt_diagnostics_are_bounded_and_reject_invalid_metadata():
    from provider_observation_details import observation_details
    details = observation_details({
        'provider': 'TWSE company announcement history',
        'request_observations': [{'url': 'https://evil.invalid/private', 'method': 'GET',
            'elapsed_seconds': float('nan'), 'http_status': True,
            'error_kind': 'oops token=secret', 'response_sha256': 'secret',
            'response_complete': 'true'}] * 100,
    })
    assert len(details['request_observations']) <= 64
    for attempt in details['request_observations']:
        assert set(attempt) <= {'method'}


@pytest.mark.parametrize('complete', [True, False])
def test_new_index_with_only_cached_bodies_is_not_new_body_acquisition(clock, monkeypatch, complete):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    from provider_acquisition import observation_kind
    rows, diagnostic = receipt(complete=complete)
    diagnostic.update(body_cache_hit=True, detail_new_body_count=0,
                      detail_cache_hit_count=1, body_fetched_at_epoch=900.0)
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', lambda *a: (rows, diagnostic))
    result = TwseCompanyHistoryProvider().fetch(FetchRequest.from_ticker('2851.TW'))
    audit = result.audit
    kind = observation_kind({'provider': result.provider, 'status': result.status,
        'record_count': len(result.value), 'message': '', 'details': audit})
    assert kind == ('fresh_cache_count' if complete else 'degraded_count')
    assert audit['http_request_sent'] is True and audit['http_request_count'] == 3
    assert audit['request_observations']
    if complete:
        assert result.status == 'skipped_fresh_cache' and audit['fetched_at_epoch'] == 900


def test_public_provider_advances_real_collector_without_refetching_verified_bodies(monkeypatch):
    from test_twse_announcement_progress import Replay
    import shared_provider_cache
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    replay = Replay(monkeypatch, count=37, detail_cost=.7)
    monkeypatch.setattr(shared_provider_cache.time, 'time', replay.clock.time)
    monkeypatch.setattr(shared_provider_cache.time, 'monotonic', replay.clock.monotonic)
    monkeypatch.setattr(TwseCompanyHistoryProvider, '_fetch_records', lambda *a: replay.fetch())
    provider = TwseCompanyHistoryProvider()
    request = FetchRequest.from_ticker('2891.TW')
    first = provider.fetch(request)
    assert first.status == 'degraded_enrichment'
    assert 0 < len(first.value) < 37
    replay.advance(61)
    second = provider.fetch(request)
    assert second.status == 'success' and len(second.value) == 37
    assert second.audit['detail_cache_hit_count'] == len(first.value)
    assert second.audit['detail_new_body_count'] == 37 - len(first.value)
