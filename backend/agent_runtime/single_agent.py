# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

import asyncio

from tenacity import AsyncRetrying, Retrying, retry_if_exception_type

from analysis_types import AnalysisContext, StockData
from llm_client import KeyRotator

from .llm_calls import (
    AgentMissingModelError,
    AgentRetryableError,
    _agent_retry_wait,
    make_agent_retry_logger,
    _run_agent_once,
    _run_agent_once_async,
)
from .cancellation import raise_if_cancelled
from .model_policy import (
    is_model_circuit_open,
    model_attempt_policy,
    record_model_failure,
    record_model_success,
    should_stop_retry,
    timeout_for_model_call,
)
from .prompting import build_prompt
from .routing import get_runtime_model_sequence
from runtime_events import emit_context_event, emit_context_event_async, emit_log, make_runtime_event


def _event_fields(context: AnalysisContext, agent_num: int, model_id: str, **metadata) -> dict:
    return {
        "current": (context.get("agent_positions", {}) or {}).get(agent_num, agent_num),
        "total": context.get("agent_total"),
        "name": f"Agent {agent_num}",
        "agent_num": agent_num,
        "pipeline_id": context.get("pipeline_id"),
        "pipeline_label": context.get("pipeline_label"),
        "metadata": {"model_id": model_id, **{k: v for k, v in metadata.items() if v is not None}},
    }


def _emit_sync_model_event(context: AnalysisContext, agent_num: int, phase: str, level: str, message: str, model_id: str, **metadata) -> None:
    emit_context_event(
        context,
        make_runtime_event("status", phase=phase, level=level, message=message, **_event_fields(context, agent_num, model_id, **metadata)),
    )


async def _emit_async_model_event(context: AnalysisContext, agent_num: int, phase: str, level: str, message: str, model_id: str, **metadata) -> None:
    await emit_context_event_async(
        context,
        make_runtime_event("status", phase=phase, level=level, message=message, **_event_fields(context, agent_num, model_id, **metadata)),
    )

