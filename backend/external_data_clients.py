"""Compatibility facade for optional external market data HTTP clients."""

from __future__ import annotations

import asyncio

import external_data_fmp as _fmp
import external_search_providers as _search
from config import (
    FMP_API_KEY,
    FMP_BASE_URL,
)
from external_http_client import async_json_get, build_http_warning, log_http_warning, sync_json_get


FMP_LEGACY_NEWS_URL = _fmp.FMP_LEGACY_NEWS_URL
_sync_json_get = sync_json_get
_async_json_get = async_json_get


def _sync_source_seams() -> None:
    _fmp.FMP_API_KEY = FMP_API_KEY
    _fmp.FMP_BASE_URL = FMP_BASE_URL
    _fmp._sync_json_get = _sync_json_get
    _fmp._async_json_get = _async_json_get
    _fmp.log_http_warning = log_http_warning

    _search._async_json_get = _async_json_get


def fetch_fmp_quote_fallback(ticker: str) -> dict:
    _sync_source_seams()
    return _fmp.fetch_fmp_quote_fallback(ticker)


async def fetch_fmp_quote_fallback_async(ticker: str) -> dict:
    _sync_source_seams()
    return await _fmp.fetch_fmp_quote_fallback_async(ticker)


async def fetch_alternative_search_catalysts_async(ticker: str, company_name: str, identity: dict) -> list[dict]:
    _sync_source_seams()
    return await _search.fetch_alternative_search_catalysts_async(ticker, company_name, identity)


async def fetch_alternative_peer_discovery_async(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    _sync_source_seams()
    return await _search.fetch_alternative_peer_discovery_async(ticker, company_name, sector, industry)


def fetch_fmp_news_catalysts(ticker: str) -> list[dict]:
    _sync_source_seams()
    return _fmp.fetch_fmp_news_catalysts(ticker)


async def fetch_fmp_news_catalysts_async(ticker: str) -> list[dict]:
    _sync_source_seams()
    return await _fmp.fetch_fmp_news_catalysts_async(ticker)


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
        "search_catalysts": fetch_alternative_search_catalysts_async(ticker, company_name, identity),
        "fmp_news": fetch_fmp_news_catalysts_async(ticker),
        "search_peer_discovery": fetch_alternative_peer_discovery_async(ticker, company_name, sector, industry),
    }
    if include_quote:
        tasks["fmp_quote"] = fetch_fmp_quote_fallback_async(ticker)

    names = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    bundle = {}
    warnings = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            bundle[name] = {} if name == "fmp_quote" else []
            warnings.append(build_http_warning("optional_http_bundle", name, result))
        else:
            bundle[name] = result
    if warnings:
        bundle["_warnings"] = warnings
    return bundle
