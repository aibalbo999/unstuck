"""Prompt token budget helpers for agent runtime prompts."""

from __future__ import annotations

from collections.abc import Callable

from config import (
    AGENT_MODELS,
    PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET,
    PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS,
    get_model_context_token_limit,
)
from llm_rate_limits import estimate_text_tokens


def get_agent_prompt_token_budget(agent_num: int) -> int:
    """Return the estimated input-token budget left after reserving model output space."""
    model_id = AGENT_MODELS.get(int(agent_num), "")
    context_limit = get_model_context_token_limit(model_id)
    if context_limit <= 0:
        return 0
    reserved = max(0, int(PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET)) + max(0, int(PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS))
    return max(256, int(context_limit) - reserved)


def enforce_prompt_token_budget(
    prompt: str,
    agent_num: int,
    token_budget_func: Callable[[int], int] | None = None,
) -> str:
    budget_for = token_budget_func or get_agent_prompt_token_budget
    token_budget = budget_for(agent_num)
    if token_budget <= 0 or estimate_text_tokens(prompt) <= token_budget:
        return prompt

    note = (
        "\n\n【Prompt budget guard】模型 context window 預估將超限；"
        "系統已截斷中段非關鍵 context（歷史 news、RAG、前序摘要），請優先依保留的原始資料、AgentState 與尾端規則作答。\n\n"
    )
    max_chars = max(int(token_budget * 3.5), len(note))
    available = max(max_chars - len(note), 0)
    if available <= 0:
        return note[:max_chars]

    tail_chars = min(max(512, available // 3), available)
    head_chars = max(0, available - tail_chars)
    tail = prompt[-tail_chars:].lstrip() if tail_chars else ""
    trimmed = f"{prompt[:head_chars].rstrip()}{note}{tail}"
    while estimate_text_tokens(trimmed) > token_budget and len(trimmed) > len(note):
        trim_chars = max(128, int((estimate_text_tokens(trimmed) - token_budget) * 3.5))
        if head_chars > 0:
            head_chars = max(0, head_chars - trim_chars)
        else:
            tail_chars = max(0, tail_chars - trim_chars)
        tail = prompt[-tail_chars:].lstrip() if tail_chars else ""
        trimmed = f"{prompt[:head_chars].rstrip()}{note}{tail}"
    return trimmed
