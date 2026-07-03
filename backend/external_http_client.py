"""Shared HTTP helpers for external market-data APIs."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from runtime_events import emit_log


HTTP_TIMEOUT_SECONDS = 8.0
DEFAULT_PROXY_PROVIDER = "external_http"
SENSITIVE_QUERY_PARAM_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "key",
    "password",
    "secret",
    "token",
}
URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+")
QUERY_SECRET_PATTERN = re.compile(
    r"(?i)(\b(?:access_token|api_key|apikey|key|password|secret|token)=)[^&\s'\"<>]+"
)
_PROXY_ROTATION_INDEX: dict[str, int] = {}


def sync_json_get(
    url: str,
    params: dict[str, Any],
    headers: dict[str, str] | None = None,
    *,
    provider: str | None = None,
) -> Any:
    response = sync_get(url, params=params, headers=headers, provider=provider)
    return response.json()


def sync_get(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    *,
    timeout: Any = HTTP_TIMEOUT_SECONDS,
    provider: str | None = None,
    verify: Any | None = None,
) -> httpx.Response:
    kwargs: dict[str, Any] = {"headers": headers, "timeout": _normalize_timeout(timeout)}
    if params is not None:
        kwargs["params"] = params
    if verify is not None:
        kwargs["verify"] = verify
    proxy_url = proxy_url_for_request(url, provider)
    if proxy_url:
        kwargs["proxy"] = proxy_url
    response = httpx.get(url, **kwargs)
    response.raise_for_status()
    return response


def sync_post(
    url: str,
    data: Any | None = None,
    json: Any | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    *,
    timeout: Any = HTTP_TIMEOUT_SECONDS,
    provider: str | None = None,
    verify: Any | None = None,
) -> httpx.Response:
    kwargs: dict[str, Any] = {"headers": headers, "timeout": _normalize_timeout(timeout)}
    if data is not None:
        kwargs["data"] = data
    if json is not None:
        kwargs["json"] = json
    if params is not None:
        kwargs["params"] = params
    if verify is not None:
        kwargs["verify"] = verify
    proxy_url = proxy_url_for_request(url, provider)
    if proxy_url:
        kwargs["proxy"] = proxy_url
    response = httpx.post(url, **kwargs)
    response.raise_for_status()
    return response


def _normalize_timeout(timeout: Any) -> Any:
    if isinstance(timeout, tuple) and len(timeout) == 2:
        connect_timeout, read_timeout = timeout
        return httpx.Timeout(read_timeout, connect=connect_timeout)
    return timeout


async def async_json_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> Any:
    response = await client.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


def async_client(provider: str | None = None, *, timeout: float = HTTP_TIMEOUT_SECONDS) -> httpx.AsyncClient:
    kwargs = {"timeout": timeout}
    proxy_url = proxy_url_for_provider(provider or DEFAULT_PROXY_PROVIDER)
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return httpx.AsyncClient(**kwargs)


def proxy_url_for_request(url: str, provider: str | None = None) -> str | None:
    """Return the next proxy URL for a request, preferring an explicit provider."""
    return proxy_url_for_provider(provider or _provider_from_url(url))


def proxy_url_for_provider(provider: str) -> str | None:
    """Return the next configured proxy URL for a provider using round-robin order."""
    key = _provider_key(provider)
    urls = _proxy_urls_for_provider(key)
    if not urls:
        return None
    index = _PROXY_ROTATION_INDEX.get(key, 0)
    _PROXY_ROTATION_INDEX[key] = index + 1
    return urls[index % len(urls)]


def clear_proxy_rotation_state() -> None:
    """Reset local proxy rotation counters for tests and process reloads."""
    _PROXY_ROTATION_INDEX.clear()


def _proxy_urls_for_provider(provider: str) -> list[str]:
    provider_env = f"PROVIDER_PROXY_{_provider_env_prefix(provider)}_URLS"
    raw = os.getenv(provider_env)
    if raw is None:
        raw = os.getenv("PROVIDER_PROXY_URLS", "")
    return _parse_proxy_urls(raw)


def _parse_proxy_urls(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"[\s,]+", str(raw or "")) if part.strip()]


def _provider_key(provider: str) -> str:
    return str(provider or DEFAULT_PROXY_PROVIDER).strip() or DEFAULT_PROXY_PROVIDER


def _provider_env_prefix(provider: str) -> str:
    token = "".join(ch if ch.isalnum() else "_" for ch in _provider_key(provider).upper())
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_") or "UNKNOWN"


def _provider_from_url(url: str) -> str:
    hostname = urlsplit(str(url or "")).hostname or ""
    host = hostname.lower()
    if "financialmodelingprep.com" in host:
        return "FMP"
    if "googleapis.com" in host or "google.com" in host:
        return "Google Search"
    if "gdeltproject.org" in host:
        return "GDELT"
    return DEFAULT_PROXY_PROVIDER


def _redact_secrets(text: str) -> str:
    def redact_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        parsed = urlsplit(raw_url)
        if not parsed.query:
            return raw_url

        params = [
            (key, "<redacted>" if key.lower() in SENSITIVE_QUERY_PARAM_NAMES else value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
        return urlunsplit((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(params, safe="<>"),
            parsed.fragment,
        ))

    redacted = URL_PATTERN.sub(redact_url, text)
    return QUERY_SECRET_PATTERN.sub(r"\1<redacted>", redacted)


def build_http_warning(provider: str, operation: str, exc: BaseException) -> dict:
    message = str(exc).strip() or exc.__class__.__name__
    return {
        "type": "external_http_warning",
        "provider": str(provider or "unknown"),
        "operation": _redact_secrets(str(operation or "request")),
        "error_kind": exc.__class__.__name__,
        "message": _redact_secrets(message)[:240],
    }


def log_http_warning(provider: str, operation: str, exc: BaseException) -> dict:
    warning = build_http_warning(provider, operation, exc)
    emit_log(
        "    ⚠️  "
        f"{warning['provider']} {warning['operation']} 失敗 "
        f"[{warning['error_kind']}]: {warning['message']}"
    )
    return warning
