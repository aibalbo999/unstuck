import asyncio
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from output_guardrails import (  # noqa: E402
    GuardrailDecision,
    SanitizedOutputPayload,
    SecurityViolationError,
    apply_external_guardrail,
    validate_prompt_input,
)


def test_sanitized_output_payload_rejects_non_string_content():
    with pytest.raises(ValidationError):
        SanitizedOutputPayload(content=123)


def test_external_guardrail_uses_stage_and_accepts_sanitized_replacement():
    stages = []

    class ReplacingGuardrail:
        def evaluate(self, text, *, stage):
            stages.append((text, stage))
            return GuardrailDecision(allowed=True, sanitized_text=f"{stage}:{text}")

    cleaned = asyncio.run(apply_external_guardrail("研究內容", ReplacingGuardrail(), stage="output"))

    assert cleaned == "output:研究內容"
    assert stages == [("研究內容", "output")]


def test_external_guardrail_blocks_with_reason_and_validates_prompt_input_stage():
    stages = []

    async def blocking_guardrail(_text, *, stage):
        stages.append(stage)
        return {"allowed": False, "reason": "external policy blocked"}

    with pytest.raises(SecurityViolationError, match="external policy blocked"):
        asyncio.run(validate_prompt_input("外部新聞內容", blocking_guardrail))

    assert stages == ["input"]


def test_external_guardrail_rejects_invalid_decision_shape():
    with pytest.raises(SecurityViolationError, match="外部 Guardrail 回傳格式無效"):
        asyncio.run(apply_external_guardrail("研究內容", lambda _text, *, stage: {"reason": "missing allowed"}, stage="output"))
