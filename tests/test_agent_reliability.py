import asyncio
import copy
from types import SimpleNamespace

import pytest

from agent_runtime import model_policy, quality_retry, single_agent
from agent_runtime.retry_policy import AgentConfigurationError, AgentRateLimitError
from llm_rate_limits import KeyRotator


def test_repair_circuit_uses_the_isolated_task_database(tmp_path):
    import config
    from agent_runtime import repair_circuit_breaker

    assert config.TASK_DB_PATH == str(tmp_path / "analysis_jobs.sqlite3")
    assert repair_circuit_breaker.config.TASK_DB_PATH == str(tmp_path / "analysis_jobs.sqlite3")


def test_task_db_fixture_isolates_retained_config_reference(monkeypatch, tmp_path):
    from agent_runtime import repair_circuit_breaker
    from conftest import isolate_runtime_task_db

    retained_config = SimpleNamespace(TASK_DB_PATH=str(tmp_path / "retained.sqlite3"))
    monkeypatch.setattr(repair_circuit_breaker, "config", retained_config)
    with monkeypatch.context() as patches:
        fixture = isolate_runtime_task_db.__wrapped__(patches, tmp_path)
        try:
            next(fixture)
            assert retained_config.TASK_DB_PATH == str(tmp_path / "analysis_jobs.sqlite3")
        finally:
            fixture.close()


@pytest.mark.parametrize("error_name", ["AgentServerError", "AgentTransientError"])
def test_exhausted_temporary_routes_defer_before_circuit_threshold(monkeypatch, error_name):
    from agent_runtime import retry_policy
    from agent_runtime.deferred import AgentDeferredError

    async def unavailable(*args, **kwargs):
        raise getattr(retry_policy, error_name)("provider temporarily unavailable")

    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: ["primary", "fallback"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: "prompt")
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: None)
    monkeypatch.setattr(single_agent, "_agent_retry_wait", lambda *_: 0)
    monkeypatch.setattr(single_agent, "_run_agent_once_async", unavailable)
    monkeypatch.setattr(model_policy, "LLM_MODEL_CIRCUIT_THRESHOLD", 2)
    with pytest.raises(AgentDeferredError) as caught:
        asyncio.run(single_agent.run_single_agent_async(2, {}, {}, SimpleNamespace(keys=["fake"])))
    assert {route["model_id"] for route in caught.value.routes} == {"primary", "fallback"}
    assert caught.value.retry_wait_seconds >= 60


def test_inherited_circuit_does_not_extend_or_publish(monkeypatch):
    context = {model_policy.MODEL_CIRCUITS_KEY: {"model": {"failures": 1, "opened_until": 1900, "last_error": "429"}}}
    before = copy.deepcopy(context)
    error = AgentRateLimitError("already cooling", 800, 800)
    error.all_keys_exhausted = error.parallel_circuit_open = True
    monkeypatch.setattr(model_policy.time, "time", lambda: 1100)
    state = model_policy.record_model_failure(context, "model", error)
    published = []
    rotator = SimpleNamespace(open_model_circuit=lambda *a, **kw: published.append(kw), open_shared_model_circuit=lambda *a, **kw: published.append(kw))
    model_policy.publish_shared_model_circuit(rotator, "model", state, quota_exhausted=True)
    assert context == before
    assert published == []


def test_quality_retry_retains_the_only_configured_model(monkeypatch):
    monkeypatch.setattr(quality_retry, "get_runtime_model_sequence", lambda *_: ["gemini-3.6-flash"])
    monkeypatch.setattr(quality_retry, "get_agent_model_sequence", lambda *_: ["gemini-3.6-flash"])
    assert quality_retry.quality_retry_model_sequence(16, {}) == ["gemini-3.6-flash"]


def test_all_cooled_routes_defer_without_attempt_or_circuit_refresh(monkeypatch):
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: ["primary", "fallback"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: pytest.fail("blocked routes must not build prompts"))
    rotator = SimpleNamespace(keys=["fake"], is_shared_model_circuit_open=lambda _: True, model_circuit_wait=lambda _: 600)
    with pytest.raises(AgentRateLimitError) as caught:
        asyncio.run(single_agent.run_single_agent_async(2, {}, {}, rotator))
    assert caught.value.retry_wait_seconds >= 600
    assert "primary" in str(caught.value) and "fallback" in str(caught.value)


def test_empty_model_route_is_explicit_configuration_error(monkeypatch):
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: [])
    with pytest.raises(AgentConfigurationError, match="模型"):
        asyncio.run(single_agent.run_single_agent_async(16, {}, {}, object()))


def test_retry_stops_after_all_eligible_keys_not_all_loaded_keys(monkeypatch):
    class Rotator:
        keys = ["a", "disabled", "c", "other-provider"]

        def eligible_key_slots(self, _model):
            return {1, 3}

    calls = []

    async def run_once(_agent, _context, _rotator, model, _prompt, **_kwargs):
        calls.append(model)
        if model == "primary":
            slot = 1 if calls.count(model) % 2 else 3
            raise AgentRateLimitError("429", 0, 60, key_slot=slot, key_count=4)
        return "fallback complete " * 20

    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: ["primary", "fallback"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: "prompt")
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *a, **kw: None)
    monkeypatch.setattr(single_agent, "_agent_retry_wait", lambda *_: 0)
    monkeypatch.setattr(single_agent, "_run_agent_once_async", run_once)
    result = asyncio.run(single_agent.run_single_agent_async(2, {}, {}, Rotator()))
    assert "complete" in result
    assert calls == ["primary", "primary", "fallback"]


def test_key_eligibility_is_provider_and_rpd_scoped(monkeypatch):
    monkeypatch.setattr("llm_rate_limits.create_shared_llm_limiter", lambda: None)
    rotator = KeyRotator({"google": ["a", "b", "c"], "openai": ["other"]})
    monkeypatch.setattr(rotator, "_rpd_disabled_wait", lambda key, model: 100 if key == "b" and model == "gemini-test" else 0)
    eligible = getattr(rotator, "eligible_key_slots", None)
    assert callable(eligible)
    assert eligible("gemini-test") == {1, 3}
    assert eligible("gemini-other") == {1, 2, 3}


def test_failed_quality_rewrite_retains_blocked_original(monkeypatch):
    original = "Original financial draft with an unresolved arithmetic issue. " * 5
    context = {"analyses": {2: original}, "structured_outputs": {2: {"value": 1}}}
    events = []

    async def fail(*_args, **_kwargs):
        return "[Agent 2 執行失敗：empty response]"

    async def status(*_args, **kwargs):
        events.append(kwargs)

    with pytest.raises(quality_retry.AgentQualityDraftError) as caught:
        asyncio.run(quality_retry.retry_after_agent_quality_issues(
            2, {}, context, object(), None, ["arithmetic issue"],
            agent_position=1, agent_total=1, agent_name="finance", pipeline_id="v1", pipeline_label="A",
            run_agent_async=fail, emit_status=status, parse_structured_output=lambda a, text, ctx: (True, text),
        ))
    assert type(caught.value) is quality_retry.AgentQualityDraftError
    assert context["analyses"][2] == original
    assert context.get("blocking_issues")
    assert context["structured_outputs"][2] == {"value": 1}
    assert any(event.get("phase") == "agent_quality_retry_failed" for event in events)
