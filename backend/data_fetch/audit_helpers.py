"""Source freshness and audit helpers for data-fetch payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

import data_freshness as freshness_helpers
from .audit_policy import (
    _append_cache_audit_entries,
    _append_full_fetch_audit,
    _append_skipped_fresh_cache_audit,
    _append_source_fetch_audit,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None


def _market_now(ticker: str) -> datetime:
    return freshness_helpers.market_now(ticker)


def _is_likely_market_session(ticker: str) -> bool:
    return freshness_helpers.is_likely_market_session(ticker)


def _cache_timestamp_epoch(cached: dict) -> Optional[float]:
    return freshness_helpers.cache_timestamp_epoch(cached)


def _freshness_policy(ticker: str) -> dict:
    return freshness_helpers.freshness_policy(
        ticker,
        market_session=_is_likely_market_session(ticker),
    )


def _source_max_age_seconds(source: str, ticker: str) -> int:
    return freshness_helpers.source_max_age_seconds(
        source,
        ticker,
        market_session=_is_likely_market_session(ticker),
    )


def _source_timestamp_epoch(data: dict, source: str) -> Optional[float]:
    return freshness_helpers.source_timestamp_epoch(data, source)


def _build_source_freshness_entry(
    source: str,
    ticker: str,
    fetched_at_epoch: Optional[float],
    cache_hit: bool,
    now_epoch: Optional[float] = None,
) -> dict:
    return freshness_helpers.build_source_freshness_entry(
        source,
        ticker,
        fetched_at_epoch,
        cache_hit,
        now_epoch=now_epoch,
        market_session=_is_likely_market_session(ticker),
    )


def _build_source_freshness(data: dict, ticker: str, cache_hit: bool, now_epoch: Optional[float] = None) -> dict:
    return freshness_helpers.build_source_freshness(
        data,
        ticker,
        cache_hit,
        now_epoch=now_epoch,
        market_session=_is_likely_market_session(ticker),
    )


def _source_is_stale(data: dict, source: str, ticker: Optional[str] = None, now_epoch: Optional[float] = None) -> bool:
    resolved_ticker = str(ticker or data.get("ticker") or "").strip().upper()
    return freshness_helpers.source_is_stale(
        data,
        source,
        ticker=resolved_ticker,
        now_epoch=now_epoch,
        market_session=_is_likely_market_session(resolved_ticker),
    )


def _mark_sources_fetched(
    data: dict,
    ticker: str,
    sources: Sequence[str],
    fetched_at_epoch: Optional[float] = None,
    cache_hit: bool = False,
) -> dict:
    return freshness_helpers.mark_sources_fetched(
        data,
        ticker,
        sources,
        fetched_at_epoch=fetched_at_epoch,
        cache_hit=cache_hit,
        market_session=_is_likely_market_session(ticker),
    )


def _build_data_freshness(
    ticker: str,
    market_data_fetched_at_epoch: Optional[float],
    cache_hit: bool,
    now_epoch: Optional[float] = None,
) -> dict:
    return freshness_helpers.build_data_freshness(
        ticker,
        market_data_fetched_at_epoch,
        cache_hit,
        now_epoch=now_epoch,
        market_session=_is_likely_market_session(ticker),
    )


def _assess_cached_financial_data(cached: dict, ticker: str, now_epoch: Optional[float] = None) -> tuple[bool, dict]:
    return freshness_helpers.assess_cached_financial_data(
        cached,
        ticker,
        now_epoch=now_epoch,
        market_session=_is_likely_market_session(ticker),
    )


def _mark_market_data_fetched(
    data: dict,
    ticker: str,
    fetched_at_epoch: Optional[float] = None,
    cache_hit: bool = False,
) -> dict:
    return freshness_helpers.mark_market_data_fetched(
        data,
        ticker,
        fetched_at_epoch=fetched_at_epoch,
        cache_hit=cache_hit,
        market_session=_is_likely_market_session(ticker),
    )
