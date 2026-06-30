"""Storage, cache, report lifecycle, and data freshness settings."""

from __future__ import annotations

import os
from pathlib import Path

from .env import BASE_DIR, env_int, env_list, json_env_dict


OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(BASE_DIR / "cache")))
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", str(CACHE_DIR / "stock_agent_cache.sqlite3"))
REPORT_STORAGE_BACKEND = os.getenv("REPORT_STORAGE_BACKEND", "local").strip().lower()
CACHE_BACKEND = os.getenv("CACHE_BACKEND", "redis").strip().lower()
CACHE_NAMESPACE = os.getenv("CACHE_NAMESPACE", "stock-agent").strip().strip(":")
LANGGRAPH_CHECKPOINT_PATH = os.getenv(
    "LANGGRAPH_CHECKPOINT_PATH",
    CACHE_DB_PATH,
)
MARKET_CALENDAR_DIR = os.getenv("MARKET_CALENDAR_DIR", str(CACHE_DIR / "market_calendars"))
DATA_SNAPSHOT_MAX_BYTES = env_int("DATA_SNAPSHOT_MAX_BYTES", 2 * 1024 * 1024)
FINANCIAL_DATA_CACHE_SECONDS = int(os.getenv("FINANCIAL_DATA_CACHE_SECONDS", str(24 * 60 * 60)))
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

REPORT_RETENTION_DAYS = int(os.getenv("REPORT_RETENTION_DAYS", "30"))
REPORT_CLEANUP_INTERVAL_SECONDS = int(os.getenv("REPORT_CLEANUP_INTERVAL_SECONDS", str(24 * 60 * 60)))
OPERATIONAL_DB_PATH = os.getenv("OPERATIONAL_DB_PATH", str(CACHE_DIR / "operational.sqlite3"))
TASK_DB_PATH = os.getenv("TASK_DB_PATH", OPERATIONAL_DB_PATH)
ANALYSIS_JOB_STALE_SECONDS = int(os.getenv("ANALYSIS_JOB_STALE_SECONDS", str(6 * 60 * 60)))
ANALYSIS_JOB_HISTORY_RETENTION_DAYS = env_int("ANALYSIS_JOB_HISTORY_RETENTION_DAYS", 30)
PROVIDER_SLA_RETENTION_DAYS = env_int("PROVIDER_SLA_RETENTION_DAYS", 90)
PROVIDER_SLA_WARNING_MIN_ATTEMPTS = env_int("PROVIDER_SLA_WARNING_MIN_ATTEMPTS", 3)
PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS = env_int("PROVIDER_SLA_CRITICAL_MIN_ATTEMPTS", 3)
PROVIDER_SLA_DEGRADE_LEVELS = set(env_list("PROVIDER_SLA_DEGRADE_LEVELS", ["critical"]))
SQLITE_BACKUP_DIR = os.getenv("SQLITE_BACKUP_DIR", str(CACHE_DIR / "sqlite_backups"))


__all__ = [name for name in globals() if name.isupper()]
