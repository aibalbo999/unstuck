"""Alternative web/news search providers for optional enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from config import (
    BING_SEARCH_API_KEY,
    BING_SEARCH_ENDPOINT,
    BRAVE_SEARCH_API_KEY,
    CATALYST_LOOKBACK_DAYS,
    SERPAPI_API_KEY,
    TAVILY_API_KEY,
    WEB_SEARCH_PROVIDER_ORDER,
)
from external_http_client import async_client, async_json_get, log_http_warning


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
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

DEFAULT_WEB_SEARCH_PROVIDER_ORDER = "google_news_rss,gdelt,yahoo_rss,brave,bing,tavily,serpapi"
_async_json_get = async_json_get


@dataclass(frozen=True)
class SearchResult:
    title: str
    snippet: str
    link: str
    source: str
    published_at: str = ""
    provider: str = ""


async def fetch_alternative_search_catalysts_async(
    ticker: str,
    company_name: str,
    identity: dict,
    *,
    max_results: int = 5,
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
    max_results: int = 5,
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
    max_results: int = 5,
    lookback_days: int = 30,
) -> list[SearchResult]:
    """Run configured alternative providers in order until enough records are found."""
    cleaned_query = str(query or "").strip()
    if not cleaned_query:
        return []

    results: list[SearchResult] = []
    async with async_client() as client:
        for provider in _provider_order():
            if len(results) >= max_results:
                break
            if not _provider_configured(provider):
                continue
            remaining = max(max_results - len(results), 1)
            try:
                fetched = await _fetch_provider_results(
                    client,
                    provider,
                    cleaned_query,
                    max_results=remaining,
                    lookback_days=lookback_days,
                )
            except Exception as exc:
                log_http_warning("Alternative Search", provider, exc)
                continue
            results.extend(fetched)

    return _dedupe_results(results, limit=max_results)


async def _fetch_provider_results(
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
        return await _fetch_gdelt_results(client, query, max_results=max_results, lookback_days=lookback_days)
    if provider == "google_news_rss":
        return await _fetch_google_news_rss_results(client, query, max_results=max_results)
    if provider == "yahoo_rss":
        return await _fetch_yahoo_rss_results(client, query, max_results=max_results)
    return []


async def _fetch_brave_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    payload = await _async_json_get(
        client,
        BRAVE_SEARCH_URL,
        {"q": query, "count": str(max(1, min(int(max_results), 20)))},
        headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_SEARCH_API_KEY},
    )
    return _parse_brave_payload(payload)


async def _fetch_bing_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    payload = await _async_json_get(
        client,
        BING_SEARCH_ENDPOINT,
        {"q": query, "count": str(max(1, min(int(max_results), 50))), "responseFilter": "Webpages"},
        headers={"Ocp-Apim-Subscription-Key": BING_SEARCH_API_KEY},
    )
    return _parse_bing_payload(payload)


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
    return _parse_tavily_payload(response.json())


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
    return _parse_serpapi_payload(payload)


async def _fetch_gdelt_results(
    client,
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
    return _parse_gdelt_payload(payload)


async def _fetch_yahoo_rss_results(client, query: str, *, max_results: int) -> list[SearchResult]:
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
    return _parse_news_rss_payload(response.text, provider="yahoo_rss", fallback_source="Yahoo RSS")[:max(1, int(max_results))]


async def _fetch_google_news_rss_results(client, query: str, *, max_results: int) -> list[SearchResult]:
    response = await client.get(
        GOOGLE_NEWS_RSS_URL,
        params={"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
    )
    response.raise_for_status()
    return _parse_news_rss_payload(response.text, provider="google_news_rss", fallback_source="Google News RSS")[
        :max(1, int(max_results))
    ]


def _parse_brave_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in ((payload.get("web") or {}).get("results") or []):
        if not isinstance(item, dict):
            continue
        records.append(_result_from_fields(
            item.get("title"),
            item.get("description"),
            item.get("url"),
            item.get("profile", {}).get("name") if isinstance(item.get("profile"), dict) else "",
            provider="brave",
        ))
    return [record for record in records if record.title]


def _parse_bing_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in ((payload.get("webPages") or {}).get("value") or []):
        if not isinstance(item, dict):
            continue
        records.append(_result_from_fields(
            item.get("name"),
            item.get("snippet"),
            item.get("url"),
            item.get("displayUrl"),
            provider="bing",
        ))
    return [record for record in records if record.title]


def _parse_tavily_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in payload.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        records.append(_result_from_fields(
            item.get("title"),
            item.get("content") or item.get("snippet"),
            item.get("url"),
            _domain(item.get("url")),
            published_at=item.get("published_date") or "",
            provider="tavily",
        ))
    return [record for record in records if record.title]


def _parse_serpapi_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in payload.get("organic_results", []) or []:
        if not isinstance(item, dict):
            continue
        records.append(_result_from_fields(
            item.get("title"),
            item.get("snippet"),
            item.get("link"),
            item.get("source") or item.get("displayed_link"),
            published_at=item.get("date") or "",
            provider="serpapi",
        ))
    return [record for record in records if record.title]


def _parse_gdelt_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in payload.get("articles", []) or []:
        if not isinstance(item, dict):
            continue
        records.append(_result_from_fields(
            item.get("title"),
            " · ".join(part for part in (item.get("domain"), item.get("sourcecountry")) if part),
            item.get("url"),
            item.get("domain") or "GDELT",
            published_at=item.get("seendate") or item.get("date") or "",
            provider="gdelt",
        ))
    return [record for record in records if record.title]


def _parse_news_rss_payload(payload: Any, *, provider: str, fallback_source: str) -> list[SearchResult]:
    text = str(payload or "").strip()
    if not text:
        return []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []

    records = []
    for item in root.findall(".//item"):
        title = str(item.findtext("title") or "").strip()
        link = str(item.findtext("link") or "").strip()
        source = str(item.findtext("source") or "").strip() or _domain(link) or fallback_source
        records.append(_result_from_fields(
            title,
            item.findtext("description") or "",
            link,
            source,
            published_at=item.findtext("pubDate") or "",
            provider=provider,
        ))
    return [record for record in records if record.title]


def _result_from_fields(
    title: Any,
    snippet: Any,
    link: Any,
    source: Any,
    *,
    published_at: Any = "",
    provider: str,
) -> SearchResult:
    clean_link = str(link or "").strip()
    return SearchResult(
        title=str(title or "").strip(),
        snippet=str(snippet or "").strip(),
        link=clean_link,
        source=str(source or "").strip() or _domain(clean_link) or provider,
        published_at=str(published_at or "").strip(),
        provider=provider,
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


def _dedupe_results(records: list[SearchResult], *, limit: int) -> list[SearchResult]:
    kept: list[SearchResult] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    for record in records:
        link = record.link.strip().lower()
        title = record.title.strip().lower()
        if link and link in seen_links:
            continue
        if title and title in seen_titles:
            continue
        if not link and not title:
            continue
        kept.append(record)
        if link:
            seen_links.add(link)
        if title:
            seen_titles.add(title)
        if len(kept) >= limit:
            break
    return kept


def _domain(url: Any) -> str:
    try:
        return urlparse(str(url or "")).netloc.replace("www.", "")
    except Exception:
        return ""
