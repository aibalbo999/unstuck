"""Optional HTTP-backed enrichment workflow."""

from __future__ import annotations

import asyncio

from data_trust import append_source_audit, finalize_data_trust
from .market_sources.http_enrichment import (
    fetch_fmp_news_catalysts_async,
    fetch_google_peer_discovery_results_async,
    fetch_google_search_catalysts_async,
)
from source_audit import audited_fetch_async

from .audit_helpers import _append_skipped_fresh_cache_audit, _source_is_stale
from .enrichment_merge import _merge_optional_http_bundle
from .payload_cache import cache_financial_payload


async def enrich_optional_http_async(ticker: str, data: dict) -> dict:
    """Merge Google/FMP optional enrichments into a core stock payload."""
    if not data or "error" in data:
        return data

    resolved_ticker = str(data.get("ticker") or ticker).strip().upper()
    company_name = str(data.get("company_name") or resolved_ticker).strip()
    identity = data.get("company_identity") if isinstance(data.get("company_identity"), dict) else {}
    sector = str(data.get("sector") or "")
    industry = str(data.get("industry") or "")

    cache_hit = bool(data.get("_cache_hit"))
    refresh_catalysts = (not cache_hit) or _source_is_stale(data, "recent_catalysts", resolved_ticker)
    refresh_peer_discovery = (not cache_hit) or _source_is_stale(data, "peer_discovery", resolved_ticker)

    tasks = {}
    if refresh_catalysts:
        tasks["google_catalysts"] = audited_fetch_async(
            "recent_catalysts",
            "Google Search",
            fetch_google_search_catalysts_async,
            (resolved_ticker, company_name, identity),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="Google Search 未回傳近期催化劑。",
        )
        tasks["fmp_news"] = audited_fetch_async(
            "recent_catalysts",
            "FMP news",
            fetch_fmp_news_catalysts_async,
            (ticker,),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="FMP news 未回傳近期新聞。",
        )
    if refresh_peer_discovery:
        tasks["google_peer_discovery"] = audited_fetch_async(
            "peer_discovery",
            "Google Search",
            fetch_google_peer_discovery_results_async,
            (resolved_ticker, company_name, sector, industry),
            default=[],
            cache_hit=cache_hit,
            unavailable_message="Google Search 未回傳同業 discovery 結果。",
        )

    results = {}
    if tasks:
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results = dict(zip(tasks.keys(), gathered))

    async_audit_entries = [
        result.get("audit") for result in results.values()
        if isinstance(result, dict) and result.get("audit")
    ]
    google_catalysts_records = (
        results.get("google_catalysts", {}).get("value", [])
        if isinstance(results.get("google_catalysts"), dict) else []
    )
    fmp_news_records = (
        results.get("fmp_news", {}).get("value", [])
        if isinstance(results.get("fmp_news"), dict) else []
    )
    google_peer_discovery_records = (
        results.get("google_peer_discovery", {}).get("value", [])
        if isinstance(results.get("google_peer_discovery"), dict) else []
    )
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
        "google_catalysts": google_catalysts_records,
        "google_peer_discovery": google_peer_discovery_records,
        "fmp_news": fmp_news_records,
    }

    refreshed_sources = []
    if refresh_catalysts:
        refreshed_sources.append("recent_catalysts")
    else:
        _append_skipped_fresh_cache_audit(data, ("recent_catalysts",))
    if refresh_peer_discovery:
        refreshed_sources.append("peer_discovery")
    else:
        _append_skipped_fresh_cache_audit(data, ("peer_discovery",))

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
