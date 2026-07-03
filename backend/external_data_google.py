"""Google Custom Search optional source clients."""

from __future__ import annotations

import os
import time

from config import CATALYST_LOOKBACK_DAYS, GOOGLE_CSE_ID, GOOGLE_SEARCH_API_KEY, GOOGLE_SEARCH_REFERER
from external_data_parsers import parse_google_catalyst_payload, parse_google_peer_payload
from external_http_client import async_client, async_json_get, log_http_warning, sync_json_get
from runtime_events import emit_log


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
    try:
        for params in _google_catalyst_param_sets(official_name, ticker):
            payload = _sync_google_search_json_get(params)
            records = parse_google_catalyst_payload(payload)
            if records:
                return records
    except Exception as exc:
        log_http_warning("Google Search", "recent catalysts", exc)
        if _is_restricted_google_search_response(exc):
            _log_google_search_setup_hint(exc)
            _mark_google_search_cooldown()
    return []


async def fetch_google_search_catalysts_async(ticker: str, company_name: str, identity: dict) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
        return []

    official_name = identity.get("official_name") or company_name or ticker
    try:
        async with async_client() as client:
            for params in _google_catalyst_param_sets(official_name, ticker):
                payload = await _async_google_search_json_get(client, params)
                records = parse_google_catalyst_payload(payload)
                if records:
                    return records
    except Exception as exc:
        log_http_warning("Google Search", "recent catalysts async", exc)
        if _is_restricted_google_search_response(exc):
            _log_google_search_setup_hint(exc)
            _mark_google_search_cooldown()
    return []


def fetch_google_peer_discovery_results(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    """Fetch search snippets that can help Agent 3 identify real global peers."""
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
        return []

    try:
        for params in _google_peer_param_sets(ticker, company_name, sector, industry):
            payload = _sync_google_search_json_get(params)
            records = parse_google_peer_payload(payload)
            if records:
                return records
    except Exception as exc:
        log_http_warning("Google Search", "peer discovery", exc)
        if _is_restricted_google_search_response(exc):
            _log_google_search_setup_hint(exc)
            _mark_google_search_cooldown()
    return []


async def fetch_google_peer_discovery_results_async(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_CSE_ID:
        return []
    if _google_search_cooldown_active():
        return []

    try:
        async with async_client() as client:
            for params in _google_peer_param_sets(ticker, company_name, sector, industry):
                payload = await _async_google_search_json_get(client, params)
                records = parse_google_peer_payload(payload)
                if records:
                    return records
    except Exception as exc:
        log_http_warning("Google Search", "peer discovery async", exc)
        if _is_restricted_google_search_response(exc):
            _log_google_search_setup_hint(exc)
            _mark_google_search_cooldown()
    return []


def _google_catalyst_param_sets(official_name: str, ticker: str) -> list[dict]:
    base = {"key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_CSE_ID, "num": 5, "dateRestrict": f"d{CATALYST_LOOKBACK_DAYS}"}
    primary = f"{official_name} {ticker} 法說會 展望 供應鏈 營收 投資".strip()
    broad = f"{official_name} {ticker}".strip()
    params = [{**base, "q": primary, "lr": "lang_zh-TW"}]
    if broad and broad != primary:
        params.append({**base, "q": broad})
    return params


def _google_peer_param_sets(ticker: str, company_name: str, sector: str, industry: str) -> list[dict]:
    base = {"key": GOOGLE_SEARCH_API_KEY, "cx": GOOGLE_CSE_ID, "num": 5}
    primary = f"{company_name} {ticker} global competitors peers gross margin {industry} {sector}".strip()
    broad = f"{company_name} {ticker} competitors peers {industry or sector}".strip()
    params = [{**base, "q": primary}]
    if broad and broad != primary:
        params.append({**base, "q": broad})
    return params


def _google_search_headers() -> dict[str, str]:
    referer = (GOOGLE_SEARCH_REFERER or "").strip()
    return {"Referer": referer} if referer else {}


def _sync_google_search_json_get(params: dict) -> dict:
    headers = _google_search_headers()
    if headers:
        return _sync_json_get(GOOGLE_SEARCH_URL, params, headers=headers)
    return _sync_json_get(GOOGLE_SEARCH_URL, params)


async def _async_google_search_json_get(client, params: dict) -> dict:
    headers = _google_search_headers()
    if headers:
        return await _async_json_get(client, GOOGLE_SEARCH_URL, params, headers=headers)
    return await _async_json_get(client, GOOGLE_SEARCH_URL, params)


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


def describe_google_search_setup_hint(exc: BaseException) -> str:
    reason, message = _google_search_error_reason_and_message(exc)
    if reason == "API_KEY_HTTP_REFERRER_BLOCKED":
        return (
            "Google Search API key is blocked by HTTP Referrer restrictions. "
            "For backend/server calls, prefer an IP-restricted key for Custom Search JSON API, "
            "or set GOOGLE_SEARCH_REFERER to a referrer that is explicitly allowed in Google Cloud."
        )
    if "does not have the access to Custom Search JSON API" in message:
        return (
            "This Google Cloud project does not have Custom Search JSON API access. "
            "Confirm the API is enabled on the same project as GOOGLE_SEARCH_API_KEY; "
            "if Google still rejects it, use an older Google Cloud project that already has Custom Search JSON API access "
            "or switch this optional source to another search/news provider."
        )
    if reason in {"SERVICE_DISABLED", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}:
        return "Enable Custom Search JSON API on the Google Cloud project used by GOOGLE_SEARCH_API_KEY."
    if reason in {"API_KEY_SERVICE_BLOCKED", "API_KEY_SERVICE_BLOCKED_BY_ORG_POLICY"}:
        return "Allow Custom Search JSON API in this API key's API restrictions."
    if reason in {"API_KEY_INVALID", "KEY_INVALID"}:
        return "GOOGLE_SEARCH_API_KEY is invalid; replace it with a valid API key."
    if reason in {"RATE_LIMIT_EXCEEDED", "QUOTA_EXCEEDED", "DAILY_LIMIT_EXCEEDED"}:
        return "Google Custom Search quota is exhausted or rate-limited; wait for quota reset or adjust billing/quota."
    if message:
        return f"Google Search rejected the request: {message}"
    return ""


def _google_search_error_reason_and_message(exc: BaseException) -> tuple[str, str]:
    response = getattr(exc, "response", None)
    try:
        payload = response.json() if response is not None else {}
    except Exception:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        return "", ""

    reason = ""
    for detail in error.get("details", []) or []:
        if isinstance(detail, dict) and detail.get("reason"):
            reason = str(detail.get("reason") or "")
            break
    if not reason:
        for item in error.get("errors", []) or []:
            if isinstance(item, dict) and item.get("reason"):
                reason = str(item.get("reason") or "")
                break
    return reason, str(error.get("message") or "")


def _log_google_search_setup_hint(exc: BaseException) -> None:
    hint = describe_google_search_setup_hint(exc)
    if hint:
        emit_log(f"    Google Search setup hint: {hint}")
