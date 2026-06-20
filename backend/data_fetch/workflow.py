"""Canonical provider-driven stock-data fetch workflow."""

from __future__ import annotations

import asyncio

from cache_store import get_cache_json
from data_trust import AUDIT_STATUS_SUCCESS, append_source_audit, finalize_data_trust, source_record_count
from source_audit import audited_fetch_async

from .audit_helpers import _mark_sources_fetched
from .core_provider_merge import merge_core_provider_result
from .enrichment_merge import _merge_optional_http_bundle
from .optional_provider_plan import collect_optional_providers
from .payload_cache import cache_financial_payload
from .provider_execution import fetch_provider_results, provider_value
from .provider_registry import ProviderRegistry
from .types import FetchRequest, ProviderResult
from . import workflow_cache as _workflow_cache
from .workflow_cache import fallback_cached_payload, fresh_cached_payload, schema_compatible_cached_payload
from .market_sources.http_enrichment import fetch_fmp_news_catalysts_async
from .yfinance_snapshot import fetch_stock_data_from_snapshot


async def fetch_payload_async(request: FetchRequest, registry: ProviderRegistry | None = None) -> dict:
    """Fetch core payload, then conditionally run optional providers."""
    ticker = request.ticker.strip().upper()
    registry = registry or ProviderRegistry()
    stale_cached = None
    if not request.options.force_refresh:
        _workflow_cache.get_cache_json = get_cache_json
        cached = schema_compatible_cached_payload(ticker)
        if cached:
            fresh_cached = fresh_cached_payload(ticker, cached)
            if fresh_cached:
                return fresh_cached
            stale_cached = cached

    core_result, core_audit_entries = await _fetch_core_provider_result(request, registry, ticker)
    if core_result is None:
        return {
            "ticker": ticker,
            "company_name": ticker,
            "error": "No market_data provider available",
        }

    data = await _assemble_core_payload_from_result(core_result, request)
    _append_core_provider_audits(data, core_audit_entries)
    if not data or "error" in data:
        fallback = fallback_cached_payload(ticker, stale_cached, core_result)
        if fallback:
            return fallback
        return data
    data = await _run_missing_core_provider_plan(request, registry, data)
    if request.options.skip_optional_http:
        return data

    return await _run_optional_provider_plan(request, registry, data)


async def _fetch_core_provider_result(
    request: FetchRequest,
    registry: ProviderRegistry,
    ticker: str,
) -> tuple[ProviderResult | None, list[dict]]:
    providers = registry.for_request(request, source="market_data")
    if not providers:
        return None, []

    primary = [provider for provider in providers if getattr(provider, "primary_source_provider", True)]
    fallback = [provider for provider in providers if provider not in primary]
    ordered_providers = primary + fallback
    audit_entries: list[dict] = []
    last_result: ProviderResult | None = None

    for provider in ordered_providers:
        result = await provider.fetch_async(request, {"original_ticker": ticker})
        last_result = result
        if result.audit:
            audit_entries.append(result.audit)
        if _core_provider_succeeded(result):
            return result, audit_entries

    return last_result, audit_entries


def _core_provider_succeeded(result: ProviderResult) -> bool:
    if result.status != AUDIT_STATUS_SUCCESS:
        return False
    if isinstance(result.value, dict) and result.value.get("error"):
        return False
    return bool(result.value)


def _append_core_provider_audits(data: dict, audit_entries: list[dict]) -> None:
    if not isinstance(data, dict) or not audit_entries:
        return
    existing = data.get("source_audit")
    if not isinstance(existing, list):
        data["source_audit"] = []
        existing = data["source_audit"]

    seen = {
        (
            str(entry.get("source") or ""),
            str(entry.get("provider") or ""),
            str(entry.get("status") or ""),
            str(entry.get("message") or ""),
        )
        for entry in existing
        if isinstance(entry, dict)
    }
    for entry in audit_entries:
        key = (
            str(entry.get("source") or ""),
            str(entry.get("provider") or ""),
            str(entry.get("status") or ""),
            str(entry.get("message") or ""),
        )
        if key in seen:
            continue
        append_source_audit(data, entry)
        seen.add(key)


async def _assemble_core_payload_from_result(core_result: ProviderResult, request: FetchRequest) -> dict:
    value = core_result.value if isinstance(core_result.value, dict) else {}
    if value.get("kind") == "yfinance_snapshot":
        return await asyncio.to_thread(fetch_stock_data_from_snapshot, value, True)
    return value


