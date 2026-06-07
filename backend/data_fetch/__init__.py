"""Canonical data-fetching API."""

from .enrichment_providers import (
    DynamicPeerMetricsProvider,
    FmpNewsProvider,
    GooglePeerDiscoveryProvider,
    GoogleSearchProvider,
    PeRiverChartProvider,
    YahooProvider,
)
from .provider_base import CallableProvider, DataProvider, infer_market
from .provider_registry import ProviderRegistry
from .quote_providers import FmpProvider, YFinanceProvider
from .taiwan_providers import FinMindProvider, InstitutionalTradingProvider, MonthlyRevenueProvider
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
