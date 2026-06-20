"""HTTP/news/peer enrichment providers."""

from __future__ import annotations

from source_audit import audited_fetch, audited_fetch_async

from .market_sources.common import first_number
from .provider_base import DataProvider, not_configured_provider_result, provider_result_from_audited, unavailable_provider_result
from .types import FetchRequest, ProviderResult


class FreeNewsWaterfallProvider(DataProvider):
    name = "Free news waterfall"
    source = "recent_catalysts"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
        from external_data_client import ExternalDataClient

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str((context or {}).get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        company_name = str(data.get("company_name") or ticker).strip()
        query = f"{ticker} {company_name}".strip()
        client = ExternalDataClient()
        records = client.get_news(query, ticker=ticker, limit=5)
        status = AUDIT_STATUS_SUCCESS if records else AUDIT_STATUS_UNAVAILABLE
        return ProviderResult(
            source=self.source,
            provider=self.name,
            status=status,
            value=records,
            audit={
                "source": self.source,
                "provider": self.name,
                "status": status,
                "record_count": len(records),
                "cache_hit": bool(data.get("_cache_hit")),
                "stale": False,
                "message": "免費新聞 waterfall 已回傳近期催化劑。" if records else "免費新聞 waterfall 未回傳近期催化劑。",
                "related_entries": list(client.last_news_audit),
            },
        )


class GoogleSearchProvider(DataProvider):
    name = "Google Search"
    source = "recent_catalysts"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from config import GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY
        from .market_sources.http_enrichment import fetch_google_search_catalysts_async

        if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
            return not_configured_provider_result(
                self.source,
                self.name,
                "Google Custom Search 未設定，略過近期催化劑 enrichment。",
            )
        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        company_name = str(data.get("company_name") or ticker).strip()
        identity = data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {}
        cache_hit = bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_google_search_catalysts_async,
            (ticker, company_name, identity),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="Google Search 未回傳近期催化劑。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class YahooProvider(DataProvider):
    name = "Yahoo Finance"
    source = "recent_catalysts"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.http_enrichment import fetch_yfinance_news_catalysts

        context = context or {}
        stock = context.get("stock") or (context.get("market_snapshot") or {}).get("stock")
        if stock is None:
            return unavailable_provider_result(self.source, self.name, "Yahoo news provider 需要 yfinance stock 物件。")
        result = audited_fetch(
            self.source,
            "Yahoo Finance news",
            fetch_yfinance_news_catalysts,
            (stock,),
            default=[],
            unavailable_message="Yahoo Finance 未回傳近期新聞。",
        )
        return provider_result_from_audited(result, self.source, "Yahoo Finance news")


class FmpNewsProvider(DataProvider):
    name = "FMP news"
    source = "recent_catalysts"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from config import FMP_API_KEY
        from .market_sources.http_enrichment import fetch_fmp_news_catalysts_async

        if not FMP_API_KEY:
            return not_configured_provider_result(
                self.source,
                self.name,
                "FMP_API_KEY 未設定，略過 FMP news enrichment。",
            )
        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(context.get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        cache_hit = bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_fmp_news_catalysts_async,
            (ticker,),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="FMP news 未回傳近期新聞。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class EarningsCallProvider(DataProvider):
    name = "FMP earnings call transcript"
    source = "earnings_call"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from config import FMP_API_KEY
        from .earnings_call_fetcher import fetch_latest_earnings_call

        if not FMP_API_KEY:
            return not_configured_provider_result(self.source, self.name, "FMP_API_KEY 未設定，略過法說逐字稿。")
        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str((context or {}).get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        result = audited_fetch(
            self.source,
            self.name,
            fetch_latest_earnings_call,
            (ticker,),
            default={},
            unavailable_message="FMP 未回傳法說逐字稿。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class GlobalMarketContextProvider(DataProvider):
    name = "yfinance global context"
    source = "global_market_context"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.global_context import fetch_global_market_context

        context = context or {}
        data = context.get("data", {}) or {}
        cache_hit = bool(data.get("_cache_hit"))
        result = audited_fetch(
            self.source,
            self.name,
            fetch_global_market_context,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                str(data.get("company_name") or request.ticker),
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
            ),
            default={"lookback_days": 5, "items": [], "coverage_notes": ["全球市場脈絡暫無可用資料。"]},
            record_counter=lambda value: len(value.get("items", [])) if isinstance(value, dict) else 0,
            cache_hit=cache_hit,
            unavailable_message="yfinance global context 未回傳全球市場脈絡。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class InternationalNewsContextProvider(DataProvider):
    name = "GDELT / Google News RSS"
    source = "international_news_context"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_data_gdelt import fetch_gdelt_international_news_context

        context = context or {}
        data = context.get("data", {}) or {}
        cache_hit = bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_gdelt_international_news_context,
            (
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
            ),
            default={"lookback_days": 7, "topics": [], "coverage_notes": ["國際新聞脈絡暫無可用資料。"]},
            record_counter=lambda value: len(value.get("topics", [])) if isinstance(value, dict) else 0,
            cache_hit=cache_hit,
            unavailable_message="GDELT 未回傳國際新聞脈絡。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class GooglePeerDiscoveryProvider(DataProvider):
    name = "Google Search"
    source = "peer_discovery"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from config import GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY
        from .market_sources.http_enrichment import fetch_google_peer_discovery_results_async

        if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
            return not_configured_provider_result(
                self.source,
                self.name,
                "Google Custom Search 未設定，略過同業搜尋 enrichment。",
            )
        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        company_name = str(data.get("company_name") or ticker).strip()
        sector = str(data.get("sector") or "")
        industry = str(data.get("industry") or "")
        cache_hit = bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_google_peer_discovery_results_async,
            (ticker, company_name, sector, industry),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="Google Search 未回傳同業 discovery 結果。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class DynamicPeerMetricsProvider(DataProvider):
    name = "FinMind/yfinance"
    source = "dynamic_peer_metrics"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.peers import fetch_dynamic_peer_metrics

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        result = audited_fetch(
            self.source,
            self.name,
            fetch_dynamic_peer_metrics,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                str(data.get("company_name") or request.ticker),
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
                data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {},
            ),
            default=[],
            unavailable_message="同業指標暫無可用資料。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class PeRiverChartProvider(DataProvider):
    name = "FinMind/default multiples"
    source = "pe_river_chart"

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.valuation import build_pe_river_chart_data

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        value = data.get("shares_raw", data.get("shares_outstanding"))
        shares = first_number(value)
        result = audited_fetch(
            self.source,
            self.name,
            build_pe_river_chart_data,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                list(data.get("years") or []),
                list(data.get("net_income_history") or []),
                shares,
            ),
            default={"years": list(data.get("years") or []), "eps_twd": [], "multiples": [10, 12, 15, 18], "bands": {}, "source": "unavailable"},
            unavailable_message="P/E 河流圖資料暫無可用資料。",
        )
        return provider_result_from_audited(result, self.source, self.name)
