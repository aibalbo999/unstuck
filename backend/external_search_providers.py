"""Alternative web/news search providers for optional enrichment."""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import math
import os
import re
from time import monotonic

from config import (
    BING_SEARCH_API_KEY,
    BING_SEARCH_ENDPOINT,
    BRAVE_SEARCH_API_KEY,
    CATALYST_LOOKBACK_DAYS,
    SEARCH_CATALYST_MAX_RESULTS,
    SEARCH_PEER_DISCOVERY_MAX_RESULTS,
    SERPAPI_API_KEY,
    TAVILY_API_KEY,
    WEB_SEARCH_PROVIDER_ORDER,
)
from external_http_client import async_client, log_http_warning
from external_search_provider_clients import fetch_provider_results
from external_search_quality import (
    provider_request_size as _provider_request_size,
    result_source_key as _result_source_key,
    search_quality_satisfied as _search_quality_satisfied,
    select_quality_results as _select_quality_results,
)
from external_search_types import SearchResult
from search_provider_runtime import fetch_search_upstream


# Bing Search APIs retired on 2025-08-11. Keep the implementation available
# only for explicit legacy opt-in, but do not include it in default routing.
DEFAULT_WEB_SEARCH_PROVIDER_ORDER = "tavily,serpapi,google_news_rss,gdelt,yahoo_rss,brave"
DEFAULT_WEB_SEARCH_TOTAL_TIMEOUT_SECONDS = 30.0


def _search_deadline(deadline: float | None = None) -> float:
    """Never let a nested query renew the parent's total search allowance."""
    try:
        seconds = float(os.getenv('WEB_SEARCH_TOTAL_TIMEOUT_SECONDS', '30'))
        if not math.isfinite(seconds):
            raise ValueError('non-finite search timeout')
    except (ValueError, TypeError):
        seconds = DEFAULT_WEB_SEARCH_TOTAL_TIMEOUT_SECONDS
    local_deadline = monotonic() + max(1.0, min(seconds, 60.0))
    if deadline is None:
        return local_deadline
    supplied = float(deadline)
    return min(local_deadline, supplied) if math.isfinite(supplied) else local_deadline


def _news_record(result: SearchResult) -> dict:
    return {"date":result.published_at, "title":result.title, "summary":result.snippet,
            "source":result.source, "link":result.link,
            "source_type":f"{result.provider or 'alternative'}_search"}


