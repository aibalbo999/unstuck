# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from typing import Optional

from analysis_types import AnalysisContext
from config import AGENT_FALLBACK_MODELS, AGENT_MODELS, AUDIT_FALLBACK_MODELS, AUDIT_MODEL, CONTEXT_DIGEST_MODEL
from financial_tools import (
    calculate_cagr,
    calculate_dcf,
    calculate_ddm,
    calculate_dupont,
    calculate_implied_revenue_growth,
    calculate_wacc,
)
from llm_client import KeyRotator

def get_agent_function_tools(agent_num: int) -> list:
    """Return Python function tools for agents that need deterministic math."""
    tools = []
    if agent_num in {2, 13, 18}:
        tools.append(calculate_cagr)
    if agent_num in {3, 12, 13, 18}:
        tools.append(calculate_dupont)
    if agent_num in {4, 14}:
        tools.extend([
            calculate_cagr,
            calculate_wacc,
            calculate_dcf,
            calculate_ddm,
            calculate_implied_revenue_growth,
        ])
    return tools


def get_agent_model_sequence(agent_num: int) -> list[str]:
    """Return the configured model route for an analysis agent."""
    primary = AGENT_MODELS[agent_num]
    fallbacks = AGENT_FALLBACK_MODELS.get(agent_num, [])
    return list(dict.fromkeys([primary, *fallbacks]))


def get_audit_model_sequence() -> list[str]:
    """Return the model route reserved for final audit reflection and rewrites."""
    return list(dict.fromkeys([AUDIT_MODEL, *AUDIT_FALLBACK_MODELS]))


def get_context_digest_model_sequence() -> list[str]:
    """Return the strict single-model route for context digest generation."""
    return [CONTEXT_DIGEST_MODEL]


def get_runtime_model_sequence(agent_num: int, context: Optional[AnalysisContext] = None) -> list[str]:
    """Return the active model sequence, honoring temporary audit overrides."""
    override = (context or {}).get("_model_sequence_override", {})
    if isinstance(override, dict) and agent_num in override:
        models = override.get(agent_num) or []
        return list(dict.fromkeys(model for model in models if model))
    return get_agent_model_sequence(agent_num)


def _attempts_for_model(model_index: int, model_sequence: list[str], max_retries: int, rotator: KeyRotator) -> int:
    """
    Keep primary gemma retries bounded so provider-side 429s can move to
    Gemini 2.5 Flash fallback after each available key has been tried once.
    """
    key_count = max(1, len(getattr(rotator, "keys", []) or []))
    if model_index == 0 and len(model_sequence) > 1:
        return key_count
    return max(1, max_retries)


def is_agent_execution_failure(text: str) -> bool:
    return bool(text and text.startswith("[Agent ") and "執行失敗" in text)
