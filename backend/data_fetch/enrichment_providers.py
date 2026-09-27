"""HTTP/news/peer enrichment providers."""

from __future__ import annotations

from source_audit import audited_fetch, audited_fetch_async
from search_provider_runtime import SourceResponseError
from report_freshness_summary import safe_bool

from .earnings_call_fetcher import FREE_EARNINGS_CALL_PROVIDER_NAME, apply_earnings_call_audit, fetch_free_earnings_call_context
from .enrichment_search_providers import AlternativePeerDiscoveryProvider, AlternativeSearchProvider
from .market_sources.common import first_number
from .provider_base import DataProvider, not_configured_provider_result, provider_result_from_audited
from .types import FetchRequest, ProviderResult


class FreeNewsWaterfallProvider(DataProvider):
    name = "Free news waterfall"
    source = "recent_catalysts"
    cost_tier, capabilities = "free", {"news", "recent_catalysts"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from data_trust import AUDIT_STATUS_DEGRADED_ENRICHMENT, AUDIT_STATUS_SUCCESS
        from external_data_client import ExternalDataClient

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str((context or {}).get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        from company_news_queries import company_news_query
        from config import CATALYST_LOOKBACK_DAYS
        from news_freshness_policy import apply_news_freshness
        company_data = {**data, "ticker": ticker}
        query = company_news_query(company_data, lookback_days=CATALYST_LOOKBACK_DAYS)
        client = ExternalDataClient()
        # Search ranking may put old/unrelated hits first. Apply the unchanged
        # company/date gate to a bounded pool before spending the five slots.
        records = client.get_news(query, ticker=ticker, limit=20)
        from source_content_selection import select_company_records
        records, selection = select_company_records(records, company_data, lookback_days=CATALYST_LOOKBACK_DAYS)
        selected = apply_news_freshness(dict(company_data), records=records,
                                        lookback_days=CATALYST_LOOKBACK_DAYS, limit=5)
        records = selected["recent_catalysts"]
        # Capacity exclusions are eligible evidence, not company/date failures.
        selection["news_selection"] = selected["news_selection"]
        selection["additional_recent_catalysts"] = selected["additional_recent_catalysts"]
        status = AUDIT_STATUS_SUCCESS if records and not selection['rejected_count'] else AUDIT_STATUS_DEGRADED_ENRICHMENT
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
                "cache_hit": safe_bool(data.get("_cache_hit")),
                "stale": False,
                "message": "免費新聞 waterfall 已回傳近期催化劑。" if records else "未取得公司相符且在時間窗內的新聞；不代表沒有催化劑。",
                "related_entries": list(client.last_news_audit),
                **selection,
            },
        )


class YahooProvider(DataProvider):
    name = "Yahoo Finance"
    source = "recent_catalysts"
    cost_tier, capabilities = "free", {"news", "recent_catalysts"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.http_enrichment import fetch_yfinance_news_catalysts

        context = context or {}
        data = context.get("data") if isinstance(context.get("data"), dict) else {}
        from .market_sources.yahoo_taiwan_news import (
            TRANSPORT, PARSER_VERSION, regional_ticker, source_url,
            fetch_yahoo_taiwan_news, annotate_regional_result,
        )
        resolved = regional_ticker(request.ticker, data)
        if resolved:
            diagnostic = {"transport": TRANSPORT, "actual_provider": "Yahoo Taiwan",
                          "source_url": source_url(resolved), "parser_version": PARSER_VERSION,
                          "http_request_sent": False}
            result = audited_fetch(
                self.source, "Yahoo Finance news", fetch_yahoo_taiwan_news, (resolved,),
                {"diagnostics": diagnostic}, default=[], empty_status="degraded_enrichment",
                unavailable_message="Yahoo 台灣個股頁未回傳新聞；不代表沒有事件。",
            )
            return annotate_regional_result(
                provider_result_from_audited(result, self.source, self.name),
                {**data, "ticker": resolved}, diagnostic,
            )
        stock = context.get("stock") or (context.get("market_snapshot") or {}).get("stock")
        if stock is None:
            import yfinance as yf
            data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
            ticker = str(data.get("ticker") or request.ticker).strip().upper()
            stock = yf.Ticker(ticker)
        result = audited_fetch(
            self.source,
            "Yahoo Finance news",
            fetch_yfinance_news_catalysts,
            (stock,),
            default=[],
            empty_status="degraded_enrichment",
            unavailable_message="Yahoo Finance 未回傳近期新聞。",
        )
        from source_content_selection import annotate_result
        return annotate_result(provider_result_from_audited(result, self.source, self.name),
                               {**((context or {}).get("data") or {}), "ticker": request.ticker})


class FmpNewsProvider(DataProvider):
    name = "FMP news"
    source = "recent_catalysts"
    markets = {"us"}
    cost_tier, capabilities, requires_env = "free_with_key", {"news", "recent_catalysts"}, ("FMP_API_KEY",)

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
        cache_hit = safe_bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_fmp_news_catalysts_async,
            (ticker,),
            default=[],
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="FMP news 未回傳近期新聞。",
        )
        from source_content_selection import annotate_result
        return annotate_result(provider_result_from_audited(result, self.source, self.name),
                               {**((context or {}).get("data") or {}), "ticker": request.ticker})


