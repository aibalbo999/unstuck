"""Contending enrichment searches share a bounded wait without extra HTTP retries."""
import asyncio
from contextlib import contextmanager
import time

import pytest

import search_provider_runtime as runtime


@pytest.fixture
def state(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    rows, observations = {}, []
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: rows.get(key))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: rows.__setitem__(key, value))
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda entries: observations.extend(entries))
    monkeypatch.setattr(runtime, 'provider_circuit_state', lambda key: {})
    yield rows, observations
    cache_store.reset_cache_store_for_tests()


def test_news_short_lock_and_pacing_no_longer_starve_peer_search(state):
    called = []
    async def scenario():
        entered = asyncio.Event()
        async def news():
            called.append('news')
            entered.set()
            await asyncio.sleep(0.04)
            return ['news evidence']
        async def peers():
            called.append('peers')
            return ['peer evidence']
        first = asyncio.create_task(runtime.fetch_search_upstream(
            'google_news_rss', '', news, min_interval_seconds=0.03))
        await entered.wait()
        second = await runtime.fetch_search_upstream(
            'google_news_rss', '', peers, admission_wait_seconds=0.4)
        assert await first == ['news evidence']
        assert second == ['peer evidence']
    asyncio.run(scenario())
    assert called == ['news', 'peers']
    assert [entry['event_kind'] for entry in state[1]] == ['http_attempt', 'http_attempt']


def test_default_remains_nonwaiting_and_other_endpoint_is_independent(state):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def news():
            entered.set()
            await release.wait()
            return ['news']
        async def unexpected(): pytest.fail('Default contender must not send HTTP')
        async def independent(): return ['quote']
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', news))
        await entered.wait()
        assert await runtime.fetch_search_upstream('test', '', unexpected) == []
        assert await runtime.fetch_search_upstream('other', '', independent, endpoint='quote') == ['quote']
        release.set()
        await first
    asyncio.run(scenario())


def test_long_owner_wait_is_bounded_and_sends_no_http(state):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def owner():
            entered.set()
            await release.wait()
            return ['owner']
        async def unexpected(): pytest.fail('Busy budget cannot become another HTTP call')
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', owner))
        await entered.wait()
        started = time.monotonic()
        result = await runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.06)
        assert result == [] and time.monotonic() - started < 0.3
        release.set()
        await first
    asyncio.run(scenario())
    assert state[1][0]['error_kind'] == 'single_flight_busy'
    assert state[1][0]['http_request_sent'] is False


def test_existing_cooldown_does_not_wait_until_or_ignore_retry_after(state):
    key = runtime.scope_key('test')
    guard = {'error_kind': 'rate_limited', 'retry_at': time.time() + 600, 'consecutive_failures': 3}
    state[0][key] = dict(guard)
    async def unexpected(): pytest.fail('Cooling endpoint cannot send HTTP')
    started = time.monotonic()
    assert asyncio.run(runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.4)) == []
    assert time.monotonic() - started < 0.15
    assert state[0][key] == guard


def test_waiter_rechecks_cooldown_written_by_previous_owner(state):
    key = runtime.scope_key('test')
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def owner():
            entered.set()
            await release.wait()
            raise runtime.SourceResponseError('rate_limited', status_code=429)
        async def unexpected(): pytest.fail('Owner failure must block waiter')
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', owner))
        await entered.wait()
        second = asyncio.create_task(runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.3))
        await asyncio.sleep(0.03)
        release.set()
        with pytest.raises(runtime.SourceResponseError): await first
        assert await second == []
    asyncio.run(scenario())
    assert state[0][key]['error_kind'] == 'rate_limited'


def test_wait_and_callback_share_original_timeout(state):
    async def scenario():
        entered = asyncio.Event()
        async def owner():
            entered.set()
            await asyncio.sleep(0.10)
            return ['owner']
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', owner, min_interval_seconds=0))
        await entered.wait()
        callback_budget = []
        async def callback():
            started = time.monotonic()
            try:
                await asyncio.sleep(1)
            finally:
                callback_budget.append(time.monotonic() - started)
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await runtime.fetch_search_upstream('test', '', callback, timeout_seconds=0.2, admission_wait_seconds=0.18)
        assert 0.16 <= time.monotonic() - started < 0.32
        assert 0 < callback_budget[0] < 0.15
        await first
    asyncio.run(scenario())


