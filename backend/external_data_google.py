"""Google Custom Search optional source clients."""

from __future__ import annotations

import os
import time

from config import CATALYST_LOOKBACK_DAYS, GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY
from external_data_parsers import parse_google_catalyst_payload, parse_google_peer_payload
from external_http_client import async_client, async_json_get, log_http_warning, sync_json_get


GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
DEFAULT_GOOGLE_SEARCH_RESTRICTED_COOLDOWN_SECONDS = 6 * 60 * 60
GOOGLE_SEARCH_RESTRICTED_STATUS_CODES = {401, 402, 403}
_sync_json_get = sync_json_get
_async_json_get = async_json_get
_google_search_cooldown_until = 0.0


def fetch_google_search_catalysts(ticker: str, company_name: str, identity: dict) -> list[dict]:
    """Fetch catalyst-like headlines from Google Custom Search when configured."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
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
        return parse_google_catalyst_payload(payload)
    except Exception as exc:
        log_http_warning("Google Search", "recent catalysts", exc)
        if _is_restricted_google_search_response(exc):
            _mark_google_search_cooldown()
        return []


async def fetch_google_search_catalysts_async(ticker: str, company_name: str, identity: dict) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
        return []

    official_name = identity.get("official_name") or company_name or ticker
    query = f"{official_name} {ticker} 法說會 展望 供應鏈 營收 投資"
    try:
        async with async_client() as client:
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
        return parse_google_catalyst_payload(payload)
    except Exception as exc:
        log_http_warning("Google Search", "recent catalysts async", exc)
        if _is_restricted_google_search_response(exc):
            _mark_google_search_cooldown()
        return []


def fetch_google_peer_discovery_results(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    """Fetch search snippets that can help Agent 3 identify real global peers."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
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
        return parse_google_peer_payload(payload)
    except Exception as exc:
        log_http_warning("Google Search", "peer discovery", exc)
        if _is_restricted_google_search_response(exc):
            _mark_google_search_cooldown()
        return []


async def fetch_google_peer_discovery_results_async(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
        return []

    query = f"{company_name} {ticker} global competitors peers gross margin {industry} {sector}"
    try:
        async with async_client() as client:
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
        return parse_google_peer_payload(payload)
    except Exception as exc:
        log_http_warning("Google Search", "peer discovery async", exc)
        if _is_restricted_google_search_response(exc):
            _mark_google_search_cooldown()
        return []


def _now() -> float:
    return time.time()


def _restricted_cooldown_seconds() -> float:
    try:
        configured = os.getenv(
            "GOOGLE_SEARCH_RESTRICTED_COOLDOWN_SECONDS",
            str(DEFAULT_GOOGLE_SEARCH_RESTRICTED_COOLDOWN_SECONDS),
        )
        return max(float(configured), 0.0)
    except ValueError:
        return float(DEFAULT_GOOGLE_SEARCH_RESTRICTED_COOLDOWN_SECONDS)


def _google_search_cooldown_active() -> bool:
    return _now() < _google_search_cooldown_until


def _mark_google_search_cooldown() -> None:
    global _google_search_cooldown_until
    cooldown_seconds = _restricted_cooldown_seconds()
    if cooldown_seconds <= 0:
        return
    _google_search_cooldown_until = max(_google_search_cooldown_until, _now() + cooldown_seconds)


def clear_google_search_cooldown() -> None:
    global _google_search_cooldown_until
    _google_search_cooldown_until = 0.0


def _is_restricted_google_search_response(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    try:
        return int(status_code) in GOOGLE_SEARCH_RESTRICTED_STATUS_CODES
    except (TypeError, ValueError):
        return False
