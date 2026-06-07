"""Runtime worker, timeout, and queue settings."""

from __future__ import annotations

import os

from .env import env_float


INTER_AGENT_DELAY = env_float("INTER_AGENT_DELAY", 0.0)
LLM_AGENT_CALL_TIMEOUT_SECONDS = env_float("LLM_AGENT_CALL_TIMEOUT_SECONDS", 120.0)
ANALYSIS_WORKER_COUNT = int(os.getenv("ANALYSIS_WORKER_COUNT", "2"))
TASK_QUEUE_BACKEND = os.getenv("TASK_QUEUE_BACKEND", "local").strip().lower()
TASK_QUEUE_NAME = os.getenv("TASK_QUEUE_NAME", "stock-analysis")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


__all__ = [name for name in globals() if name.isupper()]
