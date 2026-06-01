"""Importable analysis job entrypoints for local workers or RQ workers."""

import asyncio
import os
import time

from agent_runner import run_analysis_pipeline_async
from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from financial_data import async_fetch_stock_data
from job_store import append_event, update_job
from report_gen import generate_html_report, generate_markdown_report


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

        def progress_callback(current, total, name):
            append_event(job_id, {"type": "progress", "current": current, "total": total, "name": name})

        append_event(job_id, {"type": "status", "message": "開始執行非同步分析 Agent..."})
        context = await run_analysis_pipeline_async(data, progress_callback=progress_callback)

        if context.get("blocking_issues"):
            issue_text = "；".join(context["blocking_issues"][:3])
            message = f"報告未儲存：公司身分一致性檢查未通過。{issue_text}"
            update_job(job_id, "error", error=message)
            append_event(job_id, {"type": "error", "message": message})
            return ""

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
        append_event(job_id, {"type": "done", "filename": filename})
        return filename

    except Exception as e:
        message = str(e)
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message})
        raise


def run_stock_analysis_job(job_id: str, ticker: str) -> str:
    """Synchronous importable wrapper for RQ and local ThreadPool workers."""
    return asyncio.run(run_stock_analysis_job_async(job_id, ticker))
