"""Bound Agent 19 generation without shortening sources or weakening schemas."""

import asyncio
import copy

import pytest

from agent_runtime import generation_config as generation
from google_prompt_safety import sanitize_google_generation_config
from recommendation_labels import normalize_recommendation_label


MODELS = ("gemini-3.8-flash", "gemini-3-flash-preview", "gemini-3.6-flash", "gemini-3.5-flash-lite")


@pytest.mark.parametrize("model", MODELS)
def test_agent19_reserves_existing_output_budget_using_low_thinking(model):
    before = generation.build_generation_config(19, "original system")
    adjusted = generation.apply_model_generation_policy(before, model, 19)
    assert adjusted.thinking_config.thinking_level.value == "LOW"
    assert adjusted.max_output_tokens == before.max_output_tokens == 6144
    assert adjusted.response_schema == before.response_schema
    assert adjusted.system_instruction == "original system"
    assert generation.generation_event_metadata(19, model)["thinking_level"] == "low"


def test_agent19_does_not_expand_policy_to_unknown_or_other_provider_models():
    config = generation.build_generation_config(19, "original system")
    assert generation.apply_model_generation_policy(config, "unknown-model", 19) is config
    assert generation.apply_model_generation_policy(config, "openai:gpt-example", 19) is config
    assert generation.apply_model_generation_policy(config, "gemini-3.8-flash", 16).thinking_config.thinking_level.value == "MEDIUM"
    assert generation.apply_model_generation_policy(config, "gemini-3-flash-preview", 16) is config


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "gemini-3-flash-preview"])
def test_agent19_instructions_prioritize_complete_schema_and_evidence_over_redundancy(model):
    system = generation.google_safe_agent_system_instruction(19, model)
    assert "完整 JSON" in system
    assert "response_schema" in system
    assert "800–1200" in system
    assert "market_context_assessment" in system
    assert "source_refs" in system
    assert "完整來源" in system
    assert "highly detailed" not in system
    assert "建議" in system or "研究分類" in system
    assert "等待" in system
    assert "製造業" in system
    other = generation.google_safe_agent_system_instruction(18, model)
    assert "800–1200" not in other


def test_google_wire_enums_remain_valid_aliases_of_product_labels():
    original = generation.build_generation_config(19, "system")
    wire = sanitize_google_generation_config(original)
    product_values = original.response_schema["$defs"]["BubbleSniperRecommendationFields"]["properties"]["建議"]["enum"]
    wire_values = wire.response_schema["$defs"]["BubbleSniperRecommendationFields"]["properties"]["建議"]["enum"]
    assert product_values == ["買入", "持有", "避免", "放空"]
    assert wire_values == ["偏多觀察", "中性觀察", "避險觀察", "空方風險觀察"]
    assert normalize_recommendation_label(wire_values[1]) == product_values[1]
    assert normalize_recommendation_label("中性觀察") == "持有"


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_agent19_generation_keeps_entire_input_and_makes_one_call(monkeypatch, mode):
    prompt = "完整原始財務資料 marker-A\n" + "原文數字 -1.025 單位億元，日期2026-09-18\n" * 500 + "\nmarker-Z"
    original = copy.deepcopy(prompt)
    observed = []
    def capture(key, model, text, config, **kwargs):
        observed.append((text, config))
        return object()
    async def capture_async(*args, **kwargs): return capture(*args, **kwargs)
    monkeypatch.setattr(generation, "generate_content", capture)
    monkeypatch.setattr(generation, "generate_content_async", capture_async)
    monkeypatch.setattr(generation, "generate_content_stream_async", capture_async)
    if mode == "sync":
        generation._generate_content("synthetic", "gemini-3-flash-preview", 19, prompt)
    elif mode == "async":
        asyncio.run(generation._generate_content_async("synthetic", "gemini-3-flash-preview", 19, prompt))
    else:
        asyncio.run(generation._generate_content_stream_async("synthetic", "gemini-3-flash-preview", 19, prompt))
    assert len(observed) == 1
    assert observed[0][0] == prompt == original
    assert observed[0][1].max_output_tokens == 6144
    assert observed[0][1].thinking_config.thinking_level.value == "LOW"



