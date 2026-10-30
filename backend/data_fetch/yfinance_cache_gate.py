"""Cache gate helpers for yfinance core fetch."""

from __future__ import annotations

from typing import Callable

from .constants import DATA_SCHEMA_VERSION, REQUIRED_DATA_SCHEMA_FIELDS


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
    if any(field not in cached for field in REQUIRED_DATA_SCHEMA_FIELDS):
        return None, [], True

    from market_price_reconciliation import CONTRACT
    daily = cached.get("daily_market_data") or {}
    if daily.get("bars") and daily.get("price_basis_contract") != CONTRACT:
        return None, ["market_data"], True

    if daily.get("bars") and str(cached.get("ticker") or original_ticker).upper().endswith((".TW",".TWO")):
        from datetime import datetime,timezone
        from two_week_market_eligibility import completed_session
        from report_source_admission import institutional_admission,price_admission
        ticker=str(cached.get("ticker") or original_ticker).upper()
        current_expected=completed_session(datetime.fromtimestamp(now_epoch,timezone.utc), ticker=ticker)
        if not current_expected or daily.get("as_of")!=current_expected:
            return None,["market_data"],False
        if not institutional_admission(cached.get("institutional_trading"),current_expected)["eligible"] or not price_admission(daily,ticker)["eligible"]:
            return None,["institutional_trading","market_data"],False

    expected=(daily.get("history_query") or {}).get("expected_completed_session")
    if expected and daily.get("as_of") != expected:
        return None, ["market_data"], False

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
