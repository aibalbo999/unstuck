"""HTTP clients for optional external market data sources."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from config import (
    CATALYST_LOOKBACK_DAYS,
    FMP_API_KEY,
    FMP_BASE_URL,
    GOOGLE_CSE_ID,
    GOOGLE_SEARCH_API_KEY,
)


HTTP_TIMEOUT_SECONDS = 8.0
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
FMP_LEGACY_NEWS_URL = "https://financialmodelingprep.com/api/v3/stock_news"


def _sync_json_get(url: str, params: dict[str, Any]) -> Any:
    response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


async def _async_json_get(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> Any:
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def _dedupe_records(records: list[dict], key: str = "title", limit: int = 6) -> list[dict]:
    kept = []
    seen = set()
    for record in records:
        marker = str(record.get(key) or record.get("link") or "").strip().lower()
        if not marker or marker in seen:
            continue
        kept.append(record)
        seen.add(marker)
        if len(kept) >= limit:
            break
    return kept


def _parse_fmp_quote_payload(payload: Any) -> dict:
    if isinstance(payload, list) and payload:
        return payload[0] if isinstance(payload[0], dict) else {}
    return payload if isinstance(payload, dict) else {}


def _parse_google_catalyst_payload(payload: Any) -> list[dict]:
    records = []
    if not isinstance(payload, dict):
        return records

    for item in payload.get("items", []) or []:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        metatags = item.get("pagemap", {}).get("metatags", [{}]) or [{}]
        records.append({
            "date": metatags[0].get("article:published_time", ""),
            "title": title,
            "summary": str(item.get("snippet", "")).strip(),
            "source": item.get("displayLink", "Google Search"),
            "link": item.get("link", ""),
            "source_type": "google_search",
        })
    return records


def _parse_google_peer_payload(payload: Any) -> list[dict]:
    records = []
    if not isinstance(payload, dict):
        return records

    for item in payload.get("items", []) or []:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "title": title,
            "snippet": str(item.get("snippet", "")).strip(),
            "source": item.get("displayLink", "Google Search"),
            "link": item.get("link", ""),
            "source_type": "google_peer_discovery",
        })
    return _dedupe_records(records, limit=5)


def _parse_fmp_news_payload(payload: Any) -> list[dict]:
    if not isinstance(payload, list):
        return []

    records = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        records.append({
            "date": item.get("publishedDate") or item.get("date") or "",
            "title": str(item.get("title", "")).strip(),
            "summary": str(item.get("text") or item.get("summary") or "")[:280],
            "source": item.get("site") or "FMP",
            "link": item.get("url") or "",
            "source_type": "fmp_news",
        })
    return records


def fetch_fmp_quote_fallback(ticker: str) -> dict:
    """Fetch optional FMP quote data when yfinance misses key market fields."""
    if not FMP_API_KEY:
        return {}

    symbol = ticker.strip().upper()
    try:
        payload = _sync_json_get(
            f"{FMP_BASE_URL}/quote",
            {"symbol": symbol, "apikey": FMP_API_KEY},
        )
        return _parse_fmp_quote_payload(payload)
    except Exception as e:
        print(f"    ⚠️  FMP 備援資料獲取失敗：{e}")
        return {}


async def fetch_fmp_quote_fallback_async(ticker: str) -> dict:
    if not FMP_API_KEY:
        return {}

    symbol = ticker.strip().upper()
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            payload = await _async_json_get(
                client,
                f"{FMP_BASE_URL}/quote",
                {"symbol": symbol, "apikey": FMP_API_KEY},
            )
        return _parse_fmp_quote_payload(payload)
    except Exception:
        return {}


def fetch_google_search_catalysts(ticker: str, company_name: str, identity: dict) -> list[dict]:
    """Fetch catalyst-like headlines from Google Custom Search when configured."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []

    official_name = identity.get("official_name") or company_name or ticker
    query = f"{official_name} {ticker} 法說會 展望 供應鏈 營收 投資"
    try:
        payload = _sync_json_get(
            GOOGLE_SEARCH_URL,
            {
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": query,
                "num": 5,
                "dateRestrict": f"d{CATALYST_LOOKBACK_DAYS}",
                "lr": "lang_zh-TW",
            },
        )
        return _parse_google_catalyst_payload(payload)
    except Exception as e:
        print(f"    ⚠️  Google Search 催化劑資料獲取失敗：{e}")
        return []


