"""Institutional acquisition cadence, separate from the age of observations."""
from __future__ import annotations

import time

from config import INSTITUTIONAL_LOOKBACK_DAYS
from data_freshness import build_source_freshness_entry, source_max_age_seconds
from data_trust import build_source_audit_entry, source_record_count
from provider_correlation import source_operation
from provider_resilience import call_provider_with_resilience
from shared_provider_cache import shared_fetch
from source_observation_freshness import observation_recency

from .types import FetchRequest, ProviderResult

SOURCE = "institutional_trading"
PROVIDER = "FinMind"
DATASET = "FinMind TaiwanStockInstitutionalInvestorsBuySell"
STALE_RECHECK_SECONDS = 15 * 60
EMPTY_RECHECK_SECONDS = 60


def fetch_institutional_result(request: FetchRequest, *, fetch=None) -> ProviderResult:
    if fetch is None:
        from .market_sources.taiwan import fetch_institutional_trading_trend
        fetch = fetch_institutional_trading_trend

    fresh_ttl = source_max_age_seconds(SOURCE, request.ticker)

    def result_ttl(value):
        if not value:
            return EMPTY_RECHECK_SECONDS
        recency = observation_recency(value.get("latest_date"), ticker=request.ticker, now_epoch=time.time())
        return fresh_ttl if recency["observation_status"] == "recent" else STALE_RECHECK_SECONDS

    started = time.time()
    with source_operation(SOURCE, PROVIDER):
        value, meta = shared_fetch(
            f"institutional:{request.ticker}:{INSTITUTIONAL_LOOKBACK_DAYS}:v1",
            lambda: call_provider_with_resilience(PROVIDER, fetch, (request.ticker,), {}),
            freshness_seconds=fresh_ttl, retention_seconds=fresh_ttl,
            error_retry_seconds=EMPTY_RECHECK_SECONDS, result_ttl=result_ttl,
            use_cache=not request.options.force_refresh,
        )
        value = dict(value) if isinstance(value, dict) else {}
        from official_institutional_source import recover_institutional_observations
        value, recovery = recover_institutional_observations(
            request.ticker, value, now_epoch=time.time(), limit=INSTITUTIONAL_LOOKBACK_DAYS)
        if value and recovery:
            value["official_recovery"] = recovery
        primary_acquisition = dict(meta)
        if recovery.get("added_observation_count"):
            receipts = [row for row in recovery.get("reports", []) if row.get("status") == "available"]
            fetched = [row.get("fetched_at_epoch") for row in receipts if row.get("fetched_at_epoch")]
            if meta.get("fetched_at_epoch"):
                fetched.append(meta["fetched_at_epoch"])
            meta = {**meta, "fetched_at_epoch": min(fetched) if fetched else None,
                    "cache_hit": bool(receipts) and all(row.get("cache_hit") for row in receipts)
                                 and (not value.get("daily_category_observations") or bool(primary_acquisition.get("cache_hit")))}
        actual_provider = str(value.get("source") or DATASET)
        recency = observation_recency(value.get("latest_date"), ticker=request.ticker, now_epoch=time.time())
        stale = bool(meta.get("stale")) or bool(value and recency["observation_status"] != "recent")
        error_kind = str(meta.get("error_kind") or "")
        partial = bool(value) and (stale or bool(value.get("rejected_record_count"))
                                    or value.get("window_coverage_status") != "complete" or recovery.get("conflicts"))
        status = ("degraded_enrichment" if value and (stale or error_kind) else "success" if value
                  else "error" if error_kind else "unavailable")
        if error_kind in {"ProviderCircuitOpenError", "ProviderRateLimitOpenError", "single_flight_busy"}:
            status = "degraded_enrichment" if value else "unavailable"
        message = ("法人來源取得失敗；保留既有觀測並標示限制。" if error_kind else
                   "最近查詢仍未取得較新法人觀測；保留原日期與數值，不推定缺列為零。" if stale else
                   "法人來源已取得；觀測日期與實際涵蓋期間分開標示。" if value else
                   "法人來源回傳空資料；不能推定為零交易。")
        audit = build_source_audit_entry(
            SOURCE, PROVIDER, status, fetched_at_epoch=meta.get("fetched_at_epoch"),
            started_at_epoch=started, finished_at_epoch=time.time(),
            record_count=source_record_count(SOURCE, {SOURCE: value}),
            cache_hit=bool(meta.get("cache_hit")), stale=stale, error_kind=error_kind, message=message,
        )
        audit.update(meta, **recency, actual_provider=actual_provider, primary_provider=DATASET, stale=stale,
                     retrieval_status="error" if error_kind else "success" if value else "empty",
                     coverage_status="partial" if partial else "available" if value else "unavailable")
        audit["component_statuses"] = {"institutional_observations": {
            "status": audit["coverage_status"], "as_of": recency["observed_at"], "provider": actual_provider,
            "observation_status": recency["observation_status"], "observation_age_days": recency["observation_age_days"],
            "retrieval_status": audit["retrieval_status"], "stale": stale, "cache_hit": bool(meta.get("cache_hit")),
            "fetched_at_epoch": meta.get("fetched_at_epoch"),
            "reason_code": "acquisition_failed" if error_kind else "no_observations" if not value else
                           "observation_" + recency["observation_status"] if stale else
                           "incomplete_observation_window" if partial else "complete_observation_window",
        }}
        if recovery:
            audit["official_recovery"] = recovery
            audit["primary_acquisition"] = primary_acquisition
        if meta.get("retry_after_epoch"):
            audit["retry_at"] = meta["retry_after_epoch"]
        if not meta.get("fetched_at_epoch"):
            audit["fetched_at"] = None
        # This is an aggregate; SDK callback invocation is not proof of an HTTP request.
        audit["event_kind"] = "aggregate"
        if not audit.get("provider_attempts"):
            audit["http_request_sent"] = False
        if value:
            value.update(**recency, actual_provider=actual_provider, stale=stale,
                         cache_hit=bool(meta.get("cache_hit")), fetched_at_epoch=meta.get("fetched_at_epoch"),
                         coverage_status=audit["coverage_status"], coverage_note=message)
        return ProviderResult(source=SOURCE, provider=PROVIDER, status=status, value=value,
                              audit=audit, duration_ms=audit.get("duration_ms") or 0,
                              as_of=recency["observed_at"])


