"""Rolling RPM/TPM admission against local state and isolated real Redis Lua."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time

import pytest

from shared_runtime_guards import RedisFixedWindowRateLimiter
from shared_runtime_local_guards import LocalFixedWindowRateLimiter
from test_shared_cooldown import redis_socket  # Disposable Unix socket; TCP disabled.


@pytest.fixture(params=['local', 'redis'])
def rolling(request, monkeypatch):
    clock = [119.0]
    monkeypatch.setattr('shared_runtime_local_guards.time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr('shared_runtime_guards.time', SimpleNamespace(time=lambda: clock[0]))
    client = request.getfixturevalue('redis_socket') if request.param == 'redis' else None
    local = LocalFixedWindowRateLimiter()
    def factory():
        return RedisFixedWindowRateLimiter(client, namespace='sliding-test') if client else local
    def advance(seconds):
        clock[0] += seconds
        if client:
            for key in client.command('KEYS', 'sliding-test:*').splitlines():
                if client.command('TYPE', key) == 'zset':
                    for member in client.command('ZRANGE', key, 0, -1).splitlines():
                        client.command('ZINCRBY', key, -seconds * 1000, member)
    return SimpleNamespace(first=factory(), second=factory(), advance=advance, client=client)


def reserve(limiter, tokens, rpm=100):
    return limiter.reserve('key-a', 'model-a', rpm_limit=rpm, tpm_limit=16000, estimated_tokens=tokens)


def assert_wait(value, expected, *, started, redis):
    if not redis:
        assert value == pytest.approx(expected, abs=1e-9)
        return
    # Redis uses server time while each CLI command has real subprocess overhead.
    # Bound that elapsed time from before admission through this observation;
    # allow only 2 ms for Redis's integer-millisecond rounding.
    elapsed = time.monotonic() - started
    assert value > 0
    assert expected - elapsed - 0.002 <= value <= expected + 0.002


def test_cross_clock_minute_keeps_prior_38_second_token_usage(rolling):
    started = time.monotonic()
    assert reserve(rolling.first, 8831) == 0
    rolling.advance(38)
    assert_wait(reserve(rolling.second, 8895), 22, started=started, redis=rolling.client)
    rolling.advance(22.1)
    assert reserve(rolling.second, 8895) == 0


def test_denied_attempt_neither_consumes_rpm_nor_tpm(rolling):
    assert reserve(rolling.first, 9000, rpm=2) == 0
    assert reserve(rolling.second, 9000, rpm=2) > 59
    assert reserve(rolling.second, 7000, rpm=2) == 0
    assert reserve(rolling.first, 1, rpm=2) > 59


def test_waits_until_enough_tokens_expire_not_until_clock_minute(rolling):
    first_started = time.monotonic()
    assert reserve(rolling.first, 9000) == 0
    rolling.advance(30)
    second_started = time.monotonic()
    assert reserve(rolling.second, 6000) == 0
    rolling.advance(15)
    assert_wait(reserve(rolling.first, 2000), 15, started=first_started, redis=rolling.client)
    rolling.advance(15.1)
    assert reserve(rolling.second, 2000) == 0
    assert_wait(reserve(rolling.first, 9000), 29.9, started=second_started, redis=rolling.client)


def test_rpm_is_rolling_even_when_tpm_has_room(rolling):
    started = time.monotonic()
    assert reserve(rolling.first, 1, rpm=1) == 0
    rolling.advance(2)
    assert_wait(reserve(rolling.second, 1, rpm=1), 58, started=started, redis=rolling.client)


def test_concurrent_independent_redis_clients_or_local_threads_cannot_over_admit(rolling):
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve, limiter, tokens) for limiter, tokens in
                   [(rolling.first, 8831), (rolling.second, 8895)]]
        results = [future.result() for future in futures]
    assert sum(wait == 0 for wait in results) == 1
    assert max(results) > 59


def test_cooldown_does_not_consume_an_additional_reservation(rolling):
    rolling.first.penalize('key-a', 'model-a', 120)
    assert reserve(rolling.first, 9000) > 119
    assert rolling.first.reserve('key-a', 'other-model', rpm_limit=1, estimated_tokens=1) == 0


def test_redis_failure_keeps_known_usage_and_quarantines_unknown_peer_usage(monkeypatch, redis_socket):
    clock = [1000.0]
    monkeypatch.setattr('shared_runtime_guards.time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr('shared_runtime_local_guards.time', SimpleNamespace(time=lambda: clock[0]))
    limiter = RedisFixedWindowRateLimiter(redis_socket, namespace='sliding-failure')
    assert reserve(limiter, 8831) == 0
    def unavailable(*args):
        raise RuntimeError('Redis response may be lost after admission')
    redis_socket.eval = unavailable
    assert reserve(limiter, 8895) == 60
    clock[0] += 30
    assert reserve(limiter, 1) == 30
    clock[0] += 30.1
    assert reserve(limiter, 8895) == 0
    assert reserve(limiter, 8831) > 59


def test_known_long_cooldown_survives_redis_failure_quarantine(redis_socket):
    limiter = RedisFixedWindowRateLimiter(redis_socket, namespace='sliding-failure')
    limiter.penalize('key-a', 'model-a', 120)
    redis_socket.eval = lambda *args: (_ for _ in ()).throw(RuntimeError('Redis down'))
    assert reserve(limiter, 10) > 119


@pytest.mark.parametrize('legacy_minute', [1, 2])
def test_deployment_waits_for_existing_legacy_window_without_erasing_it(monkeypatch, redis_socket, legacy_minute):
    from shared_runtime_guard_utils import guard_hash
    monkeypatch.setattr('shared_runtime_guards.time', SimpleNamespace(time=lambda: 157.0))
    prefix = f'legacy-test:llm:{guard_hash("model-a")}:{guard_hash("key-a")}'
    legacy_key = f'{prefix}:{legacy_minute}:tpm'
    started = time.monotonic()
    redis_socket.set(legacy_key, 8831, px=22000)
    limiter = RedisFixedWindowRateLimiter(redis_socket, namespace='legacy-test')
    assert_wait(reserve(limiter, 8895), 22, started=started, redis=True)
    assert redis_socket.command('GET', legacy_key) == '8831'
    assert redis_socket.command('EXISTS', f'{prefix}:rolling-v1') == '0'
    redis_socket.command('PEXPIRE', legacy_key, 1)
    time.sleep(0.005)
    assert reserve(limiter, 8895) == 0


def test_redis_events_have_ttl_are_unique_and_hide_key_and_model(redis_socket):
    limiter = RedisFixedWindowRateLimiter(redis_socket, namespace='sliding-privacy')
    for _ in range(2):
        assert reserve(limiter, 1000) == 0
    keys = redis_socket.command('KEYS', 'sliding-privacy:*').splitlines()
    assert len(keys) == 1
    assert 'key-a' not in keys[0] and 'model-a' not in keys[0]
    assert 59000 <= redis_socket.pttl(keys[0]) <= 60000
    assert redis_socket.command('ZCARD', keys[0]) == '2'


def test_concurrent_rpm_admission_counts_same_millisecond_requests(rolling):
    with ThreadPoolExecutor(max_workers=4) as pool:
        waits = list(pool.map(lambda limiter: reserve(limiter, 1, rpm=2),
                              [rolling.first, rolling.second] * 2))
    assert waits.count(0) == 2
    assert sum(wait > 59 for wait in waits) == 2


def test_request_above_tpm_capacity_is_not_an_endless_wait(rolling):
    from llm_input_capacity import InputCapacityExceededError
    with pytest.raises(InputCapacityExceededError):
        reserve(rolling.first, 16001)
    assert reserve(rolling.first, 16000) == 0


def test_configured_shared_factory_quarantines_initial_connection_failure(monkeypatch):
    import shared_runtime_guards as guards
    clock = [1000.0]
    monkeypatch.setattr(guards, 'time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr('shared_runtime_local_guards.time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(guards, 'shared_guard_enabled', lambda _: True)
    monkeypatch.setattr(guards, 'create_redis_client', lambda _: None)
    limiter = guards.create_shared_llm_limiter()
    assert reserve(limiter, 8895) == 60
    clock[0] += 60.1
    assert reserve(limiter, 8895) == 0
    assert reserve(limiter, 8831) > 59


@pytest.mark.parametrize('backend', ['local', 'memory', 'auto'])
def test_pure_local_factory_reaches_key_rotator_rolling_admission(monkeypatch, backend):
    import shared_runtime_guards as guards
    import llm_rate_limits as limits
    clock = [119.0]
    monkeypatch.setenv('LLM_RATE_LIMIT_BACKEND', backend)
    monkeypatch.setattr(guards, 'TASK_QUEUE_BACKEND', 'local')
    monkeypatch.setattr(guards, 'time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr('shared_runtime_local_guards.time', SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr('llm_rate_limit_buckets.time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(limits, 'RPM_LIMITS', {'model-a': 100})
    monkeypatch.setattr(limits, 'TPM_LIMITS', {'model-a': 16000})
    monkeypatch.setattr(limits, 'RPD_LIMITS', {})
    monkeypatch.setattr(limits, 'create_shared_llm_limiter', guards.create_shared_llm_limiter)
    rotator = limits.KeyRotator(['key-a'])
    first = rotator._try_key('model-a', 8831, 1)
    assert first[0] == 0 and first[-1] == 'key-a'
    clock[0] += 38
    second = rotator._try_key('model-a', 8895, 1)
    assert second[0] == 22  # get_key waits before returning this candidate.
    clock[0] += 22.1
    assert rotator._try_key('model-a', 8895, 1)[0] == 0


@pytest.mark.parametrize('backend', ['off', 'disabled', 'none'])
def test_explicit_disabled_factory_preserves_operator_choice(monkeypatch, backend):
    from shared_runtime_guards import create_shared_llm_limiter
    monkeypatch.setenv('LLM_RATE_LIMIT_BACKEND', backend)
    assert create_shared_llm_limiter() is None
