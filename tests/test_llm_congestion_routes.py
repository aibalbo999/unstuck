"""Shared observed-congestion behavior through public routing and scope boundaries."""
import asyncio
import pytest

import config
import llm_congestion as guard
from llm_congestion_store import CongestionStore
from llm_model_circuits import ModelCircuitOpenError
from llm_rate_limits import KeyRotator

MODEL = "gemini-3.8-flash"


class Provider429(RuntimeError):
    status_code = 429


class Provider503(RuntimeError):
    status_code = 503


@pytest.fixture
def state(monkeypatch):
    now = [1000.0]
    store = CongestionStore(clock=lambda: now[0], jitter=lambda: 0)
    monkeypatch.setattr(config, "LLM_CONGESTION_GUARD_ENABLED", True)
    monkeypatch.setattr(guard, "_store", store)
    return now, store


def fail(key, error=None, model=MODEL):
    with pytest.raises(type(error) if error else Provider429):
        with guard.provider_attempt_scope(model, key):
            raise error or Provider429("busy")


def test_rotators_share_congestion_but_other_model_and_rpd_remain_separate(state, monkeypatch):
    import llm_rate_limits
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    first, second = KeyRotator(["synthetic-a", "synthetic-b"]), KeyRotator(["synthetic-b", "synthetic-a"])
    fail("synthetic-a")
    assert second.model_circuit_wait(MODEL) == 0
    fail("synthetic-b")
    assert first.model_circuit_wait(MODEL) >= 60
    assert second.model_retry_wait(MODEL) >= 60
    assert second.is_shared_model_circuit_open(MODEL)
    assert second.model_circuit_wait("gemma-4-26b-a4b-it") == 0
    assert not second.provider_quota_exhausted(MODEL)
    assert second.eligible_key_slots(MODEL) == {1, 2}
    with pytest.raises(ModelCircuitOpenError):
        second.get_key(MODEL)


def test_nested_scope_counts_failure_once_and_normal_success_does_not_erase_window(state):
    with pytest.raises(Provider429):
        with guard.provider_attempt_scope(MODEL, "synthetic-a", record_outcome=False):
            with guard.provider_attempt_scope("google:" + MODEL, "synthetic-a"):
                raise Provider429("busy")
    assert guard.congestion_wait(MODEL) == 0
    with guard.provider_attempt_scope(MODEL, "synthetic-c"):
        pass
    fail("synthetic-b")
    assert guard.congestion_wait(MODEL) >= 60


def test_rpd_and_503_are_not_aggregated_as_unknown429(state):
    error = Provider429("RequestsPerDay exceeded")
    fail("synthetic-a", error)
    fail("synthetic-b", error)
    fail("synthetic-a", RuntimeError("503 service unavailable"))
    assert guard.congestion_wait(MODEL) == 0
    fail("synthetic-c")
    assert guard.congestion_wait(MODEL) == 0


def test_cancelled_probe_is_released_with_delay_and_original_exception(state):
    now, _ = state
    fail("synthetic-a")
    fail("synthetic-b")
    now[0] += 61
    error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError) as caught:
        with guard.provider_attempt_scope(MODEL, "synthetic-c", record_outcome=False):
            with guard.provider_attempt_scope(MODEL, "synthetic-c"):
                raise error
    assert caught.value is error
    assert 0 < guard.congestion_wait(MODEL) <= 30
    now[0] += 31
    with guard.provider_attempt_scope(MODEL, "synthetic-d"):
        pass
    assert guard.congestion_wait(MODEL) == 0


def test_cache_only_outer_scope_cannot_clear_probe(state):
    now, _ = state
    fail("synthetic-a")
    fail("synthetic-b")
    now[0] += 61
    with guard.provider_attempt_scope(MODEL, "synthetic-c", record_outcome=False):
        pass
    assert guard.congestion_wait(MODEL) > 0


