import asyncio
import os
import sys
import threading
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import api_observability_service
import report_history_service
import report_refresh_service
import report_rerun_service
from agent_runtime import AnalysisPipelineRunner
from analysis_jobs import run_stock_analysis_job
from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
from api_routes.maintenance import MaintenanceRouteDeps, create_maintenance_router
from api_routes.observability import ObservabilityRouteDeps, create_observability_router
from api_routes.reports import ReportRouteDeps, create_reports_router
from api_routes.static_files import create_static_router
from config import (
    ALLOWED_ORIGINS,
    API_KEY_SETUP_MESSAGE,
    MUTATION_API_TOKEN,
    OUTPUT_DIR,
    REPORT_CLEANUP_INTERVAL_SECONDS,
    REPORT_RETENTION_DAYS,
    TASK_QUEUE_BACKEND,
    has_api_keys,
)
from data_fetch import StockDataService
from job_store import (
    append_event,
    close_job_store,
    create_job,
    find_active_job,
    get_events_since,
    get_job,
    mark_incomplete_jobs_abandoned,
    request_job_cancel,
    update_job,
)
from job_store_maintenance import cleanup_analysis_history
from pipeline_modes import (
    get_pipeline_run_agent_total,
    get_pipeline_run_label,
    get_pipeline_run_sequence,
    normalize_pipeline_run_id,
)
from provider_sla import get_provider_sla_alerts, get_provider_sla_summary
from provider_sla_maintenance import cleanup_provider_sla_events
from report_rerun_jobs import run_report_rerun_job
from report_index_maintenance import cleanup_report_index_orphans
from reporting import ReportRenderer
from runtime_events import emit_log, format_event_log_line
from settings import validate_runtime_settings
from storage_inventory import build_storage_summary
from task_queue import create_task_queue


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(OUTPUT_DIR, exist_ok=True)

report_cache = {}
analysis_task_queue = create_task_queue()
data_refresh_service = StockDataService()
analysis_pipeline_runner = AnalysisPipelineRunner()
report_renderer = ReportRenderer()
active_analyses_lock = threading.Lock()
LOCAL_MUTATION_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def parse_recommendation_summary(filename: str) -> dict:
    return report_history_service.parse_recommendation_summary(filename, output_dir=OUTPUT_DIR)


def print_streamed_event(job_id: str, payload: dict) -> None:
    if TASK_QUEUE_BACKEND != "rq":
        return
    emit_log(format_event_log_line(job_id, payload, prefix="stream"))


def require_mutation_authorized(request: Request) -> None:
    token = str(MUTATION_API_TOKEN or "").strip()
    if not token:
        client_host = str(getattr(getattr(request, "client", None), "host", "") or "").lower()
        if client_host in LOCAL_MUTATION_HOSTS:
            return
        raise HTTPException(
            status_code=403,
            detail="Mutation endpoint requires MUTATION_API_TOKEN outside localhost",
        )
    supplied = (
        request.headers.get("x-admin-token")
        or request.headers.get("x-mutation-token")
        or ""
    ).strip()
    if supplied != token:
        raise HTTPException(status_code=403, detail="Mutation endpoint requires a valid admin token")


_refresh_data_diff = report_refresh_service.refresh_data_diff


def cleanup_expired_reports(retention_days: int = REPORT_RETENTION_DAYS):
    return report_history_service.cleanup_expired_reports(OUTPUT_DIR, report_cache, retention_days)


def cleanup_orphan_markdown_reports():
    return report_history_service.cleanup_orphan_markdown_reports(OUTPUT_DIR)


async def _mark_abandoned_local_jobs() -> None:
    if TASK_QUEUE_BACKEND != "local":
        return
    abandoned = await asyncio.to_thread(
        mark_incomplete_jobs_abandoned,
        "伺服器已重啟，舊的本地分析任務已中止；請重新送出分析。",
    )
    if abandoned:
        emit_log(f"已清理 {abandoned} 筆重啟後遺留的本地分析任務。")


