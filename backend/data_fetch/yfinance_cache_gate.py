"""Cache gate helpers for yfinance core fetch."""

from __future__ import annotations

from typing import Callable

from .constants import DATA_SCHEMA_VERSION


def build_fresh_cache_payload(
    original_ticker: str,
    cached: dict | None,
    *,
    assess_cached: Callable[[dict, str], tuple[bool, dict]],
    append_cache_audit: Callable,
    now_epoch: float,
) -> tuple[dict | None, list[str], bool]:
    if not cached:
        return None, [], False
    if cached.get("data_schema_version") != DATA_SCHEMA_VERSION:
        return None, [], True

    cache_ticker = str(cached.get("ticker") or original_ticker).strip().upper()
    is_fresh, freshness = assess_cached(cached, cache_ticker)
    if not is_fresh:
        return None, freshness.get("stale_sources", []) or ["market_data"], False

    payload = dict(cached)
    payload["_cache_hit"] = True
    payload["source_audit"] = []
    payload["data_freshness"] = freshness
    payload["source_freshness"] = freshness.get("source_freshness", {})
    append_cache_audit(payload, cache_ticker, now_epoch=now_epoch)
    return payload, [], False