async def fetch_alternative_search_catalysts_async(
    ticker: str, company_name: str, identity: dict, *,
    max_results: int = SEARCH_CATALYST_MAX_RESULTS, diagnostics: dict | None = None,
    deadline: float | None = None,
) -> list[dict]:
    """Bounded company queries expand on eligible evidence shortage, not raw emptiness."""
    from source_content_selection import select_company_records
    started = monotonic()
    deadline = _search_deadline(deadline)
    official_name = str((identity or {}).get("official_name") or company_name or ticker).strip()
    data = {"ticker":ticker, "company_name":company_name, "company_identity":identity}
    queries = [f'{official_name} (法說會 OR 展望 OR 營收 OR earnings OR outlook OR revenue)',
               f'"{official_name}" {ticker.split(".")[0]}']
    raw, selected = [], []
    cutoff = datetime.now(timezone.utc)
    _, audit = select_company_records([], data, cutoff=cutoff, lookback_days=CATALYST_LOOKBACK_DAYS)
    for query in dict.fromkeys(queries):
        if monotonic() >= deadline:
            break
        observed = []
        results = await fetch_web_search_results_async(
            query, max_results=max_results, lookback_days=CATALYST_LOOKBACK_DAYS,
            require_recent=True, company_context=data, observed_records=observed, deadline=deadline,
        )
        raw.extend(_news_record(result) for result in (observed or results))
        selected, audit = select_company_records(raw, data, cutoff=cutoff, lookback_days=CATALYST_LOOKBACK_DAYS)
        candidates = [SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date']) for r in selected]
        if _search_quality_satisfied(candidates,max_results=max_results,query=official_name,
                                     require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff):
            break
    candidates = [SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date']) for r in selected]
    chosen = _select_quality_results(candidates,limit=max_results,query=official_name,
                                     require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff)
    links = {r.link for r in chosen}
    selected = [r for r in selected if r['link'] in links][:max_results]
    audit.update(usable_count=len(selected), quality_status='sufficient_candidates' if _search_quality_satisfied(
        chosen,max_results=max_results,query=official_name,require_recent=True,
        lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=cutoff) else 'insufficient_candidates')
    audit.update(search_budget_exhausted=monotonic() >= deadline,
                 search_duration_ms=max(0, int((monotonic() - started) * 1000)),
                 search_time_budget_seconds=max(0, deadline - started))
    if diagnostics is not None:
        diagnostics.update(audit)
    return selected


async def fetch_alternative_peer_discovery_async(
    ticker: str,
    company_name: str,
    sector: str,
    industry: str,
    *,
    max_results: int = SEARCH_PEER_DISCOVERY_MAX_RESULTS,
    deadline: float | None = None,
) -> list[dict]:
    """Fetch search snippets that help identify public peers/competitors."""
    deadline = _search_deadline(deadline)
    name = str(company_name or ticker).strip()
    # Short stages preserve the company anchor; sector is only a broad fallback.
    queries = [f"{name} competitors", f"{name} {str(industry or sector).strip()} peers"]
    results = []
    for query in dict.fromkeys(queries):
        if monotonic() >= deadline:
            break
        results = await fetch_web_search_results_async(query, max_results=max_results, deadline=deadline)
        if results:
            break
    return [
        {
            "title": result.title,
            "snippet": result.snippet,
            "source": result.source,
            "link": result.link,
            "source_type": "alternative_peer_discovery",
            "provider": result.provider or "alternative",
        }
        for result in results
    ]


async def fetch_web_search_results_async(
    query: str,
    *,
    max_results: int = SEARCH_CATALYST_MAX_RESULTS,
    lookback_days: int = 30,
    require_recent: bool = False,
    company_context: dict | None = None,
    observed_records: list | None = None,
    deadline: float | None = None,
) -> list[SearchResult]:
    """Run providers within one deadline, retaining evidence obtained before expiry."""
    deadline = _search_deadline(deadline)
    cleaned_query = str(query or "").strip()
    if not cleaned_query or monotonic() >= deadline:
        return []
    target_results = max(1, int(max_results))
    # Boolean syntax is not a relevance term ("OR" would match "reports").
    quality_query = re.sub(r"\bOR\b", " ", cleaned_query)

    cutoff = datetime.now(timezone.utc)
    results: list[SearchResult] = []
    async with async_client() as client:
        for provider in _provider_order():
            if monotonic() >= deadline:
                break
            selected = _select_quality_results(
                results,
                limit=target_results,
                query=quality_query,
                lookback_days=lookback_days,
                require_recent=require_recent, cutoff=cutoff, company_context=company_context,
            )
            if _search_quality_satisfied(
                selected,
                max_results=target_results,
                query=quality_query,
                lookback_days=lookback_days,
                require_recent=require_recent, cutoff=cutoff,
            ):
                break
            if not _provider_configured(provider):
                continue
            remaining = target_results - len(selected)
            request_size = _provider_request_size(remaining, max_results=target_results)
            remaining_seconds = deadline - monotonic()
            if remaining_seconds <= 0:
                break
            try:
                # Enforce the remaining *total* allowance in addition to the
                # endpoint callback's own cap. Caller cancellation propagates.
                async with asyncio.timeout(remaining_seconds):
                    fetched = await _fetch_provider_results(
                        client,
                        provider,
                        cleaned_query,
                        max_results=request_size,
                        lookback_days=lookback_days,
                    )
            except Exception as exc:
                log_http_warning("Alternative Search", provider, exc)
                continue
            results.extend(fetched)
            if observed_records is not None:
                observed_records.extend(fetched)

    return _select_quality_results(
        results,
        limit=target_results,
        query=quality_query,
        lookback_days=lookback_days,
        require_recent=require_recent, cutoff=cutoff, company_context=company_context,
    )


async def _fetch_provider_results(
    client,
    provider: str,
    query: str,
    *,
    max_results: int,
    lookback_days: int,
) -> list[SearchResult]:
    credential = {"brave": BRAVE_SEARCH_API_KEY, "bing": BING_SEARCH_API_KEY,
                  "tavily": TAVILY_API_KEY, "serpapi": SERPAPI_API_KEY}.get(provider, "")
    return await fetch_search_upstream(provider, credential or "", lambda: fetch_provider_results(
        client, provider, query, max_results=max_results, lookback_days=lookback_days,
    ))


def _provider_order() -> list[str]:
    raw = WEB_SEARCH_PROVIDER_ORDER or DEFAULT_WEB_SEARCH_PROVIDER_ORDER
    allowed = {"brave", "bing", "tavily", "serpapi", "gdelt", "google_news_rss", "yahoo_rss"}
    providers = []
    for item in str(raw).replace(";", ",").split(","):
        provider = item.strip().lower().replace("-", "_")
        if provider in allowed and provider not in providers:
            providers.append(provider)
    return providers or DEFAULT_WEB_SEARCH_PROVIDER_ORDER.split(",")


def _provider_configured(provider: str) -> bool:
    if provider in {"gdelt", "google_news_rss", "yahoo_rss"}:
        return True
    if provider == "brave":
        return bool(BRAVE_SEARCH_API_KEY)
    if provider == "bing":
        return bool(BING_SEARCH_API_KEY and BING_SEARCH_ENDPOINT)
    if provider == "tavily":
        return bool(TAVILY_API_KEY)
    if provider == "serpapi":
        return bool(SERPAPI_API_KEY)
    return False
