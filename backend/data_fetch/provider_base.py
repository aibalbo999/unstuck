"""Base classes and result helpers for data providers."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable

from data_trust import AUDIT_STATUS_NOT_CONFIGURED, AUDIT_STATUS_SUCCESS, AUDIT_STATUS_UNAVAILABLE

from .market_sources.identity import is_taiwan_ticker
from .types import FetchRequest, ProviderResult


class DataProvider:
    name = "provider"
    source = "unknown"
    markets = {"us", "tw"}
    execute_in_workflow = True
    primary_source_provider = True

    def supports(self, request: FetchRequest) -> bool:
        return infer_market(request.ticker) in self.markets

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:  # pragma: no cover - interface
        raise NotImplementedError

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        return await asyncio.to_thread(self.fetch, request, context)


class CallableProvider(DataProvider):
    def __init__(
        self,
        source: str,
        name: str,
        callback: Callable,
        markets: set[str] | None = None,
    ):
        self.source = source
        self.name = name
        self.callback = callback
        self.markets = markets or {"us", "tw"}

    def supports(self, request: FetchRequest) -> bool:
        market = infer_market(request.ticker)
        return market in self.markets

    def fetch(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        try:
            return self.callback(request, context)
        except TypeError:
            return self.callback(request)

    async def fetch_async(self, request: FetchRequest, context: dict | None = None) -> ProviderResult:
        result = self.fetch(request, context)
        if inspect.isawaitable(result):
            result = await result
        return result


def infer_market(ticker: str) -> str:
    return "tw" if is_taiwan_ticker(str(ticker or "")) else "us"


def provider_result_from_audited(result: dict, source: str, provider: str) -> ProviderResult:
    audit = result.get("audit", {}) if isinstance(result, dict) else {}
    return ProviderResult(
        source=str(audit.get("source") or source),
        provider=str(audit.get("provider") or provider),
        status=str(audit.get("status") or AUDIT_STATUS_UNAVAILABLE),
        value=result.get("value") if isinstance(result, dict) else None,
        audit=dict(audit),
        duration_ms=int(audit.get("duration_ms") or 0),
    )


def provider_result_from_payload(
    source: str,
    provider: str,
    payload: dict,
    *,
    started_at_epoch: float | None = None,
) -> ProviderResult:
    audit_entries = payload.get("source_audit", []) if isinstance(payload.get("source_audit"), list) else []
    matching = next(
        (
            entry for entry in audit_entries
            if isinstance(entry, dict)
            and entry.get("source") == source
            and (not provider or provider.lower() in str(entry.get("provider") or "").lower())
        ),
        None,
    )
    if matching is None:
        matching = next((entry for entry in audit_entries if isinstance(entry, dict) and entry.get("source") == source), None)
    status = str((matching or {}).get("status") or (AUDIT_STATUS_SUCCESS if payload and "error" not in payload else AUDIT_STATUS_UNAVAILABLE))
    duration_ms = int((matching or {}).get("duration_ms") or 0)
    if duration_ms <= 0 and started_at_epoch is not None:
        duration_ms = max(0, int(round((time.time() - started_at_epoch) * 1000)))
    return ProviderResult(
        source=source,
        provider=str((matching or {}).get("provider") or provider),
        status=status,
        value=payload,
        audit=dict(matching or {}),
        duration_ms=duration_ms,
        warnings=list(payload.get("data_source_notes", []) or []) if isinstance(payload, dict) else [],
    )


def unavailable_provider_result(source: str, provider: str, message: str = "") -> ProviderResult:
    return ProviderResult(
        source=source,
        provider=provider,
        status=AUDIT_STATUS_UNAVAILABLE,
        value=None,
        audit={
            "source": source,
            "provider": provider,
            "status": AUDIT_STATUS_UNAVAILABLE,
            "record_count": 0,
            "cache_hit": False,
            "stale": False,
            "message": message,
        },
    )


def not_configured_provider_result(source: str, provider: str, message: str = "") -> ProviderResult:
    return ProviderResult(
        source=source,
        provider=provider,
        status=AUDIT_STATUS_NOT_CONFIGURED,
        value=None,
        audit={
            "source": source,
            "provider": provider,
            "status": AUDIT_STATUS_NOT_CONFIGURED,
            "record_count": 0,
            "cache_hit": False,
            "stale": False,
            "message": message,
        },
    )
