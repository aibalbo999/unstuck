import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


import agent_runtime.prompting as prompting  # noqa: E402
from llm_rate_limits import estimate_text_tokens  # noqa: E402
from prompt_builder import format_data_for_prompt, render_prompt_template  # noqa: E402
from temporal_memory_service import build_valuation_memory_slice  # noqa: E402


def _payload_from_prompt(prompt_text: str) -> dict:
    payload_text = prompt_text.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
    return json.loads(payload_text)


def test_render_prompt_template_warns_for_legacy_placeholders():
    with pytest.warns(DeprecationWarning, match="legacy prompt placeholder"):
        rendered = render_prompt_template("標的 {ticker}", {"ticker": "2330.TW"})

    assert rendered == "標的 2330.TW"


def test_data_for_agent_prompt_routes_new_context_by_role():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": {"source": "FRED"},
        "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
        "alternative_data": {"job_openings_104": {"job_count": 128}},
        "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
        "social_sentiment": {"dcard": [{"title": "Dcard 討論"}]},
        "sec_edgar": {"recent_filings": [{"form": "10-Q"}]},
        "taiwan_open_data": {"rates": {"USD": {"sell": "31.50"}}},
    }

    assert hasattr(prompting, "data_for_agent_prompt")
    assert "macro_indicators" in prompting.data_for_agent_prompt(11, data)
    assert "chip_data" not in prompting.data_for_agent_prompt(11, data)
    assert "chip_data" in prompting.data_for_agent_prompt(15, data)
    assert "chip_data" in prompting.data_for_agent_prompt(18, data)
    assert "sentiment_context" in prompting.data_for_agent_prompt(17, data)
    assert "social_sentiment" in prompting.data_for_agent_prompt(17, data)
    assert "alternative_data" in prompting.data_for_agent_prompt(14, data)
    assert "alternative_data" in prompting.data_for_agent_prompt(13, data)
    assert "sec_edgar" in prompting.data_for_agent_prompt(13, data)
    assert "sec_edgar" in prompting.data_for_agent_prompt(14, data)
    assert "sec_edgar" in prompting.data_for_agent_prompt(21, data)
    assert "taiwan_open_data" in prompting.data_for_agent_prompt(11, data)
    assert "macro_indicators" not in prompting.data_for_agent_prompt(12, data)
    assert "chip_data" not in prompting.data_for_agent_prompt(12, data)
    assert "alternative_data" not in prompting.data_for_agent_prompt(12, data)
    assert "sentiment_context" not in prompting.data_for_agent_prompt(12, data)
    assert "social_sentiment" not in prompting.data_for_agent_prompt(12, data)
    assert "sec_edgar" not in prompting.data_for_agent_prompt(12, data)
    assert "taiwan_open_data" not in prompting.data_for_agent_prompt(12, data)


def test_valuation_agents_receive_temporal_memory_slice_only():
    temporal_memory = {
        "previous_report": {
            "target_3m": "650",
            "target_6m": "700",
            "target_12m": "800",
            "recommendation": "買入",
            "date": "2024-01-01",
            "summary": "很長的前期完整報告文字不應進入估值 Agent。",
        },
        "backtests": [{"roi_pct": 12.5, "hit": True, "summary": "完整回測說明"}],
        "reflection_prompt": "完整最終 Agent 反思 prompt",
    }
    data = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "temporal_memory": temporal_memory,
    }

    valuation_payload = prompting.data_for_agent_prompt(4, data)
    final_payload = prompting.data_for_agent_prompt(7, data)

    assert "valuation_memory" in valuation_payload
    assert "temporal_memory" not in valuation_payload
    assert valuation_payload["valuation_memory"]["prior_target_3m"] == "650"
    assert valuation_payload["valuation_memory"]["latest_backtest_roi"] == 12.5
    assert "summary" not in valuation_payload["valuation_memory"]
    assert "temporal_memory" in final_payload
    assert "valuation_memory" not in final_payload


def test_build_valuation_memory_slice_keeps_only_valuation_fields():
    result = build_valuation_memory_slice({
        "previous_report": {"target_3m": "650", "recommendation": "買入", "date": "2024-01-01", "summary": "完整報告"},
        "backtests": [{"roi_pct": 12.5, "hit": True, "details": "long"}],
    })

    assert result["prior_target_3m"] == "650"
    assert result["latest_backtest_hit"] is True
    assert "note" in result
    assert "summary" not in result


