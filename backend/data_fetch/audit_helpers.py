"""Source freshness and audit helpers for data-fetch payloads."""

from __future__ import annotations

import time as time_module
from datetime import datetime
from typing import Optional, Sequence

import data_freshness as freshness_helpers
from data_trust import (
    AUDIT_STATUS_ERROR,
    AUDIT_STATUS_SKIPPED_FRESH_CACHE,
    AUDIT_STATUS_SUCCESS,
    AUDIT_STATUS_UNAVAILABLE,
    append_source_audit,
    build_source_audit_entry,
    finalize_data_trust,
    source_record_count,
)

from .constants import CORE_CACHE_SOURCES, SOURCE_FRESHNESS_SOURCES

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


def _source_freshness_stale(data: dict, source: str) -> bool:
    freshness = data.get("source_freshness", {}) if isinstance(data.get("source_freshness"), dict) else {}
    entry = freshness.get(source, {}) if isinstance(freshness.get(source), dict) else {}
    return bool(entry.get("stale"))


def _append_source_fetch_audit(
    data: dict,
    source: str,
    provider: str,
    status: str,
    *,
    fetched_at_epoch: Optional[float] = None,
    started_at_epoch: Optional[float] = None,
    finished_at_epoch: Optional[float] = None,
    record_count: Optional[int] = None,
    cache_hit: bool = False,
    stale: Optional[bool] = None,
    error_kind: str = "",
    message: str = "",
) -> dict:
    append_source_audit(
        data,
        build_source_audit_entry(
            source,
            provider,
            status,
            fetched_at_epoch=fetched_at_epoch,
            started_at_epoch=started_at_epoch,
            finished_at_epoch=finished_at_epoch,
            record_count=source_record_count(source, data) if record_count is None else record_count,
            cache_hit=cache_hit,
            stale=_source_freshness_stale(data, source) if stale is None else stale,
            error_kind=error_kind,
            message=message,
        ),
    )
    return data


def _append_cache_audit_entries(data: dict, ticker: str, now_epoch: Optional[float] = None) -> dict:
    now_epoch = float(now_epoch or time_module.time())
    freshness = data.get("source_freshness", {}) if isinstance(data.get("source_freshness"), dict) else {}
    for source in SOURCE_FRESHNESS_SOURCES:
        entry = freshness.get(source, {}) if isinstance(freshness.get(source), dict) else {}
        stale = bool(entry.get("stale"))
        status = AUDIT_STATUS_UNAVAILABLE if stale else AUDIT_STATUS_SKIPPED_FRESH_CACHE
        message = "快取仍在新鮮度門檻內，跳過外部 API。" if not stale else "快取來源已過期，等待重新抓取或 async 補強。"
        _append_source_fetch_audit(
            data,
            source,
            "cache",
            status,
            fetched_at_epoch=entry.get("fetched_at_epoch") if isinstance(entry, dict) else now_epoch,
            finished_at_epoch=now_epoch,
            record_count=source_record_count(source, data),
            cache_hit=True,
            stale=stale,
            message=message,
        )
    finalize_data_trust(data)
    return data


def _append_skipped_fresh_cache_audit(data: dict, sources: Sequence[str], now_epoch: Optional[float] = None) -> dict:
    now_epoch = float(now_epoch or time_module.time())
    freshness = data.get("source_freshness", {}) if isinstance(data.get("source_freshness"), dict) else {}
    for source in sources:
        entry = freshness.get(source, {}) if isinstance(freshness.get(source), dict) else {}
        _append_source_fetch_audit(
            data,
            source,
            "cache",
            AUDIT_STATUS_SKIPPED_FRESH_CACHE,
            fetched_at_epoch=entry.get("fetched_at_epoch") if isinstance(entry, dict) else now_epoch,
            finished_at_epoch=now_epoch,
            record_count=source_record_count(source, data),
            cache_hit=True,
            stale=False,
            message="快取仍新鮮，本次略過 optional 外部 API。",
        )
    finalize_data_trust(data)
    return data


def _append_full_fetch_audit(
    data: dict,
    ticker: str,
    provider_name: str,
    *,
    started_at_epoch: Optional[float],
    fetched_at_epoch: Optional[float],
    skip_optional_http: bool,
) -> dict:
    provider_label = provider_name or "market_data_provider"
    source_specs = [
        ("market_data", provider_label, source_record_count("market_data", data) > 0, AUDIT_STATUS_ERROR, "市場價格或估值資料缺漏"),
        ("financial_statements", provider_label, source_record_count("financial_statements", data) > 0, AUDIT_STATUS_ERROR, "年度財報資料缺漏"),
        ("monthly_revenue", "FinMind", source_record_count("monthly_revenue", data) > 0, AUDIT_STATUS_UNAVAILABLE, "非台股或 FinMind 月營收暫無可用資料"),
        ("recent_catalysts", "FinMind/Yahoo", source_record_count("recent_catalysts", data) > 0, AUDIT_STATUS_UNAVAILABLE, "近期催化劑暫無可用資料"),
        ("institutional_trading", "FinMind", source_record_count("institutional_trading", data) > 0, AUDIT_STATUS_UNAVAILABLE, "非台股或法人籌碼暫無可用資料"),
        ("dynamic_peer_metrics", "FinMind/yfinance", source_record_count("dynamic_peer_metrics", data) > 0, AUDIT_STATUS_UNAVAILABLE, "同業指標暫無可用資料"),
        ("pe_river_chart", "FinMind/default multiples", source_record_count("pe_river_chart", data) > 0, AUDIT_STATUS_UNAVAILABLE, "P/E 河流圖資料暫無可用資料"),
    ]
    if not skip_optional_http:
        source_specs.append(
            ("peer_discovery", "Google Search", source_record_count("peer_discovery", data) > 0, AUDIT_STATUS_UNAVAILABLE, "同業搜尋暫無可用資料")
        )

    for source, provider, ok, fallback_status, fallback_message in source_specs:
        _append_source_fetch_audit(
            data,
            source,
            provider,
            AUDIT_STATUS_SUCCESS if ok else fallback_status,
            fetched_at_epoch=fetched_at_epoch,
            started_at_epoch=started_at_epoch,
            finished_at_epoch=fetched_at_epoch,
            record_count=source_record_count(source, data),
            cache_hit=False,
            stale=False,
            error_kind="missing_data" if fallback_status == AUDIT_STATUS_ERROR and not ok else "",
            message="本次重新抓取完成。" if ok else fallback_message,
        )
    finalize_data_trust(data)
    return data
