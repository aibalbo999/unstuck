"""Partial report rerun orchestration services."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import HTTPException

from agent_runtime import AnalysisRequest
from agent_runtime.cancellation import attach_cancel_check
from agent_runtime.quality_gates import run_agent_with_quality_gates_async
from company_display import company_display_name
from config import API_KEYS
from data_fetch import FetchRequest
from final_audit import run_final_report_audit
from llm_client import KeyRotator
from pipeline_modes import get_pipeline_definition, get_structured_agent_num, normalize_pipeline_id
from report_index import is_safe_report_filename, parse_report_filename
from report_rerun_context import (
    RERUN_SCOPE_LABELS,
    normalize_rerun_scope,
    parse_agent_sections_from_markdown,
    read_report_markdown,
    read_report_snapshot,
    rerun_context_from_snapshot,
)
from report_rerun_rendering import render_and_save_rerun_report
from storage.report_storage import ReportStorage
from structured_outputs import parse_structured_data


async def _run_full_pipeline_rerun(
    *,
    snapshot: dict,
    output_dir: str,
    pipeline_runner: Any,
    report_renderer: Any,
    source_filename: str,
    pipeline_id: str,
    scope: str,
    refresh_service: Any = None,
    progress_callback: Any = None,
    cancel_check: Any = None,
    storage: ReportStorage | None = None,
) -> dict:
    data = dict(snapshot.get("data") or {})
    if not data:
        raise HTTPException(status_code=400, detail="資料快照缺少 data payload")
    if refresh_service is not None:
        ticker = str(snapshot.get("ticker") or data.get("ticker") or "").strip().upper()
        if not ticker:
            raise HTTPException(status_code=400, detail="資料快照缺少 ticker，無法完整重抓資料")
        if callable(progress_callback):
            progress_callback({
                "type": "status",
                "phase": "rerun_refresh_data",
                "message": "完整重跑前正在刷新資料快照...",
                "pipeline_id": pipeline_id,
            })
        fetch_result = await refresh_service.fetch_async(
            FetchRequest.from_ticker(ticker, force_refresh=True)
        )
        refreshed_data = fetch_result.data or {}
        if not isinstance(refreshed_data, dict) or refreshed_data.get("error"):
            message = refreshed_data.get("error") if isinstance(refreshed_data, dict) else "資料刷新失敗"
            raise HTTPException(status_code=502, detail=f"完整重跑前資料刷新失敗：{message}")
        data = refreshed_data
    if callable(cancel_check):
        cancel_check()
    analysis_result = await pipeline_runner.run_async(
        AnalysisRequest(data=data, pipeline_id=pipeline_id, progress_callback=progress_callback, cancel_check=cancel_check)
    )
    if callable(cancel_check):
        cancel_check()
    return await render_and_save_rerun_report(
        context=analysis_result.context,
        pipeline_id=pipeline_id,
        output_dir=output_dir,
        report_renderer=report_renderer,
        scope=scope,
        source_filename=source_filename,
        storage=storage,
    )


def _build_final_rerun_context(filename: str, snapshot: dict, output_dir: str) -> tuple[dict, dict, int]:
    data = dict(snapshot.get("data") or {})
    pipeline_id = normalize_pipeline_id(snapshot.get("pipeline") or parse_report_filename(filename)["pipeline_id"])
    pipeline_def = get_pipeline_definition(pipeline_id)
    final_agent = get_structured_agent_num("recommendation", pipeline_id)
    if final_agent is None:
        raise HTTPException(status_code=400, detail="此 pipeline 沒有可重跑的最終建議 Agent")
    if snapshot.get("refreshed_without_analysis_rerun") or snapshot.get("decision_validity_status") == "needs_rerun":
        reason = str(snapshot.get("requires_rerun_reason") or snapshot.get("analysis_text_stale_message") or "").strip()
        detail = "資料快照已刷新，但前序分析、估值與風險段落仍來自舊資料；請使用完整重跑產生一致報告。"
        if reason:
            detail = f"{detail} 原因：{reason}"
        raise HTTPException(status_code=409, detail=detail)

    analyses, structured_outputs = rerun_context_from_snapshot(snapshot)
    required_previous = [agent for agent in pipeline_def["agents"] if agent < final_agent]
    missing = [agent for agent in required_previous if agent not in analyses]
    if missing:
        markdown_text = read_report_markdown(filename, output_dir)
        markdown_analyses = parse_agent_sections_from_markdown(markdown_text)
        analyses.update({agent: text for agent, text in markdown_analyses.items() if agent not in analyses})
    missing = [agent for agent in required_previous if agent not in analyses]
    if missing:
        raise HTTPException(status_code=409, detail=f"原始報告缺少前序 Agent 段落，無法只重跑最終建議：{missing}")
    analyses.pop(final_agent, None)
    structured_outputs.pop(final_agent, None)

    context = {
        "ticker": snapshot.get("ticker") or data.get("ticker"),
        "company_name": company_display_name(data, snapshot.get("company_name") or data.get("ticker")),
        "data": data,
        "analyses": analyses,
        "structured_outputs": structured_outputs,
        "start_time": time.time(),
        "execution_mode": "partial_rerun",
        "pipeline_id": pipeline_def["id"],
        "pipeline_label": pipeline_def["label"],
        "agent_sequence": pipeline_def["agents"],
        "agent_positions": {final_agent: len(pipeline_def["agents"])},
        "agent_total": len(pipeline_def["agents"]),
    }
    return context, pipeline_def, final_agent


async def _run_final_recommendation_rerun(
    *,
    filename: str,
    snapshot: dict,
    output_dir: str,
    report_renderer: Any,
    refresh_service: Any = None,
    progress_callback: Any = None,
    cancel_check: Any = None,
    storage: ReportStorage | None = None,
) -> dict:
    if callable(cancel_check):
        cancel_check()
    context, pipeline_def, final_agent = _build_final_rerun_context(filename, snapshot, output_dir)
    attach_cancel_check(context, cancel_check)
    required_previous = [agent for agent in pipeline_def["agents"] if agent < final_agent]
    if callable(progress_callback):
        progress_callback({
            "type": "status",
            "phase": "rerun_final_agent",
            "message": f"重跑 {pipeline_def['label']} 最終投資建議 Agent...",
            "current": len(required_previous),
            "total": len(pipeline_def["agents"]),
            "name": f"Agent {final_agent}",
            "agent_num": final_agent,
            "pipeline_id": pipeline_def["id"],
            "pipeline_label": pipeline_def["label"],
        })
    if callable(cancel_check):
        cancel_check()
    rotator = KeyRotator(API_KEYS)
    await run_agent_with_quality_gates_async(final_agent, context["data"], context, rotator)
    if callable(cancel_check):
        cancel_check()
    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    context["total_time"] = time.time() - context["start_time"]
    if callable(progress_callback):
        progress_callback({
            "type": "progress",
            "phase": "completed",
            "message": "最終投資建議重跑完成。",
            "current": len(pipeline_def["agents"]),
            "total": len(pipeline_def["agents"]),
            "name": f"Agent {final_agent}",
            "agent_num": final_agent,
            "pipeline_id": pipeline_def["id"],
            "pipeline_label": pipeline_def["label"],
        })

    return await render_and_save_rerun_report(
        context=context,
        pipeline_id=pipeline_def["id"],
        output_dir=output_dir,
        report_renderer=report_renderer,
        scope="final_recommendation",
        source_filename=filename,
        storage=storage,
    )


async def rerun_report_analysis(
    filename: str,
    *,
    scope: str,
    output_dir: str,
    pipeline_runner: Any,
    report_renderer: Any,
    refresh_service: Any = None,
    progress_callback: Any = None,
    cancel_check: Any = None,
    storage: ReportStorage | None = None,
) -> dict:
    normalized_scope = normalize_rerun_scope(scope)
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not os.path.exists(os.path.join(output_dir, filename)):
        raise HTTPException(status_code=404, detail="找不到報告")

    snapshot = read_report_snapshot(filename, output_dir)
    source_pipeline_id = normalize_pipeline_id(snapshot.get("pipeline") or parse_report_filename(filename)["pipeline_id"])
    if normalized_scope == "full_report":
        return await _run_full_pipeline_rerun(
            snapshot=snapshot,
            output_dir=output_dir,
            pipeline_runner=pipeline_runner,
            report_renderer=report_renderer,
            source_filename=filename,
            pipeline_id=source_pipeline_id,
            scope="full_report",
            refresh_service=refresh_service,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            storage=storage,
        )
    if normalized_scope == "mode_b":
        return await _run_full_pipeline_rerun(
            snapshot=snapshot,
            output_dir=output_dir,
            pipeline_runner=pipeline_runner,
            report_renderer=report_renderer,
            source_filename=filename,
            pipeline_id="v2",
            scope="mode_b",
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            storage=storage,
        )
    return await _run_final_recommendation_rerun(
        filename=filename,
        snapshot=snapshot,
        output_dir=output_dir,
        report_renderer=report_renderer,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
        storage=storage,
    )


__all__ = [
    "RERUN_SCOPE_LABELS",
    "normalize_rerun_scope",
    "parse_agent_sections_from_markdown",
    "rerun_report_analysis",
]
