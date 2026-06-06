"""Importable analysis job entrypoints for local workers or RQ workers."""

import asyncio
import os
import time

from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from financial_data import async_fetch_stock_data
from job_store import append_event, update_job
from pipeline import run_analysis_pipeline_async
from pipeline_modes import (
    get_pipeline_definition,
    get_pipeline_run_agent_total,
    get_pipeline_run_label,
    get_pipeline_run_sequence,
    normalize_pipeline_run_id,
)
from report_gen import generate_html_report_async, generate_markdown_report


def build_operator_audit_notice(context: dict) -> dict:
    """Summarize final audit state for progress events and UI notices."""
    audit = context.get("final_audit", {}) or {}
    critical = list(audit.get("critical", []) or [])
    blocking = [
        issue for issue in (context.get("blocking_issues", []) or [])
        if issue not in critical
    ]
    warnings = list(audit.get("warnings", []) or [])
    corrections = list(audit.get("corrections", []) or [])
    repair_log = list(context.get("audit_repair_log", []) or [])

    if critical or blocking:
        issues = [*critical[:5], *blocking[:3]]
        first_issue = issues[0] if issues else "最終稽核仍有異常"
        return {
            "status": "needs_attention",
            "message": f"最終稽核仍有異常，報告已保留並標示提醒：{first_issue}",
            "issues": issues,
            "repair_log": repair_log[:5],
        }

    if warnings or corrections or repair_log:
        details = [*warnings[:3], *corrections[:3], *repair_log[:3]]
        return {
            "status": "passed_with_notes",
            "message": "最終稽核已通過；系統曾自動修復或套用非阻斷校正。",
            "issues": details,
            "repair_log": repair_log[:5],
        }

    return {"status": "passed", "message": "最終稽核已通過。", "issues": [], "repair_log": []}