def run_single_agent(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """
    執行單個分析 Agent
    - 自動選擇可用的 API Key
    - 超限時自動重試
    - 錯誤時返回錯誤訊息
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_single_agent_async(agent_num, data, context, rotator, max_retries))

    model_sequence = get_runtime_model_sequence(agent_num, context)
    last_error = ""

    for model_index, model_id in enumerate(model_sequence):
        raise_if_cancelled(context)
        if model_index > 0:
            message = f"切換備援模型：{model_id}"
            emit_log(f"    🔁 {message}")
            _emit_sync_model_event(context, agent_num, "model_fallback", "warning", message, model_id, model_index=model_index)

        if is_model_circuit_open(context, model_id) and model_index < len(model_sequence) - 1:
            message = f"模型 {model_id} 暫時熔斷，直接切換備援模型。"
            emit_log(f"    🔁 {message}")
            _emit_sync_model_event(context, agent_num, "model_circuit_open", "warning", message, model_id)
            continue

        has_fallback = len(model_sequence) > model_index + 1
        policy = model_attempt_policy(model_index, has_fallback, max_retries, len(getattr(rotator, "keys", []) or []))
        try:
            context["_primary_probe_prompt"] = model_index == 0 and has_fallback
            prompt = build_prompt(agent_num, data, context)
        finally:
            context.pop("_primary_probe_prompt", None)
        retryer = Retrying(
            stop=lambda retry_state: should_stop_retry(retry_state, policy),
            wait=_agent_retry_wait,
            retry=retry_if_exception_type(AgentRetryableError),
            before_sleep=make_agent_retry_logger(context, agent_num, model_id),
            reraise=True,
        )
        try:
            for attempt in retryer:
                raise_if_cancelled(context)
                with attempt:
                    result = _run_agent_once(agent_num, context, rotator, model_id, prompt)
                    record_model_success(context, model_id)
                    return result
        except AgentMissingModelError as exc:
            last_error = str(exc)
            message = f"模型 {model_id} 不可用，改試下一個備援模型..."
            emit_log(f"    ❌ {message}")
            _emit_sync_model_event(context, agent_num, "model_fallback", "warning", message, model_id, error_kind=exc.__class__.__name__)
            continue
        except AgentRetryableError as exc:
            last_error = str(exc)
            circuit_state = record_model_failure(context, model_id, exc)
            message = f"{model_id} 多次重試後仍失敗：{last_error[:120]}"
            emit_log(f"    ❌ {message}")
            _emit_sync_model_event(
                context,
                agent_num,
                "model_failed",
                "error",
                message,
                model_id,
                error_kind=exc.__class__.__name__,
                circuit_open=bool(circuit_state.get("opened_until")),
            )
            continue

    return f"[Agent {agent_num} 執行失敗：所有模型/Key 不可用，最後錯誤：{last_error[:120]}]"


async def run_single_agent_async(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """
    非同步執行單個分析 Agent。
    - 使用 Google GenAI SDK 的 client.aio 非同步呼叫
    - quota/rate limit 會快速切換下一組 Key 或下一個模型
    """
    model_sequence = get_runtime_model_sequence(agent_num, context)
    last_error = ""

    for model_index, model_id in enumerate(model_sequence):
        raise_if_cancelled(context)
        if model_index > 0:
            message = f"切換備援模型：{model_id}"
            emit_log(f"    🔁 {message}")
            await _emit_async_model_event(context, agent_num, "model_fallback", "warning", message, model_id, model_index=model_index)

        if is_model_circuit_open(context, model_id) and model_index < len(model_sequence) - 1:
            message = f"模型 {model_id} 暫時熔斷，直接切換備援模型。"
            emit_log(f"    🔁 {message}")
            await _emit_async_model_event(context, agent_num, "model_circuit_open", "warning", message, model_id)
            continue

        has_fallback = len(model_sequence) > model_index + 1
        timeout_seconds = timeout_for_model_call(model_index, has_fallback)
        policy = model_attempt_policy(model_index, has_fallback, max_retries, len(getattr(rotator, "keys", []) or []))
        try:
            context["_primary_probe_prompt"] = model_index == 0 and has_fallback
            prompt = build_prompt(agent_num, data, context)
        finally:
            context.pop("_primary_probe_prompt", None)
        retryer = AsyncRetrying(
            stop=lambda retry_state: should_stop_retry(retry_state, policy),
            wait=_agent_retry_wait,
            retry=retry_if_exception_type(AgentRetryableError),
            before_sleep=make_agent_retry_logger(context, agent_num, model_id),
            reraise=True,
        )
        try:
            async for attempt in retryer:
                raise_if_cancelled(context)
                with attempt:
                    result = await _run_agent_once_async(
                        agent_num,
                        context,
                        rotator,
                        model_id,
                        prompt,
                        timeout_seconds=timeout_seconds,
                    )
                    record_model_success(context, model_id)
                    return result
        except AgentMissingModelError as exc:
            last_error = str(exc)
            message = f"模型 {model_id} 不可用，改試下一個備援模型..."
            emit_log(f"    ❌ {message}")
            await _emit_async_model_event(context, agent_num, "model_fallback", "warning", message, model_id, error_kind=exc.__class__.__name__)
            continue
        except AgentRetryableError as exc:
            last_error = str(exc)
            circuit_state = record_model_failure(context, model_id, exc)
            message = f"{model_id} 多次重試後仍失敗：{last_error[:120]}"
            emit_log(f"    ❌ {message}")
            await _emit_async_model_event(
                context,
                agent_num,
                "model_failed",
                "error",
                message,
                model_id,
                error_kind=exc.__class__.__name__,
                circuit_open=bool(circuit_state.get("opened_until")),
            )
            continue

    return f"[Agent {agent_num} 執行失敗：所有模型/Key 不可用，最後錯誤：{last_error[:120]}]"
