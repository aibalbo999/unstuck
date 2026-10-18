"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
import official_financials_mops_conference as conference
import search_provider_runtime as runtime
KEY = runtime.scope_key('MOPS', endpoint='mopsov_investor_conference')
MONTHLY_KEY = runtime.scope_key('MOPS', endpoint='mopsov_investor_conference_monthly')

@pytest.fixture
def state(monkeypatch):
    now = [1792000000.0]
    cache = {}
    monkeypatch.setattr(runtime.time, 'time', lambda: now[0])
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: deepcopy(cache.get(key)))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: cache.__setitem__(key, deepcopy(value)))
    monkeypatch.setattr(conference, 'record_observation', lambda *a, **k: None)
    return (now, cache)

def fail():
    return runtime.remember_failure(KEY, runtime.SourceResponseError('timeout'))

def test_native_recognized_empty_ends_streak_but_does_not_create_data(state, monkeypatch):
    now, cache = state
    first = fail()
    now[0] = first['retry_at'] + 1
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='查無資料', status_code=200))
    assert conference._fetch_uncached_events('2330.TW', year=2026) == []
    assert cache[KEY] == first
    after_recovery = fail()
    assert after_recovery['consecutive_failures'] == 1
    assert after_recovery['retry_at'] == now[0] + 60

def test_monthly_query_recovers_while_annual_page_is_cooled_down(state, monkeypatch):
    _, cache = state
    annual = fail()
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs['data'])
        return SimpleNamespace(text='查無符合條件之資料', status_code=200)
    monkeypatch.setattr(conference, '_http_post', post)
    assert conference._fetch_uncached_events('2330.TW', year=2026, month=9) == []
    assert calls[0]['month'] == '09'
    assert cache[KEY] == annual
    assert MONTHLY_KEY not in cache

def test_unknown_html_does_not_end_failure_streak(state, monkeypatch):
    now, cache = state
    first = fail()
    now[0] = first['retry_at'] + 1
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='<html>unknown layout</html>', status_code=200))
    with pytest.raises(runtime.SourceResponseError):
        conference._fetch_uncached_events('2330.TW', year=2026)
    assert cache[KEY]['consecutive_failures'] == 2

def test_supplied_session_does_not_reset_shared_runtime_guard(state, monkeypatch):
    now, cache = state
    first = fail()
    now[0] = first['retry_at'] + 1
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='查無資料', status_code=200))
    conference._fetch_uncached_events('2330.TW', year=2026, session=object())
    assert fail()['consecutive_failures'] == 2

def test_success_cannot_clear_active_retry_after_or_future_failure(state):
    now, cache = state
    response = SimpleNamespace(status_code=429, headers={'Retry-After': '7200'})
    error = runtime.SourceResponseError('rate_limited', status_code=429)
    error.response = response
    first = runtime.remember_failure(KEY, error)
    assert runtime.remember_success(KEY, request_started_at=now[0]) is False
    assert cache[KEY] == first
    assert fail()['retry_at'] >= first['retry_at']

def test_recovered_streak_resets_once_then_real_consecutive_errors_escalate(state):
    now, _ = state
    first = fail()
    now[0] = first['retry_at'] + 1
    assert runtime.remember_success(KEY, request_started_at=now[0])
    second = fail()
    assert second['consecutive_failures'] == 1
    now[0] = second['retry_at'] + 1
    third = fail()
    assert third['consecutive_failures'] == 2
    assert third['retry_at'] == now[0] + 120

def test_success_marker_racing_with_new_failure_does_not_reset_new_streak(state, monkeypatch):
    now, cache = state
    first = fail()
    now[0] = first['retry_at'] + 1
    original_set = runtime.set_cache_json

    def write(key, value, ttl_seconds):
        if key.startswith('provider_endpoint_recovery:'):
            fail()
        original_set(key, value, ttl_seconds)
    monkeypatch.setattr(runtime, 'set_cache_json', write)
    assert runtime.remember_success(KEY, request_started_at=now[0])
    assert cache[KEY]['consecutive_failures'] == 2
    now[0] = cache[KEY]['retry_at'] + 1
    assert fail()['consecutive_failures'] == 3

@pytest.mark.parametrize('started', [True, None, '1', 0, -1, float('nan'), float('inf'), 1792000100.0])
def test_invalid_or_future_request_time_cannot_reset_streak(state, started):
    now, cache = state
    first = fail()
    now[0] = first['retry_at'] + 1
    assert runtime.remember_success(KEY, request_started_at=started) is False
    assert cache[KEY] == first
    assert fail()['consecutive_failures'] == 2

def test_recovery_storage_failure_preserves_native_result(state, monkeypatch):
    now, cache = state
    first = fail()
    now[0] = first['retry_at'] + 1
    monkeypatch.setattr(conference, '_http_post', lambda *a, **k: SimpleNamespace(text='查無資料', status_code=200))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda *a, **k: (_ for _ in ()).throw(OSError('storage unavailable')))
    assert conference._fetch_uncached_events('2330.TW', year=2026) == []
    assert cache[KEY] == first
