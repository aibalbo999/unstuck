"""Actual provider 504s share recovery backoff without inventing quota failure."""
import asyncio
from types import SimpleNamespace

import pytest

import config
import llm_congestion as guard
from llm_congestion_store import CongestionStore
from llm_model_circuits import ModelCircuitOpenError


MODEL = "gemini-3.8-flash"


class Provider504(RuntimeError):
    code = 504


@pytest.fixture
def rig(monkeypatch):
    now, events = [1000.0], []
    store = CongestionStore(clock=lambda: now[0], jitter=lambda: 0)
    monkeypatch.setattr(config, "LLM_CONGESTION_GUARD_ENABLED", True)
    monkeypatch.setattr(guard, "_store", store)
    monkeypatch.setattr(guard, "observe_transition", lambda *args, **kwargs: events.append((args, kwargs)))
    return now, events


def fail(key, error):
    with pytest.raises(type(error)) as caught:
        with guard.provider_attempt_scope(MODEL, key, record_outcome=False):
            with guard.provider_attempt_scope(MODEL, key):
                raise error
    assert caught.value is error


def test_actual_504_blocks_other_key_and_recovers_with_one_probe(rig):
    now, events = rig
    fail("synthetic-a", Provider504("Gateway timeout"))
    assert guard.congestion_wait(MODEL) == 60
    outcome, metadata = events[-1]
    assert outcome[1] == "provider_504"
    assert metadata["provider_status"] == 504
    assert outcome[2]["transition"] == "opened"
    with pytest.raises(ModelCircuitOpenError):
        with guard.provider_attempt_scope(MODEL, "synthetic-b"):
            pytest.fail("a second key must not bypass provider backoff")
    with guard.provider_attempt_scope("gemini-healthy", "synthetic-b"):
        pass
    now[0] += 61
    with guard.provider_attempt_scope(MODEL, "synthetic-b"):
        with pytest.raises(ModelCircuitOpenError):
            with guard.provider_attempt_scope(MODEL, "synthetic-c"):
                pytest.fail("only one recovery probe may be in flight")
    assert guard.congestion_wait(MODEL) == 0


def test_504_recovery_failure_escalates_backoff_and_keeps_status(rig):
    now, events = rig
    fail("synthetic-a", Provider504("Gateway timeout"))
    now[0] += 61
    fail("synthetic-b", Provider504("Gateway still unavailable"))
    assert guard.congestion_wait(MODEL) == 120
    assert events[-1][0][1] == "provider_504"
    assert events[-1][0][2]["transition"] == "reopened"


def test_504_response_status_honors_retry_after(rig):
    error = RuntimeError("upstream deadline")
    error.response = SimpleNamespace(status_code=504, headers={"Retry-After": "600"})
    fail("synthetic-a", error)
    assert guard.congestion_wait(MODEL) == 600


def test_504_transition_reaches_safe_telemetry_sink(rig, monkeypatch):
    import api_usage_store
    import llm_congestion_telemetry

    recorded = []
    monkeypatch.setattr(api_usage_store, "record_api_usage", lambda **row: recorded.append(row))
    monkeypatch.setattr(guard, "observe_transition", llm_congestion_telemetry.observe_transition)
    fail("synthetic-secret-key", Provider504("private error text"))
    row = recorded[-1]
    assert row["operation"] == "llm_congestion_transition"
    assert row["units"] == 0
    assert row["metadata"]["outcome"] == "provider_504"
    assert row["metadata"]["provider_status_code"] == 504
    assert row["metadata"]["transition"] == "opened"
    assert "synthetic-secret-key" not in str(recorded)
    assert "private error text" not in str(recorded)


@pytest.mark.parametrize("error", [TimeoutError("local timeout 504"), asyncio.CancelledError()])
def test_local_timeout_and_cancel_do_not_invent_provider_504_or_quota(rig, error):
    now, events = rig
    fail("synthetic-a", error)
    assert guard.congestion_wait(MODEL) == 0
    assert events[-1][0][1] == "released_error"
    assert events[-1][1]["provider_status"] is None
    fail("synthetic-a", Provider504("Gateway timeout"))
    now[0] += 61
    fail("synthetic-b", error)
    assert guard.congestion_wait(MODEL) == 30
    assert events[-1][0][1] == "released_error"
    assert events[-1][1]["provider_status"] is None


def test_504_remains_availability_failure_without_daily_key_exhaustion(rig, monkeypatch):
    import llm_rate_limits
    from agent_runtime.deferred import unavailable_model

    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    rotator = llm_rate_limits.KeyRotator(["synthetic-a", "synthetic-b"])
    fail("synthetic-a", Provider504("Gateway timeout"))
    assert rotator.eligible_key_slots(MODEL) == {1, 2}
    assert not rotator.provider_quota_exhausted(MODEL)
    blocked = unavailable_model({}, rotator, MODEL)
    assert blocked["reason_code"] == "model_cooldown"
    assert blocked["provider_quota_confirmed"] is False
    assert blocked["retry_wait_seconds"] == 60
