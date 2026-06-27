import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


import agent_runtime.prompting as prompting  # noqa: E402
from prompt_builder import format_data_for_prompt  # noqa: E402


def _payload_from_prompt(prompt_text: str) -> dict:
    payload_text = prompt_text.split("【財務資料 JSON】\n", 1)[1].split("\n\n【使用規則】", 1)[0]
    return json.loads(payload_text)


def test_data_for_agent_prompt_routes_new_context_by_role():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": {"source": "FRED"},
        "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
        "alternative_data": {"job_openings_104": {"job_count": 128}},
        "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
    }

    assert hasattr(prompting, "data_for_agent_prompt")
    assert "macro_indicators" in prompting.data_for_agent_prompt(11, data)
    assert "chip_data" not in prompting.data_for_agent_prompt(11, data)
    assert "chip_data" in prompting.data_for_agent_prompt(15, data)
    assert "chip_data" in prompting.data_for_agent_prompt(18, data)
    assert "sentiment_context" in prompting.data_for_agent_prompt(17, data)
    assert "alternative_data" in prompting.data_for_agent_prompt(14, data)
    assert "alternative_data" in prompting.data_for_agent_prompt(13, data)
    assert "macro_indicators" not in prompting.data_for_agent_prompt(12, data)
    assert "chip_data" not in prompting.data_for_agent_prompt(12, data)
    assert "alternative_data" not in prompting.data_for_agent_prompt(12, data)
    assert "sentiment_context" not in prompting.data_for_agent_prompt(12, data)


def test_format_data_for_prompt_exposes_only_agent_routed_external_context():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "macro_indicators": {"source": "FRED", "summary_text": "macro"},
        "chip_data": {"tdcc_shareholder_distribution": {"major_holders_gt_1000_lots_pct": 42.1}},
        "alternative_data": {"job_openings_104": {"job_count": 128}},
        "sentiment_context": {"ptt_titles": ["AI 題材升溫"]},
    }

    assert hasattr(prompting, "data_for_agent_prompt")
    agent_11_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(11, data)))
    agent_12_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(12, data)))
    agent_15_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(15, data)))
    agent_17_payload = _payload_from_prompt(format_data_for_prompt(prompting.data_for_agent_prompt(17, data)))

    assert agent_11_payload["agent_context"]["macro_indicators"]["source"] == "FRED"
    assert "chip_data" not in agent_11_payload["agent_context"]
    assert agent_15_payload["agent_context"]["chip_data"]["tdcc_shareholder_distribution"]["major_holders_gt_1000_lots_pct"] == 42.1
    assert agent_17_payload["agent_context"]["sentiment_context"]["ptt_titles"] == ["AI 題材升溫"]
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
