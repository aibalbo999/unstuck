"""Input admission checks before a single-agent provider call."""

from __future__ import annotations

from dataclasses import dataclass

import config
from analysis_types import AnalysisContext
from gemma_evidence_batches import EvidenceBatchInvalid
from llm_client import KeyRotator
from llm_input_capacity import InputCapacityExceededError, ensure_input_capacity

from . import gemma_evidence_runtime as evidence_batches
from .generation_config import estimate_agent_input_tokens
from .single_agent_events import reject_async_model, reject_sync_model


@dataclass(frozen=True)
class ModelInputAdmission:
    call_provider: bool
    evidence_notes: str
    last_error: str | None = None


def append_evidence_notes(agent_num: int, model_id: str, prompt: str, notes: str, context: AnalysisContext) -> str:
    return evidence_batches.append_if_capacity_allows(agent_num, model_id, prompt, notes, context)


def _preflight_model_input_capacity(agent_num: int, model_id: str, prompt: str) -> None:
    """Reject an impossible route before emitting a provider-attempt event."""
    estimated = estimate_agent_input_tokens(agent_num, model_id, prompt)
    input_limits = config.MODEL_INPUT_TOKEN_LIMITS
    tpm_limits = config.TPM_LIMITS
    ensure_input_capacity(
        model_id,
        estimated,
        input_limit=input_limits.get(model_id, input_limits.get("*", 0)),
        tpm_limit=tpm_limits.get(model_id, tpm_limits.get("*", 0)),
    )


def admit_model_input_sync(
    agent_num: int,
    model_id: str,
    prompt: str,
    context: AnalysisContext,
    rotator: KeyRotator,
    *,
    has_fallback: bool,
    evidence_notes: str,
) -> ModelInputAdmission:
    if has_fallback and evidence_batches.should_batch(agent_num, model_id, prompt, context):
        try:
            notes = evidence_batches.collect_evidence(agent_num, prompt, context, rotator)
        except EvidenceBatchInvalid as exc:
            return ModelInputAdmission(False, evidence_notes, reject_sync_model(context, agent_num, model_id, exc))
        return ModelInputAdmission(False, notes)
    try:
        _preflight_model_input_capacity(agent_num, model_id, prompt)
    except InputCapacityExceededError as exc:
        return ModelInputAdmission(False, evidence_notes, reject_sync_model(context, agent_num, model_id, exc))
    return ModelInputAdmission(True, evidence_notes)


async def admit_model_input_async(
    agent_num: int,
    model_id: str,
    prompt: str,
    context: AnalysisContext,
    rotator: KeyRotator,
    *,
    has_fallback: bool,
    evidence_notes: str,
) -> ModelInputAdmission:
    if has_fallback and evidence_batches.should_batch(agent_num, model_id, prompt, context):
        try:
            notes = await evidence_batches.collect_evidence_async(agent_num, prompt, context, rotator)
        except EvidenceBatchInvalid as exc:
            error = await reject_async_model(context, agent_num, model_id, exc)
            return ModelInputAdmission(False, evidence_notes, error)
        return ModelInputAdmission(False, notes)
    try:
        _preflight_model_input_capacity(agent_num, model_id, prompt)
    except InputCapacityExceededError as exc:
        error = await reject_async_model(context, agent_num, model_id, exc)
        return ModelInputAdmission(False, evidence_notes, error)
    return ModelInputAdmission(True, evidence_notes)


__all__ = [
    "EvidenceBatchInvalid",
    "ModelInputAdmission",
    "admit_model_input_async",
    "admit_model_input_sync",
    "append_evidence_notes",
]
