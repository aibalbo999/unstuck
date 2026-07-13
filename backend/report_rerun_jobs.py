"""Background job entrypoints for partial report reruns."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException

from agent_runtime import AnalysisPipelineRunner
from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from data_trust import sanitize_for_snapshot
from data_fetch import StockDataService
from job_store import append_event, is_job_cancel_requested, update_job
from mapping_fields import safe_int, safe_mapping_dict, safe_text
import report_rerun_service
from reporting import ReportRenderer
from runtime_dependencies import create_report_storage_for_output_dir
from storage.report_storage import ReportStorage


PIPELINE_RUNNER = AnalysisPipelineRunner()
REPORT_RENDERER = ReportRenderer()
REFRESH_SERVICE = StockDataService()


class ReportRerunJobCancelled(Exception):
    pass


def _raise_if_cancelled(job_id: str) -> None:
    if is_job_cancel_requested(job_id):
        raise ReportRerunJobCancelled("報告重跑任務已取消。")


def _scope_label(scope: str) -> str:
    try:
        normalized = report_rerun_service.normalize_rerun_scope(scope)
    except HTTPException:
        normalized = str(scope or "final_recommendation")
    return report_rerun_service.RERUN_SCOPE_LABELS.get(normalized, normalized)


def _result_text(payload: dict[str, Any], key: str, default: str = "") -> str:
    text = safe_text(dict.get(payload, key)).strip()
    return text or default


def _error_message(value: Any, default: str) -> str:
    text = safe_text(value).strip()
    return text or default


def _source_filename(value: Any) -> str:
    return safe_text(value).strip()


def _scope_value(value: Any, default: str = "final_recommendation") -> str:
    text = safe_text(value).strip().lower().replace("-", "_")
    return text or default


def _event_control_text(value: Any, default: str = "") -> str:
    if isinstance(value, Mapping) or isinstance(value, (list, tuple, set, frozenset)):
        return default
    text = safe_text(value).strip()
    return text or default


def _http_status_code(value: Any, default: int = 500) -> int:
    status_code = safe_int(value)
    if 100 <= status_code <= 599:
        return status_code
    return default


def _append_progress_event(job_id: str, filename: str, scope: str, raw_event: Any) -> None:
    _raise_if_cancelled(job_id)
    event_map = safe_mapping_dict(raw_event) or {}
    event_payload = sanitize_for_snapshot(event_map)
    event = event_payload if isinstance(event_payload, dict) else {}
    if not event:
        event = {
            "type": "progress",
            "current": safe_int(raw_event),
            "total": 1,
            "name": "報告重跑",
        }
    event["type"] = _event_control_text(dict.get(event, "type"), "status")
    event["phase"] = _event_control_text(dict.get(event, "phase"), "rerun")
    level = _event_control_text(dict.get(event, "level"))
    if level:
        event["level"] = level
    else:
        event.pop("level", None)
    if "current" in event:
        event["current"] = safe_int(dict.get(event, "current"))
    if "total" in event:
        event["total"] = safe_int(dict.get(event, "total"))
    if "agent_num" in event:
        event["agent_num"] = safe_int(dict.get(event, "agent_num"))
    if "pipeline_id" in event:
        event["pipeline_id"] = _event_control_text(dict.get(event, "pipeline_id"))
    if "pipeline_label" in event:
        event["pipeline_label"] = _event_control_text(dict.get(event, "pipeline_label"))
    if "metadata" in event:
        event["metadata"] = safe_mapping_dict(dict.get(event, "metadata")) or {}
    if "message" in event:
        event["message"] = _event_control_text(dict.get(event, "message"))
    if "name" in event:
        event["name"] = _event_control_text(dict.get(event, "name"))
    if "detail" in event:
        event["detail"] = _event_control_text(dict.get(event, "detail"))
    event["rerun_scope"] = _scope_value(scope)
    event["source_filename"] = _source_filename(filename)
    append_event(job_id, event)


async def run_report_rerun_job_async(
    job_id: str,
    filename: str,
    scope: str = "final_recommendation",
    *,
    output_dir: str = OUTPUT_DIR,
    pipeline_runner: Any = None,
    report_renderer: Any = None,
    refresh_service: Any = None,
    storage: ReportStorage | None = None,
) -> str:
    """Run a partial report rerun and persist job events for SSE clients."""
    event_source_filename = _source_filename(filename)
    normalized_scope = _scope_value(scope)
    scope_label = _scope_label(normalized_scope)

    try:
        normalized_scope = report_rerun_service.normalize_rerun_scope(scope)
        scope_label = _scope_label(normalized_scope)
        update_job(job_id, "running")

        if not has_api_keys():
            update_job(job_id, "error", error=API_KEY_SETUP_MESSAGE)
            append_event(job_id, {
                "type": "error",
                "message": API_KEY_SETUP_MESSAGE,
                "rerun_scope": normalized_scope,
                "source_filename": event_source_filename,
            })
            return ""

        _raise_if_cancelled(job_id)
        append_event(job_id, {
            "type": "status",
            "phase": "rerun_start",
            "message": f"開始{scope_label}重跑...",
            "rerun_scope": normalized_scope,
            "source_filename": event_source_filename,
        })

        def progress_callback(event):
            _append_progress_event(job_id, filename, normalized_scope, event)

        report_storage = storage or create_report_storage_for_output_dir(output_dir)
        result = await report_rerun_service.rerun_report_analysis(
            filename,
            scope=normalized_scope,
            output_dir=output_dir,
            pipeline_runner=pipeline_runner or PIPELINE_RUNNER,
            report_renderer=report_renderer or REPORT_RENDERER,
            refresh_service=refresh_service or REFRESH_SERVICE,
            progress_callback=progress_callback,
            cancel_check=lambda: _raise_if_cancelled(job_id),
            storage=report_storage,
        )
        _raise_if_cancelled(job_id)
        result_map = safe_mapping_dict(result) or {}
        result_payload = sanitize_for_snapshot(result_map)
        if not isinstance(result_payload, dict):
            result_payload = {}
        result_metadata = safe_mapping_dict(dict.get(result_payload, "metadata")) or {}
        generated_filename = _result_text(result_payload, "filename")
        generated_md_filename = _result_text(result_payload, "md_filename")
        generated_data_filename = _result_text(result_payload, "data_filename")
        generated_scope_label = _result_text(result_payload, "scope_label", scope_label)
        generated_pipeline_id = _result_text(result_metadata, "pipeline_id") or _result_text(result_payload, "pipeline_id")
        generated_data_trust = safe_mapping_dict(dict.get(result_payload, "data_trust")) or {}
        generated_partial_rerun = safe_mapping_dict(dict.get(result_payload, "partial_rerun")) or {}
        update_job(job_id, "done", filename=generated_filename)
        report_event = {
            "type": "report_done",
            "filename": generated_filename,
            "md_filename": generated_md_filename,
            "data_filename": generated_data_filename,
            "data_trust": generated_data_trust,
            "rerun_scope": normalized_scope,
            "source_filename": event_source_filename,
            "scope_label": generated_scope_label,
            "partial_rerun": generated_partial_rerun,
            "pipeline_id": generated_pipeline_id,
        }
        append_event(job_id, report_event)
        append_event(job_id, {
            "type": "done",
            "filename": generated_filename,
            "md_filename": generated_md_filename,
            "data_filename": generated_data_filename,
            "data_trust": generated_data_trust,
            "rerun_scope": normalized_scope,
            "source_filename": event_source_filename,
            "scope_label": generated_scope_label,
        })
        return generated_filename

    except ReportRerunJobCancelled as exc:
        message = _error_message(exc, "報告重跑任務已取消。")
        update_job(job_id, "cancelled", error=message)
        append_event(job_id, {
            "type": "error",
            "phase": "cancelled",
            "level": "warning",
            "message": message,
            "rerun_scope": normalized_scope,
            "source_filename": event_source_filename,
        })
        return ""
    except HTTPException as exc:
        message = _error_message(exc.detail, "報告重跑失敗")
        update_job(job_id, "error", error=message)
        append_event(job_id, {
            "type": "error",
            "status_code": _http_status_code(exc.status_code),
            "message": message,
            "rerun_scope": normalized_scope,
            "source_filename": event_source_filename,
        })
        return ""
    except Exception as exc:
        message = _error_message(exc, "報告重跑失敗")
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message, "rerun_scope": normalized_scope, "source_filename": event_source_filename})
        raise


def run_report_rerun_job(job_id: str, filename: str, scope: str = "final_recommendation") -> str:
    """Importable wrapper for local async queue or RQ workers.

    In local mode the caller is LocalAsyncQueue._worker which already runs
    inside an asyncio event loop.  Calling asyncio.run() inside a running loop
    raises RuntimeError and the job silently stays stuck in 'queued' forever.
    Instead, return the bare coroutine so _worker can detect it via
    inspect.isawaitable() and await it directly — the same pattern used by
    run_stock_analysis_job().

    In RQ / non-local mode there is no running loop, so asyncio.run() is safe.
    """
    from config import TASK_QUEUE_BACKEND
    if TASK_QUEUE_BACKEND == "local":
        return run_report_rerun_job_async(job_id, filename, scope)
    return asyncio.run(run_report_rerun_job_async(job_id, filename, scope))
