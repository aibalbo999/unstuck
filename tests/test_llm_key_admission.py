"""Shared throttling must not hide ready keys or consume unsent local requests."""
import asyncio
from types import SimpleNamespace

import pytest

import llm_rate_limits as limits
import llm_rate_limit_buckets as buckets
import shared_runtime_local_guards as local_guards
from llm_daily_budget import DailyBudgetStore
from shared_runtime_guards import RedisFixedWindowRateLimiter


@pytest.fixture
def admission(monkeypatch, tmp_path):
    clock = [120.0]
    waits = []
    monkeypatch.setattr(buckets, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(local_guards, "time", SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(limits, "RPM_LIMITS", {"m": 1})
    monkeypatch.setattr(limits, "TPM_LIMITS", {"m": 100})
    monkeypatch.setattr(limits, "RPD_LIMITS", {"m": 10})
    monkeypatch.setattr(limits, "MODEL_INPUT_TOKEN_LIMITS", {})
    monkeypatch.setattr(limits, "LLM_PROVIDER_QUOTA_AUTHORITATIVE", False)
    shared = RedisFixedWindowRateLimiter(None)
    monkeypatch.setattr(limits, "create_shared_llm_limiter", lambda: shared)
    rotator = limits.KeyRotator(["key-a", "key-b"])
    store = DailyBudgetStore(path_getter=lambda: tmp_path / "daily.sqlite3")
    rotator._daily_budget = store

    def sleep(seconds):
        waits.append(seconds)
        assert len(waits) <= 3, "key admission must converge after shared cooldown"
        clock[0] += seconds

    async def async_sleep(seconds):
        sleep(seconds)

    monkeypatch.setattr(limits, "time", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(limits.asyncio, "sleep", async_sleep)

    def get(async_mode):
        if async_mode:
            return asyncio.run(rotator.async_get_key("m", 20))
        return rotator.get_key("m", 20)

    yield SimpleNamespace(shared=shared, rotator=rotator, get=get, waits=waits, clock=clock)
    store.close_current_thread()


@pytest.mark.parametrize("async_mode", [False, True])
def test_shared_busy_key_does_not_block_another_ready_key(admission, async_mode):
    h = admission
    assert h.shared.reserve("key-a", "m", rpm_limit=1, tpm_limit=100, estimated_tokens=20) == 0
    assert h.get(async_mode) == "key-b"
    assert h.waits == []
    assert h.rotator._rpm_buckets[("key-a", "m")].tokens == 1
    assert h.rotator._tpm_buckets[("key-a", "m")].tokens == 100
    assert h.rotator._daily_budget.remaining(["key-a", "key-b"], "m", 10) == {"key-a": 10, "key-b": 9}


@pytest.mark.parametrize("async_mode", [False, True])
def test_all_shared_keys_cooling_waits_for_earliest_and_debits_once(admission, async_mode):
    h = admission
    h.shared.penalize("key-a", "m", 30)
    h.shared.penalize("key-b", "m", 5)
    assert h.get(async_mode) == "key-b"
    assert h.waits == [5]
    assert h.rotator._rpm_buckets[("key-a", "m")].tokens == 1
    assert h.rotator._rpm_buckets[("key-b", "m")].tokens == 0
    assert h.rotator._tpm_buckets[("key-b", "m")].tokens == 80
    assert h.rotator._daily_budget.remaining(["key-a", "key-b"], "m", 10) == {"key-a": 10, "key-b": 9}


@pytest.mark.parametrize("async_mode", [False, True])
def test_local_throttle_remains_enforced_without_reserving_shared_budget(admission, async_mode):
    h = admission
    assert h.get(async_mode) == "key-a"
    assert h.get(async_mode) == "key-b"
    assert h.get(async_mode) == "key-a"
    assert h.waits == [60]
    assert h.rotator._daily_budget.remaining(["key-a", "key-b"], "m", 10) == {"key-a": 8, "key-b": 9}


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_agent_key_wait_stops_without_provider_send_or_daily_charge(admission, monkeypatch, async_mode, stop):
    import agent_runtime.llm_calls as calls

    h = admission
    monkeypatch.setattr("time.monotonic", lambda: h.clock[0])
    monkeypatch.setattr(calls, "estimate_agent_input_tokens", lambda *args: 20)
    h.shared.penalize("key-a", "m", 30)
    h.shared.penalize("key-b", "m", 30)

    class Cancelled(Exception):
        pass

    def check_cancel():
        if stop == "cancel" and h.clock[0] >= 121:
            raise Cancelled("cancel requested")

    def forbidden(*args, **kwargs):
        pytest.fail("cancelled or expired key wait must never send a provider request")

    monkeypatch.setattr(calls, "_generate_content", forbidden)
    monkeypatch.setattr(calls, "_generate_content_async", forbidden)
    context = {"_cancel_check": check_cancel}
    args = (1, context, h.rotator, "m", "prompt")
    expected = Cancelled if stop == "cancel" else calls.AgentRateLimitError
    with pytest.raises(expected) as caught:
        if async_mode:
            asyncio.run(calls._run_agent_once_async(*args, timeout_seconds=2))
        else:
            calls._run_agent_once(*args, timeout_seconds=2)
    assert h.clock[0] == (121 if stop == "cancel" else 122)
    assert not any(e["phase"] == "llm_provider_request" for e in context["_runtime_events"])
    assert h.rotator._daily_budget.remaining(["key-a", "key-b"], "m", 10) == {"key-a": 10, "key-b": 10}
    assert h.rotator.model_circuit_wait("m") == 0
    assert h.rotator.provider_quota_exhausted("m") is False
    if stop == "deadline":
        assert caught.value.preflight_blocked is True
        assert caught.value.retry_wait_seconds == 28
        assert context["_runtime_events"][-1]["metadata"]["error_category"] == "local_admission_wait"
    remaining = 150 - h.clock[0]
    h.waits.clear()
    assert h.get(async_mode) == "key-a"  # Request scope must not leak into the next caller.
    assert h.waits == [remaining]


@pytest.mark.parametrize("entry", ["async", "sync_in_event_loop"])
def test_key_wait_deadline_advances_to_configured_fallback_once(admission, monkeypatch, entry):
    from agent_runtime import llm_calls, single_agent, single_agent_admission

    h = admission
    monkeypatch.setattr("time.monotonic", lambda: h.clock[0])
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *a: ["m", "backup"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *a: "original evidence")
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *a: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *a, **kw: None)
    monkeypatch.setattr(single_agent, "timeout_for_model_call", lambda *a: 2)
    monkeypatch.setattr(llm_calls, "estimate_agent_input_tokens", lambda *a: 20)
    monkeypatch.setattr(single_agent_admission, "estimate_agent_input_tokens", lambda *a: 20)
    h.shared.penalize("key-a", "m", 30)
    h.shared.penalize("key-b", "m", 30)
    sent = []

    def generate(key, model, agent, prompt):
        sent.append((model, prompt))
        return SimpleNamespace(text="Complete analysis with original evidence. " * 10)

    async def generate_async(*args):
        return generate(*args)

    monkeypatch.setattr(llm_calls, "_generate_content", generate)
    monkeypatch.setattr(llm_calls, "_generate_content_async", generate_async)
    context = {}

    async def invoke():
        if entry == "sync_in_event_loop":
            return single_agent.run_single_agent(1, {}, context, h.rotator)
        return await single_agent.run_single_agent_async(1, {}, context, h.rotator)

    assert "Complete analysis" in asyncio.run(invoke())
    assert sent == [("backup", "original evidence")]
    assert sum(h.waits) == 2
    assert h.rotator.model_circuit_wait("m") == 0
    assert h.rotator.provider_quota_exhausted("m") is False
    assert not any(e["phase"] == "llm_rate_limit_retry" for e in context["_runtime_events"])


def test_admission_timeout_ledger_does_not_count_as_provider_failure(monkeypatch):
    import api_usage_recorders

    recorded = []
    monkeypatch.setattr(api_usage_recorders, "record_api_usage", lambda **kw: recorded.append(kw))
    api_usage_recorders.record_runtime_event_usage("job", {
        "phase": "llm_model_error", "message": "本機等待逾時，尚未送出請求。",
        "metadata": {"model_id": "m", "error_category": "local_admission_wait"},
    })
    assert recorded[0]["status"] == "local_admission_wait"
    assert recorded[0]["units"] == 0


@pytest.mark.parametrize("projection", ["route_errors", "daily_usage"])
def test_local_admission_wait_is_excluded_from_provider_error_projections(projection):
    import json
    import sqlite3
    from datetime import datetime, timezone
    from job_ops_dashboard_provider_errors import provider_error_rows
    from llm_daily_usage import build_daily_usage_profile

    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    metadata = {"error_category": "local_admission_wait", "error_kind": "KeyAdmissionTimeout"}
    row = {"created_at": now.timestamp(), "service": "Gemini / Google AI", "operation": "llm_model_error",
           "status": "local_admission_wait", "model_id": "m", "units": 0, "metadata_json": json.dumps(metadata)}
    if projection == "daily_usage":
        result = build_daily_usage_profile([row], now=now)
        assert result["today"]["local_blocks"] == 1
        assert result["today"]["other_errors"] == 0
        assert result["today"]["input_tokens"]["terminal_events"] == 0
    else:
        with sqlite3.connect(":memory:") as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("CREATE TABLE api_usage_events (id INTEGER PRIMARY KEY, service, operation, model_id, status, metadata_json)")
            conn.execute("INSERT INTO api_usage_events (service,operation,model_id,status,metadata_json) VALUES (?,?,?,?,?)",
                         tuple(row[k] for k in ("service", "operation", "model_id", "status", "metadata_json")))
            assert provider_error_rows(conn, 100) == []


@pytest.mark.parametrize("async_mode", [False, True])
def test_local_wait_cap_does_not_spend_primary_generation_timeout(admission, monkeypatch, async_mode):
    """A ready fallback must not wait six minutes behind a throttled primary."""
    import agent_runtime.llm_calls as calls
    import agent_runtime.llm_waiting as waiting

    h = admission
    monkeypatch.setattr("time.monotonic", lambda: h.clock[0])
    monkeypatch.setattr(waiting, "LLM_KEY_ADMISSION_TIMEOUT_SECONDS", 15.0, raising=False)
    monkeypatch.setattr(calls, "estimate_agent_input_tokens", lambda *args: 20)
    h.shared.penalize("key-a", "m", 300)
    h.shared.penalize("key-b", "m", 300)

    def forbidden(*args, **kwargs):
        pytest.fail("a locally throttled request must not contact the provider")

    monkeypatch.setattr(calls, "_generate_content", forbidden)
    monkeypatch.setattr(calls, "_generate_content_async", forbidden)
    context = {}
    args = (1, context, h.rotator, "m", "full evidence")
    with pytest.raises(calls.AgentRateLimitError) as caught:
        if async_mode:
            asyncio.run(calls._run_agent_once_async(*args, timeout_seconds=360))
        else:
            calls._run_agent_once(*args, timeout_seconds=360)
    assert h.clock[0] == 135
    assert caught.value.preflight_blocked is True
    assert caught.value.retry_wait_seconds == 285
    assert not any(e['phase'] == 'llm_provider_request' for e in context['_runtime_events'])
    assert h.rotator._daily_budget.remaining(['key-a', 'key-b'], 'm', 10) == {'key-a': 10, 'key-b': 10}
    assert h.shared._fallback.cooldown_wait('key-a', 'm') == 285


@pytest.mark.parametrize('configured,generation,expected', [
    (15, 360, 15), (15, 120, 15), (15, 2, 2),
    (15, 0, 15), (15, float('inf'), 15),
    (0, 360, 15), (-1, 360, 15), (float('nan'), 360, 15),
])
def test_admission_timeout_remains_finite_without_extending_shorter_deadlines(monkeypatch, configured, generation, expected):
    import agent_runtime.llm_waiting as waiting
    monkeypatch.setattr(waiting, 'LLM_KEY_ADMISSION_TIMEOUT_SECONDS', configured)
    assert waiting.key_admission_timeout(generation) == expected
