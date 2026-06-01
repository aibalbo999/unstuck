import asyncio
import json
import os
import time
import re

# 取得 api.py 所在目錄的絕對路徑，確保不論從哪裡啟動都能找到靜態檔案
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
from typing import Optional

from analysis_jobs import run_stock_analysis_job
from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, REPORT_CLEANUP_INTERVAL_SECONDS, REPORT_RETENTION_DAYS, has_api_keys
from job_store import append_event, create_job, find_active_job, get_events_since, get_job, update_job
from task_queue import create_task_queue

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 掛載靜態網頁檔案
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 儲存分析結果的記憶體快取 (ticker -> filepath)
report_cache = {}
analysis_task_queue = create_task_queue()

# 全域鎖用於防範多裝置同時建立同一 ticker 任務。
active_analyses_lock = threading.Lock()


@app.on_event("startup")
async def start_report_cleanup_loop():
    async def cleanup_loop():
        while True:
            await asyncio.to_thread(cleanup_expired_reports)
            await asyncio.to_thread(cleanup_orphan_markdown_reports)
            await asyncio.sleep(REPORT_CLEANUP_INTERVAL_SECONDS)

    asyncio.create_task(cleanup_loop())


def is_safe_report_filename(filename: str, suffix: Optional[str] = None) -> bool:
    if "/" in filename or "\\" in filename or filename != os.path.basename(filename):
        return False
    if suffix and not filename.endswith(suffix):
        return False
    return True


def cleanup_expired_reports(retention_days: int = REPORT_RETENTION_DAYS):
    """刪除超過保留天數的 HTML/Markdown 報告，避免 output 無限成長。"""
    if not os.path.exists(OUTPUT_DIR) or retention_days <= 0:
        return []

    cutoff = time.time() - retention_days * 24 * 60 * 60
    deleted = []
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith((".html", ".md")):
            continue
        path = os.path.join(OUTPUT_DIR, filename)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted.append(filename)
        except OSError:
            pass

    if deleted:
        for ticker, cached_filename in list(report_cache.items()):
            if cached_filename in deleted:
                del report_cache[ticker]
    return deleted


def cleanup_orphan_markdown_reports():
    """移除沒有對應 HTML 的 Markdown 報告，避免前端刪除後後端殘留。"""
    if not os.path.exists(OUTPUT_DIR):
        return []

    html_stems = {
        os.path.splitext(filename)[0]
        for filename in os.listdir(OUTPUT_DIR)
        if filename.endswith(".html")
    }
    deleted = []
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith(".md"):
            continue
        stem = os.path.splitext(filename)[0]
        if stem in html_stems:
            continue
        path = os.path.join(OUTPUT_DIR, filename)
        try:
            os.remove(path)
            deleted.append(filename)
        except OSError:
            pass
    return deleted


@app.get("/api/reports")
def get_reports():
    """取得歷史報告清單"""
    cleanup_expired_reports()
    cleanup_orphan_markdown_reports()
    reports = []
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith(".html"):
                filepath = os.path.join(OUTPUT_DIR, filename)
                # Parse ticker and time from filename (e.g., 2449_TW_report_20260523_124313.html)
                parts = filename.replace(".html", "").split("_report_")
                if len(parts) == 2:
                    ticker = parts[0].replace("_", ".")
                    date_str = parts[1]
                    try:
                        dt = time.strptime(date_str, "%Y%m%d_%H%M%S")
                        formatted_date = time.strftime("%Y-%m-%d %H:%M", dt)
                    except:
                        formatted_date = date_str
                else:
                    ticker = filename
                    formatted_date = "未知時間"
                    
                # 動態解析 HTML 報告中的公司名稱
                company_name = ticker
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        match = re.search(r'<div class="sidebar-name">([^<]+)</div>', content)
                        if match:
                            company_name = match.group(1).strip()
                except Exception:
                    pass

                reports.append({
                    "filename": filename,
                    "ticker": ticker,
                    "company_name": company_name,
                    "date": formatted_date,
                    "timestamp": os.path.getmtime(filepath)
                })
    # 依時間遞減排序
    reports.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"reports": reports}

