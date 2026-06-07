"""Canonical data-fetching API."""

from .providers import (
    CallableProvider,
    DataProvider,
    DynamicPeerMetricsProvider,
    FinMindProvider,
    FmpProvider,
    FmpNewsProvider,
    GooglePeerDiscoveryProvider,
    GoogleSearchProvider,
    InstitutionalTradingProvider,
    MonthlyRevenueProvider,
    PeRiverChartProvider,
    ProviderRegistry,
    YahooProvider,
    YFinanceProvider,
    infer_market,
)
from .service import DEFAULT_STOCK_DATA_SERVICE, StockDataService, fetch_stock_data_async
from .types import FetchOptions, FetchRequest, FetchResult, ProviderResult

__all__ = [
    "CallableProvider",
    "DataProvider",
    "DEFAULT_STOCK_DATA_SERVICE",
    "DynamicPeerMetricsProvider",
    "FetchOptions",
    "FetchRequest",
    "FetchResult",
    "FinMindProvider",
    "FmpProvider",
    "FmpNewsProvider",
    "GooglePeerDiscoveryProvider",
    "GoogleSearchProvider",
    "InstitutionalTradingProvider",
    "MonthlyRevenueProvider",
    "PeRiverChartProvider",
    "ProviderRegistry",
    "ProviderResult",
    "StockDataService",
    "YahooProvider",
    "YFinanceProvider",
    "fetch_stock_data_async",
    "infer_market",
]
