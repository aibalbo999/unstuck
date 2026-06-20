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
