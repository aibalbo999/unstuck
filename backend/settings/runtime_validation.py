"""Runtime settings validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def validate_runtime_settings_from(settings: Mapping[str, Any]) -> list[str]:
    """Return startup configuration warnings without exposing secrets."""
    get = settings.get
    warnings = [
        message
        for failed, message in (
            (not get("DEFAULT_ANALYSIS_MODEL") or not get("DEFAULT_DECISION_MODEL"), "DEFAULT_ANALYSIS_MODEL / DEFAULT_DECISION_MODEL 未設定。"),
            (get("DATA_SNAPSHOT_MAX_BYTES", 0) <= 0, "DATA_SNAPSHOT_MAX_BYTES 必須大於 0。"),
            (get("ANALYSIS_WORKER_COUNT", 0) <= 0, "ANALYSIS_WORKER_COUNT 必須大於 0。"),
            (
                get("TASK_QUEUE_BACKEND") not in {"local", "rq", "arq"},
                f"TASK_QUEUE_BACKEND 應為 local、rq 或 arq，目前為 {get('TASK_QUEUE_BACKEND')}。",
            ),
            (not get("TASK_QUEUE_NAMES"), "TASK_QUEUE_NAMES 不可為空。"),
            (get("RQ_JOB_MAX_RETRIES_INVALID"), "RQ_JOB_MAX_RETRIES 必須為整數。"),
            (get("RQ_JOB_MAX_RETRIES", 0) <= 0, "RQ_JOB_MAX_RETRIES 必須大於 0。"),
            (get("RQ_JOB_RETRY_INTERVALS_INVALID"), "RQ_JOB_RETRY_INTERVALS 每個值都必須為整數。"),
            (not get("RQ_JOB_RETRY_INTERVALS"), "RQ_JOB_RETRY_INTERVALS 不可為空。"),
            (len(get("RQ_JOB_RETRY_INTERVALS", ())) < get("RQ_JOB_MAX_RETRIES", 0), "RQ_JOB_RETRY_INTERVALS 至少需涵蓋 RQ_JOB_MAX_RETRIES 次重試。"),
            (any(interval <= 0 for interval in get("RQ_JOB_RETRY_INTERVALS", ())), "RQ_JOB_RETRY_INTERVALS 每個值都必須大於 0。"),
            (get("RQ_JOB_TIMEOUT_SECONDS_INVALID"), "RQ_JOB_TIMEOUT_SECONDS 必須為整數。"),
            (get("RQ_JOB_TIMEOUT_SECONDS", 0) <= 0, "RQ_JOB_TIMEOUT_SECONDS 必須大於 0。"),
            (get("LLM_AGENT_CALL_TIMEOUT_SECONDS", 0) < 0, "LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。"),
            (get("PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS", 0) <= 0, "PRIMARY_LLM_AGENT_CALL_TIMEOUT_SECONDS 必須大於 0。"),
            (get("FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS", 0) < 0, "FALLBACK_LLM_AGENT_CALL_TIMEOUT_SECONDS 不可為負數。"),
            (
                get("PRIMARY_MODEL_TRANSIENT_MAX_ATTEMPTS", 0) <= 0 or get("PRIMARY_MODEL_QUOTA_MAX_ATTEMPTS", 0) <= 0,
                "PRIMARY_MODEL_*_MAX_ATTEMPTS 必須大於 0。",
            ),
            (
                get("LLM_SERVER_ERROR_MAX_ATTEMPTS", 0) <= 0 or get("LLM_SERVER_ERROR_RETRY_MAX_WAIT_SECONDS", 0) <= 0,
                "LLM_SERVER_ERROR_* 必須大於 0。",
            ),
            (
                get("LLM_MODEL_CIRCUIT_THRESHOLD", 0) <= 0 or get("LLM_MODEL_CIRCUIT_COOLDOWN_SECONDS", 0) <= 0,
                "LLM_MODEL_CIRCUIT_* 必須大於 0。",
            ),
            (get("LLM_SEMANTIC_CACHE_SECONDS", 0) <= 0, "LLM_SEMANTIC_CACHE_SECONDS 必須大於 0。"),
            (
                get("LLM_SEMANTIC_CACHE_MIN_SIMILARITY", 0) <= 0 or get("LLM_SEMANTIC_CACHE_MIN_SIMILARITY", 0) > 1,
                "LLM_SEMANTIC_CACHE_MIN_SIMILARITY 必須大於 0 且小於或等於 1。",
            ),
            (get("LLM_SEMANTIC_CACHE_MAX_INDEX_ENTRIES", 0) <= 0, "LLM_SEMANTIC_CACHE_MAX_INDEX_ENTRIES 必須大於 0。"),
            (not get("ALLOWED_ORIGINS"), "ALLOWED_ORIGINS 為空，瀏覽器前端可能無法呼叫 API。"),
            (get("DEPLOYMENT_MODE") not in {"local", "dev", "development", "test", "lan", "server", "production", "prod"}, "DEPLOYMENT_MODE 應為 local、lan、server 或 production。"),
            (
                get("REPORT_STORAGE_BACKEND") not in {"local", "memory"},
                f"REPORT_STORAGE_BACKEND 應為 local 或 memory，目前為 {get('REPORT_STORAGE_BACKEND')}。",
            ),
            (get("CACHE_BACKEND") not in {"sqlite", "redis", "memory"}, f"CACHE_BACKEND 應為 sqlite、redis 或 memory，目前為 {get('CACHE_BACKEND')}。"),
            (not get("CACHE_NAMESPACE"), "CACHE_NAMESPACE 不可為空。"),
            (
                get("LANGGRAPH_CHECKPOINT_BACKEND") not in {"sqlite", "postgres"},
                f"LANGGRAPH_CHECKPOINT_BACKEND 應為 sqlite 或 postgres，目前為 {get('LANGGRAPH_CHECKPOINT_BACKEND')}。",
            ),
            (
                get("LANGGRAPH_CHECKPOINT_BACKEND") == "postgres" and not str(get("LANGGRAPH_CHECKPOINT_POSTGRES_DSN") or "").strip(),
                "LANGGRAPH_CHECKPOINT_BACKEND=postgres 時必須設定 LANGGRAPH_CHECKPOINT_POSTGRES_DSN。",
            ),
        )
        if failed
    ]
    _append_cross_setting_warnings(settings, warnings)
    return warnings


def _append_cross_setting_warnings(settings: Mapping[str, Any], warnings: list[str]) -> None:
    get = settings.get
    missing_queue_routes = sorted({name for name in get("TASK_QUEUE_ROUTES", {}).values() if name and name not in get("TASK_QUEUE_NAMES", ())})
    if missing_queue_routes:
        warnings.append("TASK_QUEUE_ROUTES 指向未列於 TASK_QUEUE_NAMES 的 queue：" + ", ".join(missing_queue_routes))

    is_production = get("is_production_profile")(get("DEPLOYMENT_MODE")) if callable(get("is_production_profile")) else False
    if is_production and not get("MUTATION_API_TOKEN"):
        raise RuntimeError("production/lan/server profile 必須設定 MUTATION_API_TOKEN，避免 mutation endpoints 在未受保護狀態下啟動。")
    if is_production and "*" in get("ALLOWED_ORIGINS", ()):
        raise RuntimeError("production/lan/server profile 不允許 ALLOWED_ORIGINS 使用萬用字元 *。")
    has_guard = get("has_network_access_guard")
    if is_production and callable(has_guard) and not has_guard():
        raise RuntimeError("production/lan/server profile 必須設定 BASIC_AUTH_USERNAME/BASIC_AUTH_PASSWORD，或設 EXTERNAL_ACCESS_CONTROLLED=true 表示已有外層控管。")
    if is_production and get("LANGGRAPH_CHECKPOINT_BACKEND") == "sqlite" and _is_sqlite_checkpoint_path(get("LANGGRAPH_CHECKPOINT_PATH")):
        warnings.append(
            "LANGGRAPH_CHECKPOINT_PATH 目前使用 SQLite checkpoint；"
            "production 高併發建議改用 langgraph-checkpoint-postgres / PostgreSQL。"
        )

    invalid_freshness = [source for source, seconds in get("SOURCE_FRESHNESS_MAX_AGE_SECONDS", {}).items() if int(seconds) <= 0]
    if invalid_freshness:
        warnings.append("SOURCE_FRESHNESS_*_SECONDS 必須大於 0：" + ", ".join(sorted(invalid_freshness)))


def _is_sqlite_checkpoint_path(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text.endswith((".sqlite", ".sqlite3", ".db"))
