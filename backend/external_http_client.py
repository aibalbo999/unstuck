"""Shared HTTP helpers for external market-data APIs."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from runtime_events import emit_log


HTTP_TIMEOUT_SECONDS = 8.0
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


def sync_json_get(url: str, params: dict[str, Any]) -> Any:
    response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


async def async_json_get(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> Any:
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)


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
    return {
        "type": "external_http_warning",
        "provider": str(provider or "unknown"),
        "operation": _redact_secrets(str(operation or "request")),
        "error_kind": exc.__class__.__name__,
        "message": _redact_secrets(str(exc))[:240],
    }


def log_http_warning(provider: str, operation: str, exc: BaseException) -> dict:
    warning = build_http_warning(provider, operation, exc)
    emit_log(
        "    ⚠️  "
        f"{warning['provider']} {warning['operation']} 失敗 "
        f"[{warning['error_kind']}]: {warning['message']}"
    )
    return warning
