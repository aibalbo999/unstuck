import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


DISCLAIMER = (
    "This request is for a stock research assistance tool that summarizes, parses, "
    "and formats user-provided market data for informational research only. "
    "Do not act as a financial advisor. Do not provide financial advice, personalized "
    "investment recommendations, or instructions to buy, sell, short, or hold securities."
)


def test_google_transport_discloses_research_assistance_purpose(monkeypatch):
    import llm_transport

    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured.update(kwargs)
            return object()

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(llm_transport, "_get_client", lambda _api_key: FakeClient())

    llm_transport.generate_content("fake-key", "gemini-test", "請整理資料", object())

    assert captured["contents"].startswith("請以股票研究輔助工具的資料摘要員")
    assert captured["contents"].endswith(DISCLAIMER)
    assert "internal software testing" not in captured["contents"]


def test_agent_google_system_instruction_is_data_parser_not_financial_advisor():
    from agent_runtime.generation_config import google_safe_agent_system_instruction

    safe_instruction = google_safe_agent_system_instruction(7, "gemini-2.5-pro")

    assert "股票研究輔助工具" in safe_instruction
    assert "投資情境與風險整合器" in safe_instruction
    assert "資料摘要員" in safe_instruction
    assert "資料解析與計算輔助工具" in safe_instruction
    assert "Do not act as a financial advisor" in safe_instruction
    assert "internal software testing" not in safe_instruction
    assert "You are a financial advisor" not in safe_instruction


def test_google_prompt_rewrites_explicit_trade_advice_terms():
    from google_prompt_safety import sanitize_google_prompt

    prompt = "Agent 19 請輸出投資建議：建議：強烈放空；若轉強則買進或賣出。"

    safe_prompt = sanitize_google_prompt(prompt)

    assert "投資建議" not in safe_prompt
    assert "強烈放空" not in safe_prompt
    assert "買進" not in safe_prompt
    assert "賣出" not in safe_prompt
    assert "研究分類" in safe_prompt
    assert "空方風險觀察" in safe_prompt


def test_agent19_google_system_instruction_avoids_direct_short_advice():
    from agent_runtime.generation_config import google_safe_agent_system_instruction

    safe_instruction = google_safe_agent_system_instruction(19, "gemini-2.5-pro")

    assert "強烈放空" not in safe_instruction
    assert "recommend short exposure" not in safe_instruction
    assert "short-selling report author" not in safe_instruction
    assert "空方風險觀察" in safe_instruction
    assert "research-ready downside-risk report" in safe_instruction


def test_google_generation_config_rewrites_agent19_schema_for_google():
    from agent_runtime.generation_config import build_generation_config
    from google_prompt_safety import sanitize_google_generation_config
    import json

    config = build_generation_config(19, "system")
    safe_config = sanitize_google_generation_config(config)
    schema_text = json.dumps(getattr(safe_config, "response_schema", {}), ensure_ascii=False)

    assert "強烈放空" not in schema_text
    assert "買進" not in schema_text
    assert "空方風險觀察" in schema_text
    assert "偏多觀察" in schema_text
