"""An exhausted 5xx route backs off across jobs without disabling API keys."""
import asyncio
from types import SimpleNamespace

import pytest

from agent_runtime import model_policy, single_agent
from agent_runtime.deferred import AgentDeferredError, record_route_failure
from agent_runtime.retry_policy import AgentServerError
from llm_rate_limits import KeyRotator
from shared_runtime_guards import RedisFixedWindowRateLimiter


@pytest.fixture(params=["local", "redis"])
def service(monkeypatch, request):
    clock = [1000.0]
    timer = SimpleNamespace(time=lambda: clock[0])
    for module in ("agent_runtime.model_policy", "agent_runtime.deferred", "llm_model_circuits",
                   "shared_runtime_guards", "shared_runtime_local_guards"):
        monkeypatch.setattr(module + ".time", timer)
    shared = RedisFixedWindowRateLimiter(None)

    class RedisDouble:
        expirations = {}

        def set(self, key, value, *, px):
            self.expirations[key] = clock[0] + px / 1000

        def pttl(self, key):
            return max(-2, round((self.expirations.get(key, 0) - clock[0]) * 1000))

    client = RedisDouble()
    # Distinct limiter instances exercise the Redis publication boundary.
    factory = (lambda: shared) if request.param == "local" else (lambda: RedisFixedWindowRateLimiter(client))
    monkeypatch.setattr("llm_rate_limits.create_shared_llm_limiter", factory)
    monkeypatch.setattr(model_policy, "LLM_ROUTE_SERVER_ERROR_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(model_policy, "LLM_SERVER_ERROR_MODEL_COOLDOWN_SECONDS", 60)
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: ["busy", "ready"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: "full original evidence " * 20)
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *a, **kw: None)
    monkeypatch.setattr(single_agent, "_agent_retry_wait", lambda *_: 0)
    calls = []
    failing = {"busy"}

    def generate(_agent, _context, _rotator, model, prompt, **kwargs):
        calls.append((model, prompt))
        if model in failing:
            raise AgentServerError("503 UNAVAILABLE")
        return "Complete result with all original evidence. " * 10

    async def generate_async(*args, **kwargs):
        return generate(*args, **kwargs)

    monkeypatch.setattr(single_agent, "_run_agent_once", generate)
    monkeypatch.setattr(single_agent, "_run_agent_once_async", generate_async)
    return SimpleNamespace(clock=clock, shared=shared, calls=calls, failing=failing,
                           rotator=lambda: KeyRotator(["test-a", "test-b"]))


@pytest.mark.parametrize("entry", ["async", "sync_in_loop"])
def test_exhausted_server_route_is_shared_and_expires(service, entry):
    h = service

    async def run(rotator):
        if entry == "sync_in_loop":
            return single_agent.run_single_agent(2, {}, {}, rotator)
        return await single_agent.run_single_agent_async(2, {}, {}, rotator)

    first, second = h.rotator(), h.rotator()
    assert "Complete" in asyncio.run(run(first))
    assert [m for m, _ in h.calls] == ["busy", "busy", "ready"]
    assert second.model_circuit_wait("busy") == 60
    h.clock[0] += 10
    assert "Complete" in asyncio.run(run(second))
    assert [m for m, _ in h.calls] == ["busy", "busy", "ready", "ready"]
    assert second.model_circuit_wait("busy") == 50  # A skip must not renew it.
    assert all(prompt == "full original evidence " * 20 for _, prompt in h.calls)
    assert second.eligible_key_slots("busy") == {1, 2}
    assert second.provider_quota_exhausted("busy") is False
    h.clock[0] += 51
    h.failing.clear()
    assert "Complete" in asyncio.run(run(h.rotator()))
    assert h.calls[-1][0] == "busy"


def test_all_failed_routes_defer_then_other_job_sends_nothing(service):
    h = service
    h.failing.add("ready")
    for _ in range(2):
        with pytest.raises(AgentDeferredError) as caught:
            asyncio.run(single_agent.run_single_agent_async(2, {}, {}, h.rotator()))
        assert caught.value.provider_quota_confirmed is False
        assert caught.value.retry_wait_seconds == 60
    assert [m for m, _ in h.calls] == ["busy", "busy", "ready", "ready"]


def test_inherited_server_circuit_does_not_extend_or_publish(service):
    h = service
    rotator = h.rotator()
    rotator.open_shared_model_circuit("busy", opened_until=1060)
    h.clock[0] += 20
    error = AgentServerError("503 from an in-flight peer request")
    policy = model_policy.model_attempt_policy(0, True, 3, 2)
    stop = model_policy.make_model_retry_stop_for_rotator(policy, rotator, "busy")
    state = SimpleNamespace(attempt_number=1, outcome=SimpleNamespace(exception=lambda: error))
    assert stop(state) is True
    assert getattr(error, "parallel_circuit_open", False) is True
    record_route_failure({}, rotator, "busy", error, [])
    assert rotator.model_circuit_wait("busy") == 40


def test_recovered_route_does_not_open_shared_circuit(service, monkeypatch):
    h = service
    attempts = []

    async def recover(*args, **kwargs):
        attempts.append(args[3])
        if len(attempts) == 1:
            raise AgentServerError("503 temporarily busy")
        return "Recovered complete original analysis. " * 10

    monkeypatch.setattr(single_agent, "_run_agent_once_async", recover)
    asyncio.run(single_agent.run_single_agent_async(2, {}, {}, h.rotator()))
    assert attempts == ["busy", "busy"]
    assert h.rotator().model_circuit_wait("busy") == 0
