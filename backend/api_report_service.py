"""Report API business logic shared by route handlers and tests."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from agent_runtime import AnalysisRequest
from agent_runtime.quality_gates import run_agent_with_quality_gates_async
from config import API_KEYS, REPORT_RETENTION_DAYS
from final_audit import run_final_report_audit
from llm_client import KeyRotator
from data_fetch import FetchRequest
from data_trust import build_data_snapshot, data_snapshot_filename_for_report, normalize_data_trust
from pipeline_modes import get_pipeline_definition, get_structured_agent_num, normalize_pipeline_id
from report_index import (
    delete_report_metadata,
    is_safe_report_filename,
    normalize_recommendation_label,
    parse_report_filename,
    parse_recommendation_summary as parse_report_recommendation_summary,
    query_report_metadata,
    upsert_report_metadata,
)
from reporting import ReportRequest
from structured_outputs import parse_structured_data


ANALYSIS_TEXT_STALE_MESSAGE = "資料快照已刷新，但 HTML/Markdown 分析本文未重新執行；投資結論仍以原報告生成時間為準。"
RERUN_SCOPE_LABELS = {
    "final_recommendation": "只重跑最終建議",
    "mode_b": "只重跑模式 B",
}


def parse_recommendation_summary(filename: str, output_dir: str) -> dict:
    return parse_report_recommendation_summary(filename, output_dir=output_dir)


def cleanup_expired_reports(
    output_dir: str,
    report_cache: dict,
    retention_days: int = REPORT_RETENTION_DAYS,
) -> list[str]:
    """刪除超過保留天數的 HTML/Markdown/資料快照，避免 output 無限成長。"""
    if not os.path.exists(output_dir) or retention_days <= 0:
        return []

    cutoff = time.time() - retention_days * 24 * 60 * 60
    deleted = []
    for filename in os.listdir(output_dir):
        if not filename.endswith((".html", ".md", ".data.json")):
            continue
        path = os.path.join(output_dir, filename)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted.append(filename)
                if filename.endswith(".html"):
                    delete_report_metadata(filename, output_dir)
        except OSError:
            pass

    if deleted:
        for ticker, cached_filename in list(report_cache.items()):
            if cached_filename in deleted:
                del report_cache[ticker]
    return deleted


def cleanup_orphan_markdown_reports(output_dir: str) -> list[str]:
    """移除沒有對應 HTML 的 Markdown 報告與資料快照。"""
    if not os.path.exists(output_dir):
        return []

    html_stems = {
        os.path.splitext(filename)[0]
        for filename in os.listdir(output_dir)
        if filename.endswith(".html")
    }
    deleted = []
    for filename in os.listdir(output_dir):
        if not filename.endswith((".md", ".data.json")):
            continue
        stem = filename[:-10] if filename.endswith(".data.json") else os.path.splitext(filename)[0]
        if stem in html_stems:
            continue
        path = os.path.join(output_dir, filename)
        try:
            os.remove(path)
            deleted.append(filename)
        except OSError:
            pass
    return deleted


def list_reports(
    *,
    page: int,
    limit: int,
    q: str,
    pipeline: str,
    recommendation: str,
    data_trust: str,
    output_dir: str,
    report_cache: dict,
) -> dict:
    cleanup_expired_reports(output_dir, report_cache)
    cleanup_orphan_markdown_reports(output_dir)
    query = q.strip().lower()
    pipeline_filter = pipeline.strip().lower()
    if pipeline_filter in {"mode_a", "a", "academic"}:
        pipeline_filter = "v1"
    elif pipeline_filter in {"mode_b", "b", "trading"}:
        pipeline_filter = "v2"
    if pipeline_filter not in {"all", "v1", "v2"}:
        pipeline_filter = "all"

    recommendation_filter = normalize_recommendation_label(recommendation)
    if recommendation_filter not in {"買入", "持有", "避免"}:
        recommendation_filter = "all"
    data_trust_value = data_trust if isinstance(data_trust, str) else "all"
    data_trust_filter = data_trust_value.strip().lower()
    if data_trust_filter not in {"all", "fresh", "partial", "stale", "error", "unknown"}:
        data_trust_filter = "all"

    if os.path.exists(output_dir):
        reports, total = query_report_metadata(
            page=page,
            limit=limit,
            q=query,
            pipeline=pipeline_filter,
            recommendation=recommendation_filter,
            data_trust=data_trust_filter,
            output_dir=output_dir,
        )
    else:
        reports, total = [], 0

    total_pages = max((total + limit - 1) // limit, 1)
    return {
        "reports": reports,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "query": q,
            "pipeline": pipeline_filter,
            "recommendation": recommendation_filter,
            "data_trust": data_trust_filter,
        },
    }


def delete_report_files(filename: str, output_dir: str, report_cache: dict) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        return {"success": False, "error": "Invalid filename"}

    html_path = os.path.join(output_dir, filename)
    md_filename = filename[:-5] + ".md"
    data_filename = data_snapshot_filename_for_report(filename)
    md_path = os.path.join(output_dir, md_filename)
    data_path = os.path.join(output_dir, data_filename)

    if not os.path.exists(html_path) and not os.path.exists(md_path) and not os.path.exists(data_path):
        return {"success": False, "error": "File not found"}

    deleted = []
    errors = []
    for path in [html_path, md_path, data_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted.append(os.path.basename(path))
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

    if errors:
        return {"success": False, "error": "; ".join(errors), "deleted": deleted}

    for ticker, cached_filename in list(report_cache.items()):
        if cached_filename == filename:
            del report_cache[ticker]
    delete_report_metadata(filename, output_dir)
    return {"success": True, "deleted": deleted}


def get_report_file(filename: str, output_dir: str):
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = os.path.join(output_dir, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    return HTMLResponse("<h1>找不到報告</h1>", status_code=404)


def download_report_file(filename: str, output_dir: str, kind: str):
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    if kind == "html":
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            return FileResponse(
                filepath,
                filename=filename,
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        return HTMLResponse("<h1>找不到報告</h1>", status_code=404)
    if kind == "md":
        md_filename = filename.replace(".html", ".md")
        filepath = os.path.join(output_dir, md_filename)
        if os.path.exists(filepath):
            return FileResponse(
                filepath,
                filename=md_filename,
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename={md_filename}"},
            )
        return HTMLResponse("<h1>找不到報告 Markdown 版本</h1>", status_code=404)
    if kind == "data":
        data_filename = data_snapshot_filename_for_report(filename)
        filepath = os.path.join(output_dir, data_filename)
        if os.path.exists(filepath):
            return FileResponse(
                filepath,
                filename=data_filename,
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={data_filename}"},
            )
        return HTMLResponse("<h1>找不到報告資料快照</h1>", status_code=404)
    raise ValueError(f"Unknown report download kind: {kind}")


def _source_status_map(snapshot: dict) -> dict:
    status_map = {}
    entries = snapshot.get("source_audit", []) if isinstance(snapshot, dict) else []
    if not isinstance(entries, list):
        return status_map
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "unknown")
        provider = str(entry.get("provider") or "unknown")
        status_map[(source, provider)] = {
            "source": source,
            "provider": provider,
            "status": str(entry.get("status") or "unknown"),
            "message": str(entry.get("message") or entry.get("error_kind") or "")[:160],
        }
    return status_map


def refresh_data_diff(previous_snapshot: dict, refreshed_snapshot: dict) -> dict:
    before_trust = normalize_data_trust(previous_snapshot.get("data_trust") if isinstance(previous_snapshot, dict) else None)
    after_trust = normalize_data_trust(refreshed_snapshot.get("data_trust") if isinstance(refreshed_snapshot, dict) else None)
    before_stale = set(before_trust.get("stale_sources", []) or [])
    after_stale = set(after_trust.get("stale_sources", []) or [])
    before_failures = set(before_trust.get("critical_failures", []) or [])
    after_failures = set(after_trust.get("critical_failures", []) or [])
    before_status = _source_status_map(previous_snapshot)
    after_status = _source_status_map(refreshed_snapshot)
    source_status_changes = []
    for key in sorted(set(before_status) | set(after_status)):
        before = before_status.get(key, {"source": key[0], "provider": key[1], "status": "missing", "message": ""})
        after = after_status.get(key, {"source": key[0], "provider": key[1], "status": "missing", "message": ""})
        if before["status"] != after["status"]:
            source_status_changes.append({
                "source": key[0],
                "provider": key[1],
                "before": before["status"],
                "after": after["status"],
                "message": after.get("message") or before.get("message") or "",
            })

    summary = []
    if before_trust.get("status") != after_trust.get("status"):
        summary.append(f"可信度 {before_trust.get('status')} → {after_trust.get('status')}")
    removed_stale = sorted(before_stale - after_stale)
    added_stale = sorted(after_stale - before_stale)
    removed_failures = sorted(before_failures - after_failures)
    added_failures = sorted(after_failures - before_failures)
    if removed_stale:
        summary.append("解除過期：" + "、".join(removed_stale[:4]))
    if added_stale:
        summary.append("新增過期：" + "、".join(added_stale[:4]))
    if removed_failures:
        summary.append("解除核心異常：" + "、".join(removed_failures[:4]))
    if added_failures:
        summary.append("新增核心異常：" + "、".join(added_failures[:4]))
    if not summary:
        summary.append("資料可信度狀態未變更")

    return {
        "data_trust_status": {
            "before": before_trust.get("status"),
            "after": after_trust.get("status"),
            "changed": before_trust.get("status") != after_trust.get("status"),
        },
        "stale_sources": {"removed": removed_stale, "added": added_stale},
        "critical_failures": {"removed": removed_failures, "added": added_failures},
        "source_status_changes": source_status_changes[:20],
        "summary": summary,
    }


async def refresh_report_data_snapshot(
    filename: str,
    *,
    output_dir: str,
    refresh_service: Any,
) -> dict:
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    html_path = os.path.join(output_dir, filename)
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="找不到報告")

    data_filename = data_snapshot_filename_for_report(filename)
    data_path = os.path.join(output_dir, data_filename)
    if not os.path.exists(data_path):
        raise HTTPException(status_code=404, detail="舊報告沒有資料快照，無法只刷新資料")

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            previous_snapshot = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"資料快照無法讀取：{exc}") from exc

    ticker = str(previous_snapshot.get("ticker") or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="資料快照缺少 ticker")

    result = await refresh_service.fetch_async(FetchRequest.from_ticker(ticker, force_refresh=True))
    refreshed_data = result.data or {}
    if not isinstance(refreshed_data, dict) or "error" in refreshed_data:
        message = refreshed_data.get("error") if isinstance(refreshed_data, dict) else "資料刷新失敗"
        raise HTTPException(status_code=502, detail=message)

    context = {
        "ticker": refreshed_data.get("ticker") or ticker,
        "company_name": refreshed_data.get("company_name") or previous_snapshot.get("company_name") or ticker,
        "pipeline_id": previous_snapshot.get("pipeline"),
        "data": refreshed_data,
        "deterministic_fallbacks": previous_snapshot.get("deterministic_fallbacks", []),
        "report_lint": previous_snapshot.get("report_lint", {}),
        "refreshed_from_report": filename,
        "refreshed_without_analysis_rerun": True,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE,
    }
    refreshed_snapshot = build_data_snapshot(context, pipeline_id=previous_snapshot.get("pipeline"))
    refreshed_snapshot["refreshed_without_analysis_rerun"] = True
    refreshed_snapshot["analysis_text_stale_message"] = ANALYSIS_TEXT_STALE_MESSAGE
    refresh_diff = refresh_data_diff(previous_snapshot, refreshed_snapshot)

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(refreshed_snapshot, f, ensure_ascii=False, indent=2)
    metadata = upsert_report_metadata(
        filename,
        output_dir=output_dir,
        data_trust=refreshed_snapshot.get("data_trust"),
    )
    return {
        "success": True,
        "filename": filename,
        "data_filename": data_filename,
        "data_trust": refreshed_snapshot.get("data_trust"),
        "source_audit": refreshed_snapshot.get("source_audit", [])[:12],
        "refresh_diff": refresh_diff,
        "analysis_text_stale": True,
        "analysis_text_stale_message": ANALYSIS_TEXT_STALE_MESSAGE,
        "metadata": metadata or {},
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
        AnalysisRequest(data=data, pipeline_id="v2", progress_callback=progress_callback)
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
