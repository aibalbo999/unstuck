"""Background job entrypoints for partial report reruns."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from agent_runtime import AnalysisPipelineRunner
from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from data_fetch import StockDataService
from job_store import append_event, is_job_cancel_requested, update_job
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


def _append_progress_event(job_id: str, filename: str, scope: str, raw_event: Any) -> None:
    _raise_if_cancelled(job_id)
    event = dict(raw_event) if isinstance(raw_event, dict) else {}
    if not event:
        event = {
            "type": "progress",
            "current": int(raw_event or 0),
            "total": 1,
            "name": "報告重跑",
        }
    event.setdefault("type", "status")
    event.setdefault("phase", "rerun")
    event["rerun_scope"] = scope
    event["source_filename"] = filename
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
    normalized_scope = report_rerun_service.normalize_rerun_scope(scope)
    scope_label = _scope_label(normalized_scope)
    update_job(job_id, "running")

    try:
        if not has_api_keys():
            update_job(job_id, "error", error=API_KEY_SETUP_MESSAGE)
            append_event(job_id, {"type": "error", "message": API_KEY_SETUP_MESSAGE, "rerun_scope": normalized_scope})
            return ""

        _raise_if_cancelled(job_id)
        append_event(job_id, {
            "type": "status",
            "phase": "rerun_start",
            "message": f"開始{scope_label}重跑...",
            "rerun_scope": normalized_scope,
            "source_filename": filename,
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
        generated_filename = result.get("filename", "")
        update_job(job_id, "done", filename=generated_filename)
        report_event = {
            "type": "report_done",
            "filename": generated_filename,
            "md_filename": result.get("md_filename"),
            "data_filename": result.get("data_filename"),
            "data_trust": result.get("data_trust"),
            "rerun_scope": normalized_scope,
            "source_filename": filename,
            "scope_label": result.get("scope_label", scope_label),
            "partial_rerun": result.get("partial_rerun"),
            "pipeline_id": result.get("metadata", {}).get("pipeline_id") or result.get("pipeline_id"),
        }
        append_event(job_id, report_event)
        append_event(job_id, {
            "type": "done",
            "filename": generated_filename,
            "md_filename": result.get("md_filename"),
            "data_filename": result.get("data_filename"),
            "data_trust": result.get("data_trust"),
            "rerun_scope": normalized_scope,
            "source_filename": filename,
            "scope_label": result.get("scope_label", scope_label),
        })
        return generated_filename

    except ReportRerunJobCancelled as exc:
        message = str(exc)
        update_job(job_id, "cancelled", error=message)
        append_event(job_id, {
            "type": "error",
            "phase": "cancelled",
            "level": "warning",
            "message": message,
            "rerun_scope": normalized_scope,
            "source_filename": filename,
        })
        return ""
    except HTTPException as exc:
        message = str(exc.detail or "報告重跑失敗")
        update_job(job_id, "error", error=message)
        append_event(job_id, {
            "type": "error",
            "status_code": exc.status_code,
            "message": message,
            "rerun_scope": normalized_scope,
            "source_filename": filename,
        })
        return ""
    except Exception as exc:
        message = str(exc)
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message, "rerun_scope": normalized_scope, "source_filename": filename})
        raise


def run_report_rerun_job(job_id: str, filename: str, scope: str = "final_recommendation") -> str:
    """Synchronous importable wrapper for local ThreadPool or RQ workers."""
    return asyncio.run(run_report_rerun_job_async(job_id, filename, scope))
