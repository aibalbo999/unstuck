"""Background scheduler for due watchlist batch analyses."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextvars import copy_context
from datetime import datetime
from functools import partial
from threading import Event
from typing import Any

import market_screener
from report_freshness_summary import safe_bool
import watchlist_service


SCREENER_SCHEDULE_TIME = "18:00"


def _run_due_watchlist_batch(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    emit_log: Callable[[str], None],
    stop_event: Event | None = None,
) -> dict:
    if stop_event is not None and stop_event.is_set():
        return {"success": True, "queued": [], "skipped": [], "errors": [], "interrupted": True}
    due_items = watchlist_service.claim_due_watchlist_items()
    if not due_items:
        return {"success": True, "queued": [], "skipped": []}
    result = watchlist_service.enqueue_watchlist_items(
        due_items,
        create_job=create_job,
        find_active_job=find_active_job,
        task_queue=task_queue,
        run_stock_analysis_job=run_stock_analysis_job,
        **({'stop_event': stop_event} if stop_event is not None else {}),
    )
    queued_count = len(result.get("queued") or [])
    skipped_count = len(result.get("skipped") or [])
    emit_log(f"watchlist 批次分析：queued={queued_count}, skipped={skipped_count}, errors={len(result.get('errors') or [])}")
    return result


def _screener_due(now) -> bool:
    hour, minute = [int(part) for part in SCREENER_SCHEDULE_TIME.split(":", 1)]
    return now >= now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _run_daily_market_screener(
    *,
    emit_log: Callable[[str], None],
    now=None,
) -> dict:
    now = now or datetime.now(watchlist_service.TAIPEI)
    run_date = now.date().isoformat()
    if not _screener_due(now):
        return {"success": True, "skipped": [{"reason": "before_daily_screener_time"}]}
    if market_screener.screener_already_ran(run_date):
        return {"success": True, "skipped": [{"reason": "already_ran", "run_date": run_date}]}
    result = market_screener.run_daily_market_screener(now=now)
    if safe_bool(result.get("success")):
        market_screener.mark_screener_ran(run_date)
    emit_log(
        "daily screener："
        f"candidates={result.get('candidate_count', 0)}, "
        f"imported={result.get('imported_count', 0)}, "
        f"errors={len(result.get('errors') or [])}, "
        f"warnings={len(result.get('warnings') or [])}"
    )
    return result


async def _watchlist_scheduler_forever(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    data_service: Any,
    emit_log: Callable[[str], None],
    interval_seconds: int = 60,
) -> None:
    while True:
        try:
            stop_event = Event()
            # Keep the actual executor future private: cancelling all asyncio
            # tasks must not mark the producer complete while its thread runs.
            batch = asyncio.get_running_loop().run_in_executor(None, copy_context().run, partial(
                _run_due_watchlist_batch,
                create_job=create_job,
                find_active_job=find_active_job,
                task_queue=task_queue,
                run_stock_analysis_job=run_stock_analysis_job,
                emit_log=emit_log,
                stop_event=stop_event,
            ))
            try:
                await asyncio.shield(batch)
            except asyncio.CancelledError as cancelled:
                stop_event.set()
                while not batch.done():
                    try:
                        await asyncio.shield(batch)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                try:
                    batch.result()
                except Exception as exc:
                    emit_log(f"watchlist 關閉時批次收尾失敗：{type(exc).__name__}")
                raise cancelled
            await asyncio.to_thread(_run_daily_market_screener, emit_log=emit_log)
            trigger_result = await watchlist_service.monitor_watchlist_triggers(
                data_service=data_service,
                create_job=create_job,
                find_active_job=find_active_job,
                task_queue=task_queue,
                run_stock_analysis_job=run_stock_analysis_job,
            )
            if trigger_result.get("queued") or trigger_result.get("errors"):
                emit_log(
                    "watchlist 事件雷達："
                    f"triggered={len(trigger_result.get('queued') or [])}, "
                    f"errors={len(trigger_result.get('errors') or [])}"
                )
        except Exception as exc:
            emit_log(f"watchlist 批次分析檢查失敗：{type(exc).__name__}: {exc}")
        await asyncio.sleep(interval_seconds)


async def run_watchlist_scheduler(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    data_service: Any,
    emit_log: Callable[[str], None],
    interval_seconds: int = 60,
) -> None:
    await _watchlist_scheduler_forever(
        create_job=create_job,
        find_active_job=find_active_job,
        task_queue=task_queue,
        run_stock_analysis_job=run_stock_analysis_job,
        data_service=data_service,
        emit_log=emit_log,
        interval_seconds=interval_seconds,
    )


def create_watchlist_scheduler_task(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    data_service: Any,
    emit_log: Callable[[str], None],
) -> asyncio.Task:
    return asyncio.create_task(
        run_watchlist_scheduler(
            create_job=create_job,
            find_active_job=find_active_job,
            task_queue=task_queue,
            run_stock_analysis_job=run_stock_analysis_job,
            data_service=data_service,
            emit_log=emit_log,
        )
    )
