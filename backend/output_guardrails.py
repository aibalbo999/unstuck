"""Strict payload and external guardrail adapters for model I/O."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError


DEFAULT_SAFE_OUTPUT_MESSAGE = "系統偵測到輸出包含不安全內容，已改以安全訊息取代。"


class SecurityViolationError(RuntimeError):
    """Raised when sanitized LLM output still contains unsafe instructions."""


class SanitizedOutputPayload(BaseModel):
    """Strict boundary model for text entering or leaving the sanitizer."""

    model_config = ConfigDict(strict=True, extra="forbid")

    content: StrictStr = Field(max_length=200_000)


class GuardrailDecision(BaseModel):
    """Normalized decision returned by an external output guardrail."""

    model_config = ConfigDict(strict=True, extra="forbid")

    allowed: StrictBool
    reason: StrictStr = ""
    sanitized_text: StrictStr | None = None


GuardrailResult = GuardrailDecision | dict[str, Any]
GuardrailStage = Literal["input", "output"]


class ExternalGuardrail(Protocol):
    """Boundary adapter for Llama Guard, NeMo Guardrails, or equivalent services."""

    def evaluate(self, text: str, *, stage: GuardrailStage) -> GuardrailResult | Awaitable[GuardrailResult]: ...


GuardrailHook = ExternalGuardrail | Callable[..., GuardrailResult | Awaitable[GuardrailResult]]


def validate_structured_text(text: Any) -> str:
    try:
        return SanitizedOutputPayload.model_validate({"content": text}).content
    except ValidationError as exc:
        raise SecurityViolationError("模型邊界內容不符合嚴格文字結構。") from exc


async def apply_external_guardrail(text: str, guardrail: GuardrailHook, *, stage: GuardrailStage) -> str:
    """Apply a stage-aware external policy decision and return approved text."""
    evaluator = getattr(guardrail, "evaluate", guardrail)
    result = evaluator(validate_structured_text(text), stage=stage)
    if inspect.isawaitable(result):
        result = await result
    try:
        decision = GuardrailDecision.model_validate(result)
    except ValidationError as exc:
        raise SecurityViolationError("外部 Guardrail 回傳格式無效。") from exc
    if not decision.allowed:
        raise SecurityViolationError(decision.reason or DEFAULT_SAFE_OUTPUT_MESSAGE)
    return decision.sanitized_text if decision.sanitized_text is not None else text


async def validate_prompt_input(text: str, guardrail: GuardrailHook) -> str:
    """Validate untrusted prompt context before it enters a model request."""
    return await apply_external_guardrail(text, guardrail, stage="input")
