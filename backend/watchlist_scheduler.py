"""Background scheduler for due watchlist batch analyses."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import watchlist_service


def _run_due_watchlist_batch(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    emit_log: Callable[[str], None],
) -> dict:
    due_items = watchlist_service.due_watchlist_items()
    if not due_items:
        return {"success": True, "queued": [], "skipped": []}
    result = watchlist_service.enqueue_watchlist_items(
        due_items,
        create_job=create_job,
        find_active_job=find_active_job,
        task_queue=task_queue,
        run_stock_analysis_job=run_stock_analysis_job,
    )
    queued_count = len(result.get("queued") or [])
    skipped_count = len(result.get("skipped") or [])
    emit_log(f"watchlist 批次分析：queued={queued_count}, skipped={skipped_count}")
    return result


async def _watchlist_scheduler_forever(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    emit_log: Callable[[str], None],
    interval_seconds: int = 60,
) -> None:
    while True:
        try:
            await asyncio.to_thread(
                _run_due_watchlist_batch,
                create_job=create_job,
                find_active_job=find_active_job,
                task_queue=task_queue,
                run_stock_analysis_job=run_stock_analysis_job,
                emit_log=emit_log,
            )
        except Exception as exc:
            emit_log(f"watchlist 批次分析檢查失敗：{exc}")
        await asyncio.sleep(interval_seconds)


def create_watchlist_scheduler_task(
    *,
    create_job: Callable[[str, str], str],
    find_active_job: Callable[[str, str], dict],
    task_queue: Any,
    run_stock_analysis_job: Callable[[str, str, str], str],
    emit_log: Callable[[str], None],
) -> asyncio.Task:
    return asyncio.create_task(
        _watchlist_scheduler_forever(
            create_job=create_job,
            find_active_job=find_active_job,
            task_queue=task_queue,
            run_stock_analysis_job=run_stock_analysis_job,
            emit_log=emit_log,
        )
    )
