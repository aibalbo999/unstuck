"""HTTP client adapters for alternative search providers."""

from __future__ import annotations

import httpx

from config import (
    BING_SEARCH_API_KEY,
    BING_SEARCH_ENDPOINT,
    BRAVE_SEARCH_API_KEY,
    SERPAPI_API_KEY,
    TAVILY_API_KEY,
)
from external_http_client import async_json_get, log_http_warning
from external_search_payloads import (
    parse_bing_payload,
    parse_brave_payload,
    parse_gdelt_payload,
    parse_news_rss_payload,
    parse_serpapi_payload,
    parse_tavily_payload,
)
from external_search_types import SearchResult


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BING_SEARCH_URL = BING_SEARCH_ENDPOINT
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
YAHOO_NEWS_RSS_URL = "https://news.search.yahoo.com/rss"

# Free / public providers (GDELT, Yahoo RSS) are unreliable — use a shorter
# timeout so a ConnectTimeout fails fast and the next provider is tried sooner.
_FREE_PROVIDER_TIMEOUT_SECONDS = 5.0
# Yahoo RSS returns HTTP 500 when the query string is too long.
_YAHOO_RSS_MAX_QUERY_CHARS = 120
_async_json_get = async_json_get


async def fetch_provider_results(
    client,
    provider: str,
    query: str,
    *,
    max_results: int,
    lookback_days: int,
) -> list[SearchResult]:
    if provider == "brave":
        return await _fetch_brave_results(client, query, max_results=max_results)
    if provider == "bing":
        return await _fetch_bing_results(client, query, max_results=max_results)
    if provider == "tavily":
        return await _fetch_tavily_results(client, query, max_results=max_results)
    if provider == "serpapi":
        return await _fetch_serpapi_results(client, query, max_results=max_results)
    if provider == "gdelt":
        return await _fetch_gdelt_results(query, max_results=max_results, lookback_days=lookback_days)
    if provider == "google_news_rss":
        return await _fetch_google_news_rss_results(client, query, max_results=max_results)
    if provider == "yahoo_rss":
        return await _fetch_yahoo_rss_results(query, max_results=max_results)
    return []


async def _fetch_brave_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    payload = await _async_json_get(
        client,
        BRAVE_SEARCH_URL,
        {"q": query, "count": str(max(1, min(int(max_results), 20)))},
        headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_SEARCH_API_KEY},
    )
    return parse_brave_payload(payload)


async def _fetch_bing_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    payload = await _async_json_get(
        client,
        BING_SEARCH_URL,
        {"q": query, "count": str(max(1, min(int(max_results), 50))), "responseFilter": "Webpages"},
        headers={"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY},
    )
    return parse_bing_payload(payload)


async def _fetch_tavily_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    response = await client.post(
        TAVILY_SEARCH_URL,
        json={
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(int(max_results), 10)),
        },
        headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
    )
    response.raise_for_status()
    return parse_tavily_payload(response.json())


async def _fetch_serpapi_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    payload = await _async_json_get(
        client,
        SERPAPI_SEARCH_URL,
        {
            "engine": "google",
            "q": query,
            "num": str(max(1, min(int(max_results), 10))),
            "api_key": SERPAPI_API_KEY,
        },
    )
    return parse_serpapi_payload(payload)


async def _fetch_gdelt_results(
    query: str,
    *,
    max_results: int,
    lookback_days: int,
) -> list[SearchResult]:
    async with httpx.AsyncClient(timeout=_FREE_PROVIDER_TIMEOUT_SECONDS) as gdelt_client:
        payload = await _async_json_get(
            gdelt_client,
            GDELT_DOC_URL,
            {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": str(max(1, min(int(max_results), 50))),
                "timespan": f"{max(1, int(lookback_days))}d",
                "sort": "datedesc",
            },
        )
    return parse_gdelt_payload(payload)


async def _fetch_yahoo_rss_results(query: str, *, max_results: int) -> list[SearchResult]:
    # Truncate query to avoid HTTP 500 from Yahoo RSS on very long strings.
    truncated_query = query[:_YAHOO_RSS_MAX_QUERY_CHARS].strip()
    try:
        async with httpx.AsyncClient(timeout=_FREE_PROVIDER_TIMEOUT_SECONDS) as yahoo_client:
            response = await yahoo_client.get(YAHOO_NEWS_RSS_URL, params={"p": truncated_query})
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            # Yahoo RSS returns 500 on bad/long queries — treat as empty, not a crash.
            log_http_warning("Yahoo RSS", "news search (5xx — skipped)", exc)
            return []
        raise
    return parse_news_rss_payload(response.text, provider="yahoo_rss", fallback_source="Yahoo RSS")[:max(1, int(max_results))]


async def _fetch_google_news_rss_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    response = await client.get(
        GOOGLE_NEWS_RSS_URL,
        params={"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
    )
    response.raise_for_status()
    return parse_news_rss_payload(response.text, provider="google_news_rss", fallback_source="Google News RSS")[
        :max(1, int(max_results))
    ]
