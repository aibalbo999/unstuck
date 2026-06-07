"""Canonical provider-driven stock-data fetch workflow."""

from __future__ import annotations

import asyncio

from cache_store import get_cache_json
from data_freshness import assess_cached_financial_data, source_is_stale
from data_trust import append_source_audit, finalize_data_trust, source_record_count
from source_audit import audited_fetch_async

from .audit_helpers import (
    _append_cache_audit_entries,
    _append_skipped_fresh_cache_audit,
    _append_source_fetch_audit,
    _mark_sources_fetched,
)
from .constants import DATA_SCHEMA_VERSION
from .enrichment_merge import _merge_optional_http_bundle
from .payload_cache import cache_financial_payload
from .providers import ProviderRegistry
from .types import FetchRequest, ProviderResult
from .market_sources.http_enrichment import fetch_fmp_news_catalysts_async
from .yfinance_snapshot import fetch_stock_data_from_snapshot


async def fetch_payload_async(request: FetchRequest, registry: ProviderRegistry | None = None) -> dict:
    """Fetch core payload, then conditionally run optional providers."""
    ticker = request.ticker.strip().upper()
    registry = registry or ProviderRegistry()
    stale_cached = None
    if not request.options.force_refresh:
        cached = _schema_compatible_cached_payload(ticker)
        if cached:
            fresh_cached = _fresh_cached_payload(ticker, cached)
            if fresh_cached:
                return fresh_cached
            stale_cached = cached

    core_provider = registry.first_provider(request, "market_data")
    if core_provider is None:
        return {
            "ticker": ticker,
            "company_name": ticker,
            "error": "No market_data provider available",
        }

    core_result = await core_provider.fetch_async(request, {"original_ticker": ticker})
    data = await _assemble_core_payload_from_result(core_result, request)
    if not data or "error" in data:
        fallback = _fallback_cached_payload(ticker, stale_cached, core_result)
        if fallback:
            return fallback
        return data
    data = await _run_missing_core_provider_plan(request, registry, data)
    if request.options.skip_optional_http:
        return data

    return await _run_optional_provider_plan(request, registry, data)


async def _assemble_core_payload_from_result(core_result: ProviderResult, request: FetchRequest) -> dict:
    value = core_result.value if isinstance(core_result.value, dict) else {}
    if value.get("kind") == "yfinance_snapshot":
        return await asyncio.to_thread(fetch_stock_data_from_snapshot, value, True)
    return value


async def _run_optional_provider_plan(request: FetchRequest, registry: ProviderRegistry, data: dict) -> dict:
    ticker = request.ticker.strip().upper()
    resolved_ticker = str(data.get("ticker") or ticker).strip().upper()
    cache_hit = bool(data.get("_cache_hit"))
    refresh_catalysts = (not cache_hit) or source_is_stale(data, "recent_catalysts", resolved_ticker)
    refresh_peer_discovery = (not cache_hit) or source_is_stale(data, "peer_discovery", resolved_ticker)

    providers = []
    if refresh_catalysts:
        providers.extend(
            provider for provider in registry.for_request(request, source="recent_catalysts")
            if getattr(provider, "execute_in_workflow", True)
        )
    else:
        _append_skipped_fresh_cache_audit(data, ("recent_catalysts",))

    if refresh_peer_discovery:
        providers.extend(
            provider for provider in registry.for_request(request, source="peer_discovery")
            if getattr(provider, "execute_in_workflow", True)
        )
    else:
        _append_skipped_fresh_cache_audit(data, ("peer_discovery",))

    context = {"data": data, "original_ticker": ticker}
    provider_results = await _fetch_provider_results(request, providers, context)
    fmp_news_records = _provider_value(provider_results, "recent_catalysts", "FMP news")
    async_audit_entries = [result.audit for result in provider_results if result.audit]

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
        "google_catalysts": _provider_value(provider_results, "recent_catalysts", "Google Search"),
        "fmp_news": fmp_news_records,
        "google_peer_discovery": _provider_value(provider_results, "peer_discovery", "Google Search"),
    }
    refreshed_sources = []
    if refresh_catalysts:
        refreshed_sources.append("recent_catalysts")
    if refresh_peer_discovery:
        refreshed_sources.append("peer_discovery")

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


