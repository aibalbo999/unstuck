"""Deprecated compatibility aggregator for data-fetch builder helpers.

Production code should import the focused modules in this package directly.
This file exists so older tests and external scripts using
``data_fetch.core_builder`` keep working during the staged migration.
"""

from __future__ import annotations

import time as time_module

from cache_store import get_cache_json, set_cache_json
from data_trust import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    append_source_audit,
    build_data_trust,
    build_source_audit_entry,
    finalize_data_trust,
    source_record_count,
)
from .market_sources.common import (
    _dedupe_records,
    _run_named_fetches,
    first_number,
    is_missing_value,
    safe_get,
)
from .market_sources.http_enrichment import (
    fetch_fmp_news_catalysts,
    fetch_fmp_news_catalysts_async,
    fetch_fmp_quote_fallback,
    fetch_recent_catalysts,
    fetch_yfinance_news_catalysts,
)
from .market_sources.identity import build_company_identity, is_taiwan_ticker
from .market_sources.peers import fetch_dynamic_peer_metrics
from .market_sources.taiwan import (
    DataLoader,
    _align_finmind_history,
    _history_has_values,
    fetch_finmind_financial_statement_fallback,
    fetch_finmind_news_catalysts,
    fetch_institutional_trading_trend,
)
from .market_sources.ticker_resolver import get_market_data_provider
from .market_sources.valuation import build_pe_river_chart_data
from prompt_builder import format_data_for_prompt
from source_audit import append_audit_entry, audited_fetch, audited_fetch_async

from . import yfinance_payload_builder as _builder
from .audit_helpers import (
    _append_cache_audit_entries,
    _append_full_fetch_audit,
    _append_skipped_fresh_cache_audit,
    _append_source_fetch_audit,
    _assess_cached_financial_data,
    _build_data_freshness,
    _build_source_freshness,
    _build_source_freshness_entry,
    _cache_timestamp_epoch,
    _freshness_policy,
    _is_likely_market_session,
    _market_now,
    _mark_market_data_fetched,
    _mark_sources_fetched,
    _source_is_stale,
    _source_max_age_seconds,
    _source_timestamp_epoch,
)
from .cache_helpers import _cache_financial_data
from .constants import CORE_CACHE_SOURCES, DATA_SCHEMA_VERSION, SOURCE_FRESHNESS_SOURCES
from .enrichment_merge import _merge_optional_http_bundle
from .formatting import format_number, format_pct
from .yfinance_payload_builder import (
    async_fetch_stock_data,
    fetch_stock_data,
    fetch_stock_data_from_snapshot,
    fetch_yfinance_snapshot,
)


def __getattr__(name: str):
    return getattr(_builder, name)
