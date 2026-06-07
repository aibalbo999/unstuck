"""Google Custom Search optional source clients."""

from __future__ import annotations

from config import CATALYST_LOOKBACK_DAYS, GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY
from external_data_parsers import parse_google_catalyst_payload, parse_google_peer_payload
from external_http_client import async_client, async_json_get, log_http_warning, sync_json_get


GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
_sync_json_get = sync_json_get
_async_json_get = async_json_get


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
        return parse_google_catalyst_payload(payload)
    except Exception as exc:
        log_http_warning("Google Search", "recent catalysts", exc)
        return []


async def fetch_google_search_catalysts_async(ticker: str, company_name: str, identity: dict) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
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
        return parse_google_peer_payload(payload)
    except Exception as exc:
        log_http_warning("Google Search", "peer discovery", exc)
        return []


async def fetch_google_peer_discovery_results_async(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
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
        return []