async def _run_missing_core_provider_plan(request: FetchRequest, registry: ProviderRegistry, data: dict) -> dict:
    core_sources = (
        "financial_statements",
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

    provider_results = await _fetch_provider_results(request, providers, {"data": data, "original_ticker": request.ticker})
    refreshed_sources = []
    for result in provider_results:
        _merge_core_provider_result(data, result)
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


def _merge_core_provider_result(data: dict, result: ProviderResult) -> None:
    value = result.value
    if result.source == "financial_statements" and isinstance(value, dict) and value:
        for key in (
            "years",
            "revenue_history",
            "net_income_history",
            "gross_profit_history",
            "operating_income_history",
            "fcf_history",
            "total_assets_history",
            "total_equity_history",
        ):
            if not data.get(key) and value.get(key):
                data[key] = value.get(key)
    elif result.source == "monthly_revenue" and isinstance(value, list):
        if not data.get("recent_monthly_revenue"):
            data["recent_monthly_revenue"] = value
    elif result.source == "institutional_trading" and isinstance(value, dict):
        if not data.get("institutional_trading"):
            data["institutional_trading"] = value
    elif result.source == "dynamic_peer_metrics" and isinstance(value, list):
        if not data.get("dynamic_peer_metrics"):
            data["dynamic_peer_metrics"] = value
    elif result.source == "pe_river_chart" and isinstance(value, dict):
        if not data.get("pe_river_chart") or data.get("pe_river_chart", {}).get("source") == "unavailable":
            data["pe_river_chart"] = value


def _schema_compatible_cached_payload(ticker: str) -> dict | None:
    cache_key = f"financial_data:{ticker}"
    cached = get_cache_json(cache_key)
    if not cached or cached.get("data_schema_version") != DATA_SCHEMA_VERSION:
        return None
    return cached


def _fresh_cached_payload(ticker: str, cached: dict) -> dict | None:

    cache_ticker = str(cached.get("ticker") or ticker).strip().upper()
    is_fresh, freshness = assess_cached_financial_data(cached, cache_ticker)
    if not is_fresh:
        return None

    cached = dict(cached)
    cached["_cache_hit"] = True
    cached["source_audit"] = []
    cached["data_freshness"] = freshness
    cached["source_freshness"] = freshness.get("source_freshness", {})
    _append_cache_audit_entries(cached, cache_ticker)
    return cached


def _fallback_cached_payload(ticker: str, cached: dict | None, core_result: ProviderResult) -> dict | None:
    if not cached:
        return None

    cache_ticker = str(cached.get("ticker") or ticker).strip().upper()
    _is_fresh, freshness = assess_cached_financial_data(cached, cache_ticker)
    fallback = dict(cached)
    fallback["_cache_hit"] = True
    fallback["source_audit"] = []
    fallback["data_freshness"] = freshness
    fallback["source_freshness"] = freshness.get("source_freshness", {})
    notes = list(fallback.get("data_source_notes", []) or [])
    notes.append("核心資料重新抓取失敗，本次使用既有快取作為 fallback；請查看來源審計。")
    fallback["data_source_notes"] = notes
    _append_cache_audit_entries(fallback, cache_ticker)
    if core_result.audit:
        append_source_audit(fallback, core_result.audit)
    else:
        _append_source_fetch_audit(
            fallback,
            core_result.source or "market_data",
            core_result.provider or "provider",
            core_result.status or "error",
            record_count=0,
            cache_hit=False,
            stale=True,
            message="核心 provider 重新抓取失敗，使用舊快取 fallback。",
        )
    finalize_data_trust(fallback)
    return fallback


async def _fetch_provider_results(
    request: FetchRequest,
    providers: list,
    context: dict,
) -> list[ProviderResult]:
    if not providers:
        return []
    gathered = await asyncio.gather(
        *(provider.fetch_async(request, context) for provider in providers),
        return_exceptions=True,
    )
    results = []
    for provider, result in zip(providers, gathered):
        if isinstance(result, Exception):
            results.append(
                ProviderResult(
                    source=getattr(provider, "source", "unknown"),
                    provider=getattr(provider, "name", provider.__class__.__name__),
                    status="error",
                    value=None,
                    audit={
                        "source": getattr(provider, "source", "unknown"),
                        "provider": getattr(provider, "name", provider.__class__.__name__),
                        "status": "error",
                        "record_count": 0,
                        "cache_hit": bool((context.get("data") or {}).get("_cache_hit")),
                        "stale": False,
                        "error_kind": result.__class__.__name__,
                        "message": str(result)[:240],
                    },
                )
            )
            continue
        results.append(result)
    return results


def _provider_value(results: list[ProviderResult], source: str, provider_name: str) -> list:
    for result in results:
        if result.source != source:
            continue
        if provider_name.lower() not in str(result.provider or "").lower():
            continue
        return result.value if isinstance(result.value, list) else []
    return []
