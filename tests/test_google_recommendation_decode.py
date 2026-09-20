"""Provider wire labels must round-trip without changing natural-language aliases."""

import asyncio
import json

import pytest

from agent_runtime.generation_config import build_generation_config
from google_prompt_safety import sanitize_google_generation_config
from recommendation_labels import normalize_recommendation_label
from structured_output_runtime import process_agent_response


def _payload(label, field="建議"):
    return {
        "reasoning_steps": ["估值提供佐證", "風險仍須評估", "等待催化劑驗證"],
        "recommendation": {
            field: label,
            "短期目標（3個月）": "30",
            "中期目標（6個月）": "32",
            "長期目標（12個月）": "35",
            "長期潛力（5年）": "40",
            "信心指數": "5/10",
        },
        "confidence_basis": {
            "evidence_items": ["來源一", "來源二", "來源三"],
            "key_risks_acknowledged": ["需求風險", "資料限制"], "data_gaps": [],
        },
        "scenario_triggers": [
            {"trigger_condition": "營收下降", "action": "重新評估", "direction": "bearish_downgrade"},
            {"trigger_condition": "需求回升", "action": "重新評估", "direction": "bullish_upgrade"},
        ],
        "position_plan": {"action": "等待", "entry_zone": "N/A", "position_size": "0%",
                          "stop_loss": "N/A", "risk_reward": "N/A", "invalidation_condition": "重新評估"},
        "short_setup": {"entry_trigger": "等待資料，目前不開倉", "downside_target": "N/A",
                        "cover_stop": "N/A", "squeeze_risk": "軋空風險", "thesis_invalidation": "財務改善"},
        "market_context_assessment": {"global_market_context": {
            "impact": "no_material_impact", "reason": "偏多觀察是原始來源文字，須保留",
            "source_refs": ["global:source-1"]}},
        "analysis_markdown": "偏多觀察與中性觀察均為引用文字，不可全文替換。",
    }


@pytest.mark.parametrize("agent", [7, 16, 19])
@pytest.mark.parametrize("index, expected", list(enumerate(["買入", "持有", "避免", "放空"])))
def test_google_schema_recommendation_roundtrips_through_actual_response_decoder(agent, index, expected):
    config = sanitize_google_generation_config(build_generation_config(agent, "system"))
    schema_name = "BubbleSniperRecommendationFields" if agent == 19 else "RecommendationFields"
    wire_label = config.response_schema["$defs"][schema_name]["properties"]["建議"]["enum"][index]
    payload = _payload(wire_label)
    context = {"data": {}}
    process_agent_response(agent, json.dumps(payload, ensure_ascii=False), context, model_id="gemini-3.8-flash")
    output = context["structured_outputs"][agent]
    assert output["recommendation"]["建議"] == expected
    assert output["analysis_markdown"] == payload["analysis_markdown"]
    assert output["market_context_assessment"] == payload["market_context_assessment"]
    assert output["recommendation"]["短期目標（3個月）"] == "30"


@pytest.mark.parametrize("model", ["google:gemini-test", "gemini:gemini-test", "gemini-test"])
@pytest.mark.parametrize("field", ["建議", "recommendation"])
def test_google_route_aliases_and_structured_field_alias_decode(model, field):
    context = {"data": {}}
    process_agent_response(19, json.dumps(_payload("偏多觀察", field)), context, model_id=model)
    assert context["structured_outputs"][19]["recommendation"]["建議"] == "買入"


@pytest.mark.parametrize("model", [None, "", "openai:gpt-test", "anthropic:claude-test"])
def test_without_explicit_google_boundary_natural_language_alias_remains_hold(model):
    context = {"data": {}}
    kwargs = {} if model is None else {"model_id": model}
    process_agent_response(19, json.dumps(_payload("偏多觀察")), context, **kwargs)
    assert context["structured_outputs"][19]["recommendation"]["建議"] == "持有"
    assert normalize_recommendation_label("偏多觀察") == "持有"


def test_decoder_does_not_promote_compound_natural_language_to_buy():
    context = {"data": {}}
    process_agent_response(19, json.dumps(_payload("偏多觀察，但仍須等待")), context, model_id="gemini-test")
    assert context["structured_outputs"][19]["recommendation"]["建議"] == "持有"


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_actual_agent_call_passes_google_model_identity_to_decoder(monkeypatch, mode):
    from agent_runtime import llm_calls as calls
    from test_llm_congestion_integration import ScopeSpy, _agent, _response
    _agent(monkeypatch, ScopeSpy(), [])
    monkeypatch.setattr(calls, "process_agent_response", process_agent_response)
    response = _response(json.dumps(_payload("偏多觀察")))
    monkeypatch.setattr(calls, "_generate_content", lambda *a, **k: response)
    async def generate(*a, **k): return response
    monkeypatch.setattr(calls, "_generate_content_async", generate)
    monkeypatch.setattr(calls, "_generate_content_stream_async", generate)
    monkeypatch.setattr(calls, "_should_stream_llm_response", lambda *a: mode == "stream")
    context = {"data": {}}
    if mode == "sync":
        calls._run_agent_once(19, context, object(), "gemini-test", "complete source")
    else:
        asyncio.run(calls._run_agent_once_async(19, context, object(), "gemini-test", "complete source"))
    assert context["structured_outputs"][19]["recommendation"]["建議"] == "買入"
