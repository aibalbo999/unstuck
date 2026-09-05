"""Model availability failures that must leave the workflow resumable."""

from __future__ import annotations

import math
import time

from config import LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS
from .model_policy import MODEL_CIRCUITS_KEY, eligible_model_key_slots, model_circuit_open_for_job, publish_shared_model_circuit, record_model_failure
from .retry_policy import AgentConfigurationError, AgentRateLimitError, AgentTransientError


class AgentDeferredError(AgentRateLimitError):
    """All remaining usable routes need a later retry, not a report placeholder."""

    def __init__(self, agent_num: int, routes: list[dict]):
        self.agent_num = agent_num
        self.routes = routes
        wait = max(1, math.ceil(min(route["retry_wait_seconds"] for route in routes)))
        names = ", ".join(route["model_id"] for route in routes)
        super().__init__(f"Agent {agent_num} 模型暫時不可用（{names}），至少 {wait} 秒後重試。", wait, wait)
        self.all_keys_exhausted = True
        self.preflight_blocked = True


def unavailable_model(context: dict, rotator, model_id: str) -> dict | None:
    try:
        slots = eligible_model_key_slots(rotator, model_id)
        cooling = model_circuit_open_for_job(context, rotator, model_id)
        if slots != set() and not cooling:
            return None
        state = (context.get(MODEL_CIRCUITS_KEY) or {}).get(model_id) or {}
        wait = max(0.0, float(state.get("opened_until") or 0) - time.time())
        getter = getattr(rotator, "model_retry_wait", None) or getattr(rotator, "model_circuit_wait", None)
        if callable(getter):
            value = getter(model_id)
            if isinstance(value, (int, float)) and math.isfinite(value):
                wait = max(wait, value)
        if wait <= 0:
            wait = float(LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS or 60)
        return {"model_id": model_id, "reason_code": "daily_quota_disabled" if slots == set() else "model_cooldown", "retry_wait_seconds": wait}
    except RuntimeError as exc:
        raise AgentConfigurationError(str(exc)) from exc


def failed_route_result(agent_num: int, last_error: str, deferred_routes: list[dict]) -> str:
    if deferred_routes:
        raise AgentDeferredError(agent_num, deferred_routes)
    return f"[Agent {agent_num} 執行失敗：所有模型/Key 或請求設定均失敗，最後錯誤：{last_error[:120]}]"


def record_route_failure(context: dict, rotator, model_id: str, error: Exception, deferred_routes: list[dict]) -> dict:
    state = record_model_failure(context, model_id, error)
    publish_shared_model_circuit(rotator, model_id, state, quota_exhausted=bool(getattr(error, "all_keys_exhausted", False)))
    unavailable = unavailable_model(context, rotator, model_id)
    if unavailable is None and isinstance(error, (AgentRateLimitError, AgentTransientError)):
        waits = [60.0]
        for field in ("retry_wait_seconds", "key_cooldown_seconds"):
            value = getattr(error, field, None)
            if isinstance(value, (int, float)) and math.isfinite(value):
                waits.append(value)
        unavailable = {"model_id": model_id, "reason_code": "temporary_provider_failure", "retry_wait_seconds": max(waits)}
    if unavailable:
        deferred_routes.append(unavailable)
    return state
