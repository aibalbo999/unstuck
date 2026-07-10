"""Storage, cache, report lifecycle, and data freshness settings."""

from __future__ import annotations

from pathlib import Path

from .env import BASE_DIR, env_int, env_list, env_str, json_env_dict


OUTPUT_DIR = env_str("OUTPUT_DIR", str(BASE_DIR / "output"))
CACHE_DIR = Path(env_str("CACHE_DIR", str(BASE_DIR / "cache")))
CACHE_DB_PATH = env_str("CACHE_DB_PATH", str(CACHE_DIR / "stock_agent_cache.sqlite3"))
REPORT_STORAGE_BACKEND = env_str("REPORT_STORAGE_BACKEND", "local").strip().lower()
CACHE_BACKEND = env_str("CACHE_BACKEND", "redis").strip().lower()
CACHE_NAMESPACE = env_str("CACHE_NAMESPACE", "stock-agent").strip().strip(":")
LANGGRAPH_CHECKPOINT_BACKEND = env_str("LANGGRAPH_CHECKPOINT_BACKEND", "sqlite").strip().lower()
LANGGRAPH_CHECKPOINT_PATH = env_str(
    "LANGGRAPH_CHECKPOINT_PATH",
    CACHE_DB_PATH,
)
LANGGRAPH_CHECKPOINT_POSTGRES_DSN = env_str("LANGGRAPH_CHECKPOINT_POSTGRES_DSN", "")
MARKET_CALENDAR_DIR = env_str("MARKET_CALENDAR_DIR", str(CACHE_DIR / "market_calendars"))
DATA_SNAPSHOT_MAX_BYTES = env_int("DATA_SNAPSHOT_MAX_BYTES", 2 * 1024 * 1024)
FINANCIAL_DATA_CACHE_SECONDS = env_int("FINANCIAL_DATA_CACHE_SECONDS", 24 * 60 * 60)
FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS = env_int(
    "FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS",
    max(FINANCIAL_DATA_CACHE_SECONDS, 7 * 24 * 60 * 60),
)
FINANCIAL_DATA_MARKET_CACHE_SECONDS = env_int("FINANCIAL_DATA_MARKET_CACHE_SECONDS", 15 * 60)
FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS = env_int(
    "FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS",
    FINANCIAL_DATA_CACHE_SECONDS,
)


def _load_source_freshness_seconds() -> dict[str, int]:
    defaults = {
        "market_data": FINANCIAL_DATA_MARKET_CACHE_SECONDS,
        "financial_statements": FINANCIAL_DATA_CACHE_SECONDS,
        "monthly_revenue": 24 * 60 * 60,
        "recent_catalysts": 30 * 60,
        "earnings_call": 24 * 60 * 60,
        "institutional_trading": 6 * 60 * 60,
        "dynamic_peer_metrics": 24 * 60 * 60,
        "peer_discovery": 24 * 60 * 60,
        "pe_river_chart": 24 * 60 * 60,
        "macro_indicators": 24 * 60 * 60,
        "chip_data": 6 * 60 * 60,
        "alternative_data": 24 * 60 * 60,
        "social_sentiment": 30 * 60,
        "sec_edgar": 24 * 60 * 60,
        "taiwan_open_data": 24 * 60 * 60,
    }
    for key in list(defaults):
        defaults[key] = env_int(f"SOURCE_FRESHNESS_{key.upper()}_SECONDS", defaults[key])
    for key, value in json_env_dict("SOURCE_FRESHNESS_SECONDS_JSON").items():
        try:
            defaults[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return defaults


SOURCE_FRESHNESS_MAX_AGE_SECONDS = _load_source_freshness_seconds()

REPORT_RETENTION_DAYS = env_int("REPORT_RETENTION_DAYS", 30)
REPORT_CLEANUP_INTERVAL_SECONDS = env_int("REPORT_CLEANUP_INTERVAL_SECONDS", 24 * 60 * 60)
OPERATIONAL_DB_PATH = env_str("OPERATIONAL_DB_PATH", str(CACHE_DIR / "operational.sqlite3"))
TASK_DB_PATH = env_str("TASK_DB_PATH", OPERATIONAL_DB_PATH)
ANALYSIS_JOB_STALE_SECONDS = env_int("ANALYSIS_JOB_STALE_SECONDS", 6 * 60 * 60)
ANALYSIS_JOB_HISTORY_RETENTION_DAYS = env_int("ANALYSIS_JOB_HISTORY_RETENTION_DAYS", 30)
PROVIDER_SLA_RETENTION_DAYS = env_int("PROVIDER_SLA_RETENTION_DAYS", 90)
PROVIDER_SLA_WARNING_MIN_ATTEMPTS = env_int("PROVIDER_SLA_WARNING_MIN_ATTEMPTS", 3)
PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS = env_int("PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS", 3)
PROVIDER_SLA_DEGRADE_LEVELS = set(env_list("PROVIDER_SLA_DEGRADE_LEVELS", ["critical"]))
SQLITE_BACKUP_DIR = env_str("SQLITE_BACKUP_DIR", str(CACHE_DIR / "sqlite_backups"))
SQLITE_BACKUP_INTERVAL_DAYS = env_int("SQLITE_BACKUP_INTERVAL_DAYS", 30)
SQLITE_BACKUP_RETENTION_DAYS = env_int("SQLITE_BACKUP_RETENTION_DAYS", 1)


__all__ = [name for name in globals() if name.isupper()]
