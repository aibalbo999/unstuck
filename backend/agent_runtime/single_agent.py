# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

import asyncio

from tenacity import AsyncRetrying, Retrying, retry_if_exception_type

from analysis_types import AnalysisContext, StockData
from llm_client import KeyRotator
from llm_input_capacity import InputCapacityExceededError
from .single_agent_events import route_rejection_event

from .llm_calls import (
    AgentConfigurationError,
    AgentMissingModelError,
    AgentRetryableError,
    _agent_retry_wait,
    make_agent_retry_logger,
    _run_agent_once,
    _run_agent_once_async,
)
from .cancellation import raise_if_cancelled
from .deferred import failed_route_result, record_route_failure, unavailable_model
from .model_policy import (
    make_model_retry_stop_for_rotator,
    model_attempt_policy,
    model_key_count,
    record_model_success,
    timeout_for_model_call,
)
from .prompting import build_prompt
from .routing import get_runtime_model_sequence
from .step_cache import (
    build_agent_step_cache_key,
    get_cached_agent_step,
    record_agent_step_cache_miss,
    restore_cached_agent_step,
    store_cached_agent_step,
)
from .single_agent_events import emit_async_model_event, emit_sync_model_event
from runtime_events import emit_log
def run_single_agent(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """執行單個 Agent，支援模型備援與可恢復的暫時失敗。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_single_agent_async(agent_num, data, context, rotator, max_retries))

    model_sequence = get_runtime_model_sequence(agent_num, context)
    if not model_sequence:
        raise AgentConfigurationError(f"Agent {agent_num} 未設定可用模型路由。")
    last_error = ""
    deferred_routes = []

    for model_index, model_id in enumerate(model_sequence):
        raise_if_cancelled(context)
        if model_index > 0:
            message = f"切換備援模型：{model_id}"
            emit_log(f"    🔁 {message}")
            emit_sync_model_event(context, agent_num, "model_fallback", "warning", message, model_id, model_index=model_index)

        try:
            unavailable = unavailable_model(context, rotator, model_id)
        except AgentConfigurationError as exc:
            last_error = str(exc)
            continue
        if unavailable:
            deferred_routes.append(unavailable)
            message = f"模型 {model_id} 暫時熔斷，直接切換備援模型。"
            emit_log(f"    🔁 {message}")
            emit_sync_model_event(context, agent_num, "model_circuit_open", "warning", message, model_id)
            continue

        has_fallback = len(model_sequence) > model_index + 1
        timeout_seconds = timeout_for_model_call(model_index, has_fallback)
        policy = model_attempt_policy(model_index, has_fallback, max_retries, model_key_count(rotator, model_id))
        try:
            context["_primary_probe_prompt"] = model_index == 0 and has_fallback
            prompt = build_prompt(agent_num, data, context)
        finally:
            context.pop("_primary_probe_prompt", None)
        cache_key = build_agent_step_cache_key(agent_num, data, context, model_id, prompt)
        cached_step = get_cached_agent_step(cache_key)
        if cached_step is not None:
            emit_sync_model_event(
                context,
                agent_num,
                "agent_step_cache_hit",
                "info",
                f"Agent {agent_num} 使用快取輸出。",
                model_id,
                cache_key=cache_key,
                cache_hit=True,
            )
            return restore_cached_agent_step(context, agent_num, cached_step)
        record_agent_step_cache_miss(context)
        retryer = Retrying(
            stop=make_model_retry_stop_for_rotator(policy, rotator, model_id),
            wait=_agent_retry_wait,
            retry=retry_if_exception_type(AgentRetryableError),
            before_sleep=make_agent_retry_logger(context, agent_num, model_id),
            reraise=True,
        )
        try:
            for attempt in retryer:
                raise_if_cancelled(context)
                with attempt:
                    result = _run_agent_once(
                        agent_num, context, rotator, model_id, prompt,
                        timeout_seconds=timeout_seconds,
                    )
                    record_model_success(context, model_id)
                    store_cached_agent_step(
                        cache_key,
                        agent_num=agent_num,
                        context=context,
                        model_id=model_id,
                        text=result,
                    )
                    return result
        except (InputCapacityExceededError, AgentMissingModelError, AgentConfigurationError) as exc:
            last_error = str(exc)
            phase, message, metadata = route_rejection_event(model_id, exc)
            emit_log(f"    ❌ {message}")
            emit_sync_model_event(context, agent_num, phase, "warning", message, model_id, **metadata)
            continue
        except AgentRetryableError as exc:
            last_error = str(exc)
            circuit_state = record_route_failure(context, rotator, model_id, exc, deferred_routes)
            message = f"{model_id} 多次重試後仍失敗：{last_error[:120]}"
            emit_log(f"    ❌ {message}")
            emit_sync_model_event(
                context,
                agent_num,
                "model_failed",
                "error",
                message,
                model_id,
                error_kind=exc.__class__.__name__,
                circuit_open=bool(circuit_state.get("opened_until")),
                shared_circuit_open=bool(getattr(exc, "parallel_circuit_open", False)),
            )
            continue

    return failed_route_result(agent_num, last_error, deferred_routes)


async def run_single_agent_async(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """非同步執行單個 Agent，超限時切換 Key 或模型。"""
    model_sequence = get_runtime_model_sequence(agent_num, context)
    if not model_sequence:
        raise AgentConfigurationError(f"Agent {agent_num} 未設定可用模型路由。")
    last_error = ""
    deferred_routes = []

    for model_index, model_id in enumerate(model_sequence):
        raise_if_cancelled(context)
        if model_index > 0:
            message = f"切換備援模型：{model_id}"
            emit_log(f"    🔁 {message}")
            await emit_async_model_event(context, agent_num, "model_fallback", "warning", message, model_id, model_index=model_index)

        try:
            unavailable = unavailable_model(context, rotator, model_id)
        except AgentConfigurationError as exc:
            last_error = str(exc)
            continue
        if unavailable:
            deferred_routes.append(unavailable)
            message = f"模型 {model_id} 暫時熔斷，直接切換備援模型。"
            emit_log(f"    🔁 {message}")
            await emit_async_model_event(context, agent_num, "model_circuit_open", "warning", message, model_id)
            continue

        has_fallback = len(model_sequence) > model_index + 1
        timeout_seconds = timeout_for_model_call(model_index, has_fallback)
        policy = model_attempt_policy(model_index, has_fallback, max_retries, model_key_count(rotator, model_id))
        try:
            context["_primary_probe_prompt"] = model_index == 0 and has_fallback
            prompt = build_prompt(agent_num, data, context)
        finally:
            context.pop("_primary_probe_prompt", None)
        cache_key = build_agent_step_cache_key(agent_num, data, context, model_id, prompt)
        cached_step = get_cached_agent_step(cache_key)
        if cached_step is not None:
            await emit_async_model_event(
                context,
                agent_num,
                "agent_step_cache_hit",
                "info",
                f"Agent {agent_num} 使用快取輸出。",
                model_id,
                cache_key=cache_key,
                cache_hit=True,
            )
            return restore_cached_agent_step(context, agent_num, cached_step)
        record_agent_step_cache_miss(context)
        retryer = AsyncRetrying(
            stop=make_model_retry_stop_for_rotator(policy, rotator, model_id),
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
                        agent_num, context, rotator, model_id, prompt,
                        timeout_seconds=timeout_seconds,
                    )
                    record_model_success(context, model_id)
                    store_cached_agent_step(
                        cache_key,
                        agent_num=agent_num,
                        context=context,
                        model_id=model_id,
                        text=result,
                    )
                    return result
        except (InputCapacityExceededError, AgentMissingModelError, AgentConfigurationError) as exc:
            last_error = str(exc)
            phase, message, metadata = route_rejection_event(model_id, exc)
            emit_log(f"    ❌ {message}")
            await emit_async_model_event(context, agent_num, phase, "warning", message, model_id, **metadata)
            continue
        except AgentRetryableError as exc:
            last_error = str(exc)
            circuit_state = record_route_failure(context, rotator, model_id, exc, deferred_routes)
            message = f"{model_id} 多次重試後仍失敗：{last_error[:120]}"
            emit_log(f"    ❌ {message}")
            await emit_async_model_event(
                context,
                agent_num,
                "model_failed",
                "error",
                message,
                model_id,
                error_kind=exc.__class__.__name__,
                circuit_open=bool(circuit_state.get("opened_until")),
                shared_circuit_open=bool(getattr(exc, "parallel_circuit_open", False)),
            )
            continue

    return failed_route_result(agent_num, last_error, deferred_routes)
