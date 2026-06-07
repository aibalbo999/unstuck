"""HTTP-backed optional enrichment wrappers."""

from __future__ import annotations

from external_data_clients import (
    fetch_fmp_news_catalysts as fetch_fmp_news_catalysts_http,
    fetch_fmp_news_catalysts_async,
    fetch_fmp_quote_fallback as fetch_fmp_quote_fallback_http,
    fetch_google_peer_discovery_results as fetch_google_peer_discovery_results_http,
    fetch_google_peer_discovery_results_async,
    fetch_google_search_catalysts as fetch_google_search_catalysts_http,
    fetch_google_search_catalysts_async,
)

from .common import _dedupe_records, _run_named_fetches
from .taiwan import fetch_finmind_news_catalysts


def fetch_fmp_quote_fallback(ticker: str) -> dict:
    return fetch_fmp_quote_fallback_http(ticker)


def fetch_google_search_catalysts(ticker: str, company_name: str, identity: dict) -> list[dict]:
    return fetch_google_search_catalysts_http(ticker, company_name, identity)


def fetch_google_peer_discovery_results(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    return fetch_google_peer_discovery_results_http(ticker, company_name, sector, industry)


def fetch_fmp_news_catalysts(ticker: str) -> list[dict]:
    return fetch_fmp_news_catalysts_http(ticker)


def fetch_yfinance_news_catalysts(stock) -> list[dict]:
    try:
        news = getattr(stock, "news", []) or []
    except Exception:
        return []
    records = []
    for item in news[:10]:
        content = item.get("content", item) if isinstance(item, dict) else {}
        if not isinstance(content, dict):
            continue
        title = str(content.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "date": content.get("pubDate") or content.get("displayTime") or "",
            "title": title,
            "summary": str(content.get("summary") or content.get("description") or "")[:280],
            "source": content.get("provider", {}).get("displayName") if isinstance(content.get("provider"), dict) else "Yahoo Finance",
            "link": content.get("clickThroughUrl", {}).get("url") if isinstance(content.get("clickThroughUrl"), dict) else "",
            "source_type": "yfinance_news",
        })
    return records


def fetch_recent_catalysts(
    ticker: str,
    company_name: str,
    identity: dict,
    stock,
    skip_optional_http: bool = False,
) -> list[dict]:
    records = []
    fetches = {
        "finmind": (fetch_finmind_news_catalysts, (ticker,), [], "FinMind 新聞資料獲取失敗"),
        "yfinance": (fetch_yfinance_news_catalysts, (stock,), [], "Yahoo Finance 新聞資料獲取失敗"),
    }
    if not skip_optional_http:
        fetches.update({
            "google": (fetch_google_search_catalysts, (ticker, company_name, identity), [], "Google Search 催化劑資料獲取失敗"),
            "fmp": (fetch_fmp_news_catalysts, (ticker,), [], "FMP 新聞資料獲取失敗"),
        })
    for items in _run_named_fetches(fetches, max_workers=4).values():
        records.extend(items or [])
    return _dedupe_records(records, limit=5)[:5]