def test_agent19_repair_receives_specific_non_short_contract_failure():
    from agent_runtime.repair_state import repair_contract_issues
    output = {
        "recommendation": {"建議": "持有"},
        "short_setup": {"entry_trigger": "若跌破28元則建立空單；目前觀望。",
                        "squeeze_risk": "缺少借券資料，存在軋空風險。",
                        "thesis_invalidation": "若基本面改善則重新評估。"},
    }
    context = {"pipeline_id": "v3", "data": {}, "structured_outputs": {19: output}}
    assert any("entry_trigger" in issue and "執行指令" in issue for issue in repair_contract_issues(19, context))
    output["short_setup"]["entry_trigger"] = "等待可靠借券與財務資料後重新評估，目前不開倉。"
    assert not repair_contract_issues(19, context)


@pytest.mark.parametrize("model", ["gemini-3-flash-preview", "gemini-3.6-flash", "google:gemini-3.6-flash"])
def test_agent18_complete_output_keeps_4096_budget_and_explicit_low_thinking(model):
    config = generation.build_generation_config(18, "full original system")
    adjusted = generation.apply_model_generation_policy(config, model, 18)
    assert adjusted.thinking_config.thinking_level.value == "LOW"
    assert adjusted.max_output_tokens == config.max_output_tokens == 4096
    assert adjusted.system_instruction == "full original system"
    assert adjusted.tools == config.tools
    assert generation.generation_event_metadata(18, model)["thinking_level"] == "low"
    assert generation.GENERATION_POLICY_VERSION == "agent-generation:v3"


def test_agent18_thinking_policy_stays_within_known_google_routes():
    config = generation.build_generation_config(18)
    assert generation.apply_model_generation_policy(config, "openai:gemini-3.6-flash", 18) is config
    assert generation.apply_model_generation_policy(config, "unknown-model", 18) is config
    assert generation.apply_model_generation_policy(config, "gemini-3.6-flash", 17) is config


def test_agent19_wire_enum_meaning_uses_current_forward_return_contract():
    from forward_consistency_checker import RECOMMENDATION_RETURN_GATES
    system = generation.google_safe_agent_system_instruction(19, "gemini-3.8-flash")
    gates = RECOMMENDATION_RETURN_GATES
    assert f'偏多觀察（BUY）：12 個月隱含報酬至少 {gates["買入"]["min_expected_return_pct"]:g}%' in system
    assert f'中性觀察（HOLD）：12 個月隱含報酬須介於 {gates["持有"]["min_expected_return_pct"]:g}% 至 {gates["持有"]["max_expected_return_pct"]:g}%' in system
    assert f'空方風險觀察（SHORT）：12 個月隱含報酬不得高於 {gates["放空"]["max_expected_return_pct"]:g}%' in system
    assert "避險觀察（AVOID）" in system
    assert "不等於通用的等待或不開倉" in system
    assert "不得為符合門檻補造或調整價格" in system
    assert "缺少現價或目標價時保留資料不足" in system


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_agent18_low_thinking_keeps_full_source_and_single_generation(monkeypatch, mode):
    prompt = "完整來源前端\n" + "來源數字與日期保持原樣 2026-09-20 5000千股\n" * 300 + "完整來源末端"
    observed = []
    def generate(key, model, text, config, **kwargs):
        observed.append((text, config))
        return object()
    async def generate_async(*args, **kwargs): return generate(*args, **kwargs)
    monkeypatch.setattr(generation, "generate_content", generate)
    monkeypatch.setattr(generation, "generate_content_async", generate_async)
    monkeypatch.setattr(generation, "generate_content_stream_async", generate_async)
    if mode == "sync": generation._generate_content("synthetic", "gemini-3-flash-preview", 18, prompt)
    elif mode == "async": asyncio.run(generation._generate_content_async("synthetic", "gemini-3-flash-preview", 18, prompt))
    else: asyncio.run(generation._generate_content_stream_async("synthetic", "gemini-3-flash-preview", 18, prompt))
    assert len(observed) == 1
    assert observed[0][0] == prompt
    assert observed[0][1].max_output_tokens == 4096
    assert observed[0][1].thinking_config.thinking_level.value == "LOW"
