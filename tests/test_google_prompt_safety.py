import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


DISCLAIMER = (
    "This request is for internal software testing and data parsing only. "
    "Do not act as a financial advisor. Do not provide financial advice."
)


def test_google_transport_appends_internal_testing_disclaimer(monkeypatch):
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

    assert captured["contents"].startswith("請以內部軟體測試的資料摘要員")
    assert captured["contents"].endswith(DISCLAIMER)


def test_agent_google_system_instruction_is_data_parser_not_financial_advisor():
    from agent_runtime.generation_config import google_safe_agent_system_instruction
    from agent_runtime.prompt_config import SYSTEM_PROMPTS

    safe_instruction = google_safe_agent_system_instruction(7, "gemini-2.5-pro")

    assert SYSTEM_PROMPTS[7] in safe_instruction
    assert "資料摘要員" in safe_instruction
    assert "資料解析與計算輔助工具" in safe_instruction
    assert "Do not act as a financial advisor" in safe_instruction
    assert "You are a financial advisor" not in safe_instruction