@app.delete("/api/reports/{filename}")
def delete_report(filename: str):
    """刪除特定歷史報告"""
    # 簡單防範路徑穿越
    if not is_safe_report_filename(filename, ".html"):
        return {"success": False, "error": "Invalid filename"}
        
    html_path = os.path.join(OUTPUT_DIR, filename)
    md_filename = filename[:-5] + ".md"
    md_path = os.path.join(OUTPUT_DIR, md_filename)

    if not os.path.exists(html_path) and not os.path.exists(md_path):
        return {"success": False, "error": "File not found"}

    deleted = []
    errors = []
    for path in [html_path, md_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted.append(os.path.basename(path))
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

    if errors:
        return {"success": False, "error": "; ".join(errors), "deleted": deleted}

    for ticker, cached_filename in list(report_cache.items()):
        if cached_filename == filename:
            del report_cache[ticker]

    return {"success": True, "deleted": deleted}

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/analyze/{ticker}")
async def analyze_stock(ticker: str):
    """使用 SSE 即時推播分析進度"""
    ticker_upper = ticker.strip().upper()

    if not has_api_keys():
        async def missing_key_event_generator():
            yield {"data": json.dumps({"type": "error", "message": API_KEY_SETUP_MESSAGE}, ensure_ascii=False)}

        return EventSourceResponse(missing_key_event_generator())

    should_enqueue = False
    with active_analyses_lock:
        active_job = find_active_job(ticker_upper)
        if active_job:
            job_id = active_job["job_id"]
        else:
            job_id = create_job(ticker_upper)
            should_enqueue = True

    if should_enqueue:
        try:
            analysis_task_queue.enqueue(f"analysis:{job_id}", run_stock_analysis_job, job_id, ticker_upper)
        except Exception as e:
            message = f"分析任務送入佇列失敗：{e}"
            update_job(job_id, "error", error=message)
            append_event(job_id, {"type": "error", "message": message})
        
    async def event_generator():
        last_event_id = 0
        terminal_sent = False
        try:
            while True:
                events = await asyncio.to_thread(get_events_since, job_id, last_event_id)
                for event in events:
                    last_event_id = event["id"]
                    payload = event["payload"]
                    yield {"data": json.dumps(payload, ensure_ascii=False)}

                    if payload.get("type") in ["done", "error"]:
                        terminal_sent = True
                        break

                if terminal_sent:
                    break

                job = await asyncio.to_thread(get_job, job_id)
                if job.get("status") in ["done", "error"]:
                    payload = (
                        {"type": "done", "filename": job.get("filename")}
                        if job.get("status") == "done"
                        else {"type": "error", "message": job.get("error", "分析任務失敗")}
                    )
                    yield {"data": json.dumps(payload, ensure_ascii=False)}
                    break

                if not events:
                    yield {"event": "ping", "data": "ping"}
                await asyncio.sleep(0.5)
        finally:
            pass

                
    return EventSourceResponse(event_generator())

@app.get("/api/report/{filename}")
async def get_report(filename: str):
    """取得生成的 HTML 報告"""
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="text/html")
    return HTMLResponse("<h1>找不到報告</h1>", status_code=404)

@app.get("/api/report/{filename}/download/html")
async def download_html_report(filename: str):
    """下載生成的 HTML 報告"""
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, filename=filename, media_type="text/html", headers={"Content-Disposition": f"attachment; filename={filename}"})
    return HTMLResponse("<h1>找不到報告</h1>", status_code=404)

@app.get("/api/report/{filename}/download/md")
async def download_md_report(filename: str):
    """下載生成的 Markdown 報告"""
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    md_filename = filename.replace(".html", ".md")
    filepath = os.path.join(OUTPUT_DIR, md_filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, filename=md_filename, media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename={md_filename}"})
    return HTMLResponse("<h1>找不到報告 Markdown 版本</h1>", status_code=404)
