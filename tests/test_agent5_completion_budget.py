import pytest
from google.genai import types
from agent_runtime import generation_config as generation


@pytest.mark.parametrize("model", ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-3-flash-preview"])
def test_risk_role_preserves_output_budget_by_bounding_thinking(model):
    profile = generation.generation_profile(5)
    assert profile["max_output_tokens"] == 8192
    config = types.GenerateContentConfig(**profile)
    adjusted = generation.apply_model_generation_policy(config, model, 5)
    assert adjusted.max_output_tokens == 8192
    assert adjusted.thinking_config.thinking_level.value == "LOW"
    assert generation.generation_event_metadata(5, model)["thinking_level"] == "low"



def test_agent1_completion_budget_preserves_sampling_and_agent20_cap():
    assert generation.generation_profile(1) == {"temperature": 0.45, "top_p": 0.90, "max_output_tokens": 8192}
    assert generation.build_generation_config(1, "same system").max_output_tokens == 8192
    assert generation.generation_profile(20) == {"temperature": 0.20, "top_p": 0.85, "max_output_tokens": 1024}
    assert generation.generation_profile(5)["max_output_tokens"] == 8192
    assert generation.generation_profile(6)["max_output_tokens"] == 8192


@pytest.mark.parametrize("agent", [1, 20])
@pytest.mark.parametrize("model", ["gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.8-flash", "google:gemini-3.6-flash", "models/gemini-3-flash-preview"])
def test_agent1_and20_model_specific_low_thinking_in_real_sdk_config(agent, model):
    config = generation.build_generation_config(agent, "unchanged system")
    original = config.model_dump()
    adjusted = generation.apply_model_generation_policy(config, model, agent)
    assert config.model_dump() == original
    assert adjusted.thinking_config.thinking_level.value == "LOW"
    expected = dict(original)
    expected["thinking_config"] = adjusted.thinking_config.model_dump()
    assert adjusted.model_dump() == expected
    assert adjusted.max_output_tokens == (8192 if agent == 1 else 1024)
    metadata = generation.generation_event_metadata(agent, model)
    assert metadata["thinking_level"] == "low"
    assert metadata["max_output_tokens"] == adjusted.max_output_tokens


@pytest.mark.parametrize("agent", [1, 20])
@pytest.mark.parametrize("model", ["gemma-3-27b-it", "gemini-2.5-flash", "unrecognized-model"])
def test_agent1_and20_do_not_invent_thinking_support(agent, model):
    config = generation.build_generation_config(agent, "unchanged system")
    assert generation.apply_model_generation_policy(config, model, agent) is config
    assert "thinking_level" not in generation.generation_event_metadata(agent, model)


@pytest.mark.parametrize("model", ["gemini-3.6-flash", "gemini-3-flash-preview", "gemini-3.8-flash"])
def test_agent2_full_completion_budget_and_native_sdk_policy(model):
    assert generation.generation_profile(2) == {"temperature": 0.25, "top_p": 0.90, "max_output_tokens": 8192}
    config = generation.build_generation_config(2, "original Agent2 system")
    original = config.model_dump()
    adjusted = generation.apply_model_generation_policy(config, model, 2)
    assert adjusted.max_output_tokens == 8192
    assert adjusted.thinking_config.thinking_level.value == "LOW"
    assert config.model_dump() == original
    expected = dict(original)
    expected["thinking_config"] = adjusted.thinking_config.model_dump()
    assert adjusted.model_dump() == expected
    metadata = generation.generation_event_metadata(2, model)
    assert metadata["max_output_tokens"] == 8192
    assert metadata["thinking_level"] == "low"
