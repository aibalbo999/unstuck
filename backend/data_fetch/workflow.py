"""Canonical provider-driven stock-data fetch workflow."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from time import monotonic

from cache_store import get_cache_json
from data_trust import AUDIT_STATUS_SUCCESS, append_source_audit, finalize_data_trust, source_record_count
from report_freshness_summary import safe_bool
from source_applicability import source_is_applicable
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
from .market_sources.identity import is_taiwan_ticker
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
                if not request.options.skip_optional_http:
                    # Core-cache freshness does not establish optional coverage.
                    # The normal planner selects only applicable missing/stale
                    # sources and keeps each provider's cache/backoff in force.
                    return await _run_optional_provider_plan(request, registry, fresh_cached)
                return fresh_cached
            from .cached_institutional_recovery import recover_cached_institutional
            recovery = await recover_cached_institutional(request, registry, cached)
            if recovery is not None:
                data, replaced = recovery
                if replaced:
                    cache_financial_payload(data, ticker)
                if not request.options.skip_optional_http:
                    return await _run_optional_provider_plan(request, registry, data)
                return data
            stale_cached = cached

    core_result, core_audit_entries = await _fetch_core_provider_result(request, registry, ticker)
    if core_result is None:
        return {
            "ticker": ticker,
            "company_name": ticker,
            "error": "No market_data provider available",
        }

    regional_yahoo_planned = (
        not request.options.skip_optional_http
        and any(provider.name == "Yahoo Finance" for provider in registry.for_request(request, source="recent_catalysts"))
    )
    data = await _assemble_core_payload_from_result(
        core_result, request, defer_taiwan_yahoo_news=regional_yahoo_planned,
    )
    data["_cache_hit"] = safe_bool(data.get("_cache_hit"))
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
    if isinstance(result.value, dict) and result.value.get("kind") == "yfinance_snapshot":
        return safe_bool(result.value.get("is_valid"))
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


async def _assemble_core_payload_from_result(
    core_result: ProviderResult, request: FetchRequest, *, defer_taiwan_yahoo_news: bool = False,
) -> dict:
    value = core_result.value if isinstance(core_result.value, dict) else {}
    if value.get("kind") == "yfinance_snapshot":
        return await asyncio.to_thread(
            fetch_stock_data_from_snapshot,
            value,
            True,
            request.options.force_refresh,
            defer_taiwan_yahoo_news,
            request.options.radar_refresh,
        )
    return value


async def _run_optional_provider_plan(request: FetchRequest, registry: ProviderRegistry, data: dict, *, sources=None) -> dict:
    ticker = request.ticker.strip().upper()
    resolved_ticker = str(data.get("ticker") or ticker).strip().upper()
    cache_hit = safe_bool(data.get("_cache_hit"))
    providers, refresh_by_source = collect_optional_providers(request, registry, data, resolved_ticker, sources=sources)
    if cache_hit and not providers:
        return data
    refresh_catalysts = refresh_by_source.get("recent_catalysts", False)

    context = {"data": data, "original_ticker": ticker}
    # Taiwan's regional Yahoo endpoint is a useful fallback, but the other
    # news feeds often already supply enough distinct, dated articles. Finish
    # those concurrent requests first and only spend a Yahoo request for a
    # real remaining evidence gap. Other markets retain the existing plan.
    yahoo_fallback = [provider for provider in providers
                      if is_taiwan_ticker(resolved_ticker)
                      and provider.source == "recent_catalysts" and provider.name == "Yahoo Finance"]
    peer_publishers = [provider for provider in providers
                       if provider.source == "peer_discovery" and provider.name in {
                           "Yahoo Taiwan published industry ranking", "MoneyDJ published food-biotech cohort",
                           "MoneyDJ/TWSE published medical cohort"}]
    peer_search = [provider for provider in providers
                   if provider.source == "peer_discovery" and provider.name == "Alternative Search"]
    segment_fallback = [provider for provider in providers
                        if provider.source == "peer_discovery" and provider.name == "TPEx official segment discovery"]
    catalyst_search = [provider for provider in providers
                       if is_taiwan_ticker(resolved_ticker) and provider.source == "recent_catalysts"
                       and provider.name == "Alternative Search"]
    trading_notices = [provider for provider in providers
                       if provider.source == "recent_catalysts" and provider.name == "TWSE official trading notices"]
    if catalyst_search:
        from external_search_providers import _search_deadline
        catalyst_deadline = _search_deadline()
    primary_providers = [provider for provider in providers
                         if provider not in yahoo_fallback and provider not in peer_publishers
                         and provider not in peer_search and provider not in segment_fallback
                         and provider not in catalyst_search and provider not in trading_notices]
    primary_results, published_results = await asyncio.gather(
        fetch_provider_results(request, primary_providers, context) if primary_providers else asyncio.sleep(0, result=[]),
        fetch_provider_results(request, peer_publishers, context) if peer_publishers else asyncio.sleep(0, result=[]),
    )
    provider_results = primary_results + published_results
    if segment_fallback:
        if _sufficient_published_peer_candidates(published_results, resolved_ticker):
            provider_results.append(ProviderResult(
                "peer_discovery", "TPEx official segment discovery", "not_applicable", value=[],
                audit={"source": "peer_discovery", "provider": "TPEx official segment discovery",
                       "status": "not_applicable", "event_kind": "local_block", "http_request_sent": False,
                       "cache_hit": False, "stale": False, "record_count": 0,
                       "reason_code": "published_peer_candidates_sufficient",
                       "message": "skip: 既有已核對的同業候選足夠，未另抓官方細分產業鏈。"}))
        else:
            segment_results = await fetch_provider_results(request, segment_fallback, context)
            published_results.extend(segment_results)
            provider_results.extend(segment_results)
    if catalyst_search or yahoo_fallback or trading_notices:
        from .catalyst_search_plan import current_catalyst_evidence
        decision = current_catalyst_evidence(data, primary_results)
    if trading_notices:
        if decision["sufficient"]:
            provider_results.append(ProviderResult(
                "recent_catalysts", "TWSE official trading notices", "not_applicable", value=[],
                audit={"source":"recent_catalysts", "provider":"TWSE official trading notices",
                       "status":"not_applicable", "event_kind":"local_block", "http_request_sent":False,
                       "cache_hit":False, "stale":False, "record_count":0,
                       "reason_code":"current_catalyst_evidence_sufficient", "existing_evidence":decision,
                       "message":"skip: 既有完整催化劑證據已達原筆數與來源門檻。"}))
        else:
            provider_results.extend(await fetch_provider_results(request,trading_notices,context))
    if catalyst_search:
        expired = monotonic() >= catalyst_deadline
        if decision["sufficient"] or expired:
            reason = "current_catalyst_evidence_sufficient" if decision["sufficient"] else "catalyst_search_deadline_exhausted"
            # A deliberate local skip is neither a HTTP success nor a cache hit.
            provider_results.append(ProviderResult(
                "recent_catalysts", "Alternative Search", "not_applicable" if decision["sufficient"] else "unavailable",
                value=[], audit={"source":"recent_catalysts", "provider":"Alternative Search",
                    "status":"not_applicable" if decision["sufficient"] else "unavailable",
                    "event_kind":"local_block", "http_request_sent":False, "cache_hit":False, "stale":False,
                    "record_count":0, "reason_code":reason, "existing_evidence":decision,
                    "message":"skip: 現有合格資料已達原搜尋筆數及來源門檻。" if decision["sufficient"]
                              else "skip: 補充搜尋的原總期限已用盡，未另行延長。"}))
        else:
            provider_results.extend(await fetch_provider_results(
                request, catalyst_search, {**context, "catalyst_search_deadline":catalyst_deadline}))
    # A current, independently checked publisher cohort already supplies
    # discovery candidates. Use the broader search only as a fallback; it has
    # repeatedly returned no verified relationship for broad-classified 5314.
    if peer_search and not _sufficient_published_peer_candidates(published_results, resolved_ticker):
        provider_results.extend(await fetch_provider_results(request, peer_search, context))
    if yahoo_fallback:
        if decision["sufficient"]:
            provider_results.append(ProviderResult(
                "recent_catalysts", "Yahoo Finance", "not_applicable", value=[],
                audit={"source":"recent_catalysts", "provider":"Yahoo Finance news", "status":"not_applicable",
                    "event_kind":"local_block", "http_request_sent":False, "cache_hit":False, "stale":False,
                    "record_count":0, "reason_code":"current_catalyst_evidence_sufficient",
                    "existing_evidence":decision, "message":"skip: 現有合格資料已達原搜尋筆數及來源門檻。"}))
        elif not _sufficient_non_yahoo_catalysts(provider_results):
            provider_results.extend(await fetch_provider_results(request, yahoo_fallback, context))
    fmp_news_records = provider_value(provider_results, "recent_catalysts", "FMP news")
    async_audit_entries = _audit_entries_from_provider_results(provider_results)

    if refresh_catalysts and resolved_ticker != ticker and not is_taiwan_ticker(resolved_ticker) and not fmp_news_records:
        from config import FMP_API_KEY
        if FMP_API_KEY:
            retry_result = await audited_fetch_async(
                "recent_catalysts",
                "FMP news retry",
                fetch_fmp_news_catalysts_async,
                (resolved_ticker,),
                default=[],
                cache_hit=cache_hit,
                empty_status="degraded_enrichment",
                unavailable_message="FMP news retry 未回傳近期新聞。",
            )
            fmp_news_records = retry_result.get("value") if isinstance(retry_result.get("value"), list) else []
            if retry_result.get("audit"):
                async_audit_entries.append(retry_result["audit"])

    http_bundle = {
        "free_news": provider_value(provider_results, "recent_catalysts", "Free news waterfall"),
        "official_company_history": provider_value(provider_results, "recent_catalysts", "TWSE company announcement history"),
        "tpex_company_history": provider_value(provider_results, "recent_catalysts", "TPEx MOPS company announcement history"),
        "issuer_news": provider_value(provider_results, "recent_catalysts", "Verified issuer news"),
        "official_trading_notices": provider_value(provider_results, "recent_catalysts", "TWSE official trading notices"),
        "search_catalysts": provider_value(provider_results, "recent_catalysts", "Alternative Search"),
        "fmp_news": fmp_news_records,
        "yahoo_news": provider_value(provider_results, "recent_catalysts", "Yahoo Finance"),
        "global_market_context": _provider_context_value(provider_results, "global_market_context"),
        "international_news_context": _provider_context_value(provider_results, "international_news_context"),
        "macro_indicators": _provider_context_value(provider_results, "macro_indicators"),
        "chip_data": _provider_context_value(provider_results, "chip_data"),
        "alternative_data": _provider_context_value(provider_results, "alternative_data"),
        "annual_workforce": _provider_context_value(provider_results, "annual_workforce"),
        "social_sentiment": _provider_context_value(provider_results, "social_sentiment"),
        "sec_edgar": _provider_context_value(provider_results, "sec_edgar"),
        "taiwan_open_data": _provider_context_value(provider_results, "taiwan_open_data"),
        "official_disclosures": _provider_context_value(provider_results, "official_disclosures"),
        "earnings_call": _provider_context_value(provider_results, "earnings_call"),
        "search_peer_discovery": provider_value(provider_results, "peer_discovery", "Alternative Search"),
        "publisher_peer_discovery": provider_value(provider_results, "peer_discovery", "Yahoo Taiwan published industry ranking"),
        "moneydj_peer_discovery": provider_value(provider_results, "peer_discovery", "MoneyDJ published food-biotech cohort"),
        "medical_peer_discovery": provider_value(provider_results, "peer_discovery", "MoneyDJ/TWSE published medical cohort"),
        "official_segment_peer_discovery": provider_value(provider_results, "peer_discovery", "TPEx official segment discovery"),
    }
    refreshed_sources = [source for source, should_refresh in refresh_by_source.items() if should_refresh]

    for audit_entry in async_audit_entries:
        append_source_audit(data, audit_entry)
    data = _merge_optional_http_bundle(
        data,
        http_bundle,
        refreshed_sources=refreshed_sources,
        source_errors={},
    )
    finalize_data_trust(data)
    cache_financial_payload(data, ticker)
    return data


def _sufficient_non_yahoo_catalysts(results: list[ProviderResult]) -> bool:
    """Require two curated feeds, five distinct recent URLs and two publishers."""
    from config import CATALYST_LOOKBACK_DAYS
    from news_freshness_policy import news_cutoff, publication_datetime, publisher_identity
    from news_record_utils import canonical_link

    selected = {}
    for result in results:
        if result.source != "recent_catalysts" or result.provider not in {
                "Free news waterfall", "Alternative Search"}:
            continue
        selected[result.provider] = result
    if set(selected) != {"Free news waterfall", "Alternative Search"}:
        return False
    now = news_cutoff()
    cutoff = now - timedelta(days=CATALYST_LOOKBACK_DAYS)
    links, publishers = set(), set()
    for result in selected.values():
        audit = result.audit if isinstance(result.audit, dict) else {}
        curated_partial = (
            result.provider == "Free news waterfall"
            and result.status == "degraded_enrichment"
            and audit.get("quality_status") == "eligible_evidence"
        ) or (
            result.provider == "Alternative Search"
            and result.status == "degraded_enrichment"
            and audit.get("quality_status") == "insufficient_candidates"
            and isinstance(result.value, list)
            and audit.get("usable_count") == len(result.value)
        )
        if (result.status != AUDIT_STATUS_SUCCESS and not curated_partial) or not isinstance(result.value, list):
            return False
        valid = set()
        for record in result.value:
            if not isinstance(record, dict) or not str(record.get("title") or "").strip():
                continue
            when = publication_datetime(record)
            link = canonical_link(record.get("link") or record.get("url"))
            publisher = publisher_identity(record)[1]
            if link and publisher and when is not None and cutoff <= when <= now:
                valid.add(link)
                links.add(link)
                publishers.add(publisher)
        if len(valid) < 3:
            return False
    return len(links) >= 5 and len(publishers) >= 2


def _sufficient_published_peer_candidates(results: list[ProviderResult], ticker: str) -> bool:
    """Two distinct, current publisher candidates can satisfy discovery."""
    from .market_sources.moneydj_peer_cohort import is_moneydj_peer_record
    from .market_sources.moneydj_medical_peer_cohort import is_medical_peer_record,medical_record_hint
    from .market_sources.yahoo_peer_ranking import is_published_peer_record
    from .market_sources.official_segment_discovery import is_segment_discovery_record, segment_record_hint

    candidates = set()
    for result in results:
        if result.source != "peer_discovery" or result.status not in {"success", "skipped_fresh_cache"}:
            continue
        if not isinstance(result.value, list):
            continue
        for record in result.value:
            valid=(is_segment_discovery_record(record,ticker) if segment_record_hint(record) else
                   is_medical_peer_record(record,ticker) if medical_record_hint(record) else
                   is_moneydj_peer_record(record,ticker) or is_published_peer_record(record,ticker))
            if not valid:
                continue
            candidates.add(record["counterparty"]["ticker"])
    return len(candidates) >= 2


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
    from provider_correlation import current_correlation
    from .institutional_provider import institutional_acquired_in_fetch
    institutional_acquired = institutional_acquired_in_fetch(data, current_correlation().get("fetch_id"))
    core_sources = (
        "financial_statements",
        "twse_official",
        "monthly_revenue",
        "institutional_trading",
        "dynamic_peer_metrics",
        "pe_river_chart",
    )
    providers = []
    current_fetch_id = current_correlation().get("fetch_id")
    for source in core_sources:
        if source == "institutional_trading" and institutional_acquired:
            continue
        if not source_is_applicable(source, data, request.ticker):
            continue
        if source_record_count(source, data) > 0:
            continue
        if source == "dynamic_peer_metrics" and current_fetch_id and any(
            isinstance(entry, dict)
            and entry.get("source") == source
            and entry.get("provider") == "FinMind/yfinance"
            and entry.get("fetch_id") == current_fetch_id
            and entry.get("operation_id")
            and isinstance(entry.get("provider_attempts"), list)
            and any(isinstance(attempt, dict)
                    and attempt.get("source") == source
                    and attempt.get("provider") == "FinMind/yfinance"
                    for attempt in entry["provider_attempts"])
            for entry in (data.get("source_audit") or [])
        ):
            # The yfinance core has just run the same peer collector. Its
            # empty result remains visible; an immediate identical retry adds
            # requests but no new evidence. A later fetch may retry normally.
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
        for entry in _audit_entries_from_provider_results([result]):
            append_source_audit(data, entry)
        if result.status == "success":
            refreshed_sources.append(result.source)

    if refreshed_sources:
        _mark_sources_fetched(
            data,
            str(data.get("ticker") or request.ticker).strip().upper(),
            tuple(sorted(set(refreshed_sources))),
            cache_hit=safe_bool(data.get("_cache_hit")),
        )
    from .institutional_provider import apply_institutional_freshness
    from .market_sources.official_monthly_revenue import apply_monthly_freshness
    for result in provider_results:
        if result.source == "institutional_trading":
            apply_institutional_freshness(data, request.ticker, result.audit)
        elif result.source == "monthly_revenue":
            apply_monthly_freshness(data, request.ticker, result.audit)
    finalize_data_trust(data)
    return data
