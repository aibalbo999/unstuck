"""Alternative web/news search providers for optional enrichment."""

from __future__ import annotations

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


# Bing Search APIs retired on 2025-08-11. Keep the implementation available
# only for explicit legacy opt-in, but do not include it in default routing.
DEFAULT_WEB_SEARCH_PROVIDER_ORDER = "tavily,serpapi,google_news_rss,gdelt,yahoo_rss,brave"


async def fetch_alternative_search_catalysts_async(
    ticker: str,
    company_name: str,
    identity: dict,
    *,
    max_results: int = SEARCH_CATALYST_MAX_RESULTS,
) -> list[dict]:
    """Fetch recent catalyst-like search results from non-Google providers."""
    official_name = str((identity or {}).get("official_name") or company_name or ticker).strip()
    query = (
        f"{official_name} {ticker} 法說會 展望 供應鏈 營收 投資 "
        "earnings outlook revenue catalyst"
    ).strip()
    results = await fetch_web_search_results_async(
        query,
        max_results=max_results,
        lookback_days=CATALYST_LOOKBACK_DAYS,
    )
    if not results:
        broad_query = f"{official_name} {ticker}".strip()
        if broad_query and broad_query != query:
            results = await fetch_web_search_results_async(
                broad_query,
                max_results=max_results,
                lookback_days=CATALYST_LOOKBACK_DAYS,
            )
    return [
        {
            "date": result.published_at,
            "title": result.title,
            "summary": result.snippet,
            "source": result.source,
            "link": result.link,
            "source_type": f"{result.provider or 'alternative'}_search",
        }
        for result in results
    ]


async def fetch_alternative_peer_discovery_async(
    ticker: str,
    company_name: str,
    sector: str,
    industry: str,
    *,
    max_results: int = SEARCH_PEER_DISCOVERY_MAX_RESULTS,
) -> list[dict]:
    """Fetch search snippets that help identify public peers/competitors."""
    query = f"{company_name} {ticker} global competitors peers gross margin {industry} {sector}".strip()
    results = await fetch_web_search_results_async(query, max_results=max_results)
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
) -> list[SearchResult]:
    """Run configured alternative providers in order until enough records are found."""
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        return []
    target_results = max(1, int(max_results))

    results: list[SearchResult] = []
    async with async_client() as client:
        for provider in _provider_order():
            selected = _select_quality_results(
                results,
                limit=target_results,
                query=cleaned_query,
                lookback_days=lookback_days,
            )
            if _search_quality_satisfied(
                selected,
                max_results=target_results,
                query=cleaned_query,
                lookback_days=lookback_days,
            ):
                break
            if not _provider_configured(provider):
                continue
            remaining = target_results - len(selected)
            request_size = _provider_request_size(remaining, max_results=target_results)
            try:
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

    return _select_quality_results(
        results,
        limit=target_results,
        query=cleaned_query,
        lookback_days=lookback_days,
    )


async def _fetch_provider_results(
    client,
    provider: str,
    query: str,
    *,
    max_results: int,
    lookback_days: int,
) -> list[SearchResult]:
    return await fetch_provider_results(
        client,
        provider,
        query,
        max_results=max_results,
        lookback_days=lookback_days,
    )


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
