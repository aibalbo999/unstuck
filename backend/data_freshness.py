"""Freshness policy helpers for stock data payloads."""

from __future__ import annotations

import math
import time as time_module
from datetime import datetime, timezone
from typing import Optional, Sequence

from config import (
    FINANCIAL_DATA_CACHE_SECONDS as _DEFAULT_FINANCIAL_DATA_CACHE_SECONDS,
    FINANCIAL_DATA_MARKET_CACHE_SECONDS as _DEFAULT_FINANCIAL_DATA_MARKET_CACHE_SECONDS,
    FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS as _DEFAULT_FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
    SOURCE_FRESHNESS_MAX_AGE_SECONDS as _DEFAULT_SOURCE_FRESHNESS_MAX_AGE_SECONDS,
)
from data_freshness_market import calendar_coverage, is_likely_market_session, is_taiwan_ticker, market_now
from data_freshness_policy import (
    CORE_CACHE_SOURCES,
    SOURCE_FRESHNESS_SOURCES,
)
from data_trust_audit import source_record_count
from report_freshness_summary import safe_bool
from source_observation_freshness import observation_recency

FINANCIAL_DATA_MARKET_CACHE_SECONDS = _DEFAULT_FINANCIAL_DATA_MARKET_CACHE_SECONDS
FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS = _DEFAULT_FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS
FINANCIAL_DATA_CACHE_SECONDS = _DEFAULT_FINANCIAL_DATA_CACHE_SECONDS
SOURCE_FRESHNESS_MAX_AGE_SECONDS = dict(_DEFAULT_SOURCE_FRESHNESS_MAX_AGE_SECONDS)


def freshness_policy(ticker: str, market_session: Optional[bool] = None) -> dict:
    session = is_likely_market_session(ticker) if market_session is None else bool(market_session)
    coverage = calendar_coverage(ticker)
    unknown = coverage['coverage_status'] != 'available'
    return {
        "calendar": coverage,
        "policy": "calendar_unknown_conservative" if unknown else "market_session" if session else "offhours_or_weekend",
        "market_session": session,
        "max_age_seconds": FINANCIAL_DATA_MARKET_CACHE_SECONDS
        if session or unknown else FINANCIAL_DATA_OFFHOURS_CACHE_SECONDS,
    }


def source_max_age_seconds(source: str, ticker: str, market_session: Optional[bool] = None) -> int:
    if source == "market_data":
        return int(freshness_policy(ticker, market_session=market_session)["max_age_seconds"])
    return int(SOURCE_FRESHNESS_MAX_AGE_SECONDS.get(source, FINANCIAL_DATA_CACHE_SECONDS))


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


def _twse_original_timestamp(data: dict, now_epoch: Optional[float] = None) -> Optional[float]:
    """Use only the selected TWSE observation, never aggregate/market time.

    An explicit entry (including unknown or invalid) is authoritative. Without
    one, only source-specific fields are eligible. Audit selection remains with
    its producer; source-only refresh already projects retained original audits.
    """
    now_epoch = time_module.time() if now_epoch is None else now_epoch
    freshness = data.get("source_freshness")
    if isinstance(freshness, dict) and "twse_official" in freshness:
        entry = freshness["twse_official"]
        if not isinstance(entry, dict):
            return None
        epoch, iso = entry.get("fetched_at_epoch"), entry.get("fetched_at")
    else:
        epoch, iso = data.get("twse_official_fetched_at_epoch"), data.get("twse_official_fetched_at")
    try:
        if epoch is not None:
            if type(epoch) not in (int, float) or not math.isfinite(epoch):
                return None
            epoch = float(epoch)
        if iso is not None:
            if not isinstance(iso, str):
                return None
            parsed = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return None
            iso_epoch = parsed.timestamp()
            if not math.isfinite(iso_epoch) or not 0 < iso_epoch <= now_epoch:
                return None
            if epoch is not None and abs(epoch - iso_epoch) >= 1:
                return None
            epoch = iso_epoch if epoch is None else epoch
        return epoch if epoch is not None and math.isfinite(epoch) and 0 < epoch <= now_epoch else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def source_timestamp_epoch(data: dict, source: str, *, now_epoch: Optional[float] = None) -> Optional[float]:
    if source == "twse_official":
        return _twse_original_timestamp(data, now_epoch=now_epoch)
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
    source_data: Optional[dict] = None,
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
        "fetch_is_fresh": is_fresh,
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
        entry["calendar"] = policy["calendar"]
    if source == "institutional_trading" and isinstance(source_data, dict) and source_data:
        entry.update(observation_recency(source_data.get("latest_date"), ticker=ticker,
                                         now_epoch=now_epoch, max_age_days=7))
        entry["is_fresh"] = is_fresh and entry["observation_status"] == "recent"
        entry["stale"] = not entry["is_fresh"]
    if isinstance(source_data, dict) and source_data.get('stale') is True:
        entry.update(is_fresh=False, stale=True, coverage_status=source_data.get('status', 'stale'))
    return entry


def build_source_freshness(
    data: dict,
    ticker: str,
    cache_hit: bool,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> dict:
    now_epoch = float(now_epoch or time_module.time())
    from source_applicability import source_is_applicable
    return {
        source: build_source_freshness_entry(
            source,
            ticker,
            source_timestamp_epoch(data, source, now_epoch=now_epoch),
            cache_hit=cache_hit,
            now_epoch=now_epoch,
            market_session=market_session,
            source_data=data.get(source),
        ) if source_is_applicable(source, data, ticker) else {
            "source": source, "status": "not_applicable", "stale": False,
            "is_fresh": None, "fetched_at": None, "cache_hit": False,
        }
        for source in SOURCE_FRESHNESS_SOURCES
    }


def source_is_stale(
    data: dict,
    source: str,
    ticker: Optional[str] = None,
    now_epoch: Optional[float] = None,
    market_session: Optional[bool] = None,
) -> bool:
    from source_applicability import source_is_applicable
    if not source_is_applicable(source, data, ticker):
        return False
    payload = data.get(source)
    observed_empty_documents = (source == 'official_disclosures' and isinstance(payload, dict)
        and payload.get('retrieval_status') in {'success', 'valid_empty'}
        and bool(payload.get('fetched_at_epoch')) and not safe_bool(payload.get('stale')))
    if source != "market_data" and source_record_count(source, data) <= 0 and not observed_empty_documents:
        return True
    ticker = str(ticker or data.get("ticker") or "").strip().upper()
    entry = build_source_freshness_entry(
        source,
        ticker,
        source_timestamp_epoch(data, source, now_epoch=now_epoch),
        cache_hit=safe_bool(data.get("_cache_hit")),
        now_epoch=now_epoch,
        market_session=market_session,
        source_data=data.get(source),
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
        from source_applicability import source_is_applicable
        if not source_is_applicable(source, data, ticker):
            source_freshness[source] = {"source": source, "status": "not_applicable", "stale": False,
                                        "is_fresh": None, "fetched_at": None, "cache_hit": False}
            continue
        source_freshness[source] = build_source_freshness_entry(
            source,
            ticker,
            fetched_at_epoch,
            cache_hit=cache_hit,
            now_epoch=fetched_at_epoch,
            market_session=market_session,
            source_data=data.get(source),
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
        "calendar": policy["calendar"],
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
