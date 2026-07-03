"""FMP optional HTTP source clients."""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import FMP_API_KEY, FMP_BASE_URL
from external_data_parsers import parse_fmp_news_payload, parse_fmp_quote_payload
from external_http_client import async_client, async_json_get, log_http_warning, sync_json_get


FMP_LEGACY_NEWS_URL = "https://financialmodelingprep.com/api/v3/stock_news"
DEFAULT_FMP_RESTRICTED_COOLDOWN_SECONDS = 6 * 60 * 60
FMP_RESTRICTED_STATUS_CODES = {401, 402, 403}
_sync_json_get = sync_json_get
_async_json_get = async_json_get
_fmp_endpoint_cooldowns: dict[str, float] = {}


def fetch_fmp_quote_fallback(ticker: str) -> dict:
    """Fetch optional FMP quote data when yfinance misses key market fields."""
    if not FMP_API_KEY:
        return {}
    if _endpoint_cooldown_active("quote"):
        return {}

    symbol = ticker.strip().upper()
    try:
        payload = _sync_json_get(f"{FMP_BASE_URL}/quote", {"symbol": symbol, "apikey": FMP_API_KEY})
        return parse_fmp_quote_payload(payload)
    except Exception as exc:
        log_http_warning("FMP", "quote fallback", exc)
        if _is_restricted_fmp_response(exc):
            _mark_endpoint_cooldown("quote")
        return {}


async def fetch_fmp_quote_fallback_async(ticker: str) -> dict:
    if not FMP_API_KEY:
        return {}
    if _endpoint_cooldown_active("quote"):
        return {}

    symbol = ticker.strip().upper()
    try:
        async with async_client("FMP") as client:
            payload = await _async_json_get(client, f"{FMP_BASE_URL}/quote", {"symbol": symbol, "apikey": FMP_API_KEY})
        return parse_fmp_quote_payload(payload)
    except Exception as exc:
        log_http_warning("FMP", "quote fallback async", exc)
        if _is_restricted_fmp_response(exc):
            _mark_endpoint_cooldown("quote")
        return {}


def _fmp_news_candidates(symbol: str) -> list[tuple[str, dict]]:
    return [
        (f"{FMP_BASE_URL}/news/stock", {"symbols": symbol, "limit": 5, "apikey": FMP_API_KEY}),
    ]


def fetch_fmp_news_catalysts(ticker: str) -> list[dict]:
    """Fetch optional FMP stock news when an API key is available."""
    if not FMP_API_KEY:
        return []
    if _endpoint_cooldown_active("news"):
        return []

    symbol = ticker.strip().upper()

    def fetch_endpoint(url: str, params: dict) -> list[dict]:
        try:
            payload = _sync_json_get(url, params)
        except Exception as exc:
            log_http_warning("FMP", f"news candidate {url}", exc)
            if _is_restricted_fmp_response(exc):
                _mark_endpoint_cooldown("news")
            return []
        return parse_fmp_news_payload(payload)

    candidates = _fmp_news_candidates(symbol)
    with ThreadPoolExecutor(max_workers=len(candidates)) as executor:
        futures = {executor.submit(fetch_endpoint, url, params): index for index, (url, params) in enumerate(candidates)}
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
    if _endpoint_cooldown_active("news"):
        return []

    symbol = ticker.strip().upper()
    candidates = _fmp_news_candidates(symbol)

    async def fetch_endpoint(client, url: str, params: dict) -> list[dict]:
        try:
            payload = await _async_json_get(client, url, params)
        except Exception as exc:
            log_http_warning("FMP", f"news async candidate {url}", exc)
            if _is_restricted_fmp_response(exc):
                _mark_endpoint_cooldown("news")
            return []
        return parse_fmp_news_payload(payload)

    async with async_client("FMP") as client:
        results = await asyncio.gather(
            *(fetch_endpoint(client, url, params) for url, params in candidates),
            return_exceptions=False,
        )

    for records in results:
        if records:
            return records
    return []


def _now() -> float:
    return time.time()


def _restricted_cooldown_seconds() -> float:
    try:
        configured = os.getenv("FMP_RESTRICTED_COOLDOWN_SECONDS", str(DEFAULT_FMP_RESTRICTED_COOLDOWN_SECONDS))
        return max(float(configured), 0.0)
    except ValueError:
        return float(DEFAULT_FMP_RESTRICTED_COOLDOWN_SECONDS)


def _endpoint_cooldown_active(endpoint: str) -> bool:
    return _now() < float(_fmp_endpoint_cooldowns.get(endpoint, 0.0) or 0.0)


def _mark_endpoint_cooldown(endpoint: str) -> None:
    cooldown_seconds = _restricted_cooldown_seconds()
    if cooldown_seconds <= 0:
        return
    _fmp_endpoint_cooldowns[endpoint] = max(
        float(_fmp_endpoint_cooldowns.get(endpoint, 0.0) or 0.0),
        _now() + cooldown_seconds,
    )


def clear_fmp_endpoint_cooldowns() -> None:
    _fmp_endpoint_cooldowns.clear()


def _is_restricted_fmp_response(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    try:
        return int(status_code) in FMP_RESTRICTED_STATUS_CODES
    except (TypeError, ValueError):
        return False
