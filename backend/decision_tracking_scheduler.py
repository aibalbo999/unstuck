"""Background scheduler for daily decision tracking price refreshes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import decision_tracking_service


async def _decision_tracking_scheduler_forever(
    *,
    get_output_dir: Callable[[], str],
    get_refresh_service: Callable[[], object],
    emit_log: Callable[[str], None],
    interval_seconds: int = 900,
) -> None:
    while True:
        try:
            result = await decision_tracking_service.refresh_tracking_items(
                output_dir=get_output_dir(),
                refresh_service=get_refresh_service(),
                due_only=True,
            )
            if result.get("updated_count") or result.get("errors"):
                emit_log(
                    "每日決策追蹤刷新："
                    f"updated={result.get('updated_count', 0)}, errors={len(result.get('errors', []))}"
                )
        except Exception as exc:
            emit_log(f"每日決策追蹤刷新失敗：{exc}")
        await asyncio.sleep(interval_seconds)


def create_decision_tracking_scheduler_task(
    *,
    get_output_dir: Callable[[], str],
    get_refresh_service: Callable[[], object],
    emit_log: Callable[[str], None],
):
    return asyncio.create_task(
        _decision_tracking_scheduler_forever(
            get_output_dir=get_output_dir,
            get_refresh_service=get_refresh_service,
            emit_log=emit_log,
        )
    )
