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
            emit_log(f"每日決策追蹤刷新失敗：{type(exc).__name__}: {exc}")
        try:
            backtest_result = await asyncio.to_thread(
                decision_tracking_service.run_due_backtests,
                output_dir=get_output_dir(),
            )
            retryable = [row for row in backtest_result.get("skipped", []) if row.get("retryable") is True]
            emit_log(
                "每日決策追蹤回測輪詢完成："
                f"backtests={backtest_result.get('evaluated_count', 0)}, "
                f"skipped={len(backtest_result.get('skipped', []))}, "
                f"retryable_data_gaps={len(retryable)}, "
                f"errors={len(backtest_result.get('errors', []))}"
            )
            revisions = backtest_result.get("legacy_evidence_revisions", {})
            if revisions:
                from legacy_source_wait_log import source_wait_log, validation_rejection_log, revision_exception_log
                from legacy76_dispositions import BATCH_ID
                for wait in revisions.get('source_waits', []):
                    emit_log(source_wait_log(wait))
                for rejection in revisions.get('validation_rejections', []):
                    emit_log(validation_rejection_log(rejection))
                for error in revisions.get('errors', []):
                    if error.get('batch_id') == BATCH_ID:
                        emit_log(revision_exception_log(error))
                emit_log("歷史證據追加版本輪詢：" f"new={revisions.get('new_revisions', 0)}, evidence_session={revisions.get('as_of_evidence_session', 'unknown')}, awaiting_maturity={revisions.get('awaiting_maturity', 0)}, already_attempted_session={revisions.get('already_attempted_session', 0)}, already_terminal={revisions.get('already_terminal', 0)}, closed_unscored={revisions.get('closed_unscored', 0)}, validation_rejections={revisions.get('validation_rejection_count', 0)}, awaiting_source_evidence={revisions.get('awaiting_source_evidence', 0)}, source_wait_retryable=true, errors={len(revisions.get('errors', []))}")
        except Exception as exc:
            emit_log(f"每日決策追蹤回測失敗：{type(exc).__name__}: {exc}")
        await asyncio.sleep(interval_seconds)


async def run_decision_tracking_scheduler(
    *,
    get_output_dir: Callable[[], str],
    get_refresh_service: Callable[[], object],
    emit_log: Callable[[str], None],
    interval_seconds: int = 900,
) -> None:
    await _decision_tracking_scheduler_forever(
        get_output_dir=get_output_dir,
        get_refresh_service=get_refresh_service,
        emit_log=emit_log,
        interval_seconds=interval_seconds,
    )


def create_decision_tracking_scheduler_task(
    *,
    get_output_dir: Callable[[], str],
    get_refresh_service: Callable[[], object],
    emit_log: Callable[[str], None],
):
    return asyncio.create_task(
        run_decision_tracking_scheduler(
            get_output_dir=get_output_dir,
            get_refresh_service=get_refresh_service,
            emit_log=emit_log,
        )
    )
