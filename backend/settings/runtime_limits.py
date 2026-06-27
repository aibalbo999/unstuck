"""Runtime worker, timeout, and queue settings."""

from __future__ import annotations

import os

from .env import env_float


def _env_int_with_invalid_flag(name: str, default: int) -> tuple[int, bool]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default, False
    try:
        return int(raw), False
    except ValueError:
        return default, True


def _env_int_tuple_with_invalid_flag(name: str, default: str) -> tuple[tuple[int, ...], bool]:
    raw = os.getenv(name, default).strip()
    values = []
    invalid = False
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            values.append(int(value))
        except ValueError:
            invalid = True
    return tuple(values), invalid


LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float("LLM_AGENT_CALL_TIMEOUT_SECONDS", 120.0)
PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float("PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS", 360.0)
FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float(
    "FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS",
    LLM_AGENT_CALL_TIMEOUT_SECONDS,
)
PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS = int(os.getenv("PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS", "1"))
PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS = int(os.getenv("PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS", "2"))
LLM_SERVER_ERROR_MAX_ATTEMPTS = int(os.getenv("LLM_SERVER_ERROR_MAX_ATTEMPTS", "6"))
LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS = env_float("LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS", 45.0)
LLM_MODEL_CIRCUIT_THRESHOLD = int(os.getenv("LLM_MODEL_CIRCUIT_THRESHOLD", "2"))
LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS = env_float("LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS", 15 * 60.0)
ANALYSIS_WORKER_COUNT = int(os.getenv("ANALYSIS_WORKER_COUNT", "2"))
TASK_QUEUE_BACKEND = os.getenv("TASK_QUEUE_BACKEND", "rq").strip().lower()
TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "stock-analysis")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RQ_JOB_MAX_RETRIES, RQ_JOB_MAX_RETRIES_INVALID = _env_int_with_invalid_flag("RQ_JOB_MAX_RETRIES", 4)
RQ_JOB_RETRY_INTERVALS, RQ_JOB_RETRY_INTERVALS_INVALID = _env_int_tuple_with_invalid_flag(
    "RQ_JOB_RETRY_INTERVALS",
    "60,300,900,1800",
)
RQ_JOB_TIMEOUT_SECONDS, RQ_JOB_TIMEOUT_SECONDS_INVALID = _env_int_with_invalid_flag("RQ_JOB_TIMEOUT_SECONDS", 4 * 60 * 60)
LLM_RATE_LIMIT_BACKEND = os.getenv("LLM_RATE_LIMIT_BACKEND", "auto").strip().lower()
PROVIDER_CIRCUIT_BACKEND = os.getenv("PROVIDER_CIRCUIT_BACKEND", "auto").strip().lower()


__all__ = [name for name in globals() if name.isupper()]
