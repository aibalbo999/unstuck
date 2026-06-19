"""Compatibility facade for provider classes and registry."""

from __future__ import annotations

from .enrichment_providers import (
    DynamicPeerMetricsProvider,
    FmpNewsProvider,
    FreeNewsWaterfallProvider,
    GooglePeerDiscoveryProvider,
    GoogleSearchProvider,
    PeRiverChartProvider,
    YahooProvider,
)
from .provider_base import (
    CallableProvider,
    DataProvider,
    infer_market,
    provider_result_from_audited,
    provider_result_from_payload,
    unavailable_provider_result,
)
from .provider_registry import ProviderRegistry, default_providers
from .quote_providers import FmpProvider, YFinanceProvider
from .taiwan_providers import FinMindProvider, InstitutionalTradingProvider, MonthlyRevenueProvider, TwseOfficialProvider

__all__ = [
    name
    for name in globals()
    if not name.startswith("__") and name not in {"annotations"}
]