async def fetch_google_search_catalysts_async(ticker: str, company_name: str, identity: dict) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []

    official_name = identity.get("official_name") or company_name or ticker
    query = f"{official_name} {ticker} 法說會 展望 供應鏈 營收 投資"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            payload = await _async_json_get(
                client,
                GOOGLE_SEARCH_URL,
                {
                    "key": GOOGLE_SEARCH_API_KEY,
                    "cx": GOOGLE_CSE_ID,
                    "q": query,
                    "num": 5,
                    "dateRestrict": f"d{CATALYST_LOOKBACK_DAYS}",
                    "lr": "lang_zh-TW",
                },
            )
        return _parse_google_catalyst_payload(payload)
    except Exception:
        return []


def fetch_google_peer_discovery_results(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    """Fetch search snippets that can help Agent 3 identify real global peers."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []

    query = f"{company_name} {ticker} global competitors peers gross margin {industry} {sector}"
    try:
        payload = _sync_json_get(
            GOOGLE_SEARCH_URL,
            {
                "key": GOOGLE_SEARCH_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": query,
                "num": 5,
            },
        )
        return _parse_google_peer_payload(payload)
    except Exception as e:
        print(f"    ⚠️  Google Search 同業 discovery 失敗：{e}")
        return []


async def fetch_google_peer_discovery_results_async(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []

    query = f"{company_name} {ticker} global competitors peers gross margin {industry} {sector}"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            payload = await _async_json_get(
                client,
                GOOGLE_SEARCH_URL,
                {
                    "key": GOOGLE_SEARCH_API_KEY,
                    "cx": GOOGLE_CSE_ID,
                    "q": query,
                    "num": 5,
                },
            )
        return _parse_google_peer_payload(payload)
    except Exception:
        return []


def _fmp_news_candidates(symbol: str) -> list[tuple[str, dict]]:
    return [
        (FMP_LEGACY_NEWS_URL, {"tickers": symbol, "limit": 5, "apikey": FMP_API_KEY}),
        (f"{FMP_BASE_URL}/stock_news", {"tickers": symbol, "limit": 5, "apikey": FMP_API_KEY}),
    ]


def fetch_fmp_news_catalysts(ticker: str) -> list[dict]:
    """Fetch optional FMP stock news when an API key is available."""
    if not FMP_API_KEY:
        return []

    symbol = ticker.strip().upper()

    def fetch_endpoint(url: str, params: dict) -> list[dict]:
        try:
            payload = _sync_json_get(url, params)
        except Exception:
            return []
        return _parse_fmp_news_payload(payload)

    candidates = _fmp_news_candidates(symbol)
    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        futures = {
            executor.submit(fetch_endpoint, url, params): index
            for index, (url, params) in enumerate(candidates)
        }
        ordered_results = {}
        for future in as_completed(futures):
            ordered_results[futures[future]] = future.result()

    for index in range(len(candidates)):
        records = ordered_results.get(index) or []
        if records:
            return records
    return []


async def fetch_fmp_news_catalysts_async(ticker: str) -> list[dict]:
    if not FMP_API_KEY:
        return []

    symbol = ticker.strip().upper()
    candidates = _fmp_news_candidates(symbol)

    async def fetch_endpoint(client: httpx.AsyncClient, url: str, params: dict) -> list[dict]:
        try:
            payload = await _async_json_get(client, url, params)
        except Exception:
            return []
        return _parse_fmp_news_payload(payload)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        results = await asyncio.gather(
            *(fetch_endpoint(client, url, params) for url, params in candidates),
            return_exceptions=False,
        )

    for records in results:
        if records:
            return records
    return []


async def fetch_optional_http_data_bundle(
    ticker: str,
    company_name: str,
    identity: dict,
    sector: str = "",
    industry: str = "",
    include_quote: bool = False,
) -> dict:
    """
    Fetch all optional HTTP-backed sources concurrently.

    SDK-backed sources such as yfinance and FinMind stay outside this bundle.
    """
    tasks = {
        "google_catalysts": fetch_google_search_catalysts_async(ticker, company_name, identity),
        "fmp_news": fetch_fmp_news_catalysts_async(ticker),
        "google_peer_discovery": fetch_google_peer_discovery_results_async(ticker, company_name, sector, industry),
    }
    if include_quote:
        tasks["fmp_quote"] = fetch_fmp_quote_fallback_async(ticker)

    names = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    bundle = {}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            bundle[name] = {} if name == "fmp_quote" else []
        else:
            bundle[name] = result
    return bundle