def test_cancel_waiter_is_immediate_and_does_not_release_owners_lock(state):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def owner():
            entered.set()
            await release.wait()
            return ['owner']
        async def unexpected(): pytest.fail('Cancelled waiter cannot send HTTP')
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', owner))
        await entered.wait()
        second = asyncio.create_task(runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=2))
        await asyncio.sleep(0.02)
        second.cancel()
        with pytest.raises(asyncio.CancelledError): await second
        assert await runtime.fetch_search_upstream('test', '', unexpected) == []
        release.set()
        await first
    asyncio.run(scenario())


def test_storage_failure_after_admission_is_fail_closed(state, monkeypatch):
    def broken(key): raise OSError('guard unavailable')
    monkeypatch.setattr(runtime, 'get_cache_json', broken)
    async def unexpected(): pytest.fail('Storage failure must not send HTTP')
    assert asyncio.run(runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.1)) == []
    assert state[1][-1]['error_kind'] == 'guard_storage_unavailable'


def test_lost_lease_before_callback_is_fail_closed(state, monkeypatch):
    import search_admission
    @contextmanager
    def lost(key, **kwargs): yield lambda: False
    monkeypatch.setattr(search_admission, 'endpoint_admission', lost)
    async def unexpected(): pytest.fail('Lease loss before request must not send HTTP')
    assert asyncio.run(runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.1)) == []
    assert state[1][-1]['error_kind'] == 'lease_lost'


def test_pacing_larger_than_wait_budget_is_not_bypassed(state):
    key = runtime.scope_key('test')
    state[0][key] = {'next_request_at': time.time() + 5}
    async def unexpected(): pytest.fail('Long pacing delay must not send HTTP')
    assert asyncio.run(runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.06)) == []
    assert state[1][-1]['error_kind'] == 'request_pacing'


def test_external_search_explicitly_opts_in_without_query_changes(state, monkeypatch):
    import external_search_providers as search
    seen = []
    async def upstream(provider, credential, callback, **kwargs):
        seen.append((provider, kwargs))
        return await callback()
    async def fetched(client, provider, query, **kwargs):
        assert query == 'same company competitors'
        return ['peer']
    monkeypatch.setattr(search, 'fetch_search_upstream', upstream)
    monkeypatch.setattr(search, 'fetch_provider_results', fetched)
    assert asyncio.run(search._fetch_provider_results(None, 'google_news_rss', 'same company competitors', max_results=3, lookback_days=30)) == ['peer']
    assert seen == [('google_news_rss', {'admission_wait_seconds': 2.0})]


def test_parent_total_deadline_cancels_admission_before_new_http(state):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def owner():
            entered.set()
            await release.wait()
            return ['owner']
        async def unexpected(): pytest.fail('Parent deadline must prevent HTTP')
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', owner))
        await entered.wait()
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.04):
                await runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=2)
        assert time.monotonic() - started < 0.2
        release.set()
        await first
    asyncio.run(scenario())
    assert len(state[1]) == 1


def test_lease_loss_during_pacing_prevents_callback(state, monkeypatch):
    import search_admission
    ownership = [True]
    @contextmanager
    def lease(key, **kwargs): yield lambda: ownership[0]
    monkeypatch.setattr(search_admission, 'endpoint_admission', lease)
    state[0][runtime.scope_key('test')] = {'next_request_at': time.time() + 0.06}
    async def scenario():
        async def lose():
            await asyncio.sleep(0.02)
            ownership[0] = False
        async def unexpected(): pytest.fail('Lost lease must prevent HTTP after pacing')
        losing = asyncio.create_task(lose())
        assert await runtime.fetch_search_upstream('test', '', unexpected, admission_wait_seconds=0.2) == []
        await losing
    asyncio.run(scenario())
    assert state[1][-1]['error_kind'] == 'lease_lost'


def test_short_callback_timeout_caps_long_admission_wait(state):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def owner():
            entered.set()
            await release.wait()
            return ['owner']
        async def unexpected(): pytest.fail('Wait cannot exceed the callback total budget')
        first = asyncio.create_task(runtime.fetch_search_upstream('test', '', owner))
        await entered.wait()
        started = time.monotonic()
        assert await runtime.fetch_search_upstream('test', '', unexpected, timeout_seconds=0.04, admission_wait_seconds=2) == []
        assert time.monotonic() - started < 0.2
        release.set()
        await first
    asyncio.run(scenario())
