"""Freshness policy helpers for stock data payloads."""

from __future__ import annotations

import time as time_module
from datetime import datetime, timezone
from typing import Optional, Sequence

from config import (
    FINANCIAL_DATA_CACHE_SECONDS,
    FINANCIAL_DATA_MARKET_CACHE_SECONDS,
    FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
    SOURCE_FRESHNESS_MAX_AGE_SECONDS,
)

SOURCE_FRESHNESS_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "recent_catalysts",
    "institutional_trading",
    "dynamic_peer_metrics",
    "peer_discovery",
    "pe_river_chart",
)
CORE_CACHE_SOURCES = (
    "market_data",
    "financial_statements",
    "monthly_revenue",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None


def is_taiwan_ticker(ticker: str) -> bool:
    stock_id = str(ticker).replace(".TW", "").replace(".TWO", "")
    return str(ticker).endswith(".TW") or str(ticker).endswith(".TWO") or (stock_id.isdigit() and len(stock_id) == 4)


def market_now(ticker: str) -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    zone_name = "Asia/Taipei" if is_taiwan_ticker(ticker) else "America/New_York"
    return datetime.now(ZoneInfo(zone_name))


def is_likely_market_session(ticker: str) -> bool:
    now = market_now(ticker)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    if is_taiwan_ticker(ticker):
        return 9 * 60 <= minutes <= 13 * 60 + 30
    return 9 * 60 + 30 <= minutes <= 16 * 60


def cache_timestamp_epoch(cached: dict) -> Optional[float]:
    for key in ("market_data_fetched_at_epoch", "cache_generated_at_epoch"):
        value = cached.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    raw_iso = str(cached.get("market_data_fetched_at") or cached.get("cache_generated_at") or "").strip()
    if not raw_iso:
        return None
    try:
        parsed = datetime.fromisoformat(raw_iso.replace("Z", "+00:00"))
        return parsed.timestamp()
    except ValueError:
        return None


def freshness_policy(ticker: str, market_session: Optional[bool] = None) -> dict:
    if market_session is None:
        market_session = is_likely_market_session(ticker)
    return {
        "market_session": market_session,
        "max_age_seconds": FINANCIAL_DATA_MARKET_CACHE_SECONDS if market_session else FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
        "policy": "market_session" if market_session else "offhours_or_weekend",
    }


def source_max_age_seconds(source: str, ticker: str, market_session: Optional[bool] = None) -> int:
    if source == "market_data":
        return int(freshness_policy(ticker, market_session=market_session)["max_age_seconds"])
    return int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(source, FINANCIAL_DATA_CACHE_SECONDS))


def source_timestamp_epoch(data: dict, source: str) -> Optional[float]:
    source_freshness = data.get("source_freshness", {}) if isinstance(data.get("source_freshness"), dict) else {}
    entry = source_freshness.get(source, {}) if isinstance(source_freshness.get(source), dict) else {}
    for key in ("fetched_at_epoch", "market_data_fetched_at_epoch", "cache_generated_at_epoch"):
        value = entry.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    if source_freshness and source not in source_freshness:
        return None
    if source == "market_data":
        return cache_timestamp_epoch(data)

    value = data.get(f"{source}_fetched_at_epoch")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    value = data.get("cache_generated_at_epoch")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return cache_timestamp_epoch(data)


