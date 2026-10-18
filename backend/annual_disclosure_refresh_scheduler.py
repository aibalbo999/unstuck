"""Low-frequency refresh of exchange-wide annual disclosure snapshots."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from typing import Any

from data_fetch.types import FetchRequest


DAILY_REFRESH_SECONDS = 24 * 60 * 60
FAILURE_RETRY_SECONDS = 6 * 60 * 60
REFRESH_GRACE_SECONDS = 60
MIN_SLEEP_SECONDS = 30
MAX_SLEEP_SECONDS = 60 * 60
MARKET_SNAPSHOT_TICKERS = ("2002.TW", "5314.TWO")
DISCLOSURE_SOURCES = frozenset({"annual_workforce", "esg_occupational_safety"})


def _fresh_source_stamp(audits: Any) -> float | None:
    """Return the oldest verified component timestamp, if both sources are fresh."""
    stamps: dict[str, float] = {}
    if not isinstance(audits, list):
        return None
    for row in audits:
        if not isinstance(row, dict) or row.get("source") not in DISCLOSURE_SOURCES:
            continue
        stamp = row.get("fetched_at_epoch")
        count = row.get("record_count")
        if (
            row.get("status") != "success"
            or isinstance(count, bool)
            or not isinstance(count, (int, float))
            or not math.isfinite(count)
            or count <= 0
            or row.get("stale") is not False
            or row.get("error_kind") not in (None, "")
            or isinstance(stamp, bool)
            or not isinstance(stamp, (int, float))
            or not math.isfinite(stamp)
        ):
            continue
        stamps[row["source"]] = float(stamp)
    if set(stamps) != DISCLOSURE_SOURCES:
        return None
    return min(stamps.values())


async def refresh_due_annual_disclosures(
    runtime: Any,
    schedule: dict[str, float],
    *,
    now: float | None = None,
    emit: Callable[[str], None] | None = None,
) -> dict[str, float]:
    """Refresh each exchange's shared annual dataset when its local due time arrives.

    The provider owns the 24-hour shared cache. This scheduler never forces a
    refresh, so a recent snapshot is reused without an HTTP request.
    """
    now = time.time() if now is None else float(now)
    emit = emit or (lambda _message: None)
    service = getattr(runtime, "data_refresh_service", None)
    if service is None:
        raise RuntimeError("Annual disclosure scheduler needs a data refresh service.")

    for ticker in MARKET_SNAPSHOT_TICKERS:
        if schedule.get(ticker, 0.0) > now:
            continue
        try:
            request = FetchRequest.from_ticker(ticker, record_provider_sla=True, force_refresh=False)
            result = await service.fetch_source_async(request, "annual_workforce")
            fetched_at = _fresh_source_stamp(getattr(result, "source_audit", None))
            if fetched_at is None:
                schedule[ticker] = now + FAILURE_RETRY_SECONDS
                emit(f"年度揭露快照刷新未完整成功：market={ticker[-3:]}, retry_hours=6")
                continue
            due_at = max(now + REFRESH_GRACE_SECONDS, fetched_at + DAILY_REFRESH_SECONDS + REFRESH_GRACE_SECONDS)
            schedule[ticker] = due_at
            emit(f"年度揭露快照已核驗：market={ticker[-3:]}, next_refresh_in_hours=24")
        except Exception as exc:
            schedule[ticker] = now + FAILURE_RETRY_SECONDS
            emit(f"年度揭露快照刷新失敗：market={ticker[-3:]}, error={type(exc).__name__}, retry_hours=6")
    return schedule


async def run_annual_disclosure_refresh_scheduler(
    runtime: Any,
    *,
    emit: Callable[[str], None] | None = None,
) -> None:
    """Run cache-aware annual disclosure refreshes for the life of the worker."""
    emit = emit or (lambda _message: None)
    schedule: dict[str, float] = {}
    while True:
        await refresh_due_annual_disclosures(runtime, schedule, emit=emit)
        now = time.time()
        next_due = min(schedule.values(), default=now + MAX_SLEEP_SECONDS)
        delay = min(MAX_SLEEP_SECONDS, max(MIN_SLEEP_SECONDS, next_due - now))
        await asyncio.sleep(delay)
