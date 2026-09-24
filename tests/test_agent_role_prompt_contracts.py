"""Offline contracts for the instructions actually delivered to each research role."""

import json
import re

import pytest


def _request(agent, pipeline, **context):
    from agent_runtime.generation_config import google_safe_agent_system_instruction
    from agent_runtime.prompting import build_prompt

    model = "gemini-3.8-flash"
    data = {
        "ticker": "ROLE-CONTRACT.TW",
        "company_name": "角色契約測試公司",
        "current_price": 100,
        "free_cash_flow_raw": -1_000_000_000,
        "data_trust": {"status": "fresh", "critical_failures": []},
    }
    prompt = build_prompt(agent, data, {"pipeline_id": pipeline, "_prompt_model_id": model, **context})
    return google_safe_agent_system_instruction(agent, model), prompt


@pytest.mark.parametrize("agent,pipeline", [(2, "v1"), (3, "v1"), (4, "v1"), (7, "v1"), (12, "v2"), (14, "v2"), (16, "v2")])
def test_structured_roles_have_one_json_envelope_without_legacy_first_block(agent, pipeline):
    from agent_runtime.prompt_config import SYSTEM_PROMPTS, ANALYSIS_PROMPTS

    system, prompt = _request(agent, pipeline)
    assert "只輸出合法 JSON" in system
    assert "只輸出合法 JSON" in prompt
    assert "analysis_markdown" in system and "analysis_markdown" in prompt
    instructions = SYSTEM_PROMPTS[agent] + "\n" + ANALYSIS_PROMPTS[agent]
    assert not re.search(r"(?:第一段|第一行|最上方).{0,70}(?:輸出|護城河評分|目標股價|風險評估)", instructions)
    assert not re.search(r"\[(?:護城河評分|目標股價|風險評估)\]\n", instructions)
    assert "renderer" in system


@pytest.mark.parametrize("agent,pipeline", [(7, "v1"), (16, "v2")])
@pytest.mark.parametrize("count", [0, 1, 2, 5])
def test_final_role_receives_and_answers_only_actual_bear_findings(agent, pipeline, count):
    from structured_output_risk_models import BearAdvocateStructuredOutput

    risks = [{"title": f"ACTUAL_RISK_{n}", "evidence": f"原始來源_{n}", "impact": "可能影響現金流", "falsifier": f"可證偽條件_{n}"} for n in range(count)]
    bear = BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "僅有本次來源支持的反證",
        "downside_risks": risks,
        "analysis_markdown": "\n".join(r["title"] for r in risks) or "無足夠反證，資料限制需保留。",
    })
    _, prompt = _request(agent, pipeline, analyses={21: bear.analysis_markdown}, structured_outputs={21: bear.model_dump()})
    for n in range(count):
        assert f"ACTUAL_RISK_{n}" in prompt
    assert "3 至 5 項空頭結論" not in prompt
    assert "實際提供" in prompt and "逐項回應" in prompt
    assert "0 項" in prompt and "不得補造" in prompt
    assert "接受、部分接受或駁回" in prompt


def test_swing_risk_rule_uses_visible_fcf_and_does_not_invent_its_period():
    system, prompt = _request(24, "v4")
    financial = json.loads(prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0])
    assert financial["cash_flow"]["free_cash_flow_billion_twd"] == -1.0
    assert "cash_flow.free_cash_flow_billion_twd" in system
    assert "ttm_financials.free_cash_flow" not in system
    assert "TTM 自由現金流為負" not in system
    assert "期間" in system and "High" in system


def test_growth_role_distinguishes_evidence_assumptions_and_verified_calculations():
    system, prompt = _request(5, "v1")
    for text in (system, prompt):
        assert all(term in text for term in ("已觀測事實", "情境假設", "deterministic", "未評估"))
        assert "列舉 3-5 個" not in text
    assert "NT$XXX億" not in prompt
    assert "不強迫填滿三情境數字" in prompt


@pytest.mark.parametrize("agent,pipeline", [(13, "v2"), (18, "v3")])
def test_forensic_roles_allow_no_adverse_findings_and_unassessed_sparse_data(agent, pipeline):
    system, prompt = _request(agent, pipeline)
    assert "未評估" in system and "未評估" in prompt
    assert "列出 1~3" not in prompt
    assert "零項" in prompt
    assert "至少提供 1 項 evidence_items" in prompt  # Retain evidence contract, not a minimum red-flag count.
    assert "資料限制" in prompt
    if agent == 18:
        assert "派發評分" in prompt and "派發評分" in system
        assert "不得以預設分數" in prompt
        assert "允許駁回 Agent C1" in system


@pytest.mark.parametrize("agent,pipeline,tools", [(2, "v1", {"calculate_cagr"}), (13, "v2", {"calculate_cagr", "calculate_dupont"}), (18, "v3", {"calculate_cagr", "calculate_dupont"})])
def test_financial_calculator_instructions_match_available_tools_and_require_results(agent, pipeline, tools):
    from agent_runtime.routing import get_agent_function_tools
    from agent_runtime.prompting import build_numeric_tool_instruction

    names = {tool.__name__ for tool in get_agent_function_tools(agent)}
    assert names == tools
    rules = build_numeric_tool_instruction(agent)
    assert "優先引用" in rules and "成功回傳" in rules
    assert "來源、期間、單位" in rules
    for name in tools:
        assert name in rules
    assert "CAGR 只引用" not in rules
    _, prompt = _request(agent, pipeline)
    assert "所有精確數值（包含 CAGR、FCF轉換率等）必須直接引用 {quant_metrics}" not in prompt


def test_macro_company_debate_and_editor_responsibilities_are_explicit():
    from agent_runtime.prompt_config import NAMED_SYSTEM_PROMPTS

    _, business = _request(1, "v1", analyses={11: "MACRO_EVIDENCE_FOR_COMPANY"})
    assert "Agent 11" in business and "公司" in business
    assert "MACRO_EVIDENCE_FOR_COMPANY" in business
    debate_system, debate = _request(6, "v1")
    assert "同一次模型生成" in debate_system
    assert "不代表兩個獨立" in debate_system
    assert "模擬" in debate and "Round 3" in debate
    chief = NAMED_SYSTEM_PROMPTS["chief_editor"]
    assert "legacy" in chief and "run_chief_editor_synthesis" in chief and "deterministic" in chief


def test_all_registered_role_templates_and_modes_remain_valid():
    from agent_catalog import AGENT_NAMES
    from agent_runtime.prompt_config import SYSTEM_PROMPTS, ANALYSIS_PROMPTS
    from pipeline_modes import PIPELINE_DEFINITIONS
    from prompt_loader import load_agent_prompt_config

    config = load_agent_prompt_config()
    assert config["prompt_fingerprint"]
    assert set(SYSTEM_PROMPTS) == set(ANALYSIS_PROMPTS) == set(AGENT_NAMES)
    for pipeline, definition in PIPELINE_DEFINITIONS.items():
        for agent in definition["agents"]:
            system, prompt = _request(agent, pipeline)
            assert len(system) > 50 and len(prompt) > 100
            assert "角色契約測試公司" in prompt
            assert "{{ ticker }}" not in prompt and "{{ name }}" not in prompt
