import asyncio
import json
import os
import sys
import time
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

# 取得 api.py 所在目錄的絕對路徑，確保不論從哪裡啟動都能找到靜態檔案
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
from typing import Optional

from analysis_jobs import run_stock_analysis_job
from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, REPORT_CLEANUP_INTERVAL_SECONDS, REPORT_RETENTION_DAYS, TASK_QUEUE_BACKEND, has_api_keys
from job_store import append_event, create_job, find_active_job, get_events_since, get_job, mark_incomplete_jobs_abandoned, update_job
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
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


def print_streamed_event(job_id: str, payload: dict) -> None:
    if TASK_QUEUE_BACKEND != "rq":
        return
    event_type = payload.get("type", "event")
    message = payload.get("message") or payload.get("name") or payload.get("filename") or ""
    if event_type == "progress":
        message = f"Agent {payload.get('current')}/{payload.get('total')} 完成：{payload.get('name', '')}"
    detail = payload.get("detail")
    line = f"[stream {job_id[:8]}] {event_type}: {message}"
    if detail:
        line += f" | {detail}"
    print(line[:500], flush=True)


@app.on_event("startup")
async def start_report_cleanup_loop():
    if TASK_QUEUE_BACKEND == "local":
        abandoned = await asyncio.to_thread(
            mark_incomplete_jobs_abandoned,
            "伺服器已重啟，舊的本地分析任務已中止；請重新送出分析。",
        )
        if abandoned:
            print(f"已清理 {abandoned} 筆重啟後遺留的本地分析任務。", flush=True)

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


def clean_report_text(value: str, limit: int = 360) -> str:
    """Collapse report markdown/html text for compact API summaries."""
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def extract_section(markdown_text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown_text or "")
    return match.group("body").strip() if match else ""


def parse_recommendation_summary(filename: str) -> dict:
    """Extract the decision snapshot shown before opening a full report."""
    summary = {
        "recommendation": "N/A",
        "current_price": "N/A",
        "target_3m": "N/A",
        "target_6m": "N/A",
        "target_12m": "N/A",
        "confidence": "N/A",
        "summary": "",
    }
    if not is_safe_report_filename(filename, ".html"):
        return summary

    md_filename = filename[:-5] + ".md"
    md_path = os.path.join(OUTPUT_DIR, md_filename)
    if not os.path.exists(md_path):
        return summary

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()
    except OSError:
        return summary

    one_page = extract_section(markdown_text, "一頁式摘要")
    if one_page:
        summary["summary"] = clean_report_text(one_page)

    metrics_section = extract_section(markdown_text, "📊 關鍵指標")
    price_match = re.search(
        r"^\s*-\s*\*\*股價:\*\*\s*(?P<value>.+?)\s*$",
        metrics_section,
        re.MULTILINE,
    )
    if price_match:
        summary["current_price"] = clean_report_text(price_match.group("value"), limit=80)

    recommendation_section = extract_section(markdown_text, "🎯 最終投資建議")
    field_map = {
        "綜合建議": "recommendation",
        "3個月目標": "target_3m",
        "6個月目標": "target_6m",
        "12個月目標": "target_12m",
        "信心指數": "confidence",
    }
    for raw_label, key in field_map.items():
        match = re.search(
            rf"^\s*-\s*\*\*{re.escape(raw_label)}:\*\*\s*(?P<value>.+?)\s*$",
            recommendation_section,
            re.MULTILINE,
        )
        if match:
            summary[key] = clean_report_text(match.group("value"), limit=80)

    # Some older markdown reports may omit the top recommendation card but keep
    # the final block in the decision agent section.
    if summary["recommendation"] == "N/A":
        match = re.search(r"\[投資建議\](?P<body>.*?)\[/投資建議\]", markdown_text, re.DOTALL)
        if match:
            body = match.group("body")
            fallback_map = {
                "建議": "recommendation",
                "3個月": "target_3m",
                "6個月": "target_6m",
                "12個月": "target_12m",
                "信心": "confidence",
            }
            for label, key in fallback_map.items():
                field = re.search(rf"^\s*.*{label}.*?[：:]\s*(?P<value>.+?)\s*$", body, re.MULTILINE)
                if field:
                    summary[key] = clean_report_text(field.group("value"), limit=80)

    if not summary["summary"]:
        title_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
        if title_match:
            summary["summary"] = clean_report_text(title_match.group(1))

    return summary


def normalize_recommendation_label(value: str) -> str:
    text = str(value or "").strip()
    if "買入" in text or text.lower() == "buy":
        return "買入"
    if "避免" in text or "賣出" in text or text.lower() in {"avoid", "sell"}:
        return "避免"
    if "持有" in text or text.lower() == "hold":
        return "持有"
    return text or "N/A"


