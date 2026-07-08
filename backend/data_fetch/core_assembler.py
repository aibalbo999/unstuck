"""Core payload assembly compatibility surface.

Focused builder helpers now live in formatting/audit/cache/enrichment and
yfinance payload modules. This file keeps historical helper names available
while production workflow depends on the typed provider/service boundary.
"""

from __future__ import annotations

from . import core_builder as _builder
from .core_builder import (  # noqa: F401
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    CORE_CACHE_SOURCES,
    DATA_SCHEMA_VERSION,
    SOURCE_FRESHNESS_SOURCES,
    DataLoader,
    _append_cache_audit_entries,
    _append_full_fetch_audit,
    _append_skipped_fresh_cache_audit,
    _append_source_fetch_audit,
    _assess_cached_financial_data,
    _build_data_freshness,
    _build_source_freshness,
    _build_source_freshness_entry,
    _cache_financial_data,
    _cache_timestamp_epoch,
    _dedupe_records,
    _freshness_policy,
    _history_has_values,
    _is_likely_market_session,
    _market_now,
    _mark_market_data_fetched,
    _mark_sources_fetched,
    _merge_optional_http_bundle,
    _source_is_stale,
    _source_max_age_seconds,
    _source_timestamp_epoch,
    append_audit_entry,
    append_source_audit,
    async_fetch_stock_data,
    audited_fetch,
    audited_fetch_async,
    build_company_identity,
    build_data_trust,
    build_pe_river_chart_data,
    build_source_audit_entry,
    fetch_dynamic_peer_metrics,
    fetch_finmind_financial_statement_fallback,
    fetch_finmind_news_catalysts,
    fetch_fmp_news_catalysts,
    fetch_fmp_news_catalysts_async,
    fetch_fmp_quote_fallback,
    fetch_institutional_trading_trend,
    fetch_recent_catalysts,
    fetch_stock_data,
    fetch_stock_data_from_snapshot,
    fetch_yfinance_snapshot,
    fetch_yfinance_news_catalysts,
    finalize_data_trust,
    first_number,
    format_data_for_prompt,
    format_number,
    format_pct,
    get_cache_json,
    get_market_data_provider,
    is_missing_value,
    is_taiwan_ticker,
    safe_get,
    set_cache_json,
    source_record_count,
    time_module,
)


def __getattr__(name: str):
    return getattr(_builder, name)
