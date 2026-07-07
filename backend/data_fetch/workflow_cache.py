"""Cache gate and fallback helpers for stock-data workflow."""

from __future__ import annotations

from cache_store import get_cache_json
from data_freshness import assess_cached_financial_data
from data_trust import append_source_audit, finalize_data_trust

from .audit_helpers import _append_cache_audit_entries, _append_source_fetch_audit
from .constants import DATA_SCHEMA_VERSION, REQUIRED_DATA_SCHEMA_FIELDS
from .types import ProviderResult


def schema_compatible_cached_payload(ticker: str) -> dict | None:
    cache_key = f"financial_data:{ticker}"
    cached = get_cache_json(cache_key)
    if not cached or cached.get("data_schema_version") != DATA_SCHEMA_VERSION:
        return None
    if any(field not in cached for field in REQUIRED_DATA_SCHEMA_FIELDS):
        return None
    return cached


def fresh_cached_payload(ticker: str, cached: dict) -> dict | None:
    cache_ticker = str(cached.get("ticker") or ticker).strip().upper()
    is_fresh, freshness = assess_cached_financial_data(cached, cache_ticker)
    if not is_fresh:
        return None

    cached = dict(cached)
    cached["_cache_hit"] = True
    cached["source_audit"] = []
    cached["data_freshness"] = freshness
    cached["source_freshness"] = freshness.get("source_freshness", {})
    _append_cache_audit_entries(cached, cache_ticker)
    return cached


def fallback_cached_payload(ticker: str, cached: dict | None, core_result: ProviderResult) -> dict | None:
    if not cached:
        return None

    cache_ticker = str(cached.get("ticker") or ticker).strip().upper()
    _is_fresh, freshness = assess_cached_financial_data(cached, cache_ticker)
    fallback = dict(cached)
    fallback["_cache_hit"] = True
    fallback["source_audit"] = []
    fallback["data_freshness"] = freshness
    fallback["source_freshness"] = freshness.get("source_freshness", {})
    notes = list(fallback.get("data_source_notes", []) or [])
    notes.append("核心資料重新抓取失敗，本次使用既有快取作為 fallback；請查看來源審計。")
    fallback["data_source_notes"] = notes
    _append_cache_audit_entries(fallback, cache_ticker)
    if core_result.audit:
        append_source_audit(fallback, core_result.audit)
    else:
        _append_source_fetch_audit(
            fallback,
            core_result.source or "market_data",
            core_result.provider or "provider",
            core_result.status or "error",
            record_count=0,
            cache_hit=False,
            stale=True,
            message="核心 provider 重新抓取失敗，使用舊快取 fallback。",
        )
    finalize_data_trust(fallback)
    return fallback
