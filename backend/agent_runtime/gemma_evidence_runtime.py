"""Gemma evidence requests reuse provider quota controls, with per-batch cache."""
import asyncio
import json
import time

from google.genai import types

from cache_store import get_cache_json, set_cache_json
from config import GEMMA_EVIDENCE_BATCHING_ENABLED, MODEL_INPUT_TOKEN_LIMITS
from gemma_evidence_batches import (MODEL, ROLES, SYSTEM, EvidenceBatchInvalid, batch_input_tokens,
                                    batch_prompt, evidence_appendix, plan_batches, validate_observations)
from llm_client import generate_content, generate_content_async, response_text
from llm_response_diagnostics import response_diagnostics
from llm_errors import extract_quota_details
from llm_evidence_request import evidence_request_scope
from runtime_events import emit_context_event, make_runtime_event
from .cancellation import raise_if_cancelled
from .generation_config import estimate_agent_input_tokens
from .llm_call_metadata import _key_slot_fields, _record_llm_token_usage
from .model_policy import record_model_success
from .retry_policy import AgentTransientError, _agent_error_category, _raise_agent_call_error
from .retry_error_classification import provider_status_code

TIMEOUT = 60
CACHE_SECONDS = 3600
TRANSIENT_MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 2


def should_batch(agent_num, model_id, prompt, context):
    if not GEMMA_EVIDENCE_BATCHING_ENABLED or model_id != MODEL or agent_num not in ROLES:
        return False
    if context.get("_model_sequence_override") or any(context.get(k) for k in (
        "_audit_retry_instruction", "_audit_reflection_instruction", "_identity_retry_instruction")):
        return False
    limit = MODEL_INPUT_TOKEN_LIMITS.get(MODEL, 12000)
    return limit > 0 and estimate_agent_input_tokens(agent_num, MODEL, prompt) > limit


def append_if_capacity_allows(agent_num, model_id, prompt, notes, context=None):
    if not notes or model_id == MODEL:
        return prompt
    combined = prompt + notes
    limit = MODEL_INPUT_TOKEN_LIMITS.get(model_id, 0)
    attached = not (limit and estimate_agent_input_tokens(agent_num, model_id, combined) > limit)
    emit_context_event(context, make_runtime_event(
        "status", phase="gemma_evidence_appendix_prepared", level="info",
        message="整合提示已附上驗證摘錄。" if attached else "整合提示容量不足，保留完整原始資料，略過附加摘錄。",
        agent_num=agent_num, pipeline_id=(context or {}).get("pipeline_id"),
        metadata={"model_id": model_id, "evidence_appendix_attached": attached},
    ))
    return combined if attached else prompt


def config():
    # A separate extraction protocol, never the final agent's output schema.
    return types.GenerateContentConfig(temperature=0, max_output_tokens=2048, system_instruction=SYSTEM,
                                       http_options=types.HttpOptions(
                                           timeout=TIMEOUT * 1000,
                                           # Count every HTTP send in our own ledger/retry loop.
                                           retry_options=types.HttpRetryOptions(attempts=1),
                                       ))


def event(context, batch, phase, rotator=None, key=None, event_message=None, **extra):
    emit_context_event(context, make_runtime_event(
        "status", phase=phase, level="warning" if phase.endswith("error") else "info",
        message=event_message or f"Agent {batch['agent_num']} Gemma 分批證據處理：{phase.removeprefix('gemma_evidence_')}",
        agent_num=batch["agent_num"], pipeline_id=context.get("pipeline_id"),
        metadata={"model_id": MODEL, "call_purpose": "evidence_batch", "batch_id": batch["batch_id"],
                  "estimated_input_tokens": batch_input_tokens(batch),
                  "input_estimate_basis": "batch_prompt_with_system", "source_record_count": len(batch["records"]),
                  **(_key_slot_fields(rotator, key) if rotator is not None else {}), **extra},
    ))


def finish_response(batch, context, rotator, key, response):
    raise_if_cancelled(context)
    _record_llm_token_usage(context, batch["agent_num"], response)
    text = response_text(response)
    try:
        validate_observations(batch, text)
    except EvidenceBatchInvalid:
        event(context, batch, "gemma_evidence_error", rotator, key, error_category="evidence_validation")
        raise
    record_model_success(context, MODEL)
    event(context, batch, "gemma_evidence_response", rotator, key, response_diagnostics=response_diagnostics(response))
    return json.loads(text)


