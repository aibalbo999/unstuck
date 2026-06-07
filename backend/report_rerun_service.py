"""Partial report rerun orchestration services."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import HTTPException

from agent_runtime import AnalysisRequest
from agent_runtime.cancellation import attach_cancel_check
from agent_runtime.quality_gates import run_agent_with_quality_gates_async
from config import API_KEYS
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
from structured_outputs import parse_structured_data


async def _run_full_pipeline_rerun(
    *,
    snapshot: dict,
    output_dir: str,
    pipeline_runner: Any,
    report_renderer: Any,
    source_filename: str,
    progress_callback: Any = None,
    cancel_check: Any = None,
) -> dict:
    data = dict(snapshot.get("data") or {})
    if not data:
        raise HTTPException(status_code=400, detail="資料快照缺少 data payload")
    if callable(cancel_check):
        cancel_check()
    analysis_result = await pipeline_runner.run_async(
        AnalysisRequest(data=data, pipeline_id="v2", progress_callback=progress_callback, cancel_check=cancel_check)
    )
    if callable(cancel_check):
        cancel_check()
    return await render_and_save_rerun_report(
        context=analysis_result.context,
        pipeline_id="v2",
        output_dir=output_dir,
        report_renderer=report_renderer,
        scope="mode_b",
        source_filename=source_filename,
    )


def _build_final_rerun_context(filename: str, snapshot: dict, output_dir: str) -> tuple[dict, dict, int]:
    data = dict(snapshot.get("data") or {})
    pipeline_id = normalize_pipeline_id(snapshot.get("pipeline") or parse_report_filename(filename)["pipeline_id"])
    pipeline_def = get_pipeline_definition(pipeline_id)
    final_agent = get_structured_agent_num("recommendation", pipeline_id)
    if final_agent is None:
        raise HTTPException(status_code=400, detail="此 pipeline 沒有可重跑的最終建議 Agent")

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
        "company_name": snapshot.get("company_name") or data.get("company_name") or data.get("ticker"),
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
    progress_callback: Any = None,
    cancel_check: Any = None,
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
    )


async def rerun_report_analysis(
    filename: str,
    *,
    scope: str,
    output_dir: str,
    pipeline_runner: Any,
    report_renderer: Any,
    progress_callback: Any = None,
    cancel_check: Any = None,
) -> dict:
    normalized_scope = normalize_rerun_scope(scope)
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not os.path.exists(os.path.join(output_dir, filename)):
        raise HTTPException(status_code=404, detail="找不到報告")

    snapshot = read_report_snapshot(filename, output_dir)
    if normalized_scope == "mode_b":
        return await _run_full_pipeline_rerun(
            snapshot=snapshot,
            output_dir=output_dir,
            pipeline_runner=pipeline_runner,
            report_renderer=report_renderer,
            source_filename=filename,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )
    return await _run_final_recommendation_rerun(
        filename=filename,
        snapshot=snapshot,
        output_dir=output_dir,
        report_renderer=report_renderer,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )


__all__ = [
    "RERUN_SCOPE_LABELS",
    "normalize_rerun_scope",
    "parse_agent_sections_from_markdown",
    "rerun_report_analysis",
]
