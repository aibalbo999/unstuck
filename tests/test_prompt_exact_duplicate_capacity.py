"""Remove only exact repeated context; full sources and repair diagnostics remain."""
import asyncio
import copy
import json

import pytest

from agent_runtime import prompting
from agent_runtime.single_agent_prompt import build_model_prompt
from agent_runtime.trade_source_repair import repair_trade_sources
from fixtures.data_payloads import fresh_audited_payload
from state_memory import initialize_agent_state
from structured_output_runtime import process_agent_response
from test_trade_source_completion import setup_payload
from test_trade_source_precise_guidance import source_context, REF
from trade_source_contract import source_block
from trade_source_guidance import source_guidance_text


MODEL = "gemini-3.5-flash-lite"


def test_agent4_includes_complete_previous_context_exactly_once(monkeypatch):
    previous = 'FULL_PREVIOUS_CONTEXT\n' + json.dumps({
        "source": "原始引文，不改數字與單位", "value": 123.456, "warning": "不可省略的反證",
    }, ensure_ascii=False)
    monkeypatch.setattr(prompting, "_format_previous", lambda *args, **kwargs: previous)
    data = fresh_audited_payload()
    context = {"pipeline_id": "v1", "agent_state": initialize_agent_state(data)}
    original = copy.deepcopy((data, context))

    prompt = build_model_prompt(4, data, context, MODEL, False, prompt_builder=prompting.build_prompt)

    assert prompt.count(previous) == 1
    assert "前序分析摘要" in prompt and "不得取代原始資料" in prompt
    assert "【財務資料 JSON】" in prompt and "【AgentState view】" in prompt
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    assert (data, context) == original


def test_trade_repair_deduplicates_guidance_but_preserves_full_source_and_receipt(monkeypatch):
    block, context = source_context()
    context["data"]["company_name"] = "佳大"
    payload = setup_payload()
    payload.update(core_catalyst="外資近30個交易日持續淨賣超3005.03千股。", catalyst_source_refs=[REF])
    result = process_agent_response(24, json.dumps(payload, ensure_ascii=False), context)
    original = copy.deepcopy(context)
    guidance = source_guidance_text(context["_trade_source_manifest"]["catalog"])
    captured = {}

    async def generate(agent, data, ctx, _rotator):
        captured["instruction"] = ctx["_audit_retry_instruction"]
        with monkeypatch.context() as patch:
            patch.setattr(prompting, "deduplicate_source_repair_guidance", lambda instruction, *_: instruction)
            captured["before"] = build_model_prompt(agent, data, ctx, MODEL, False, prompt_builder=prompting.build_prompt)
        captured["prompt"] = build_model_prompt(agent, data, ctx, MODEL, False, prompt_builder=prompting.build_prompt)
        return "offline candidate"

    asyncio.run(repair_trade_sources(result, context["data"], context, None, generate))

    prompt = captured["prompt"]
    assert captured["before"].count(guidance) == 2
    assert prompt.count(guidance) == 1
    assert prompt == "".join(captured["before"].rsplit(guidance, 1))
    assert block in prompt
    assert captured["instruction"].endswith(guidance)
    assert captured["instruction"][:-len(guidance)] in prompt
    assert "continuous_trend_not_established" in prompt
    assert '"value":-3005.03' in prompt and REF in prompt
    assert prompt.endswith(prompting.OUTPUT_CLEANLINESS_RULE)
    assert context["data"] == original["data"]
    assert context["analyses"] == original["analyses"]
    assert context["_trade_source_manifest"]["catalog"] == original["_trade_source_manifest"]["catalog"]


@pytest.mark.parametrize("mismatch", ["instruction", "source_block", "catalog"])
def test_different_guidance_or_incomplete_source_block_is_not_removed(mismatch):
    from trade_source_diagnostics import deduplicate_source_repair_guidance

    block, context = source_context()
    catalog = context["_trade_source_manifest"]["catalog"]
    guidance = source_guidance_text(catalog)
    instruction = "UNIQUE_DIAGNOSTIC" + guidance
    if mismatch == "instruction":
        instruction += "\nUNIQUE_FOLLOWUP_AFTER_GUIDANCE"
    elif mismatch == "source_block":
        block = block.replace(guidance, "", 1)
    else:
        catalog = copy.deepcopy(catalog)
        catalog["short_term_market_context"]["institutional_evidence"]["records"][0]["value"] = -8888.0
    assert deduplicate_source_repair_guidance(instruction, block, catalog) == instruction