async def _cleanup_reports_forever() -> None:
    from cache_store import cleanup_expired_cache_entries

    while True:
        await asyncio.to_thread(cleanup_expired_reports)
        await asyncio.to_thread(cleanup_orphan_markdown_reports)
        await asyncio.to_thread(cleanup_expired_cache_entries)
        await asyncio.sleep(REPORT_CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    for warning in validate_runtime_settings():
        emit_log(f"設定檢查警告：{warning}")
    await _mark_abandoned_local_jobs()
    cleanup_task = asyncio.create_task(_cleanup_reports_forever())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        from cache_store import close_cache_store
        from llm_transport import close_cached_clients_async

        close_job_store()
        close_cache_store()
        await close_cached_clients_async()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials="*" not in ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(create_static_router(lambda: STATIC_DIR))
    app.include_router(create_reports_router(ReportRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        get_report_cache=lambda: report_cache,
        get_refresh_service=lambda: data_refresh_service,
        get_pipeline_runner=lambda: analysis_pipeline_runner,
        get_report_renderer=lambda: report_renderer,
        get_task_queue=lambda: analysis_task_queue,
        run_report_rerun_job=run_report_rerun_job,
        create_job=lambda ticker, pipeline_id: create_job(ticker, pipeline_id),
        get_job=lambda job_id: get_job(job_id),
        get_events_since=lambda job_id, after_id=0: get_events_since(job_id, after_id),
        update_job=update_job,
        append_event=append_event,
        request_job_cancel=lambda job_id, reason: request_job_cancel(job_id, reason),
        print_streamed_event=print_streamed_event,
        require_mutation_authorized=require_mutation_authorized,
    )))
    app.include_router(create_observability_router(ObservabilityRouteDeps(
        get_provider_sla_summary=lambda limit: get_provider_sla_summary(limit),
        get_provider_sla_alerts=lambda limit: get_provider_sla_alerts(limit),
    )))
    app.include_router(create_maintenance_router(MaintenanceRouteDeps(
        require_mutation_authorized=require_mutation_authorized,
        build_storage_summary=build_storage_summary,
        cleanup_report_index_orphans=cleanup_report_index_orphans,
        cleanup_provider_sla_events=cleanup_provider_sla_events,
        cleanup_analysis_history=cleanup_analysis_history,
    )))
    app.include_router(create_analysis_router(AnalysisRouteDeps(
        active_analyses_lock=active_analyses_lock,
        get_analysis_task_queue=lambda: analysis_task_queue,
        run_stock_analysis_job=run_stock_analysis_job,
        has_api_keys=lambda: has_api_keys(),
        api_key_setup_message=lambda: API_KEY_SETUP_MESSAGE,
        normalize_pipeline_run_id=normalize_pipeline_run_id,
        get_pipeline_run_sequence=get_pipeline_run_sequence,
        get_pipeline_run_label=get_pipeline_run_label,
        get_pipeline_run_agent_total=get_pipeline_run_agent_total,
        get_job=lambda job_id: get_job(job_id),
        find_active_job=lambda ticker, pipeline_id: find_active_job(ticker, pipeline_id),
        create_job=lambda ticker, pipeline_id: create_job(ticker, pipeline_id),
        get_events_since=lambda job_id, after_id=0: get_events_since(job_id, after_id),
        update_job=update_job,
        append_event=append_event,
        request_job_cancel=lambda job_id, reason: request_job_cancel(job_id, reason),
        print_streamed_event=print_streamed_event,
        require_mutation_authorized=require_mutation_authorized,
    )))
    return app


app = create_app()


def get_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    q: str = Query("", max_length=80),
    pipeline: str = Query("all", max_length=24),
    recommendation: str = Query("all", max_length=24),
    data_trust: str = Query("all", max_length=24),
    include_versions: bool = Query(False),
):
    return report_history_service.list_reports(
        page=page,
        limit=limit,
        q=q,
        pipeline=pipeline,
        recommendation=recommendation,
        data_trust=data_trust,
        include_versions=include_versions,
        output_dir=OUTPUT_DIR,
        report_cache=report_cache,
    )


def delete_report(filename: str, request: Request):
    require_mutation_authorized(request)
    return report_history_service.delete_report_files(filename, OUTPUT_DIR, report_cache)


async def provider_sla_summary(limit: int = Query(100, ge=1, le=1000), window: str = Query("all", max_length=24)):
    return await api_observability_service.build_provider_sla_payload(
        get_provider_sla_summary,
        get_provider_sla_alerts,
        limit,
        window=window,
    )


async def refresh_report_data_snapshot(filename: str, request: Request):
    require_mutation_authorized(request)
    return await report_refresh_service.refresh_report_data_snapshot(
        filename,
        output_dir=OUTPUT_DIR,
        refresh_service=data_refresh_service,
    )


async def rerun_report_analysis(filename: str, request: Request, scope: str = "final_recommendation"):
    require_mutation_authorized(request)
    return await report_rerun_service.rerun_report_analysis(
        filename,
        scope=scope,
        output_dir=OUTPUT_DIR,
        pipeline_runner=analysis_pipeline_runner,
        report_renderer=report_renderer,
    )
