"""Partial report rerun services."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from fastapi import HTTPException

from agent_runtime import AnalysisRequest
from agent_runtime.cancellation import attach_cancel_check
from agent_runtime.quality_gates import run_agent_with_quality_gates_async
from config import API_KEYS
from data_trust import data_snapshot_filename_for_report
from final_audit import run_final_report_audit
from llm_client import KeyRotator
from pipeline_modes import get_pipeline_definition, get_structured_agent_num, normalize_pipeline_id
from report_index import is_safe_report_filename, parse_report_filename, upsert_report_metadata
from reporting import ReportRequest
from structured_outputs import parse_structured_data


RERUN_SCOPE_LABELS = {
    "final_recommendation": "只重跑最終建議",
    "mode_b": "只重跑模式 B",
}


def normalize_rerun_scope(scope: str) -> str:
    value = str(scope or "final_recommendation").strip().lower().replace("-", "_")
    aliases = {
        "final": "final_recommendation",
        "recommendation": "final_recommendation",
        "final_agent": "final_recommendation",
        "modeb": "mode_b",
        "v2": "mode_b",
        "trading": "mode_b",
    }
    value = aliases.get(value, value)
    if value not in RERUN_SCOPE_LABELS:
        raise HTTPException(status_code=400, detail="scope must be final_recommendation or mode_b")
    return value


def _read_report_snapshot(filename: str, output_dir: str) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    data_path = os.path.join(output_dir, data_snapshot_filename_for_report(filename))
    if not os.path.exists(data_path):
        raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法局部重跑")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"資料快照無法讀取：{exc}") from exc
    if not isinstance(snapshot.get("data"), dict):
        raise HTTPException(status_code=400, detail="資料快照缺少可重跑的 data payload")
    return snapshot


def _read_report_markdown(filename: str, output_dir: str) -> str:
    md_path = os.path.join(output_dir, filename[:-5] + ".md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=404, detail="找不到原始 Markdown，無法還原前序 Agent 段落")
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Markdown 無法讀取：{exc}") from exc


def parse_agent_sections_from_markdown(markdown_text: str) -> dict[int, str]:
    heading_re = re.compile(r"^##\s+\d+\.\s+.*?\(Agent\s+(\d+)\)\s*$", re.MULTILINE)
    matches = list(heading_re.finditer(markdown_text or ""))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        agent_num = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        body = markdown_text[start:end]
        body = re.split(r"\n---\n\n##\s+(?:來源審計|📚)", body, maxsplit=1)[0]
        body = re.sub(r"\n---\s*$", "", body.strip())
        if body:
            sections[agent_num] = body.strip()
    return sections


def _coerce_agent_map(value: Any) -> dict[int, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[int, Any] = {}
    for key, item in value.items():
        try:
            agent_num = int(key)
        except (TypeError, ValueError):
            continue
        result[agent_num] = item
    return result


def _rerun_context_from_snapshot(snapshot: dict) -> tuple[dict[int, str], dict[int, Any]]:
    rerun_context = snapshot.get("rerun_context") if isinstance(snapshot.get("rerun_context"), dict) else {}
    analyses = {
        agent_num: str(text)
        for agent_num, text in _coerce_agent_map(rerun_context.get("analyses")).items()
        if str(text or "").strip()
    }
    structured_outputs = _coerce_agent_map(rerun_context.get("structured_outputs"))
    return analyses, structured_outputs


def _rerun_report_filename(ticker: str, pipeline_id: str) -> tuple[str, str, str]:
    safe_ticker = str(ticker or "report").strip().upper().replace(".", "_").replace("/", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_ticker}_{pipeline_id}_report_{timestamp}.html"
    md_filename = f"{safe_ticker}_{pipeline_id}_report_{timestamp}.md"
    data_filename = data_snapshot_filename_for_report(filename)
    return filename, md_filename, data_filename


async def _render_and_save_rerun_report(
    *,
    context: dict,
    pipeline_id: str,
    output_dir: str,
    report_renderer: Any,
    scope: str,
    source_filename: str,
) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    filename, md_filename, data_filename = _rerun_report_filename(context.get("ticker"), pipeline_id)
    context["partial_rerun"] = {
        "scope": scope,
        "label": RERUN_SCOPE_LABELS[scope],
        "source_report": source_filename,
        "generated_report": filename,
    }
    report_bundle = await report_renderer.render_async(
        ReportRequest(
            context=context,
            pipeline_id=pipeline_id,
            filename=filename,
        )
    )
    data_snapshot = dict(report_bundle.data_snapshot)
    data_snapshot["partial_rerun"] = context["partial_rerun"]
    data_snapshot["rerun_from_report"] = source_filename
    data_snapshot["rerun_scope"] = scope

    with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
        f.write(report_bundle.html)
    with open(os.path.join(output_dir, md_filename), "w", encoding="utf-8") as f:
        f.write(report_bundle.markdown)
    with open(os.path.join(output_dir, data_filename), "w", encoding="utf-8") as f:
        json.dump(data_snapshot, f, ensure_ascii=False, indent=2)

    metadata = upsert_report_metadata(
        filename,
        output_dir=output_dir,
        html_content=report_bundle.html,
        markdown_content=report_bundle.markdown,
        data_trust=data_snapshot.get("data_trust"),
    )
    return {
        "success": True,
        "scope": scope,
        "scope_label": RERUN_SCOPE_LABELS[scope],
        "source_filename": source_filename,
        "filename": filename,
        "md_filename": md_filename,
        "data_filename": data_filename,
        "data_trust": data_snapshot.get("data_trust"),
        "partial_rerun": context["partial_rerun"],
        "metadata": metadata or {},
    }


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
    context = analysis_result.context
    return await _render_and_save_rerun_report(
        context=context,
        pipeline_id="v2",
        output_dir=output_dir,
        report_renderer=report_renderer,
        scope="mode_b",
        source_filename=source_filename,
    )


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
    data = dict(snapshot.get("data") or {})
    pipeline_id = normalize_pipeline_id(snapshot.get("pipeline") or parse_report_filename(filename)["pipeline_id"])
    pipeline_def = get_pipeline_definition(pipeline_id)
    final_agent = get_structured_agent_num("recommendation", pipeline_id)
    if final_agent is None:
        raise HTTPException(status_code=400, detail="此 pipeline 沒有可重跑的最終建議 Agent")

    analyses, structured_outputs = _rerun_context_from_snapshot(snapshot)
    required_previous = [agent for agent in pipeline_def["agents"] if agent < final_agent]
    missing = [agent for agent in required_previous if agent not in analyses]
    if missing:
        markdown_text = _read_report_markdown(filename, output_dir)
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
    attach_cancel_check(context, cancel_check)
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
    await run_agent_with_quality_gates_async(final_agent, data, context, rotator)
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

    return await _render_and_save_rerun_report(
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

    snapshot = _read_report_snapshot(filename, output_dir)
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