def provider_error(batch, context, rotator, key, exc):
    event(context, batch, "gemma_evidence_error", rotator, key,
          error_category=_agent_error_category(exc), error_kind=type(exc).__name__,
          provider_status_code=provider_status_code(exc), provider_quota=extract_quota_details(exc))
    _raise_agent_call_error(exc, key, MODEL, rotator, 1)


def retry_event(batch, context, exc, attempt):
    event(
        context,
        batch,
        "gemma_evidence_retry",
        event_message=(
            f"Agent {batch['agent_num']} Gemma 證據請求暫時失敗，"
            f"{RETRY_DELAY_SECONDS} 秒後再試一次；若仍失敗即切換備援模型。"
        ),
        attempt=attempt,
        max_attempts=TRANSIENT_MAX_ATTEMPTS,
        retry_delay_seconds=RETRY_DELAY_SECONDS,
        error_category=_agent_error_category(exc),
        provider_status_code=provider_status_code(exc),
    )


def call_batch_with_retry(batch, context, rotator):
    for attempt in range(1, TRANSIENT_MAX_ATTEMPTS + 1):
        try:
            return call_batch(batch, context, rotator)
        except AgentTransientError as exc:
            if attempt >= TRANSIENT_MAX_ATTEMPTS:
                raise
            retry_event(batch, context, exc, attempt + 1)
            time.sleep(RETRY_DELAY_SECONDS)


async def call_batch_with_retry_async(batch, context, rotator):
    for attempt in range(1, TRANSIENT_MAX_ATTEMPTS + 1):
        try:
            return await call_batch_async(batch, context, rotator)
        except AgentTransientError as exc:
            if attempt >= TRANSIENT_MAX_ATTEMPTS:
                raise
            retry_event(batch, context, exc, attempt + 1)
            await asyncio.sleep(RETRY_DELAY_SECONDS)


def call_batch(batch, context, rotator):
    raise_if_cancelled(context)
    key = None
    event(context, batch, "gemma_evidence_call")
    try:
        key = rotator.get_key(MODEL, batch_input_tokens(batch))
    except Exception as exc:
        provider_error(batch, context, rotator, key, exc)
    raise_if_cancelled(context)
    try:
        event(context, batch, "gemma_evidence_request", rotator, key)
        with evidence_request_scope():
            response = generate_content(key, MODEL, batch_prompt(batch), config())
    except Exception as exc:
        provider_error(batch, context, rotator, key, exc)
    return finish_response(batch, context, rotator, key, response)


async def call_batch_async(batch, context, rotator):
    raise_if_cancelled(context)
    key = None
    event(context, batch, "gemma_evidence_call")
    try:
        key = await rotator.async_get_key(MODEL, batch_input_tokens(batch))
    except Exception as exc:
        provider_error(batch, context, rotator, key, exc)
    raise_if_cancelled(context)
    try:
        event(context, batch, "gemma_evidence_request", rotator, key)
        with evidence_request_scope():
            response = await asyncio.wait_for(generate_content_async(key, MODEL, batch_prompt(batch), config()), TIMEOUT)
    except Exception as exc:
        provider_error(batch, context, rotator, key, exc)
    return finish_response(batch, context, rotator, key, response)


def cached_response(batch):
    try:
        response = get_cache_json("gemma-evidence:" + batch["batch_id"])
        validate_observations(batch, response)
        return response
    except Exception:
        return None


def save_response(batch, response):
    validate_observations(batch, response)
    try:
        set_cache_json("gemma-evidence:" + batch["batch_id"], response, CACHE_SECONDS)
    except Exception:
        pass  # Valid evidence remains usable when an optional cache write fails.


def collect_evidence(agent_num, prompt, context, rotator):
    batches = plan_batches(agent_num, prompt)
    responses = []
    for batch in batches:
        raise_if_cancelled(context)
        response = cached_response(batch)
        if response is None:
            response = call_batch_with_retry(batch, context, rotator)
            save_response(batch, response)
        else:
            event(context, batch, "gemma_evidence_cache_hit")
        responses.append(response)
    return evidence_appendix(batches, responses)


async def collect_evidence_async(agent_num, prompt, context, rotator):
    batches = plan_batches(agent_num, prompt)
    responses = []
    # Serial within a role: every request must enter the existing RPM/TPM gate.
    for batch in batches:
        raise_if_cancelled(context)
        response = cached_response(batch)
        if response is None:
            response = await call_batch_with_retry_async(batch, context, rotator)
            save_response(batch, response)
        else:
            event(context, batch, "gemma_evidence_cache_hit")
        responses.append(response)
    return evidence_appendix(batches, responses)
