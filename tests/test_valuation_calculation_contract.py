"""The valuation request cannot promise calculators its JSON route does not expose."""

import json

import pytest

from agent_runtime.generation_config import build_generation_config
from agent_runtime.prompt_config import SYSTEM_PROMPTS
from agent_runtime.prompting import build_prompt
from financial_tools import build_financial_tool_context


def _financials():
    return {
        "ticker": "TEST.TW", "company_name": "測試公司", "current_price": 208.0,
        "shares_raw": 66_000_000, "market_cap_raw": 13_728_000_000,
        "total_debt_raw": 2_898_000_000, "total_cash_raw": 500_000_000,
        "free_cash_flow_raw": 461_411_616, "trailing_eps": 5.0,
        "revenue_history": [1.0, 1.2],
    }


def _request(agent, data):
    prompt = build_prompt(agent, data, {"pipeline_id": "v1" if agent == 4 else "v2"})
    return SYSTEM_PROMPTS[agent] + "\n" + prompt, json.loads(
        prompt.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
    )


@pytest.mark.parametrize("agent", [4, 14])
def test_native_json_valuation_request_does_not_require_unavailable_tools(agent):
    config = build_generation_config(agent)
    assert config.response_mime_type == "application/json"
    assert config.response_schema
    assert not config.tools

    instructions, _ = _request(agent, _financials())
    assert "本次估值回應未提供可呼叫工具" in instructions
    assert "必須主動呼叫對應工具" not in instructions
    assert "調整參數但沒有對應 deterministic 計算結果時" in instructions
    assert "不得聲稱已呼叫工具或已完成重算" in instructions


@pytest.mark.parametrize("agent", [4, 14])
def test_valuation_prompt_preserves_precomputed_values_and_provenance(agent):
    data = _financials()
    instructions, payload = _request(agent, data)
    tools = payload["deterministic_financial_tool_results"]
    assert tools == build_financial_tool_context(data)
    assert tools["metric_status"]["dcf"]["status"] == "available"
    assert tools["input_provenance"]["shares_raw"] == {
        "path": "data.shares_raw", "unit": "shares", "value": 66_000_000,
    }
    assert "method/unit/input_provenance" in instructions
    assert "不得以固定百分比下修" in instructions
    assert "額外保守 10-15%" not in instructions
    assert "額外下修 15–30%" not in instructions


@pytest.mark.parametrize("agent", [4, 14])
def test_missing_valuation_input_does_not_instruct_fabricated_scenarios(agent):
    data = {**_financials(), "free_cash_flow_raw": -1}
    instructions, payload = _request(agent, data)
    tools = payload["deterministic_financial_tool_results"]
    assert tools["metric_status"]["dcf"]["status"] == "unavailable"
    assert tools["dcf_scenarios"] == {}
    assert "dcf_scenarios_default" not in tools["calculations"]
    assert "若資料不足，仍需輸出保守可比較的三情境數字" not in instructions
    assert "不得為補齊三情境而產生數字" in instructions
    assert "保留品質阻擋" in instructions
