import asyncio
from types import SimpleNamespace

import pytest

import llm_rate_limits
from llm_rate_limit_buckets import TokenBucket


@pytest.mark.parametrize("method", ["reserve", "peek_wait"])
def test_token_bucket_does_not_clip_oversized_request(method):
    bucket = TokenBucket.per_minute(16000)
    with pytest.raises(ValueError, match="capacity"):
        getattr(bucket, method)(24228)
    assert bucket.tokens == 16000


@pytest.mark.parametrize("async_call", [False, True])
def test_rotator_rejects_oversize_before_reserving_or_waiting(monkeypatch, async_call):
    monkeypatch.setattr(llm_rate_limits, "TPM_LIMITS", {"model-a": 16000})
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    rotator = llm_rate_limits.KeyRotator(["key"])
    monkeypatch.setattr(rotator, "_available_candidate_key_positions", lambda _: pytest.fail("must reject before selecting a key"))
    assert hasattr(llm_rate_limits, "InputCapacityExceededError")
    with pytest.raises(llm_rate_limits.InputCapacityExceededError) as exc:
        if async_call:
            asyncio.run(rotator.async_get_key("model-a", 24228))
        else:
            rotator.get_key("model-a", 24228)
    assert exc.value.limit == 16000
    assert exc.value.basis == "configured_input_tpm"


def test_input_capacity_failure_is_not_a_retryable_provider_error():
    from agent_runtime.retry_policy import _raise_agent_call_error, AgentRetryableError
    assert hasattr(llm_rate_limits, "InputCapacityExceededError")
    error = llm_rate_limits.InputCapacityExceededError("model-a", 20000, 12000, "local_input_budget")
    with pytest.raises(type(error)):
        _raise_agent_call_error(error, None, "model-a", SimpleNamespace(keys=["key"]), 60)
    assert not isinstance(error, AgentRetryableError)


def test_redis_rejects_oversize_before_network():
    import shared_runtime_guards
    client = SimpleNamespace(eval=lambda *_: pytest.fail("must reject before Redis"))
    limiter = shared_runtime_guards.RedisFixedWindowRateLimiter(client)
    assert hasattr(llm_rate_limits, "InputCapacityExceededError")
    with pytest.raises(llm_rate_limits.InputCapacityExceededError):
        limiter.reserve("key", "model-a", rpm_limit=5, tpm_limit=16000, estimated_tokens=24228)


def test_agent_input_estimate_includes_system_and_schema_but_not_output_reserve(monkeypatch):
    from agent_runtime import generation_config
    assert hasattr(generation_config, "estimate_agent_input_tokens")
    monkeypatch.setattr(generation_config, "google_safe_agent_system_instruction", lambda *_: "system")
    monkeypatch.setattr(generation_config, "build_generation_config", lambda *_: SimpleNamespace(
        model_dump=lambda **_: {"max_output_tokens": 999999, "system_instruction": "system", "response_schema": {"type": "OBJECT"}}))
    amount = generation_config.estimate_agent_input_tokens(1, "model-a", "prompt")
    assert 10 < amount < 1000


def test_local_input_budget_does_not_change_unrelated_model(monkeypatch):
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    monkeypatch.setattr(llm_rate_limits, "TPM_LIMITS", {})
    assert hasattr(llm_rate_limits, "MODEL_INPUT_TOKEN_LIMITS")
    monkeypatch.setattr(llm_rate_limits, "MODEL_INPUT_TOKEN_LIMITS", {"model-a": 12000})
    rotator = llm_rate_limits.KeyRotator(["key"])
    with pytest.raises(llm_rate_limits.InputCapacityExceededError):
        rotator.get_key("model-a", 16000)
    assert rotator.get_key("model-b", 16000) == "key"


def test_new_flash_models_use_supported_bounded_thinking():
    from agent_runtime import generation_config
    assert hasattr(generation_config, "apply_model_generation_policy")
    config = generation_config.build_generation_config(7, "test")
    for model in ("gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"):
        adjusted = generation_config.apply_model_generation_policy(config, model)
        assert adjusted.thinking_config.thinking_level.value == "LOW"
        assert adjusted.response_schema == config.response_schema
    assert generation_config.apply_model_generation_policy(config, "old-model") is config


def test_capacity_error_has_local_category_and_safe_event_details():
    from agent_runtime.retry_error_classification import _agent_error_category
    from agent_runtime.llm_call_events import llm_model_error_fields
    error = llm_rate_limits.InputCapacityExceededError("model-a", 20000, 12000, "local_input_budget")
    assert _agent_error_category(error) == "input_capacity"
    event = llm_model_error_fields({}, 1, "model-a", "prompt", SimpleNamespace(keys=["key"]), None,
                                  timeout_seconds=10, error=error)
    assert event["metadata"]["input_capacity"]["limit"] == 12000
    assert "key_slot" not in event["metadata"]


@pytest.mark.parametrize("async_call", [False, True])
def test_oversize_route_falls_back_once_without_opening_circuit(monkeypatch, async_call):
    from agent_runtime import single_agent, llm_calls
    from agent_runtime.model_policy import MODEL_CIRCUITS_KEY
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    monkeypatch.setattr(llm_rate_limits, "TPM_LIMITS", {})
    monkeypatch.setattr(llm_rate_limits, "MODEL_INPUT_TOKEN_LIMITS", {"small": 1})
    monkeypatch.setattr(single_agent, "get_runtime_model_sequence", lambda *_: ["small", "large"])
    monkeypatch.setattr(single_agent, "build_prompt", lambda *_: "Full evidence remains unchanged. " * 100)
    monkeypatch.setattr(single_agent, "get_cached_agent_step", lambda *_: None)
    monkeypatch.setattr(single_agent, "store_cached_agent_step", lambda *_, **__: None)
    sent = []

    def generate(key, model, agent, prompt):
        sent.append((model, prompt))
        return SimpleNamespace(text="A complete analysis section. " * 20)

    async def generate_async(*args):
        return generate(*args)

    monkeypatch.setattr(llm_calls, "_generate_content", generate)
    monkeypatch.setattr(llm_calls, "_generate_content_async", generate_async)
    context = {}
    rotator = llm_rate_limits.KeyRotator(["key"])
    if async_call:
        result = asyncio.run(single_agent.run_single_agent_async(2, {}, context, rotator))
    else:
        result = single_agent.run_single_agent(2, {}, context, rotator)
    assert "complete" in result
    assert [model for model, _ in sent] == ["large"]
    assert sent[0][1] == "Full evidence remains unchanged. " * 100
    assert not context.get(MODEL_CIRCUITS_KEY)
def test_request_units_include_automatic_function_calling_bound():
    from agent_runtime.generation_config import agent_request_budget_options
    assert agent_request_budget_options(2) == {"request_units": 6}
    assert agent_request_budget_options(13) == {"request_units": 6}
    assert agent_request_budget_options(18) == {"request_units": 6}
    assert agent_request_budget_options(24) == {}
