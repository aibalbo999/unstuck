"""Runtime worker, timeout, and queue settings."""

from __future__ import annotations

import os

from .env import env_float



LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float("LLM_AGENT_CALL_TIMEOUT_SECONDS", 120.0)
PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float("PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS", 1.0)
FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float(
    "FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS",
    LLM_AGENT_CALL_TIMEOUT_SECONDS,
)
PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS = int(os.getenv("PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS", "1"))
PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS = int(os.getenv("PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS", "2"))
LLM_MODEL_CIRCUIT_THRESHOLD = int(os.getenv("LLM_MODEL_CIRCUIT_THRESHOLD", "2"))
LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS = env_float("LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS", 15 * 60.0)
ANALYSIS_WORKER_COUNT = int(os.getenv("ANALYSIS_WORKER_COUNT", "2"))
TASK_QUEUE_BACKEND = os.getenv("TASK_QUEUE_BACKEND", "local").strip().lower()
TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "stock-analysis")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LLM_RATE_LIMIT_BACKEND = os.getenv("LLM_RATE_LIMIT_BACKEND", "auto").strip().lower()
PROVIDER_CIRCUIT_BACKEND = os.getenv("PROVIDER_CIRCUIT_BACKEND", "auto").strip().lower()


__all__ = [name for name in globals() if name.isupper()]
