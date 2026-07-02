"""Deprecated compatibility shim for stock financial data fetching.

New code should use data_fetch.StockDataService and data_fetch.FetchRequest.
"""

from __future__ import annotations

import warnings

import data_freshness as _freshness
from data_fetch import FetchRequest, StockDataService
from data_fetch import core_assembler as _orchestrator
from data_fetch.core_assembler import *  # noqa: F401,F403
from prompt_builder import format_data_for_prompt  # noqa: F401


_PATCHABLE_ORCHESTRATOR_NAMES = (
    "DataLoader",
    "FINANCIAL_DATA_CACHE_SECONDS",
    "FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS",
    "FINANCIAL_DATA_MARKET_CACHE_SECONDS",
    "FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS",
    "SOURCE_FRESHNESS_MAX_AGE_SECONDS",
    "get_cache_json",
    "set_cache_json",
    "time_module",
    "_is_likely_market_session",
    "fetch_google_search_catalysts_async",
    "fetch_fmp_news_catalysts_async",
    "fetch_google_peer_discovery_results_async",
    "fetch_google_search_catalysts",
    "fetch_fmp_news_catalysts",
    "fetch_finmind_news_catalysts",
    "fetch_yfinance_news_catalysts",
    "fetch_fmp_quote_fallback",
    "fetch_recent_catalysts",
    "fetch_institutional_trading_trend",
    "fetch_dynamic_peer_metrics",
    "fetch_google_peer_discovery_results",
    "fetch_finmind_financial_statement_fallback",
    "build_pe_river_chart_data",
    "get_market_data_provider",
)


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"financial_data.{name} is deprecated; use data_fetch.StockDataService/FetchRequest instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def _sync_orchestrator_patchables() -> None:
    for name in _PATCHABLE_ORCHESTRATOR_NAMES:
        if name in globals():
            setattr(_orchestrator, name, globals()[name])
            if hasattr(_freshness, name):
                setattr(_freshness, name, globals()[name])


def fetch_stock_data(ticker: str, skip_optional_http: bool = False) -> dict:
    _warn_deprecated("fetch_stock_data")
    _sync_orchestrator_patchables()
    request = FetchRequest.from_ticker(ticker, skip_optional_http=skip_optional_http)
    return StockDataService().fetch(request).data


_FACADE_FETCH_STOCK_DATA = fetch_stock_data


async def async_fetch_stock_data(ticker: str) -> dict:
    _warn_deprecated("async_fetch_stock_data")
    _sync_orchestrator_patchables()
    patched_fetch = globals().get("fetch_stock_data")
    original_fetch = _orchestrator.fetch_stock_data
    if patched_fetch is not _FACADE_FETCH_STOCK_DATA:
        setattr(_orchestrator, "fetch_stock_data", patched_fetch)
    try:
        request = FetchRequest.from_ticker(ticker)
        return (await StockDataService().fetch_async(request)).data
    finally:
        setattr(_orchestrator, "fetch_stock_data", original_fetch)


def _cache_financial_data(data: dict, original_ticker: str):
    _sync_orchestrator_patchables()
    return _orchestrator._cache_financial_data(data, original_ticker)


def _merge_optional_http_bundle(*args, **kwargs):
    _sync_orchestrator_patchables()
    return _orchestrator._merge_optional_http_bundle(*args, **kwargs)


def _assess_cached_financial_data(*args, **kwargs):
    _sync_orchestrator_patchables()
    return _orchestrator._assess_cached_financial_data(*args, **kwargs)


def _append_source_fetch_audit(*args, **kwargs):
    _sync_orchestrator_patchables()
    return _orchestrator._append_source_fetch_audit(*args, **kwargs)


def _append_skipped_fresh_cache_audit(*args, **kwargs):
    _sync_orchestrator_patchables()
    return _orchestrator._append_skipped_fresh_cache_audit(*args, **kwargs)


def __getattr__(name: str):
    return getattr(_orchestrator, name)
