"""Provider registry for market-data and enrichment sources."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Callable, Iterable

from data_trust import AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE
from source_audit import audited_fetch, audited_fetch_async

from .market_sources.common import first_number, is_missing_value
from .market_sources.identity import _stock_id_from_ticker, is_taiwan_ticker
from .types import FetchRequest, ProviderResult


class DataProvider:
    name = "provider"
    source = "unknown"
    markets = {"us", "tw"}
    execute_in_workflow = True
    primary_source_provider = True

    def supports(self, request: FetchRequest) -> bool:
        return infer_market(request.ticker) in self.markets

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:  # pragma: no cover - interface
        raise NotImplementedError

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        return await asyncio.to_thread(self.fetch, request, context)


class CallableProvider(DataProvider):
    def __init__(
        self,
        source: str,
        name: str,
        callback: Callable,
        markets: set[str] | None = None,
    ):
        self.source = source
        self.name = name
        self.callback = callback
        self.markets = markets or {"us", "tw"}

    def supports(self, request: FetchRequest) -> bool:
        market = infer_market(request.ticker)
        return market in self.markets

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        try:
            return self.callback(request, context)
        except TypeError:
            return self.callback(request)

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        result = self.fetch(request, context)
        if inspect.isawaitable(result):
            result = await result
        return result


class YFinanceProvider(DataProvider):
    name = "yfinance"
    source = "market_data"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .yfinance_snapshot import fetch_yfinance_snapshot

        started = time.time()
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_yfinance_snapshot,
            (request.ticker,),
            default={},
            record_counter=lambda value: len((value or {}).get("info") or {}),
            unavailable_if_empty=False,
            unavailable_message="yfinance 未回傳可用市場快照。",
        )
        provider_result = provider_result_from_audited(result, self.source, self.name)
        provider_result.duration_ms = max(0, int(round((time.time() - started) * 1000)))
        return provider_result


class FinMindProvider(DataProvider):
    name = "FinMind"
    source = "financial_statements"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.taiwan import fetch_finmind_financial_statement_fallback

        result = audited_fetch(
            self.source,
            "FinMind financial statement fallback",
            fetch_finmind_financial_statement_fallback,
            (request.ticker,),
            default={},
            unavailable_message="FinMind 財報備援未回傳可用年度資料。",
        )
        return provider_result_from_audited(result, self.source, "FinMind financial statement fallback")


class FmpProvider(DataProvider):
    name = "FMP stable quote"
    source = "market_data"
    primary_source_provider = False

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.http_enrichment import fetch_fmp_quote_fallback

        context = context or {}
        data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
        needs_quote = not data or any(
            is_missing_value(data.get(field))
            for field in ("current_price", "market_cap_raw", "pe_ratio_raw", "week_52_high", "week_52_low")
        )
        if not needs_quote:
            return unavailable_provider_result(self.source, self.name, "核心市場欄位已有資料，略過 FMP quote fallback。")

        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        result = audited_fetch(
            self.source,
            self.name,
            fetch_fmp_quote_fallback,
            (ticker,),
            default={},
            unavailable_message="FMP stable quote 未回傳可補值欄位。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class GoogleSearchProvider(DataProvider):
    name = "Google Search"
    source = "recent_catalysts"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.http_enrichment import fetch_google_search_catalysts_async

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
        from .market_sources.http_enrichment import fetch_fmp_news_catalysts_async

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


class GooglePeerDiscoveryProvider(DataProvider):
    name = "Google Search"
    source = "peer_discovery"

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.http_enrichment import fetch_google_peer_discovery_results_async

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


class MonthlyRevenueProvider(DataProvider):
    name = "FinMind TaiwanStockMonthRevenue"
    source = "monthly_revenue"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from datetime import datetime, timedelta
        from .market_sources.taiwan import DataLoader

        def fetch_records():
            if DataLoader is None:
                return []
            fm_dl = DataLoader()
            stock_id = _stock_id_from_ticker(request.ticker)
            start_date = (datetime.now() - timedelta(days=240)).strftime("%Y-%m-%d")
            df_rev = fm_dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date)
            records = []
            if df_rev is not None and not df_rev.empty:
                for _, row in df_rev.tail(6).iterrows():
                    year = row.get("revenue_year")
                    month = row.get("revenue_month")
                    value = row.get("revenue")
                    if year and month and value:
                        records.append(f"{year}年{month}月: NT${float(value) / 1e8:.2f}億")
            return records

        result = audited_fetch(
            self.source,
            self.name,
            fetch_records,
            default=[],
            unavailable_message="FinMind 月營收未回傳可用資料。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class InstitutionalTradingProvider(DataProvider):
    name = "FinMind"
    source = "institutional_trading"
    markets = {"tw"}

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from .market_sources.taiwan import fetch_institutional_trading_trend

        result = audited_fetch(
            self.source,
            self.name,
            fetch_institutional_trading_trend,
            (request.ticker,),
            default={},
            unavailable_message="法人籌碼資料暫無可用資料。",
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


def infer_market(ticker: str) -> str:
    return "tw" if is_taiwan_ticker(str(ticker or "")) else "us"


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
        GoogleSearchProvider(),
        FmpNewsProvider(),
        YahooProvider(),
        GooglePeerDiscoveryProvider(),
        MonthlyRevenueProvider(),
        InstitutionalTradingProvider(),
        DynamicPeerMetricsProvider(),
        PeRiverChartProvider(),
    ]


def provider_result_from_audited(result: dict, source: str, provider: str) -> ProviderResult:
    audit = result.get("audit", {}) if isinstance(result, dict) else {}
    return ProviderResult(
        source=str(audit.get("source") or source),
        provider=str(audit.get("provider") or provider),
        status=str(audit.get("status") or AUDIT_STATUS_UNAVAILABLE),
        value=result.get("value") if isinstance(result, dict) else None,
        audit=dict(audit),
        duration_ms=int(audit.get("duration_ms") or 0),
    )


def provider_result_from_payload(
    source: str,
    provider: str,
    payload: dict,
    *,
    started_at_epoch: float | None = None,
) -> ProviderResult:
    audit_entries = payload.get("source_audit", []) if isinstance(payload.get("source_audit"), list) else []
    matching = next(
        (
            entry for entry in audit_entries
            if isinstance(entry, dict)
            and entry.get("source") == source
            and (not provider or provider.lower() in str(entry.get("provider") or "").lower())
        ),
        None,
    )
    if matching is None:
        matching = next((entry for entry in audit_entries if isinstance(entry, dict) and entry.get("source") == source), None)
    status = str((matching or {}).get("status") or (AUDIT_STATUS_SUCCESS if payload and "error" not in payload else AUDIT_STATUS_UNAVAILABLE))
    duration_ms = int((matching or {}).get("duration_ms") or 0)
    if duration_ms <= 0 and started_at_epoch is not None:
        duration_ms = max(0, int(round((time.time() - started_at_epoch) * 1000)))
    return ProviderResult(
        source=source,
        provider=str((matching or {}).get("provider") or provider),
        status=status,
        value=payload,
        audit=dict(matching or {}),
        duration_ms=duration_ms,
        warnings=list(payload.get("data_source_notes", []) or []) if isinstance(payload, dict) else [],
    )


def unavailable_provider_result(source: str, provider: str, message: str = "") -> ProviderResult:
    return ProviderResult(
        source=source,
        provider=provider,
        status=AUDIT_STATUS_UNAVAILABLE,
        value=None,
        audit={
            "source": source,
            "provider": provider,
            "status": AUDIT_STATUS_UNAVAILABLE,
            "record_count": 0,
            "cache_hit": False,
            "stale": False,
            "message": message,
        },
    )
