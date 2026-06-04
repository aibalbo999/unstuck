"""Importable analysis job entrypoints for local workers or RQ workers."""

import asyncio
import os
import time

from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from financial_data import async_fetch_stock_data
from job_store import append_event, update_job
from pipeline import run_analysis_pipeline_async
from report_gen import generate_html_report, generate_markdown_report


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


async def run_stock_analysis_job_async(job_id: str, ticker: str) -> str:
    """Run the full stock analysis and persist progress events for SSE clients."""
    ticker_upper = ticker.strip().upper()
    update_job(job_id, "running")

    try:
        if not has_api_keys():
            update_job(job_id, "error", error=API_KEY_SETUP_MESSAGE)
            append_event(job_id, {"type": "error", "message": API_KEY_SETUP_MESSAGE})
            return ""

        append_event(job_id, {"type": "status", "message": f"正在獲取 {ticker_upper} 財務數據..."})
        data = await async_fetch_stock_data(ticker_upper)
        if "error" in data:
            append_event(job_id, {"type": "status", "message": f"財務數據獲取有誤：{data['error']}，將繼續分析"})

        def progress_callback(current, total, name, phase="completed", message=None):
            if phase == "completed":
                append_event(job_id, {"type": "progress", "current": current, "total": total, "name": name})
                return

            append_event(job_id, {
                "type": "status",
                "message": message or f"{name} 進行中...",
                "detail": f"Agent {current}/{total} · {name}" if current and current <= total else str(name),
                "current": current,
                "total": total,
                "phase": phase,
            })

        append_event(job_id, {"type": "status", "message": "開始執行非同步分析 Agent..."})
        context = await run_analysis_pipeline_async(data, progress_callback=progress_callback)
        audit_notice = build_operator_audit_notice(context)

        if audit_notice["status"] == "needs_attention":
            append_event(job_id, {
                "type": "status",
                "message": audit_notice["message"],
            })
        elif audit_notice["status"] == "passed_with_notes":
            append_event(job_id, {"type": "status", "message": audit_notice["message"]})

        append_event(job_id, {"type": "status", "message": "生成 HTML / Markdown 報告..."})
        html_content = generate_html_report(context)
        md_content = generate_markdown_report(context)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_ticker = ticker_upper.replace(".", "_")
        filename = f"{safe_ticker}_report_{timestamp}.html"
        md_filename = f"{safe_ticker}_report_{timestamp}.md"

        with open(os.path.join(OUTPUT_DIR, filename), "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(os.path.join(OUTPUT_DIR, md_filename), "w", encoding="utf-8") as f:
            f.write(md_content)

        update_job(job_id, "done", filename=filename)
        append_event(job_id, {"type": "done", "filename": filename, "audit": audit_notice})
        return filename

    except Exception as e:
        message = str(e)
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message})
        raise


def run_stock_analysis_job(job_id: str, ticker: str) -> str:
    """Synchronous importable wrapper for RQ and local ThreadPool workers."""
    return asyncio.run(run_stock_analysis_job_async(job_id, ticker))
