"""Provider registry and default provider plan."""

from __future__ import annotations

from collections.abc import Iterable

from .agent_context_providers import AlternativeJobOpeningsProvider, ChipDataProvider, MacroIndicatorsProvider, SocialSentimentProvider
from .enrichment_providers import (
    AlternativePeerDiscoveryProvider,
    AlternativeSearchProvider,
    DynamicPeerMetricsProvider,
    EarningsCallProvider,
    FmpNewsProvider,
    FreeNewsWaterfallProvider,
    GlobalMarketContextProvider,
    InternationalNewsContextProvider,
    PeRiverChartProvider,
    YahooProvider,
)
from .provider_base import DataProvider
from .quote_providers import FmpProvider, YFinanceProvider
from .taiwan_providers import FinMindProvider, InstitutionalTradingProvider, MonthlyRevenueProvider, TwseOfficialProvider
from .sec_edgar_provider import SecEdgarProvider
from .taiwan_open_data_provider import TaiwanOpenDataProvider
from .types import FetchRequest


class ProviderRegistry:
    """Simple source/market registry used by the canonical fetch service."""

    def __init__(self, providers: Iterable[DataProvider] | None = None):
        self.providers = list(providers) if providers is not None else default_providers()

    def for_request(self, request: FetchRequest, source: str | None = None) -> list[DataProvider]:
        return [
            provider for provider in self.providers
            if provider.supports(request) and (source is None or provider.source == source)
        ]

    def provider_names(self, request: FetchRequest, source: str | None = None) -> list[str]:
        return [provider.name for provider in self.for_request(request, source=source)]

    def first_provider(self, request: FetchRequest, source: str) -> DataProvider | None:
        providers = [
            provider for provider in self.for_request(request, source=source)
            if getattr(provider, "primary_source_provider", True)
        ]
        return providers[0] if providers else None


def default_providers() -> list[DataProvider]:
    return [
        YFinanceProvider(),
        FinMindProvider(),
        FmpProvider(),
        FreeNewsWaterfallProvider(),
        AlternativeSearchProvider(),
        FmpNewsProvider(),
        EarningsCallProvider(),
        YahooProvider(),
        GlobalMarketContextProvider(),
        InternationalNewsContextProvider(),
        MacroIndicatorsProvider(),
        TaiwanOpenDataProvider(),
        ChipDataProvider(),
        AlternativeJobOpeningsProvider(),
        SocialSentimentProvider(),
        SecEdgarProvider(),
        AlternativePeerDiscoveryProvider(),
        TwseOfficialProvider(),
        MonthlyRevenueProvider(),
        InstitutionalTradingProvider(),
        DynamicPeerMetricsProvider(),
        PeRiverChartProvider(),
    ]
