import asyncio
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

# 取得 api.py 所在目錄的絕對路徑，確保不論從哪裡啟動都能找到靜態檔案
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
from typing import Optional

from analysis_jobs import run_stock_analysis_job
from config import ALLOWED_ORIGINS, API_KEY_SETUP_MESSAGE, OUTPUT_DIR, REPORT_CLEANUP_INTERVAL_SECONDS, REPORT_RETENTION_DAYS, TASK_QUEUE_BACKEND, has_api_keys
from data_fetch import FetchRequest, StockDataService
from data_trust import build_data_snapshot, data_snapshot_filename_for_report
from job_store import (
    append_event,
    create_job,
    find_active_job,
    get_events_since,
    get_job,
    mark_incomplete_jobs_abandoned,
    request_job_cancel,
    update_job,
)
from pipeline_modes import (
    get_pipeline_run_agent_total,
    get_pipeline_run_label,
    get_pipeline_run_sequence,
    normalize_pipeline_run_id,
)
from provider_sla import get_provider_sla_alerts, get_provider_sla_summary
from report_index import (
    delete_report_metadata,
    is_safe_report_filename,
    normalize_recommendation_label,
    parse_recommendation_summary as parse_report_recommendation_summary,
    query_report_metadata,
    upsert_report_metadata,
)
from runtime_events import emit_log, format_event_log_line
from task_queue import create_task_queue

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials="*" not in ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 掛載靜態網頁檔案
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 儲存分析結果的記憶體快取 (ticker -> filepath)
report_cache = {}
analysis_task_queue = create_task_queue()
data_refresh_service = StockDataService()

# 全域鎖用於防範多裝置同時建立同一 ticker 任務。
active_analyses_lock = threading.Lock()


def parse_recommendation_summary(filename: str) -> dict:
    return parse_report_recommendation_summary(filename, output_dir=OUTPUT_DIR)


def print_streamed_event(job_id: str, payload: dict) -> None:
    if TASK_QUEUE_BACKEND != "rq":
        return
    emit_log(format_event_log_line(job_id, payload, prefix="stream"))


@app.on_event("startup")
async def start_report_cleanup_loop():
    if TASK_QUEUE_BACKEND == "local":
        abandoned = await asyncio.to_thread(
            mark_incomplete_jobs_abandoned,
            "伺服器已重啟，舊的本地分析任務已中止；請重新送出分析。",
        )
        if abandoned:
            emit_log(f"已清理 {abandoned} 筆重啟後遺留的本地分析任務。")

    async def cleanup_loop():
        while True:
            await asyncio.to_thread(cleanup_expired_reports)
            await asyncio.to_thread(cleanup_orphan_markdown_reports)
            await asyncio.sleep(REPORT_CLEANUP_INTERVAL_SECONDS)

    asyncio.create_task(cleanup_loop())


def cleanup_expired_reports(retention_days: int = REPORT_RETENTION_DAYS):
    """刪除超過保留天數的 HTML/Markdown/資料快照，避免 output 無限成長。"""
    if not os.path.exists(OUTPUT_DIR) or retention_days <= 0:
        return []

    cutoff = time.time() - retention_days * 24 * 60 * 60
    deleted = []
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith((".html", ".md", ".data.json")):
            continue
        path = os.path.join(OUTPUT_DIR, filename)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                deleted.append(filename)
                if filename.endswith(".html"):
                    delete_report_metadata(filename, OUTPUT_DIR)
        except OSError:
            pass

    if deleted:
        for ticker, cached_filename in list(report_cache.items()):
            if cached_filename in deleted:
                del report_cache[ticker]
    return deleted


def cleanup_orphan_markdown_reports():
    """移除沒有對應 HTML 的 Markdown 報告與資料快照。"""
    if not os.path.exists(OUTPUT_DIR):
        return []

    html_stems = {
        os.path.splitext(filename)[0]
        for filename in os.listdir(OUTPUT_DIR)
        if filename.endswith(".html")
    }
    deleted = []
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith((".md", ".data.json")):
            continue
        stem = filename[:-10] if filename.endswith(".data.json") else os.path.splitext(filename)[0]
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
def get_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    q: str = Query("", max_length=80),
    pipeline: str = Query("all", max_length=24),
    recommendation: str = Query("all", max_length=24),
    data_trust: str = Query("all", max_length=24),
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
    data_trust_value = data_trust if isinstance(data_trust, str) else "all"
    data_trust_filter = data_trust_value.strip().lower()
    if data_trust_filter not in {"all", "fresh", "partial", "stale", "error", "unknown"}:
        data_trust_filter = "all"

    if os.path.exists(OUTPUT_DIR):
        reports, total = query_report_metadata(
            page=page,
            limit=limit,
            q=query,
            pipeline=pipeline_filter,
            recommendation=recommendation_filter,
            data_trust=data_trust_filter,
            output_dir=OUTPUT_DIR,
        )
    else:
        total = 0

    page_reports = reports
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
            "data_trust": data_trust_filter,
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
    data_filename = data_snapshot_filename_for_report(filename)
    md_path = os.path.join(OUTPUT_DIR, md_filename)
    data_path = os.path.join(OUTPUT_DIR, data_filename)

    if not os.path.exists(html_path) and not os.path.exists(md_path) and not os.path.exists(data_path):
        return {"success": False, "error": "File not found"}

    deleted = []
    errors = []
    for path in [html_path, md_path, data_path]:
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
    delete_report_metadata(filename, OUTPUT_DIR)

    return {"success": True, "deleted": deleted}

@app.get("/")
def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "favicon.ico"), media_type="image/x-icon")


