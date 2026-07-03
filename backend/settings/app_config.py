"""Compatibility aggregator for grouped application settings."""

from __future__ import annotations

from importlib import import_module


_SETTING_MODULE_NAMES = ("models", "providers", "runtime_limits", "security", "storage")
_EXPORTED_SETTING_NAMES: list[str] = []
for module_name in _SETTING_MODULE_NAMES:
    module = import_module(f".{module_name}", __package__)
    for name in getattr(module, "__all__", ()):
        globals()[name] = getattr(module, name)
        if name not in _EXPORTED_SETTING_NAMES:
            _EXPORTED_SETTING_NAMES.append(name)


def validate_runtime_settings() -> list[str]:
    """Return startup configuration warnings without exposing secrets."""
    warnings = [
        message
        for failed, message in (
            (not DEFAULT_ANALYSIS_MODEL or not DEFAULT_DECISION_MODEL, "DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL 未設定。"),
            (DATA_SNAPSHOT_MAX_BYTES <= 0, "DATA_SNAPSHOT_MAX_BYTES 必須大於 0。"),
            (ANALYSIS_WORKER_COUNT <= 0, "ANALYSIS_WORKER_COUNT 必須大於 0。"),
            (TASK_QUEUE_BACKEND not in {"local", "rq"}, f"TASK_QUEUE_BACKEND 應為 local 或 rq，目前為 {TASK_QUEUE_BACKEND}。"),
            (not TASK_QUEUE_NAMES, "TASK_QUEUE_NAMES 不可為空。"),
            (RQ_JOB_MAX_RETRIES_INVALID, "RQ_JOB_MAX_RETRIES 必須為整數。"),
            (RQ_JOB_MAX_RETRIES <= 0, "RQ_JOB_MAX_RETRIES 必須大於 0。"),
            (RQ_JOB_RETRY_INTERVALS_INVALID, "RQ_JOB_RETRY_INTERVALS 每個值都必須為整數。"),
            (not RQ_JOB_RETRY_INTERVALS, "RQ_JOB_RETRY_INTERVALS 不可為空。"),
            (len(RQ_JOB_RETRY_INTERVALS) < RQ_JOB_MAX_RETRIES, "RQ_JOB_RETRY_INTERVALS 至少需涵蓋 RQ_JOB_MAX_RETRIES 次重試。"),
            (any(interval <= 0 for interval in RQ_JOB_RETRY_INTERVALS), "RQ_JOB_RETRY_INTERVALS 每個值都必須大於 0。"),
            (RQ_JOB_TIMEOUT_SECONDS_INVALID, "RQ_JOB_TIMEOUT_SECONDS 必須為整數。"),
            (RQ_JOB_TIMEOUT_SECONDS <= 0, "RQ_JOB_TIMEOUT_SECONDS 必須大於 0。"),
            (LLM_AGENT_CALL_TIMEOUT_SECONDS < 0, "LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。"),
            (PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS <= 0, "PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS 必須大於 0。"),
            (FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS < 0, "FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。"),
            (PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS <= 0 or PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS <= 0, "PRIMARY_MODEL_*_MAX_ATTEMPTS 必須大於 0。"),
            (LLM_SERVER_ERROR_MAX_ATTEMPTS <= 0 or LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS <= 0, "LLM_SERVER_ERROR_* 必須大於 0。"),
            (LLM_MODEL_CIRCUIT_THRESHOLD <= 0 or LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS <= 0, "LLM_MODEL_CIRCUIT_* 必須大於 0。"),
            (not ALLOWED_ORIGINS, "ALLOWED_ORIGINS 為空，瀏覽器前端可能無法呼叫 API。"),
            (DEPLOYMENT_MODE not in {"local", "dev", "development", "test", "lan", "server", "production", "prod"}, "DEPLOYMENT_MODE 應為 local、lan、server 或 production。"),
            (REPORT_STORAGE_BACKEND not in {"local", "memory"}, f"REPORT_STORAGE_BACKEND 應為 local 或 memory，目前為 {REPORT_STORAGE_BACKEND}。"),
            (CACHE_BACKEND not in {"sqlite", "redis", "memory"}, f"CACHE_BACKEND 應為 sqlite、redis 或 memory，目前為 {CACHE_BACKEND}。"),
            (not CACHE_NAMESPACE, "CACHE_NAMESPACE 不可為空。"),
        )
        if failed
    ]
    missing_queue_routes = sorted({name for name in TASK_QUEUE_ROUTES.values() if name and name not in TASK_QUEUE_NAMES})
    if missing_queue_routes:
        warnings.append("TASK_QUEUE_ROUTES 指向未列於 TASK_QUEUE_NAMES 的 queue：" + ", ".join(missing_queue_routes))
    if is_production_profile(DEPLOYMENT_MODE) and not MUTATION_API_TOKEN:
        raise RuntimeError("production/lan/server profile 必須設定 MUTATION_API_TOKEN，避免 mutation endpoints 在未受保護狀態下啟動。")
    if is_production_profile(DEPLOYMENT_MODE) and "*" in ALLOWED_ORIGINS:
        raise RuntimeError("production/lan/server profile 不允許 ALLOWED_ORIGINS 使用萬用字元 *。")
    if is_production_profile(DEPLOYMENT_MODE) and not has_network_access_guard():
        raise RuntimeError("production/lan/server profile 必須設定 BASIC_AUTH_USERNAME/BASIC_AUTH_PASSWORD，或設 EXTERNAL_ACCESS_CONTROLLED=true 表示已有外層控管。")
    if is_production_profile(DEPLOYMENT_MODE) and _is_sqlite_checkpoint_path(LANGGRAPH_CHECKPOINT_PATH):
        warnings.append(
            "LANGGRAPH_CHECKPOINT_PATH 目前使用 SQLite checkpoint；"
            "production 高併發建議改用 langgraph-checkpoint-postgres / PostgreSQL。"
        )
    invalid_freshness = [source for source, seconds in SOURCE_FRESHNESS_MAX_AGE_SECONDS.items() if int(seconds) <= 0]
    if invalid_freshness:
        warnings.append("SOURCE_FRESHNESS_*_SECONDS 必須大於 0：" + ", ".join(sorted(invalid_freshness)))
    return warnings


def _is_sqlite_checkpoint_path(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text.endswith((".sqlite", ".sqlite3", ".db"))


__all__ = sorted({
    *_EXPORTED_SETTING_NAMES,
    "validate_runtime_settings",
})
