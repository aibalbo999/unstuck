from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib

import pytest
import cache_store
from cache_backends import InMemoryCache
import official_institutional_source as official
import shared_provider_cache as shared


@pytest.fixture
def source(monkeypatch):
    now = [datetime(2026, 10, 29, 15, tzinfo=timezone.utc).timestamp()]
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(shared.time, 'time', lambda: now[0])
    monkeypatch.setattr(official, 'expected_sessions', lambda *args, **kw: ['2026-10-29'])
    import market_evidence_policy
    if hasattr(market_evidence_policy, 'calendar_cache_token'):
        monkeypatch.setattr(market_evidence_policy, 'calendar_cache_token', lambda *args: 'unit-calendar')
    calls = []
    def fetch(market, day, timeout, **kw):
        calls.append((market, day))
        return {'rows': {code: {'foreign': 1, 'investment_trust': 2, 'dealer': 3}
                         for code in ['2356', '1101']},
                'raw_evidence': {'retrieved_at': datetime.fromtimestamp(now[0], timezone.utc).isoformat()}}
    monkeypatch.setattr(official, '_fetch_report', fetch)
    yield now, calls
    cache_store.reset_cache_store_for_tests()


def acquire(ticker, now, *, force=False):
    return official.recover_institutional_observations(ticker, {}, now_epoch=now,
        limit=30, force_refresh=force)


def test_forced_success_primes_normal_shared_table_without_new_acquisition_time(source):
    now, calls = source
    first, a = acquire('2356.TW', now[0], force=True)
    now[0] += 5
    second, b = acquire('1101.TW', now[0])
    assert len(calls) == 1
    assert a['reports'][0]['cache_hit'] is False and b['reports'][0]['cache_hit'] is True
    assert b['reports'][0]['fetched_at_epoch'] == a['reports'][0]['fetched_at_epoch']
    assert second['latest_official_observation']['raw_evidence'] == first['latest_official_observation']['raw_evidence']


def test_force_still_fetches_even_when_saved_table_is_fresh(source):
    now, calls = source
    acquire('2356.TW', now[0], force=True)
    now[0] += 5
    _, audit = acquire('2356.TW', now[0], force=True)
    assert len(calls) == 2 and audit['reports'][0]['cache_hit'] is False


def test_failed_force_preserves_complete_saved_bytes_and_ttl(source, monkeypatch):
    now, calls = source
    _, audit = acquire('2356.TW', now[0])
    key = 'shared_provider:v1:' + hashlib.sha256(audit['reports'][0]['cache_key'].encode()).hexdigest()
    before = deepcopy(cache_store.get_cache_json(key))
    def fail(*args, **kw):
        raise TimeoutError('private upstream detail')
    monkeypatch.setattr(official, '_fetch_report', fail)
    now[0] += 5
    value, audit = acquire('2356.TW', now[0], force=True)
    assert value == {} and audit['reports'][0]['status'] == 'unavailable'
    assert audit['reports'][0]['error_kind'] == 'TimeoutError'
    assert cache_store.get_cache_json(key) == before
    assert 'private upstream detail' not in str(audit)


def test_forced_acquisition_obeys_the_same_nonwaiting_lock(source, monkeypatch):
    now, calls = source
    @contextmanager
    def busy(*args, **kwargs):
        yield False
    monkeypatch.setattr(shared, '_shared_lock', busy)
    value, audit = acquire('2356.TW', now[0], force=True)
    assert not calls and value == {}
    assert audit['reports'][0]['error_kind'] == 'single_flight_busy'


def test_success_only_option_does_not_replace_saved_value_after_failure(source):
    now, _ = source
    shared.shared_fetch('unit', lambda: {'value': 1}, freshness_seconds=60)
    now[0] += 2
    def fail():
        raise TimeoutError()
    value, meta = shared.shared_fetch('unit', fail, freshness_seconds=60,
        force_refresh=True, preserve_cache_on_force_error=True)
    assert value is None and meta['error_kind'] == 'TimeoutError'
    warm, meta = shared.shared_fetch('unit', lambda: pytest.fail('saved cache should remain fresh'), freshness_seconds=60)
    assert warm == {'value': 1} and meta['cache_hit'] is True
