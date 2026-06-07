"""Shared constants for source audit, data trust, and snapshots."""

from __future__ import annotations

import re


DATA_SNAPSHOT_SCHEMA_VERSION = 3
SUPPORTED_DATA_SNAPSHOT_SCHEMA_VERSIONS = {1, 2, DATA_SNAPSHOT_SCHEMA_VERSION}
SNAPSHOT_RERUN_ANALYSIS_MAX_CHARS = 12000
SNAPSHOT_TRIMMABLE_LIST_FIELDS = (
    "recent_catalysts",
    "peer_discovery_results",
    "dynamic_peer_metrics",
)
SNAPSHOT_CORE_DATA_KEYS = {
    "data_schema_version",
    "ticker",
    "company_name",
    "raw_company_name",
    "company_identity",
    "sector",
    "industry",
    "country",
    "fetch_date",
    "current_price",
    "current_price_fmt",
    "market_cap_raw",
    "market_cap_fmt",
    "pe_ratio",
    "pe_ratio_raw",
    "forward_pe",
    "forward_pe_raw",
    "pb_ratio",
    "ps_ratio",
    "ev_ebitda",
    "shares_raw",
    "forward_eps",
    "trailing_eps",
    "revenue_ttm_raw",
    "net_income_ttm_raw",
    "free_cash_flow_raw",
    "total_debt_raw",
    "total_cash_raw",
    "years",
    "revenue_history",
    "net_income_history",
    "gross_profit_history",
    "operating_income_history",
    "fcf_history",
    "gross_margin_history",
    "op_margin_history",
    "net_margin_history",
    "roe_history",
    "total_equity_history",
    "total_assets_history",
    "recent_monthly_revenue",
    "institutional_trading",
    "pe_river_chart",
    "data_source_notes",
    "data_freshness",
    "source_freshness",
    "source_audit",
    "data_trust",
}

AUDIT_STATUS_SUCCESS = "success"
AUDIT_STATUS_ERROR = "error"
AUDIT_STATUS_SKIPPED_FRESH_CACHE = "skipped_fresh_cache"
AUDIT_STATUS_UNAVAILABLE = "unavailable"
AUDIT_STATUSES = {
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_UNAVAILABLE,
}

SOURCE_AUDIT_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
    "recent_catalysts",
    "peer_discovery",
)
CORE_DATA_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
)
CRITICAL_TRUST_SOURCES = ("market_data", "financial_statements")

TRUST_STATUS_FRESH = "fresh"
TRUST_STATUS_PARTIAL = "partial"
TRUST_STATUS_STALE = "stale"
TRUST_STATUS_ERROR = "error"
TRUST_STATUS_UNKNOWN = "unknown"
TRUST_STATUSES = {
    TRUST_STATUS_FRESH,
    TRUST_STATUS_PARTIAL,
    TRUST_STATUS_STALE,
    TRUST_STATUS_ERROR,
    TRUST_STATUS_UNKNOWN,
}

SOURCE_LABELS = {
    "market_data": "市場資料",
    "financial_statements": "年度財報",
    "monthly_revenue": "月營收",
    "institutional_trading": "法人籌碼",
    "dynamic_peer_metrics": "同業指標",
    "pe_river_chart": "P/E 河流圖",
    "recent_catalysts": "近期催化劑",
    "peer_discovery": "同業搜尋",
}

AUDIT_STATUS_LABELS = {
    AUDIT_STATUS_SUCCESS: "成功",
    AUDIT_STATUS_ERROR: "異常",
    AUDIT_STATUS_SKIPPED_FRESH_CACHE: "新鮮快取",
    AUDIT_STATUS_UNAVAILABLE: "無可用資料",
}

TRUST_STATUS_LABELS = {
    TRUST_STATUS_FRESH: "資料新鮮",
    TRUST_STATUS_PARTIAL: "部分異常",
    TRUST_STATUS_STALE: "部分過期",
    TRUST_STATUS_ERROR: "來源異常",
    TRUST_STATUS_UNKNOWN: "未記錄",
}

SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|secret|password|token|authorization|prompt|retry|env(?:iron)?(?:ment)?)",
    re.IGNORECASE,
)
