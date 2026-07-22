"""Search-backed enrichment providers."""

from __future__ import annotations

from source_audit import audited_fetch_async

from .provider_base import DataProvider, provider_result_from_audited
from .types import FetchRequest, ProviderResult


class AlternativeSearchProvider(DataProvider):
    name = "Alternative Search"
    source = "recent_catalysts"
    cost_tier, capabilities = "free", {"search", "recent_catalysts"}

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_search_providers import fetch_alternative_search_catalysts_async

        context = context or {}
        data = context.get("data", {}) or {}
        ticker = str(data.get("ticker") or request.ticker).strip().upper()
        company_name = str(data.get("company_name") or ticker).strip()
        identity = data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {}
        cache_hit = bool(data.get("_cache_hit"))
        result = await audited_fetch_async(
            self.source,
            self.name,
            fetch_alternative_search_catalysts_async,
            (ticker, company_name, identity),
            default=[],
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="Alternative Search 未回傳近期催化劑。",
        )
        return provider_result_from_audited(result, self.source, self.name)


class AlternativePeerDiscoveryProvider(DataProvider):
    name = "Alternative Search"
    source = "peer_discovery"
    cost_tier, capabilities = "free", {"peer_discovery", "search"}

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        from external_search_providers import fetch_alternative_peer_discovery_async

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
            fetch_alternative_peer_discovery_async,
            (ticker, company_name, sector, industry),
            default=[],
            cache_hit=cache_hit,
            empty_status="degraded_enrichment",
            unavailable_message="Alternative Search 未回傳同業搜尋結果。",
        )
        return provider_result_from_audited(result, self.source, self.name)