def test_format_data_for_prompt_exposes_only_agent_routed_external_context():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": {"source": "FRED", "summary_text": "macro"},
        "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
        "alternative_data": {"job_openings_104": {"job_count": 128}},
        "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
        "social_sentiment": {"dcard": [{"title": "Dcard 討論"}]},
        "sec_edgar": {"recent_filings": [{"form": "10-Q"}]},
        "taiwan_open_data": {"rates": {"USD": {"sell": "31.50"}}},
    }

    assert hasattr(prompting, "data_for_agent_prompt")
    agent_11_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(11, data)))
    agent_12_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(12, data)))
    agent_15_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(15, data)))
    agent_17_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(17, data)))
    agent_13_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(13, data)))

    assert agent_11_payload["agent_context"]["macro_indicators"]["source"] == "FRED"
    assert agent_11_payload["agent_context"]["taiwan_open_data"]["rates"]["USD"]["sell"] == "31.50"
    assert "chip_data" not in agent_11_payload["agent_context"]
    assert agent_15_payload["agent_context"]["chip_data"]["tdcc_shareholder_distribution"]["major_holders_gt_1000_lots_pct"] == 42.1
    assert agent_17_payload["agent_context"]["sentiment_context"]["ptt_titles"] == ["AI 題材升溫"]
    assert agent_17_payload["agent_context"]["social_sentiment"]["dcard"][0]["title"] == "Dcard 討論"
    assert agent_13_payload["agent_context"]["sec_edgar"]["recent_filings"][0]["form"] == "10-Q"
    assert agent_12_payload["agent_context"] == {}


def test_build_prompt_includes_final_audit_preflight_for_non_structured_agent():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }
    context = {"analyses": {}, "structured_outputs": {}, "pipeline_id": "v1"}

    prompt = prompting.build_prompt(1, data, context)

    assert "最終審核前自檢" in prompt
    assert "分析進行中" in prompt
    assert "Agent 執行失敗" in prompt
    assert "不得把同業公司事實寫成標的公司事實" in prompt
    assert "不要把自檢文字寫進正式報告" in prompt


def test_build_prompt_includes_mode_specific_final_audit_preflight_contracts():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
    }

    mode_c_prompt = prompting.build_prompt(
        19,
        data,
        {"analyses": {}, "structured_outputs": {}, "pipeline_id": "v3"},
    )
    mode_d_prompt = prompting.build_prompt(
        24,
        data,
        {"analyses": {}, "structured_outputs": {}, "pipeline_id": "v4"},
    )

    assert "做空觸發條件（Catalyst for crash）" in mode_c_prompt
    assert "防軋空停損點（Stop-loss level）" in mode_c_prompt
    assert "[投資建議]" in mode_c_prompt
    assert "[/投資建議]" in mode_c_prompt
    assert "trade_direction" in mode_d_prompt
    assert "Long|Short|Neutral" in mode_d_prompt
    assert "risk_level" in mode_d_prompt
    assert "High|Medium|Low" in mode_d_prompt


def test_build_prompt_applies_token_budget_guard_before_llm_call(monkeypatch):
    monkeypatch.setattr(prompting, "get_agent_prompt_token_budget", lambda _agent_num: 700, raising=False)
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "recent_catalysts": ["大型新聞段落 " * 80 for _ in range(20)],
        "dynamic_peer_metrics": [{"note": "同業補充 " * 120} for _ in range(10)],
    }
    context = {
        "analyses": {1: "前序分析重要片段 " * 1200},
        "structured_outputs": {},
        "rag_context": {4: "RAG 補充片段 " * 1200},
        "pipeline_id": "v1",
    }

    prompt = prompting.build_prompt(4, data, context)

    assert estimate_text_tokens(prompt) <= 700
    assert "Prompt budget guard" in prompt
    assert prompt.count("RAG 補充片段") < 100


def test_runtime_rules_cover_common_final_audit_failure_modes():
    rules = json.loads((ROOT / "backend" / "prompts" / "runtime_rules.json").read_text(encoding="utf-8"))

    preflight = rules["final_audit_preflight_rule"]
    common_text = "\n".join(preflight["rules"])
    assert "分析進行中" in common_text
    assert "prompt/system/task/meta-talk" in common_text
    assert "同業公司事實" in common_text

    structured_rules = rules["structured_agent_instructions"]
    for agent_num in ("4", "14"):
        valuation_text = "\n".join(structured_rules[agent_num]["rules"])
        assert "熊市情境 <= 基本情境 <= 牛市情境" in valuation_text
    for agent_num in ("7", "16"):
        recommendation_text = "\n".join(structured_rules[agent_num]["rules"])
        assert "短期目標（3個月）" in recommendation_text
        assert "建議只能使用 schema 允許值" in recommendation_text

    mode_c_text = "\n".join(structured_rules["19"]["rules"])
    assert "做空觸發條件（Catalyst for crash）" in mode_c_text
    assert "[/投資建議] 後" in mode_c_text

    mode_d_text = "\n".join(structured_rules["24"]["rules"])
    assert "只有六個欄位" in mode_d_text
    assert "Neutral + High" in mode_d_text