def build_source_freshness_entry(
    source: str,
    ticker: str,
    fetched_at_epoch: Optional[float],
    cache_hit: bool,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> dict:
    now_epoch = float(now_epoch or time_module.time())
    max_age_seconds = source_max_age_seconds(source, ticker, market_session=market_session)
    age_seconds = None
    if fetched_at_epoch:
        age_seconds = max(0, int(now_epoch - float(fetched_at_epoch)))
    is_fresh = age_seconds is not None and age_seconds <= max_age_seconds
    entry = {
        "source": source,
        "cache_hit": cache_hit,
        "max_age_seconds": max_age_seconds,
        "age_seconds": age_seconds,
        "is_fresh": is_fresh,
        "stale": not is_fresh,
        "fetched_at_epoch": fetched_at_epoch,
        "fetched_at": datetime.fromtimestamp(fetched_at_epoch, timezone.utc).isoformat()
        if fetched_at_epoch else None,
        "checked_at": datetime.fromtimestamp(now_epoch, timezone.utc).isoformat(),
    }
    if source == "market_data":
        policy = freshness_policy(ticker, market_session=market_session)
        entry["market_session"] = policy["market_session"]
        entry["policy"] = policy["policy"]
    return entry


def build_source_freshness(
    data: dict,
    ticker: str,
    cache_hit: bool,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> dict:
    now_epoch = float(now_epoch or time_module.time())
    return {
        source: build_source_freshness_entry(
            source,
            ticker,
            source_timestamp_epoch(data, source),
            cache_hit=cache_hit,
            now_epoch=now_epoch,
            market_session=market_session,
        )
        for source in SOURCE_FRESHNESS_SOURCES
    }


def source_is_stale(
    data: dict,
    source: str,
    ticker: Optional[str] = None,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> bool:
    ticker = str(ticker or data.get("ticker") or "").strip().upper()
    entry = build_source_freshness_entry(
        source,
        ticker,
        source_timestamp_epoch(data, source),
        cache_hit=bool(data.get("_cache_hit")),
        now_epoch=now_epoch,
        market_session=market_session,
    )
    return bool(entry["stale"])


def mark_sources_fetched(
    data: dict,
    ticker: str,
    sources: Sequence[str],
    fetched_at_epoch: Optional[float] = None,
    cache_hit: bool = False,
    market_session: Optional[bool] = None,
) -> dict:
    fetched_at_epoch = float(fetched_at_epoch or time_module.time())
    source_freshness = dict(data.get("source_freshness", {}) or {})
    for source in sources:
        source_freshness[source] = build_source_freshness_entry(
            source,
            ticker,
            fetched_at_epoch,
            cache_hit=cache_hit,
            now_epoch=fetched_at_epoch,
            market_session=market_session,
        )
    data["source_freshness"] = source_freshness
    return data


def build_data_freshness(
    ticker: str,
    market_data_fetched_at_epoch: Optional[float],
    cache_hit: bool,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> dict:
    now_epoch = float(now_epoch or time_module.time())
    policy = freshness_policy(ticker, market_session=market_session)
    age_seconds = None
    if market_data_fetched_at_epoch:
        age_seconds = max(0, int(now_epoch - float(market_data_fetched_at_epoch)))
    return {
        "cache_hit": cache_hit,
        "market_session": policy["market_session"],
        "policy": policy["policy"],
        "max_age_seconds": policy["max_age_seconds"],
        "age_seconds": age_seconds,
        "is_fresh": age_seconds is not None and age_seconds <= policy["max_age_seconds"],
        "market_data_fetched_at_epoch": market_data_fetched_at_epoch,
        "market_data_fetched_at": datetime.fromtimestamp(market_data_fetched_at_epoch, timezone.utc).isoformat()
        if market_data_fetched_at_epoch else None,
        "checked_at": datetime.fromtimestamp(now_epoch, timezone.utc).isoformat(),
    }


def assess_cached_financial_data(
    cached: dict,
    ticker: str,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> tuple[bool, dict]:
    fetched_at_epoch = cache_timestamp_epoch(cached)
    freshness = build_data_freshness(
        ticker,
        fetched_at_epoch,
        cache_hit=True,
        now_epoch=now_epoch,
        market_session=market_session,
    )
    source_freshness = build_source_freshness(
        cached,
        ticker,
        cache_hit=True,
        now_epoch=now_epoch,
        market_session=market_session,
    )
    freshness["source_freshness"] = source_freshness
    freshness["stale_sources"] = [
        source for source in CORE_CACHE_SOURCES
        if source_freshness.get(source, {}).get("stale")
    ]
    return not freshness["stale_sources"], freshness


def mark_market_data_fetched(
    data: dict,
    ticker: str,
    fetched_at_epoch: Optional[float] = None,
    cache_hit: bool = False,
    market_session: Optional[bool] = None,
) -> dict:
    fetched_at_epoch = float(fetched_at_epoch or time_module.time())
    data["market_data_fetched_at_epoch"] = fetched_at_epoch
    data["market_data_fetched_at"] = datetime.fromtimestamp(fetched_at_epoch, timezone.utc).isoformat()
    data["data_freshness"] = build_data_freshness(
        ticker,
        fetched_at_epoch,
        cache_hit=cache_hit,
        now_epoch=fetched_at_epoch,
        market_session=market_session,
    )
    mark_sources_fetched(
        data,
        ticker,
        ("market_data",),
        fetched_at_epoch=fetched_at_epoch,
        cache_hit=cache_hit,
        market_session=market_session,
    )
    return data
