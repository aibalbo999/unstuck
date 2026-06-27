import os
import secrets
import sys
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent_runtime import AnalysisPipelineRunner
from analysis_jobs import run_stock_analysis_job
from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
from api_routes.decision_tracking import DecisionTrackingRouteDeps, create_decision_tracking_router
from api_routes.maintenance import MaintenanceRouteDeps, create_maintenance_router
from api_routes.observability import ObservabilityRouteDeps, create_observability_router
from api_routes.performance import PerformanceRouteDeps, create_performance_router
from api_routes.reports import ReportRouteDeps, create_reports_router
from api_routes.review import ReviewRouteDeps, create_review_router
from api_routes.static_files import create_static_router
from api_routes.watchlist import WatchlistRouteDeps, create_watchlist_router
from config import (
    ALLOWED_ORIGINS,
    API_KEY_SETUP_MESSAGE,
    DEPLOYMENT_MODE,
    MUTATION_API_TOKEN,
    OUTPUT_DIR,
    TASK_QUEUE_BACKEND,
    has_api_keys,
)
from job_store import (
    append_event,
    create_job,
    find_active_job,
    get_events_since,
    get_job,
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
from runtime_dependencies import create_api_runtime, get_report_storage_for_output_dir, runtime_settings_for_output_dir
from runtime_events import emit_log, format_event_log_line
from settings import validate_runtime_settings
from storage_inventory import build_storage_summary
from task_queue import create_api_task_queue

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(OUTPUT_DIR, exist_ok=True)

report_cache = {}
report_cache_lock = threading.Lock()
analysis_task_queue = create_api_task_queue()
analysis_pipeline_runner = AnalysisPipelineRunner()
report_renderer = ReportRenderer()
active_analyses_lock = threading.Lock()
MUTATION_HEADER_NAME = "X-Mutation-Token"
RUNTIME_MUTATION_API_TOKEN = secrets.token_urlsafe(32)
def print_streamed_event(job_id: str, payload: dict) -> None:
    if TASK_QUEUE_BACKEND != "rq":
        return
    emit_log(format_event_log_line(job_id, payload, prefix="stream"))

def require_mutation_authorized(request: Request) -> None:
    supplied = (
        request.headers.get("x-admin-token")
        or request.headers.get("x-mutation-token")
        or ""
    ).strip()
    if supplied not in get_allowed_mutation_tokens():
        raise HTTPException(status_code=403, detail="Mutation endpoint requires a valid mutation token")
def get_runtime_mutation_token() -> str:
    return str(RUNTIME_MUTATION_API_TOKEN or "").strip()
def is_local_deployment_mode() -> bool:
    return str(DEPLOYMENT_MODE or "local").strip().lower() == "local"
def get_allowed_mutation_tokens() -> set[str]:
    runtime_token = get_runtime_mutation_token() if is_local_deployment_mode() else ""
    return {
        token for token in {
            runtime_token,
            str(MUTATION_API_TOKEN or "").strip(),
        }
        if token
    }
def get_client_config() -> dict:
    return {
        "mutation_header": MUTATION_HEADER_NAME,
        "mutation_token": get_runtime_mutation_token() if is_local_deployment_mode() else "",
        "deployment_mode": str(DEPLOYMENT_MODE or "local").strip().lower(),
    }
def create_runtime_job(ticker: str, pipeline_id: str = "v1") -> str:
    return create_job(ticker, pipeline_id)
def get_api_runtime_for_app(app: FastAPI):
    runtime = getattr(app.state, "runtime", None)
    if runtime is None:
        runtime = create_api_runtime(runtime_settings_for_output_dir(OUTPUT_DIR), task_queue=analysis_task_queue)
        app.state.runtime = runtime
    return runtime
def get_data_refresh_service(app: FastAPI):
    return get_api_runtime_for_app(app).data_refresh_service
@asynccontextmanager
async def lifespan(_app: FastAPI):
    for warning in validate_runtime_settings():
        emit_log(f"設定檢查警告：{warning}")
    existing_runtime = getattr(_app.state, "runtime", None)
    if existing_runtime is not None:
        existing_runtime.close()
    runtime = create_api_runtime(runtime_settings_for_output_dir(OUTPUT_DIR), task_queue=analysis_task_queue)
    _app.state.runtime = runtime
    try:
        yield
    finally:
        from llm_transport import close_cached_clients_async

        await close_cached_clients_async()
        runtime.close()
def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    _allow_credentials = "*" not in ALLOWED_ORIGINS
    if not _allow_credentials:
        emit_log("警告：ALLOWED_ORIGINS 含萬用字元 *，已停用 credentials 支援。")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(create_static_router(lambda: STATIC_DIR, get_client_config=get_client_config))
    app.include_router(create_reports_router(ReportRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        get_report_storage=lambda: get_report_storage_for_output_dir(app, OUTPUT_DIR),
        get_report_cache=lambda: report_cache,
        get_report_cache_lock=lambda: report_cache_lock,
        get_refresh_service=lambda: get_data_refresh_service(app),
        get_pipeline_runner=lambda: analysis_pipeline_runner,
        get_report_renderer=lambda: report_renderer,
        get_task_queue=lambda: analysis_task_queue,
        run_report_rerun_job=run_report_rerun_job,
        create_job=lambda ticker, pipeline_id: create_runtime_job(ticker, pipeline_id),
        get_job=lambda job_id: get_job(job_id),
        get_events_since=lambda job_id, after_id=0: get_events_since(job_id, after_id),
        update_job=update_job,
        append_event=append_event,
        request_job_cancel=lambda job_id, reason: request_job_cancel(job_id, reason),
        print_streamed_event=print_streamed_event,
        require_mutation_authorized=require_mutation_authorized,
    )))
    app.include_router(create_performance_router(PerformanceRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
    )))
    app.include_router(create_review_router(ReviewRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        require_mutation_authorized=require_mutation_authorized,
    )))
    app.include_router(create_decision_tracking_router(DecisionTrackingRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        get_refresh_service=lambda: get_data_refresh_service(app),
        require_mutation_authorized=require_mutation_authorized,
    )))
    app.include_router(create_observability_router(ObservabilityRouteDeps(
        get_provider_sla_summary=lambda limit: get_provider_sla_summary(limit),
        get_provider_sla_alerts=lambda limit: get_provider_sla_alerts(limit),
    )))
    app.include_router(create_watchlist_router(WatchlistRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        get_task_queue=lambda: analysis_task_queue,
        run_stock_analysis_job=run_stock_analysis_job,
        create_job=lambda ticker, pipeline_id: create_runtime_job(ticker, pipeline_id),
        find_active_job=lambda ticker, pipeline_id: find_active_job(ticker, pipeline_id),
        require_mutation_authorized=require_mutation_authorized,
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
        create_job=lambda ticker, pipeline_id: create_runtime_job(ticker, pipeline_id),
        get_events_since=lambda job_id, after_id=0: get_events_since(job_id, after_id),
        update_job=update_job,
        append_event=append_event,
        request_job_cancel=lambda job_id, reason: request_job_cancel(job_id, reason),
        print_streamed_event=print_streamed_event,
        require_mutation_authorized=require_mutation_authorized,
    )))
    return app

app = create_app()
