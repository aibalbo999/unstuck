"""Shared HTTP helpers for external market-data APIs."""

from __future__ import annotations

from typing import Any

import httpx

from runtime_events import emit_log


HTTP_TIMEOUT_SECONDS = 8.0


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


def build_http_warning(provider: str, operation: str, exc: BaseException) -> dict:
    return {
        "type": "external_http_warning",
        "provider": str(provider or "unknown"),
        "operation": str(operation or "request"),
        "error_kind": exc.__class__.__name__,
        "message": str(exc)[:240],
    }


def log_http_warning(provider: str, operation: str, exc: BaseException) -> dict:
    warning = build_http_warning(provider, operation, exc)
    emit_log(
        "    ⚠️  "
        f"{warning['provider']} {warning['operation']} 失敗 "
        f"[{warning['error_kind']}]: {warning['message']}"
    )
    return warning
