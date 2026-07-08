"""Market snapshot and quote fallback providers."""

from __future__ import annotations

import time

from source_audit import audited_fetch, audited_fetch_async

from .market_sources.common import is_missing_value
from .provider_base import DataProvider, provider_result_from_audited, unavailable_provider_result
from .types import FetchRequest, ProviderResult


class YFinanceProvider(DataProvider):
    name = "yfinance"
    source = "market_data"
    cost_tier = "free"
    capabilities = {"quote", "market_snapshot"}

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


class FmpProvider(DataProvider):
    name = "FMP stable quote"
    source = "market_data"
    markets = {"us"}
    primary_source_provider = False
    cost_tier = "free_with_key"
    capabilities = {"quote", "market_snapshot"}
    requires_env = ("FMP_API_KEY",)

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
