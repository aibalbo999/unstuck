"""Source max-age policy for stock-data freshness."""

from __future__ import annotations

from typing import Optional

from config import (
    FINANCIAL_DATA_CACHE_SECONDS,
    FINANCIAL_DATA_MARKET_CACHE_SECONDS,
    FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
    SOURCE_FRESHNESS_MAX_AGE_SECONDS,
)
from data_freshness_market import is_likely_market_session


SOURCE_FRESHNESS_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "recent_catalysts",
    "global_market_context",
    "international_news_context",
    "macro_indicators",
    "chip_data",
    "alternative_data",
    "social_sentiment",
    "sec_edgar",
    "taiwan_open_data",
    "institutional_trading",
    "dynamic_peer_metrics",
    "peer_discovery",
    "pe_river_chart",
)
CORE_CACHE_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
)


def freshness_policy(ticker: str, market_session: Optional[bool] = None) -> dict:
    if market_session is None:
        market_session = is_likely_market_session(ticker)
    return {
        "market_session": market_session,
        "max_age_seconds": FINANCIAL_DATA_MARKET_CACHE_SECONDS if market_session else FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
        "policy": "market_session" if market_session else "offhours_or_weekend",
    }


def source_max_age_seconds(source: str, ticker: str, market_session: Optional[bool] = None) -> int:
    if source == "market_data":
        return int(freshness_policy(ticker, market_session=market_session)["max_age_seconds"])
    return int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(source, FINANCIAL_DATA_CACHE_SECONDS))