@app.get("/api/reports")
def get_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    q: str = Query("", max_length=80),
    pipeline: str = Query("all", max_length=24),
    recommendation: str = Query("all", max_length=24),
):
    """取得歷史報告清單"""
    cleanup_expired_reports()
    cleanup_orphan_markdown_reports()
    reports = []
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

    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            if filename.endswith(".html"):
                filepath = os.path.join(OUTPUT_DIR, filename)
                # Parse ticker, optional pipeline, and time from filename
                parts = filename.replace(".html", "").split("_report_")
                if len(parts) == 2:
                    raw_ticker = parts[0]
                    pipeline_id = "v1"
                    if raw_ticker.endswith("_v1") or raw_ticker.endswith("_v2"):
                        pipeline_id = raw_ticker[-2:]
                        raw_ticker = raw_ticker[:-3]
                    ticker = raw_ticker.replace("_", ".")
                    date_str = parts[1]
                    try:
                        dt = time.strptime(date_str, "%Y%m%d_%H%M%S")
                        formatted_date = time.strftime("%Y-%m-%d %H:%M", dt)
                    except:
                        formatted_date = date_str
                else:
                    ticker = filename
                    formatted_date = "未知時間"
                    pipeline_id = "v1"
                    
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

                recommendation_summary = parse_recommendation_summary(filename)
                if pipeline_filter != "all" and pipeline_id != pipeline_filter:
                    continue
                if (
                    recommendation_filter != "all"
                    and normalize_recommendation_label(recommendation_summary.get("recommendation")) != recommendation_filter
                ):
                    continue

                report = {
                    "filename": filename,
                    "ticker": ticker,
                    "company_name": company_name,
                    "date": formatted_date,
                    "timestamp": os.path.getmtime(filepath),
                    "pipeline_id": pipeline_id,
                    "pipeline_label": get_pipeline_definition(pipeline_id)["short_label"],
                    "recommendation": recommendation_summary,
                }
                searchable = f"{filename} {ticker} {company_name} {recommendation_summary.get('recommendation', '')}".lower()
                if query and query not in searchable:
                    continue
                reports.append(report)
    # 依時間遞減排序
    reports.sort(key=lambda x: x["timestamp"], reverse=True)
    total = len(reports)
    start = (page - 1) * limit
    end = start + limit
    page_reports = reports[start:end]
    total_pages = max((total + limit - 1) // limit, 1)
    return {
        "reports": page_reports,
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
        },
    }

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
async def analyze_stock(
    ticker: str,
    request: Request,
    job_id: Optional[str] = Query(None),
    last_event_id: Optional[int] = Query(None, ge=0),
    pipeline: str = Query("v1", max_length=24),
):
    """使用 SSE 即時推播分析進度"""
    ticker_upper = ticker.strip().upper()
    pipeline_id = normalize_pipeline_id(pipeline)
    pipeline_def = get_pipeline_definition(pipeline_id)

    if not has_api_keys():
        async def missing_key_event_generator():
            yield {"data": json.dumps({"type": "error", "message": API_KEY_SETUP_MESSAGE}, ensure_ascii=False)}

        return EventSourceResponse(missing_key_event_generator())

    header_last_event_id = request.headers.get("last-event-id")
    if last_event_id is None and header_last_event_id:
        try:
            last_event_id = int(header_last_event_id)
        except ValueError:
            last_event_id = 0
    resume_after_id = int(last_event_id or 0)

    should_enqueue = False
    with active_analyses_lock:
        requested_job = get_job(job_id) if job_id else {}
        if requested_job and requested_job.get("ticker") == ticker_upper and requested_job.get("pipeline_id", "v1") == pipeline_id:
            job_id = requested_job["job_id"]
        else:
            active_job = find_active_job(ticker_upper, pipeline_id)
            if active_job:
                job_id = active_job["job_id"]
            else:
                job_id = create_job(ticker_upper, pipeline_id)
                should_enqueue = True

    if should_enqueue:
        try:
            analysis_task_queue.enqueue(f"analysis:{job_id}", run_stock_analysis_job, job_id, ticker_upper, pipeline_id)
        except Exception as e:
            message = f"分析任務送入佇列失敗：{e}"
            update_job(job_id, "error", error=message)
            append_event(job_id, {"type": "error", "message": message})
        
    async def event_generator():
        last_sent_event_id = resume_after_id
        terminal_sent = False
        yield {
            "data": json.dumps(
                {
                    "type": "job",
                    "job_id": job_id,
                    "ticker": ticker_upper,
                    "resume_after_id": resume_after_id,
                    "pipeline_id": pipeline_id,
                    "pipeline_label": pipeline_def["label"],
                    "agent_total": len(pipeline_def["agents"]),
                },
                ensure_ascii=False,
            )
        }
        try:
            while True:
                events = await asyncio.to_thread(get_events_since, job_id, last_sent_event_id)
                for event in events:
                    last_sent_event_id = event["id"]
                    payload = event["payload"]
                    print_streamed_event(job_id, payload)
                    yield {"id": str(event["id"]), "data": json.dumps(payload, ensure_ascii=False)}

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
