import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from agent_runtime import prompt_budget  # noqa: E402
from llm_rate_limits import estimate_text_tokens  # noqa: E402


def test_agent_prompt_token_budget_reserves_response_and_safety_margin(monkeypatch):
    monkeypatch.setattr(prompt_budget, "AGENT_MODELS", {4: "tiny-context-model"}, raising=False)
    monkeypatch.setattr(prompt_budget, "get_model_context_token_limit", lambda _model_id: 1200)
    monkeypatch.setattr(prompt_budget, "PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET", 250)
    monkeypatch.setattr(prompt_budget, "PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS", 100)

    assert prompt_budget.get_agent_prompt_token_budget(4) == 850


def test_enforce_prompt_token_budget_keeps_prompt_when_under_budget():
    prompt = "短 prompt，保留原文即可。"

    trimmed = prompt_budget.enforce_prompt_token_budget(
        prompt,
        4,
        token_budget_func=lambda _agent_num: 1000,
    )

    assert trimmed == prompt


def test_enforce_prompt_token_budget_trims_middle_context_and_keeps_tail_rules():
    prompt = "\n".join(
        [
            "開頭原始資料 " * 120,
            "中段新聞與 RAG " * 1400,
            "尾端輸出規則必須保留 " * 80,
        ]
    )

    trimmed = prompt_budget.enforce_prompt_token_budget(
        prompt,
        4,
        token_budget_func=lambda _agent_num: 300,
    )

    assert estimate_text_tokens(trimmed) <= 300
    assert "Prompt budget guard" in trimmed
    assert "尾端輸出規則必須保留" in trimmed
    assert trimmed.count("中段新聞與 RAG") < 80
