"""Prompt token budget helpers for agent runtime prompts."""

from __future__ import annotations

from collections.abc import Callable

import config
from config import (
    AGENT_MODELS,
    PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET,
    PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS,
    PRIMARY_PROMPT_RAG_CONTEXT_CHARS,
    get_agent_rag_budget,
    get_model_context_token_limit,
)
from .rag_prompt_budget import limit_rag_evidence


def get_agent_context_input_token_limit(agent_num: int, model_id: str) -> int | None:
    """Context ceiling for complete input; None means no configured window."""
    from .generation_config import generation_profile
    context_limit = config.get_model_context_token_limit(model_id)
    if context_limit <= 0:
        return None
    output = max(0, int(generation_profile(agent_num)["max_output_tokens"]))
    safety = max(0, int(config.PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS))
    return max(0, context_limit - output - safety)


def get_agent_prompt_token_budget(agent_num: int, *, model_id: str | None = None) -> int:
    """Plan supplementary context for the actual candidate, including request overhead.

    This is a planning allowance, not admission. The full serialized prompt still
    goes through single_agent_admission, which counts system/schema/tool inputs.
    """
    from .generation_config import estimate_agent_input_tokens

    model_id = model_id or AGENT_MODELS.get(int(agent_num), "")
    context_limit = get_model_context_token_limit(model_id)
    limits = []
    if context_limit > 0:
        limits.append(int(context_limit) - max(0, int(PROMPT_CONTEXT_RESPONSE_TOKEN_BUDGET)))
    for mapping in (config.MODEL_INPUT_TOKEN_LIMITS, config.TPM_LIMITS):
        limit = mapping.get(model_id, mapping.get("*", 0))
        if limit > 0:
            limits.append(int(limit))
    if not limits:
        return 0
    overhead = estimate_agent_input_tokens(agent_num, model_id, "")
    safety = max(0, int(PROMPT_CONTEXT_SAFETY_MARGIN_TOKENS))
    # Zero means unknown/unbounded to the retrieval limiter. A spent budget must
    # instead leave no room for supplementary evidence, without touching State.
    return max(1, min(limits) - overhead - safety)


def bound_agent_rag_context(
    text: str, agent_num: int, *, compact: bool = False,
    token_budget_func: Callable[[int], int] | None = None,
) -> str:
    """Use existing retrieval limits and at most one quarter of the input budget."""
    max_chars, max_chunks = get_agent_rag_budget(agent_num)
    if compact:
        max_chars = min(max_chars, PRIMARY_PROMPT_RAG_CONTEXT_CHARS)
    budget = (token_budget_func or get_agent_prompt_token_budget)(agent_num)
    return limit_rag_evidence(
        text, max_chars=max_chars, max_chunks=max_chunks,
        token_budget=max(1, budget // 4) if budget > 0 else 0,
    )


def enforce_prompt_token_budget(
    prompt: str,
    agent_num: int,
    token_budget_func: Callable[[int], int] | None = None,
) -> str:
    """Preserve complete evidence for the route's fail-closed input admission.

    A finished prompt has no safe generic middle to slice: it can contain raw
    financial records, quoted sources and source manifests. Only the separately
    identified derived/RAG sections are bounded before assembly. Retain this
    compatibility hook for prompt callers; oversized requests must fall back or
    report input capacity rather than send an incomplete evidence package.
    """
    return prompt