async def run_stock_analysis_job_async(job_id: str, ticker: str, pipeline_id: str = "v1") -> str:
    """Run the full stock analysis and persist progress events for SSE clients."""
    ticker_upper = ticker.strip().upper()
    run_id = normalize_pipeline_run_id(pipeline_id)
    pipeline_sequence = get_pipeline_run_sequence(run_id)
    run_label = get_pipeline_run_label(run_id)
    total_agents = get_pipeline_run_agent_total(run_id)
    update_job(job_id, "running")

    try:
        if not has_api_keys():
            update_job(job_id, "error", error=API_KEY_SETUP_MESSAGE)
            append_event(job_id, {"type": "error", "message": API_KEY_SETUP_MESSAGE})
            return ""

        append_event(job_id, {
            "type": "status",
            "message": f"正在獲取 {ticker_upper} 財務數據...",
            "pipeline_id": run_id,
            "pipeline_label": run_label,
            "pipeline_sequence": list(pipeline_sequence),
        })
        data = await async_fetch_stock_data(ticker_upper)
        if "error" in data:
            append_event(job_id, {"type": "status", "message": f"財務數據獲取有誤：{data['error']}，將繼續分析"})

        reports = []
        completed_agent_offset = 0
        sequence_total = len(pipeline_sequence)

        for sequence_index, current_pipeline_id in enumerate(pipeline_sequence, start=1):
            pipeline_def = get_pipeline_definition(current_pipeline_id)
            agent_count = len(pipeline_def["agents"])
            append_event(job_id, {
                "type": "status",
                "message": f"開始執行 {pipeline_def['label']}（{sequence_index}/{sequence_total}，{agent_count} 位 Agent）...",
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
                "pipeline_index": sequence_index,
                "pipeline_total": sequence_total,
                "agent_total": total_agents,
            })
            append_event(job_id, {
                "type": "pipeline_start",
                "message": f"開始第 {sequence_index}/{sequence_total} 段：{pipeline_def['label']}",
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
                "pipeline_index": sequence_index,
                "pipeline_total": sequence_total,
                "agent_offset": completed_agent_offset,
                "agent_total": total_agents,
            })

            def progress_callback(current, total, name, phase="completed", message=None):
                current = int(current or 0)
                local_total = int(total or agent_count)
                global_current = min(total_agents, completed_agent_offset + max(current, 0))
                event_name = f"{pipeline_def['short_label']} · {name}" if sequence_total > 1 else name
                if phase == "completed":
                    append_event(job_id, {
                        "type": "progress",
                        "current": global_current,
                        "total": total_agents,
                        "name": event_name,
                        "pipeline_id": current_pipeline_id,
                        "pipeline_label": pipeline_def["label"],
                        "pipeline_current": current,
                        "pipeline_total": local_total,
                    })
                    return

                detail = (
                    f"{pipeline_def['short_label']} Agent {current}/{local_total} · {name}"
                    if current and current <= local_total
                    else f"{pipeline_def['short_label']} · {name}"
                )
                append_event(job_id, {
                    "type": "status",
                    "message": message or f"{event_name} 進行中...",
                    "detail": detail,
                    "current": global_current,
                    "total": total_agents,
                    "phase": phase,
                    "pipeline_id": current_pipeline_id,
                    "pipeline_label": pipeline_def["label"],
                    "pipeline_current": current,
                    "pipeline_total": local_total,
                })

            context = await run_analysis_pipeline_async(dict(data), progress_callback=progress_callback, pipeline_id=current_pipeline_id)
            audit_notice = build_operator_audit_notice(context)

            if audit_notice["status"] == "needs_attention":
                append_event(job_id, {
                    "type": "status",
                    "message": audit_notice["message"],
                    "pipeline_id": current_pipeline_id,
                    "pipeline_label": pipeline_def["label"],
                })
            elif audit_notice["status"] == "passed_with_notes":
                append_event(job_id, {
                    "type": "status",
                    "message": audit_notice["message"],
                    "pipeline_id": current_pipeline_id,
                    "pipeline_label": pipeline_def["label"],
                })

            append_event(job_id, {
                "type": "status",
                "message": f"生成 {pipeline_def['short_label']} HTML / Markdown 報告...",
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
            })
            html_content = await generate_html_report_async(context)
            md_content = generate_markdown_report(context)

            os.makedirs(OUTPUT_DIR, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_ticker = ticker_upper.replace(".", "_")
            filename = f"{safe_ticker}_{current_pipeline_id}_report_{timestamp}.html"
            md_filename = f"{safe_ticker}_{current_pipeline_id}_report_{timestamp}.md"

            with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
                f.write(html_content)
            with open(os.path.join(OUTPUT_DIR, md_filename), "w", encoding="utf-8") as f:
                f.write(md_content)

            report_event = {
                "type": "report_done",
                "filename": filename,
                "md_filename": md_filename,
                "audit": audit_notice,
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
                "pipeline_index": sequence_index,
                "pipeline_total": sequence_total,
            }
            reports.append(report_event)
            append_event(job_id, report_event)
            completed_agent_offset += agent_count

        final_report = reports[-1] if reports else {}
        final_filename = final_report.get("filename", "")
        final_pipeline_id = final_report.get("pipeline_id", pipeline_sequence[-1])
        final_audit = final_report.get("audit", {"status": "passed", "message": "最終稽核已通過。", "issues": []})

        update_job(job_id, "done", filename=final_filename)
        append_event(job_id, {
            "type": "done",
            "filename": final_filename,
            "filenames": [report["filename"] for report in reports],
            "reports": reports,
            "audit": final_audit,
            "pipeline_id": run_id,
            "pipeline_label": run_label,
            "pipeline_sequence": list(pipeline_sequence),
            "last_pipeline_id": final_pipeline_id,
        })
        return final_filename

    except Exception as e:
        message = str(e)
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message})
        raise


def run_stock_analysis_job(job_id: str, ticker: str, pipeline_id: str = "v1") -> str:
    """Synchronous importable wrapper for RQ and local ThreadPool workers."""
    return asyncio.run(run_stock_analysis_job_async(job_id, ticker, pipeline_id))