def apply_institutional_freshness(data: dict, ticker: str, audit: dict) -> None:
    """Preserve source acquisition time when a freshly assembled package uses cache."""
    if audit.get("source") != SOURCE or "fetched_at_epoch" not in audit:
        return
    entry = build_source_freshness_entry(
        SOURCE, ticker, audit.get("fetched_at_epoch"), bool(audit.get("cache_hit")),
        now_epoch=time.time(), source_data=data.get(SOURCE),
    )
    if audit.get("stale"):
        entry.update(stale=True, is_fresh=False)
    data.setdefault("source_freshness", {})[SOURCE] = entry


def institutional_window_status(dates: list[str], ticker: str, count: int) -> str:
    """A sparse row count is not evidence of consecutive exchange sessions."""
    from datetime import datetime, timedelta
    from data_freshness_market import market_calendar
    from source_observation_freshness import parse_observation_date

    latest = parse_observation_date(dates[-1]) if dates else None
    if latest is None:
        return "missing_sessions"
    calendars = {}
    expected = []
    day = latest
    for _ in range(max(45, count * 3)):
        if day.year not in calendars:
            calendars[day.year] = market_calendar(ticker, current=datetime.combine(day, datetime.min.time()))
        calendar = calendars[day.year]
        if calendar.get("coverage_status") != "available":
            return "calendar_unknown"
        if day.weekday() < 5 and day not in calendar["holidays"]:
            expected.append(day.isoformat())
            if len(expected) == count:
                break
        day -= timedelta(days=1)
    complete = len(expected) == count and expected[0] == latest.isoformat() and set(expected) == set(dates[-count:])
    return "complete" if complete else "missing_sessions"


def institutional_acquired_in_fetch(data: dict, fetch_id: str | None) -> bool:
    """Only a typed aggregate from this exact fetch proves the primary ran already."""
    if not isinstance(fetch_id, str) or not fetch_id:
        return False
    return any(isinstance(entry, dict) and entry.get("source") == SOURCE
               and entry.get("provider") == PROVIDER and bool(entry.get("actual_provider"))
               and (entry.get("actual_provider") == DATASET or entry.get("primary_provider") == DATASET)
               and entry.get("fetch_id") == fetch_id and bool(entry.get("operation_id"))
               and entry.get("event_kind") == "aggregate"
               and entry.get("retrieval_status") in {"success", "empty", "error"}
               for entry in data.get("source_audit", []) or [])