@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def apple_touch_icon():
    return FileResponse(os.path.join(STATIC_DIR, "apple-touch-icon.png"), media_type="image/png")


@app.get("/api/analyze/{ticker}")
async def analyze_stock(
    ticker: str,
    request: Request,
    job_id: Optional[str] = Query(None),
    last_event_id: Optional[int] = Query(None, ge=0),
    pipeline: str = Query("v1", max_length=24),
    cancel_on_disconnect: bool = Query(False),
):
    """使用 SSE 即時推播分析進度"""
    ticker_upper = ticker.strip().upper()
    pipeline_id = normalize_pipeline_run_id(pipeline)
    pipeline_sequence = get_pipeline_run_sequence(pipeline_id)
    pipeline_label = get_pipeline_run_label(pipeline_id)
    agent_total = get_pipeline_run_agent_total(pipeline_id)

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
                    "pipeline_label": pipeline_label,
                    "pipeline_sequence": list(pipeline_sequence),
                    "agent_total": agent_total,
                },
                ensure_ascii=False,
            )
        }
        try:
            while True:
                if await request.is_disconnected():
                    append_event(job_id, {
                        "type": "status",
                        "phase": "client_disconnected",
                        "level": "info",
                        "message": "SSE 客戶端已斷線。",
                        "pipeline_id": pipeline_id,
                        "pipeline_label": pipeline_label,
                    })
                    if cancel_on_disconnect:
                        await asyncio.to_thread(request_job_cancel, job_id, "SSE 客戶端斷線，已要求取消分析任務。")
                    break

                events = await asyncio.to_thread(get_events_since, job_id, last_sent_event_id)
                for event in events:
                    if await request.is_disconnected():
                        terminal_sent = True
                        break
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
                if job.get("status") in ["done", "error", "cancelled"]:
                    if job.get("status") == "done":
                        job_pipeline_id = job.get("pipeline_id", pipeline_id)
                        job_pipeline_sequence = get_pipeline_run_sequence(job_pipeline_id)
                        payload = {
                            "type": "done",
                            "filename": job.get("filename"),
                            "pipeline_id": job_pipeline_id,
                            "last_pipeline_id": job_pipeline_sequence[-1],
                        }
                    elif job.get("status") == "cancelled":
                        payload = {"type": "error", "phase": "cancelled", "message": job.get("error", "分析任務已取消")}
                    else:
                        payload = {"type": "error", "message": job.get("error", "分析任務失敗")}
                    yield {"data": json.dumps(payload, ensure_ascii=False)}
                    break

                if not events:
                    if await request.is_disconnected():
                        break
                    yield {"event": "ping", "data": "ping"}
                await asyncio.sleep(0.5)
        finally:
            pass

                
    return EventSourceResponse(event_generator())


@app.get("/api/observability/provider-sla")
async def provider_sla_summary(limit: int = Query(100, ge=1, le=1000)):
    providers, alerts = await asyncio.gather(
        asyncio.to_thread(get_provider_sla_summary, limit),
        asyncio.to_thread(get_provider_sla_alerts, limit),
    )
    return {"providers": providers, "alerts": alerts}


@app.post("/api/analyze/{ticker}/cancel")
async def cancel_analysis_job(
    ticker: str,
    job_id: str = Query(..., min_length=1),
    pipeline: str = Query("v1", max_length=24),
):
    ticker_upper = ticker.strip().upper()
    pipeline_id = normalize_pipeline_run_id(pipeline)
    job = get_job(job_id)
    if not job or job.get("ticker") != ticker_upper or job.get("pipeline_id", "v1") != pipeline_id:
        return {"ok": False, "message": "找不到可取消的分析任務"}
    ok = request_job_cancel(job_id, "使用者要求取消分析任務。")
    return {"ok": ok, "job_id": job_id, "status": "cancelling" if ok else "not_found"}

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

@app.get("/api/report/{filename}/download/data")
async def download_data_snapshot(filename: str):
    """下載報告生成時保存的 sanitized 資料快照。"""
    if not is_safe_report_filename(filename, ".html"):
        return HTMLResponse("<h1>Invalid filename</h1>", status_code=400)
    data_filename = data_snapshot_filename_for_report(filename)
    filepath = os.path.join(OUTPUT_DIR, data_filename)
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            filename=data_filename,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={data_filename}"},
        )
    return HTMLResponse("<h1>找不到報告資料快照</h1>", status_code=404)


@app.post("/api/report/{filename}/refresh/data")
async def refresh_report_data_snapshot(filename: str):
    """重新抓取報告 ticker 的資料快照，不重跑 Agent 或改寫 HTML/Markdown。"""
    if not is_safe_report_filename(filename, ".html"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    html_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="找不到報告")

    data_filename = data_snapshot_filename_for_report(filename)
    data_path = os.path.join(OUTPUT_DIR, data_filename)
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

    result = await data_refresh_service.fetch_async(FetchRequest.from_ticker(ticker, force_refresh=True))
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
    }
    refreshed_snapshot = build_data_snapshot(context, pipeline_id=previous_snapshot.get("pipeline"))

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(refreshed_snapshot, f, ensure_ascii=False, indent=2)
    metadata = upsert_report_metadata(
        filename,
        output_dir=OUTPUT_DIR,
        data_trust=refreshed_snapshot.get("data_trust"),
    )
    return {
        "success": True,
        "filename": filename,
        "data_filename": data_filename,
        "data_trust": refreshed_snapshot.get("data_trust"),
        "source_audit": refreshed_snapshot.get("source_audit", [])[:12],
        "metadata": metadata or {},
    }
