"""Deprecated compatibility facade for market-data source helpers.

Production code should import from ``data_fetch.market_sources`` modules.
"""

from __future__ import annotations

import inspect
import warnings

from data_fetch.market_sources.common import (
    _dedupe_records as _dedupe_records_impl,
    _run_named_fetches as _run_named_fetches_impl,
    first_number as first_number_impl,
    is_missing_value as is_missing_value_impl,
    safe_get as safe_get_impl,
)
from data_fetch.market_sources.http_enrichment import (
    fetch_fmp_news_catalysts as fetch_fmp_news_catalysts_impl,
    fetch_fmp_news_catalysts_async as fetch_fmp_news_catalysts_async_impl,
    fetch_fmp_quote_fallback as fetch_fmp_quote_fallback_impl,
    fetch_recent_catalysts as fetch_recent_catalysts_impl,
    fetch_google_peer_discovery_results as fetch_google_peer_discovery_results_impl,
    fetch_google_peer_discovery_results_async as fetch_google_peer_discovery_results_async_impl,
    fetch_google_search_catalysts as fetch_google_search_catalysts_impl,
    fetch_google_search_catalysts_async as fetch_google_search_catalysts_async_impl,
    fetch_yfinance_news_catalysts as fetch_yfinance_news_catalysts_impl,
)
from data_fetch.market_sources.identity import (
    _stock_id_from_ticker as _stock_id_from_ticker_impl,
    build_company_identity as build_company_identity_impl,
    is_taiwan_ticker as is_taiwan_ticker_impl,
    load_taiwan_stock_info_records as load_taiwan_stock_info_records_impl,
    unique_nonempty as unique_nonempty_impl,
)
from data_fetch.market_sources.peers import (
    fetch_dynamic_peer_metrics as fetch_dynamic_peer_metrics_impl,
    infer_global_peer_tickers as infer_global_peer_tickers_impl,
)
from data_fetch.market_sources.taiwan import (
    DataLoader,
    _align_finmind_history as _align_finmind_history_impl,
    _history_has_values as _history_has_values_impl,
    fetch_finmind_financial_statement_fallback as fetch_finmind_financial_statement_fallback_impl,
    fetch_finmind_news_catalysts as fetch_finmind_news_catalysts_impl,
    fetch_institutional_trading_trend as fetch_institutional_trading_trend_impl,
)
from data_fetch.market_sources.ticker_resolver import (
    MarketDataProvider as _MarketDataProvider,
    TaiwanStockProvider as _TaiwanStockProvider,
    USStockProvider as _USStockProvider,
    get_market_data_provider as get_market_data_provider_impl,
)
from data_fetch.market_sources.valuation import build_pe_river_chart_data as build_pe_river_chart_data_impl


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        f"market_data_fetchers.{name} is deprecated; use data_fetch.market_sources modules instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def _deprecated_function(name: str, func):
    if inspect.iscoroutinefunction(func):
        async def async_wrapper(*args, **kwargs):
            _warn_deprecated(name)
            return await func(*args, **kwargs)

        return async_wrapper

    def wrapper(*args, **kwargs):
        _warn_deprecated(name)
        return func(*args, **kwargs)

    return wrapper


class MarketDataProvider(_MarketDataProvider):
    def __init__(self, *args, **kwargs):
        _warn_deprecated("MarketDataProvider")
        super().__init__(*args, **kwargs)


class USStockProvider(_USStockProvider):
    def __init__(self, *args, **kwargs):
        _warn_deprecated("USStockProvider")
        super().__init__(*args, **kwargs)


class TaiwanStockProvider(_TaiwanStockProvider):
    def __init__(self, *args, **kwargs):
        _warn_deprecated("TaiwanStockProvider")
        super().__init__(*args, **kwargs)


_align_finmind_history = _deprecated_function("_align_finmind_history", _align_finmind_history_impl)
_dedupe_records = _deprecated_function("_dedupe_records", _dedupe_records_impl)
_history_has_values = _deprecated_function("_history_has_values", _history_has_values_impl)
_run_named_fetches = _deprecated_function("_run_named_fetches", _run_named_fetches_impl)
_stock_id_from_ticker = _deprecated_function("_stock_id_from_ticker", _stock_id_from_ticker_impl)
build_company_identity = _deprecated_function("build_company_identity", build_company_identity_impl)
build_pe_river_chart_data = _deprecated_function("build_pe_river_chart_data", build_pe_river_chart_data_impl)
fetch_dynamic_peer_metrics = _deprecated_function("fetch_dynamic_peer_metrics", fetch_dynamic_peer_metrics_impl)
fetch_finmind_financial_statement_fallback = _deprecated_function("fetch_finmind_financial_statement_fallback", fetch_finmind_financial_statement_fallback_impl)
fetch_finmind_news_catalysts = _deprecated_function("fetch_finmind_news_catalysts", fetch_finmind_news_catalysts_impl)
fetch_fmp_news_catalysts = _deprecated_function("fetch_fmp_news_catalysts", fetch_fmp_news_catalysts_impl)
fetch_fmp_news_catalysts_async = _deprecated_function("fetch_fmp_news_catalysts_async", fetch_fmp_news_catalysts_async_impl)
fetch_fmp_quote_fallback = _deprecated_function("fetch_fmp_quote_fallback", fetch_fmp_quote_fallback_impl)
fetch_google_peer_discovery_results = _deprecated_function("fetch_google_peer_discovery_results", fetch_google_peer_discovery_results_impl)
fetch_google_peer_discovery_results_async = _deprecated_function("fetch_google_peer_discovery_results_async", fetch_google_peer_discovery_results_async_impl)
fetch_google_search_catalysts = _deprecated_function("fetch_google_search_catalysts", fetch_google_search_catalysts_impl)
fetch_google_search_catalysts_async = _deprecated_function("fetch_google_search_catalysts_async", fetch_google_search_catalysts_async_impl)
fetch_institutional_trading_trend = _deprecated_function("fetch_institutional_trading_trend", fetch_institutional_trading_trend_impl)
fetch_recent_catalysts = _deprecated_function("fetch_recent_catalysts", fetch_recent_catalysts_impl)
fetch_yfinance_news_catalysts = _deprecated_function("fetch_yfinance_news_catalysts", fetch_yfinance_news_catalysts_impl)
first_number = _deprecated_function("first_number", first_number_impl)
get_market_data_provider = _deprecated_function("get_market_data_provider", get_market_data_provider_impl)
infer_global_peer_tickers = _deprecated_function("infer_global_peer_tickers", infer_global_peer_tickers_impl)
is_missing_value = _deprecated_function("is_missing_value", is_missing_value_impl)
is_taiwan_ticker = _deprecated_function("is_taiwan_ticker", is_taiwan_ticker_impl)
load_taiwan_stock_info_records = _deprecated_function("load_taiwan_stock_info_records", load_taiwan_stock_info_records_impl)
safe_get = _deprecated_function("safe_get", safe_get_impl)
unique_nonempty = _deprecated_function("unique_nonempty", unique_nonempty_impl)
