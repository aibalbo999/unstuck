"""Align RQ's delayed retry with the model's actual recovery deadline."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from analysis_job_payloads import analysis_task_id


def prepare_analysis_retry(job_id: str, error: Exception, *, task_id: str | None = None) -> dict:
    waits = [60.0]
    for name in ("retry_wait_seconds", "key_cooldown_seconds"):
        value = getattr(error, name, None)
        if isinstance(value, (int, float)) and math.isfinite(value):
            waits.append(float(value))
    wait = math.ceil(max(waits))
    remaining = None
    preparation_error = None
    try:
        from rq import get_current_job

        job = get_current_job()
        if job is not None and job.id == (task_id or analysis_task_id(job_id)):
            remaining = int(job.retries_left or 0)
            if remaining > 0:
                meta = dict(getattr(job, "meta", None) or {})
                baseline = meta.setdefault("analysis_base_retry_intervals", list(job.retry_intervals or [60]))
                job.retry_intervals = [max(wait, int(interval)) for interval in baseline]
                job.meta = meta
                job.save()
                get_interval = getattr(job, "get_retry_interval", None)
                if callable(get_interval):
                    wait = max(wait, int(get_interval()))
    except Exception as exc:
        # A failed read/write leaves scheduling unconfirmed, not proven absent.
        # Keep callers on their terminal branch without leaking connection detail.
        remaining = None
        preparation_error = type(exc).__name__
    scheduled = remaining is not None and remaining > 0
    return {
        "retry_after_seconds": wait,
        "retry_at": (datetime.now(timezone.utc) + timedelta(seconds=wait)).isoformat() if scheduled else None,
        "retry_scheduled": scheduled,
        "retry_budget_exhausted": remaining == 0,
        "queue_retries_left": remaining,
        "routes": list(getattr(error, "routes", []) or []),
        **({"retry_preparation_error": preparation_error} if preparation_error else {}),
    }


def build_analysis_retry_event(error: Exception, retry: dict, *, rerun: bool = False) -> dict:
    """Share retry notices without promising an unconfirmed automatic retry."""
    scheduled = retry["retry_scheduled"]
    if scheduled:
        message = (
            f"模型暫時不可用，至少 {retry['retry_after_seconds']} 秒後重試；既有報告保持不變。"
            if rerun else
            f"模型暫時不可用；進度已保留，至少 {retry['retry_after_seconds']} 秒後重試，不產生缺段報告。"
        )
    elif retry["retry_budget_exhausted"]:
        message = (
            "模型仍不可用且自動重試次數已用完，請稍後重新送出。"
            if rerun else
            "模型仍不可用且自動重試次數已用完；進度已保留，請稍後重新送出。"
        )
    else:
        message = (
            "模型暫時不可用，但無法確認自動重試排程；既有報告保持不變，請稍後手動重新送出。"
            if rerun else
            "模型暫時不可用，但無法確認自動重試排程；任務已停止，請稍後手動重新送出。"
        )
    return {
        "type": "status" if scheduled else "error",
        "phase": "workflow_retry",
        "level": "warning",
        "message": message,
        "error": str(error) if scheduled else message,
        **retry,
    }
