"""Shared data-fetch payload constants."""

DATA_SCHEMA_VERSION = 4

SOURCE_FRESHNESS_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "recent_catalysts",
    "earnings_call",
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