class EarningsCallProvider(DataProvider):
    name = FREE_EARNINGS_CALL_PROVIDER_NAME
    source, markets = "earnings_call", {"tw"}
    cost_tier, capabilities = "free", {"earnings_call"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        ticker = str((context or {}).get("original_ticker") or data.get("ticker") or request.ticker).strip().upper()
        diagnostic = {}
        def fetch_context():
            try:
                return fetch_free_earnings_call_context(ticker, diagnostics=diagnostic)
            except SourceResponseError as exc:
                diagnostic.update(exc.diagnostic, status="error", message=str(exc))
                return {}

        result = audited_fetch(
            self.source,
            "MOPS / TWSE WebPro investor conference",
            fetch_context,
            default={},
            empty_status="degraded_enrichment",
            unavailable_message="免費法說會資料未回傳。",
        )
        apply_earnings_call_audit(result, diagnostic)
        return provider_result_from_audited(result, self.source, self.name)


class GlobalMarketContextProvider(DataProvider):
    name = "yfinance global context"
    source = "global_market_context"
    cost_tier, capabilities = "free", {"global_market_context"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.global_context import fetch_global_market_context

        context = context or {}
        data = context.get("data", {}) or {}
        cache_hit = safe_bool(data.get("_cache_hit"))
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
            empty_status="degraded_enrichment",
            unavailable_message="yfinance global context 未回傳全球市場脈絡。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class InternationalNewsContextProvider(DataProvider):
    name = "GDELT / Google News RSS"
    source = "international_news_context"
    cost_tier, capabilities = "free", {"international_news_context", "news"}

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_data_gdelt import fetch_gdelt_international_news_context

        context = context or {}
        data = context.get("data", {}) or {}
        cache_hit = safe_bool(data.get("_cache_hit"))
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
            empty_status="degraded_enrichment",
            unavailable_message="GDELT 未回傳國際新聞脈絡。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class DynamicPeerMetricsProvider(DataProvider):
    name = "FinMind/yfinance"
    source = "dynamic_peer_metrics"
    cost_tier, capabilities = "free", {"peer_metrics"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.peers import fetch_dynamic_peer_metrics_with_diagnostics

        data = (context or {}).get("data", {}) if isinstance((context or {}).get("data"), dict) else {}
        result = audited_fetch(
            self.source,
            self.name,
            fetch_dynamic_peer_metrics_with_diagnostics,
            (
                str(data.get("ticker") or request.ticker).strip().upper(),
                str(data.get("company_name") or request.ticker),
                str(data.get("sector") or ""),
                str(data.get("industry") or ""),
                data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {},
            ),
            default={"peers":[],"audit":{}},
            record_counter=lambda value: value.get("audit",{}).get("usable_count",0),
            empty_status="degraded_enrichment",
            unavailable_message="同業指標暫無可用資料。",
        )
        payload = result.get('value') or {}
        result['audit'].update(payload.get('audit') or {})
        result['value'] = payload.get('peers') or []
        if result['audit'].get('coverage_status') not in {'success', 'complete'} and result['audit'].get('status') == 'success':
            result['audit']['status'] = 'degraded_enrichment'
        return provider_result_from_audited(result, self.source, self.name)


class PeRiverChartProvider(DataProvider):
    name = "FinMind/default multiples"
    source = "pe_river_chart"
    cost_tier, capabilities = "free", {"valuation"}

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
