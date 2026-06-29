"""Compatibility aggregator for grouped application settings."""

from __future__ import annotations

from .models import *  # noqa: F401,F403
from .providers import *  # noqa: F401,F403
from .runtime_limits import *  # noqa: F401,F403
from .security import *  # noqa: F401,F403
from .storage import *  # noqa: F401,F403


def validate_runtime_settings() -> list[str]:
    """Return startup configuration warnings without exposing secrets."""
    warnings = []
    if not DEFAULT_ANALYSIS_MODEL or not DEFAULT_DECISION_MODEL:
        warnings.append("DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL 未設定。")
    if DATA_SNAPSHOT_MAX_BYTES <= 0:
        warnings.append("DATA_SNAPSHOT_MAX_BYTES 必須大於 0。")
    if ANALYSIS_WORKER_COUNT <= 0:
        warnings.append("ANALYSIS_WORKER_COUNT 必須大於 0。")
    if TASK_QUEUE_BACKEND not in {"local", "rq"}:
        warnings.append(f"TASK_QUEUE_BACKEND 應為 local 或 rq，目前為 {TASK_QUEUE_BACKEND}。")
    if not TASK_QUEUE_NAMES:
        warnings.append("TASK_QUEUE_NAMES 不可為空。")
    missing_queue_routes = sorted({name for name in TASK_QUEUE_ROUTES.values() if name and name not in TASK_QUEUE_NAMES})
    if missing_queue_routes:
        warnings.append("TASK_QUEUE_ROUTES 指向未列於 TASK_QUEUE_NAMES 的 queue：" + ", ".join(missing_queue_routes))
    if RQ_JOB_MAX_RETRIES_INVALID:
        warnings.append("RQ_JOB_MAX_RETRIES 必須為整數。")
    if RQ_JOB_MAX_RETRIES <= 0:
        warnings.append("RQ_JOB_MAX_RETRIES 必須大於 0。")
    if RQ_JOB_RETRY_INTERVALS_INVALID:
        warnings.append("RQ_JOB_RETRY_INTERVALS 每個值都必須為整數。")
    if not RQ_JOB_RETRY_INTERVALS:
        warnings.append("RQ_JOB_RETRY_INTERVALS 不可為空。")
    if len(RQ_JOB_RETRY_INTERVALS) < RQ_JOB_MAX_RETRIES:
        warnings.append("RQ_JOB_RETRY_INTERVALS 至少需涵蓋 RQ_JOB_MAX_RETRIES 次重試。")
    if any(interval <= 0 for interval in RQ_JOB_RETRY_INTERVALS):
        warnings.append("RQ_JOB_RETRY_INTERVALS 每個值都必須大於 0。")
    if RQ_JOB_TIMEOUT_SECONDS_INVALID:
        warnings.append("RQ_JOB_TIMEOUT_SECONDS 必須為整數。")
    if RQ_JOB_TIMEOUT_SECONDS <= 0:
        warnings.append("RQ_JOB_TIMEOUT_SECONDS 必須大於 0。")
    if LLM_AGENT_CALL_TIMEOUT_SECONDS < 0:
        warnings.append("LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。")
    if PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS <= 0:
        warnings.append("PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS 必須大於 0。")
    if FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS < 0:
        warnings.append("FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。")
    if PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS <= 0 or PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS <= 0:
        warnings.append("PRIMARY_MODEL_*_MAX_ATTEMPTS 必須大於 0。")
    if LLM_SERVER_ERROR_MAX_ATTEMPTS <= 0 or LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS <= 0:
        warnings.append("LLM_SERVER_ERROR_* 必須大於 0。")
    if LLM_MODEL_CIRCUIT_THRESHOLD <= 0 or LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS <= 0:
        warnings.append("LLM_MODEL_CIRCUIT_* 必須大於 0。")
    if not ALLOWED_ORIGINS:
        warnings.append("ALLOWED_ORIGINS 為空，瀏覽器前端可能無法呼叫 API。")
    if DEPLOYMENT_MODE not in {"local", "dev", "development", "test", "lan", "server", "production", "prod"}:
        warnings.append("DEPLOYMENT_MODE 應為 local、lan、server 或 production。")
    if REPORT_STORAGE_BACKEND not in {"local", "memory"}:
        warnings.append(f"REPORT_STORAGE_BACKEND 應為 local 或 memory，目前為 {REPORT_STORAGE_BACKEND}。")
    if CACHE_BACKEND not in {"sqlite", "redis", "memory"}:
        warnings.append(f"CACHE_BACKEND 應為 sqlite、redis 或 memory，目前為 {CACHE_BACKEND}。")
    if not CACHE_NAMESPACE:
        warnings.append("CACHE_NAMESPACE 不可為空。")
    if is_production_profile(DEPLOYMENT_MODE) and not MUTATION_API_TOKEN:
        raise RuntimeError("production/lan/server profile 必須設定 MUTATION_API_TOKEN，避免 mutation endpoints 在未受保護狀態下啟動。")
    if is_production_profile(DEPLOYMENT_MODE) and "*" in ALLOWED_ORIGINS:
        raise RuntimeError("production/lan/server profile 不允許 ALLOWED_ORIGINS 使用萬用字元 *。")
    if is_production_profile(DEPLOYMENT_MODE) and not has_network_access_guard():
        raise RuntimeError("production/lan/server profile 必須設定 BASIC_AUTH_USERNAME/BASIC_AUTH_PASSWORD，或設 EXTERNAL_ACCESS_CONTROLLED=true 表示已有外層控管。")
    invalid_freshness = [source for source, seconds in SOURCE_FRESHNESS_MAX_AGE_SECONDS.items() if int(seconds) <= 0]
    if invalid_freshness:
        warnings.append("SOURCE_FRESHNESS_*_SECONDS 必須大於 0：" + ", ".join(sorted(invalid_freshness)))
    return warnings


__all__ = [name for name in globals() if name.isupper() or name in {"has_api_keys", "refresh_api_keys", "validate_runtime_settings"} or name.startswith(("format_", "get_", "is_"))]