async def _run_optional_provider_plan(request: FetchRequest, registry: ProviderRegistry, data: dict) -> dict:
    ticker = request.ticker.strip().upper()
    resolved_ticker = str(data.get("ticker") or ticker).strip().upper()
    cache_hit = bool(data.get("_cache_hit"))
    providers, refresh_by_source = collect_optional_providers(request, registry, data, resolved_ticker)
    refresh_catalysts = refresh_by_source["recent_catalysts"]

    context = {"data": data, "original_ticker": ticker}
    provider_results = await fetch_provider_results(request, providers, context)
    fmp_news_records = provider_value(provider_results, "recent_catalysts", "FMP news")
    async_audit_entries = _audit_entries_from_provider_results(provider_results)

    if refresh_catalysts and resolved_ticker != ticker and not fmp_news_records:
        retry_result = await audited_fetch_async(
            "recent_catalysts",
            "FMP news retry",
            fetch_fmp_news_catalysts_async,
            (resolved_ticker,),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="FMP news retry 未回傳近期新聞。",
        )
        fmp_news_records = retry_result.get("value") if isinstance(retry_result.get("value"), list) else []
        if retry_result.get("audit"):
            async_audit_entries.append(retry_result["audit"])

    http_bundle = {
        "free_news": provider_value(provider_results, "recent_catalysts", "Free news waterfall"),
        "google_catalysts": provider_value(provider_results, "recent_catalysts", "Google Search"),
        "fmp_news": fmp_news_records,
        "yahoo_news": provider_value(provider_results, "recent_catalysts", "Yahoo Finance"),
        "global_market_context": _provider_context_value(provider_results, "global_market_context"),
        "international_news_context": _provider_context_value(provider_results, "international_news_context"),
        "macro_indicators": _provider_context_value(provider_results, "macro_indicators"),
        "chip_data": _provider_context_value(provider_results, "chip_data"),
        "alternative_data": _provider_context_value(provider_results, "alternative_data"),
        "google_peer_discovery": provider_value(provider_results, "peer_discovery", "Google Search"),
    }
    refreshed_sources = [source for source, should_refresh in refresh_by_source.items() if should_refresh]

    data = _merge_optional_http_bundle(
        data,
        http_bundle,
        refreshed_sources=refreshed_sources,
        source_errors={},
    )
    for audit_entry in async_audit_entries:
        append_source_audit(data, audit_entry)
    finalize_data_trust(data)
    cache_financial_payload(data, ticker)
    return data


def _provider_context_value(results: list[ProviderResult], source: str) -> dict:
    for result in results:
        if result.source == source and isinstance(result.value, dict):
            return result.value
    return {}


def _audit_entries_from_provider_results(results: list[ProviderResult]) -> list[dict]:
    entries: list[dict] = []
    for result in results:
        if not result.audit:
            continue
        entries.append(result.audit)
        related = result.audit.get("related_entries")
        if isinstance(related, list):
            entries.extend(entry for entry in related if isinstance(entry, dict))
    return entries


async def _run_missing_core_provider_plan(request: FetchRequest, registry: ProviderRegistry, data: dict) -> dict:
    core_sources = (
        "financial_statements",
        "twse_official",
        "monthly_revenue",
        "institutional_trading",
        "dynamic_peer_metrics",
        "pe_river_chart",
    )
    providers = []
    for source in core_sources:
        if source_record_count(source, data) > 0:
            continue
        providers.extend(
            provider for provider in registry.for_request(request, source=source)
            if getattr(provider, "execute_in_workflow", True)
        )
    if not providers:
        return data

    provider_results = await fetch_provider_results(request, providers, {"data": data, "original_ticker": request.ticker})
    refreshed_sources = []
    for result in provider_results:
        merge_core_provider_result(data, result)
        if result.audit:
            append_source_audit(data, result.audit)
        if result.status == "success":
            refreshed_sources.append(result.source)

    if refreshed_sources:
        _mark_sources_fetched(
            data,
            str(data.get("ticker") or request.ticker).strip().upper(),
            tuple(sorted(set(refreshed_sources))),
            cache_hit=bool(data.get("_cache_hit")),
        )
    finalize_data_trust(data)
    return data
