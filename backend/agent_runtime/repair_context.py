"""Context install/restore helpers for final audit repair attempts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from analysis_types import AnalysisContext

REPAIR_CONTEXT_KEYS = (
    "_audit_retry_instruction",
    "_audit_reflection_instruction",
    "_model_sequence_override",
)


def capture_repair_context(context: AnalysisContext) -> dict[str, object]:
    return {key: context.get(key) for key in REPAIR_CONTEXT_KEYS}


def install_repair_attempt_context(
    context: AnalysisContext,
    agent_num: int,
    *,
    reflection_instruction: str,
    retry_instruction: str,
    model_sequence: Iterable[str],
) -> None:
    context["_audit_reflection_instruction"] = reflection_instruction
    context["_audit_retry_instruction"] = retry_instruction
    model_override = _model_override(context.get("_model_sequence_override"))
    model_override[agent_num] = list(model_sequence)
    context["_model_sequence_override"] = model_override
    _pop_structured_output(context, agent_num)


def restore_repair_context(context: AnalysisContext, previous: dict[str, object]) -> None:
    for key, value in previous.items():
        if value is None:
            context.pop(key, None)
        else:
            context[key] = value


def _model_override(value: Any) -> dict:
    try:
        return dict(value or {})
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return {}


def _pop_structured_output(context: AnalysisContext, agent_num: int) -> None:
    structured_outputs = context.setdefault("structured_outputs", {})
    try:
        structured_outputs.pop(agent_num, None)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        context["structured_outputs"] = {}


__all__ = ["capture_repair_context", "install_repair_attempt_context", "restore_repair_context"]