def test_probe_honors_longest_configured_call_timeout(state, monkeypatch):
    now, _ = state
    monkeypatch.setattr(config, "PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS", 360)
    fail("synthetic-a")
    fail("synthetic-b")
    now[0] += 61
    with guard.provider_attempt_scope(MODEL, "synthetic-c"):
        now[0] += 121
        assert guard.congestion_wait(MODEL) >= 269
        with pytest.raises(ModelCircuitOpenError):
            with guard.provider_attempt_scope(MODEL, "synthetic-d"):
                pytest.fail("parallel recovery request escaped")


def test_disabled_guard_and_non_google_never_touch_store(state, monkeypatch):
    class MustNotCall:
        def operate(self, *args, **kwargs):
            pytest.fail("unexpected Google congestion store")
    monkeypatch.setattr(guard, "_store", MustNotCall())
    with guard.provider_attempt_scope("openai:gpt-example", "synthetic-a"):
        pass
    monkeypatch.setattr(config, "LLM_CONGESTION_GUARD_ENABLED", False)
    with guard.provider_attempt_scope(MODEL, "synthetic-a"):
        pass
    assert guard.congestion_wait(MODEL) == 0


def test_second_transport_in_outer_scope_gets_own_admission_and_outcome(state):
    with guard.provider_attempt_scope(MODEL, "synthetic-a", record_outcome=False):
        with guard.provider_attempt_scope(MODEL, "synthetic-a"):
            pass
        fail("synthetic-a")
    fail("synthetic-b")
    assert guard.congestion_wait(MODEL) >= 60


def test_actual_503_immediately_shares_backoff_and_recovers_one_probe(state):
    now, _ = state
    error = Provider503('service unavailable')
    with pytest.raises(Provider503) as caught:
        with guard.provider_attempt_scope(MODEL, 'synthetic-a', record_outcome=False):
            with guard.provider_attempt_scope(MODEL, 'synthetic-a'):
                raise error
    assert caught.value is error
    assert guard.congestion_wait(MODEL) == 60
    with guard.provider_attempt_scope('gemma-healthy', 'synthetic-a'):
        pass
    with pytest.raises(ModelCircuitOpenError):
        with guard.provider_attempt_scope(MODEL, 'synthetic-b'):
            pytest.fail('different job/key must not bypass shared 503 cooldown')
    now[0] += 61
    fail('synthetic-b', Provider503('still unavailable'))
    assert guard.congestion_wait(MODEL) == 120
    now[0] += 121
    with guard.provider_attempt_scope(MODEL, 'synthetic-c'):
        pass
    assert guard.congestion_wait(MODEL) == 0


def test_503_response_status_and_retry_after_are_preserved(state):
    from types import SimpleNamespace
    error = RuntimeError('unavailable')
    error.response = SimpleNamespace(status_code=503, headers={'Retry-After': '600'})
    fail('synthetic-a', error)
    assert guard.congestion_wait(MODEL) == 600


def test_503_stops_route_retry_without_disabling_any_daily_key(state, monkeypatch):
    from types import SimpleNamespace
    import llm_rate_limits
    from agent_runtime.model_policy import make_model_retry_stop_for_rotator, model_attempt_policy
    from agent_runtime.retry_policy import AgentServerError
    from agent_runtime.deferred import unavailable_model
    monkeypatch.setattr(llm_rate_limits, 'create_shared_llm_limiter', lambda: None)
    rotator = KeyRotator(['synthetic-a', 'synthetic-b'])
    fail('synthetic-a', Provider503('unavailable'))
    assert rotator.model_retry_wait(MODEL) == 60
    assert rotator.eligible_key_slots(MODEL) == {1, 2}
    assert not rotator.provider_quota_exhausted(MODEL)
    blocked = unavailable_model({}, rotator, MODEL)
    assert blocked['reason_code'] == 'model_cooldown'
    assert blocked['provider_quota_confirmed'] is False
    assert unavailable_model({}, rotator, 'gemma-healthy') is None
    error = AgentServerError('unavailable')
    stop = make_model_retry_stop_for_rotator(model_attempt_policy(0, True, 6, 2), rotator, MODEL)
    assert stop(SimpleNamespace(attempt_number=1, outcome=SimpleNamespace(exception=lambda: error)))
    assert error.parallel_circuit_open
