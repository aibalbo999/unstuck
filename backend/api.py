import os
import secrets
import sys
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from api_app_setup import install_cors_static_and_metrics
import api_mutation_security
from api_openapi_contract import install_openapi_contract
from api_mutation_security import MUTATION_HEADER_NAME
from api_safe_json import SafeJSONResponse
from agent_runtime import AnalysisPipelineRunner
from analysis_job_service import (
    RQ_ABANDONED_JOB_REASON,
    analysis_task_id,
    cancel_analysis_job as cancel_analysis_job_service,
    create_or_attach_analysis_job,
    serialize_analysis_job,
    serialize_node_telemetry,
    task_queue_has_task,
)
from analysis_jobs import run_stock_analysis_job
from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
from api_routes.decision_tracking import DecisionTrackingRouteDeps, create_decision_tracking_router
from api_routes.health import HealthRouteDeps, create_health_router
from api_routes.maintenance import MaintenanceRouteDeps, create_maintenance_router
from api_routes.observability import ObservabilityRouteDeps, create_observability_router
from api_routes.ops import OpsRouteDeps, create_ops_router
from api_routes.performance import PerformanceRouteDeps, create_performance_router
from api_routes.pipeline_modes import create_pipeline_modes_router
from api_routes.reports import ReportRouteDeps, create_reports_router
from api_routes.review import ReviewRouteDeps, create_review_router
from api_routes.static_files import create_static_router
from api_routes.stock_snapshot import create_stock_snapshot_router
from api_routes.watchlist import WatchlistRouteDeps, create_watchlist_router
from config import (
    ALLOW_LEGACY_ADMIN_TOKEN,
    ALLOWED_ORIGINS,
    API_KEY_SETUP_MESSAGE,
    DEPLOYMENT_MODE,
    MUTATION_API_TOKEN,
    MUTATION_RATE_LIMIT_MAX_REQUESTS,
    MUTATION_RATE_LIMIT_WINDOW_SECONDS,
    OUTPUT_DIR,
    TASK_QUEUE_BACKEND,
    has_api_keys,
)
from basic_auth import basic_auth_challenge_response, basic_auth_enabled, basic_auth_exempt_path, is_basic_auth_authorized
from database_maintenance import run_sqlite_maintenance
from job_store import (
    append_event,
    create_job,
    create_or_attach_active_job,
    find_active_job,
    get_events_since,
    get_job,
    mark_jobs_abandoned,
    request_job_cancel,
    update_job,
)
from job_store_maintenance import cleanup_analysis_history
from mutation_rate_limit import check_mutation_rate_limit
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
from runtime_health import build_health_payload, build_readiness_payload
from settings import validate_runtime_settings
from storage_inventory import build_storage_summary, ensure_runtime_storage
from task_queue import create_api_task_queue

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(OUTPUT_DIR, exist_ok=True)
analysis_task_queue = create_api_task_queue()
analysis_pipeline_runner = AnalysisPipelineRunner()
report_renderer = ReportRenderer()
active_analyses_lock = threading.Lock()
RUNTIME_MUTATION_API_TOKEN = secrets.token_urlsafe(32)
def print_streamed_event(job_id: str, payload: dict) -> None:
    if TASK_QUEUE_BACKEND != "rq":
        return
    emit_log(format_event_log_line(job_id, payload, prefix="stream"))

def require_mutation_authorized(request: Request) -> None:
    return api_mutation_security.require_mutation_authorized(
        request,
        check_mutation_rate_limit=check_mutation_rate_limit,
        allow_legacy_admin_token=ALLOW_LEGACY_ADMIN_TOKEN,
        mutation_api_token=MUTATION_API_TOKEN,
        runtime_mutation_token=get_runtime_mutation_token(),
        deployment_mode=DEPLOYMENT_MODE,
        max_requests=MUTATION_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=MUTATION_RATE_LIMIT_WINDOW_SECONDS,
    )
get_runtime_mutation_token = lambda: api_mutation_security.runtime_mutation_token(RUNTIME_MUTATION_API_TOKEN)
is_local_deployment_mode = lambda: api_mutation_security.is_local_deployment_mode(DEPLOYMENT_MODE)
is_restricted_cors_profile = lambda: api_mutation_security.is_restricted_cors_profile(DEPLOYMENT_MODE)
cors_allow_methods = lambda: api_mutation_security.cors_allow_methods(DEPLOYMENT_MODE)
cors_allow_headers = lambda: api_mutation_security.cors_allow_headers(DEPLOYMENT_MODE, MUTATION_HEADER_NAME)
get_allowed_mutation_tokens = lambda: api_mutation_security.allowed_mutation_tokens(DEPLOYMENT_MODE, get_runtime_mutation_token(), MUTATION_API_TOKEN)
get_client_config = lambda: api_mutation_security.client_config(DEPLOYMENT_MODE, get_runtime_mutation_token(), MUTATION_HEADER_NAME)
def runtime_settings_warnings_for_readiness() -> list[str]:
    try:
        return validate_runtime_settings()
    except Exception as exc:
        return [str(exc)]
create_runtime_job = create_job
def find_queue_backed_active_job(ticker: str, pipeline_id: str = "v1") -> dict:
    job = find_active_job(ticker, pipeline_id)
    if not job or TASK_QUEUE_BACKEND != "rq":
        return job
    task_id = analysis_task_id(str(job.get("job_id") or ""))
    if task_queue_has_task(analysis_task_queue, task_id) is not False:
        return job
    mark_jobs_abandoned([job["job_id"]], RQ_ABANDONED_JOB_REASON)
    return {}
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
    runtime_settings = runtime_settings_for_output_dir(OUTPUT_DIR)
    ensure_runtime_storage(
        output_dir=runtime_settings.output_dir,
        cache_db_path=runtime_settings.cache_db_path,
        checkpoint_backend=runtime_settings.checkpoint_backend,
        checkpoint_path=runtime_settings.checkpoint_path,
    )
    runtime = create_api_runtime(runtime_settings, task_queue=analysis_task_queue)
    _app.state.runtime = runtime
    try:
        yield
    finally:
        from llm_transport import close_cached_clients_async

        await close_cached_clients_async()
        runtime.close()
def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.router.default_response_class = SafeJSONResponse

    @app.middleware("http")
    async def basic_auth_middleware(request: Request, call_next):
        if basic_auth_enabled() and not basic_auth_exempt_path(request.url.path) and not is_basic_auth_authorized(request.headers.get("authorization")):
            return basic_auth_challenge_response()
        return await call_next(request)

    install_cors_static_and_metrics(
        app, allowed_origins=ALLOWED_ORIGINS, allow_methods=cors_allow_methods(),
        allow_headers=cors_allow_headers(), static_dir=STATIC_DIR,
        get_provider_sla_summary=lambda limit=100: get_provider_sla_summary(limit), get_task_queue=lambda: analysis_task_queue,
        emit_warning=emit_log,
    )

    app.include_router(create_health_router(HealthRouteDeps(
        build_health_payload=build_health_payload,
        build_readiness_payload=lambda: build_readiness_payload(
            runtime_settings=runtime_settings_for_output_dir(OUTPUT_DIR),
            task_queue=analysis_task_queue,
            warnings=runtime_settings_warnings_for_readiness(),
        ),
    )))
    app.include_router(create_static_router(lambda: STATIC_DIR, get_client_config=get_client_config))
    app.include_router(create_reports_router(ReportRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        get_report_storage=lambda: get_report_storage_for_output_dir(app, OUTPUT_DIR),
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
        create_or_attach_job=lambda ticker, pipeline_id: create_or_attach_active_job(
            ticker,
            pipeline_id,
            preserve_ticker_case=True,
        ),
    )))
    app.include_router(create_stock_snapshot_router())
    app.include_router(create_pipeline_modes_router())
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
        get_task_queue=lambda: analysis_task_queue,
    )))
    app.include_router(create_ops_router(OpsRouteDeps(
        get_provider_sla_summary=lambda limit: get_provider_sla_summary(limit),
        get_provider_sla_alerts=lambda limit: get_provider_sla_alerts(limit),
        get_task_queue=lambda: analysis_task_queue,
    )))
    app.include_router(create_watchlist_router(WatchlistRouteDeps(
        get_output_dir=lambda: OUTPUT_DIR,
        get_task_queue=lambda: analysis_task_queue,
        run_stock_analysis_job=run_stock_analysis_job,
        create_job=lambda ticker, pipeline_id: create_runtime_job(ticker, pipeline_id),
        find_active_job=lambda ticker, pipeline_id: find_queue_backed_active_job(ticker, pipeline_id),
        require_mutation_authorized=require_mutation_authorized,
    )))
    app.include_router(create_maintenance_router(MaintenanceRouteDeps(
        require_mutation_authorized=require_mutation_authorized,
        build_storage_summary=build_storage_summary,
        cleanup_report_index_orphans=cleanup_report_index_orphans,
        cleanup_provider_sla_events=cleanup_provider_sla_events,
        cleanup_analysis_history=cleanup_analysis_history,
        run_sqlite_maintenance=run_sqlite_maintenance,
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
        find_active_job=lambda ticker, pipeline_id: find_queue_backed_active_job(ticker, pipeline_id),
        create_job=lambda ticker, pipeline_id: create_runtime_job(ticker, pipeline_id),
        get_events_since=lambda job_id, after_id=0: get_events_since(job_id, after_id),
        update_job=update_job,
        append_event=append_event,
        request_job_cancel=lambda job_id, reason: request_job_cancel(job_id, reason),
        print_streamed_event=print_streamed_event,
        require_mutation_authorized=require_mutation_authorized,
        create_or_attach_analysis_job=create_or_attach_analysis_job,
        cancel_analysis_job=cancel_analysis_job_service,
        serialize_analysis_job=serialize_analysis_job,
        serialize_node_telemetry=serialize_node_telemetry,
    )))
    install_openapi_contract(app, mutation_header_name=MUTATION_HEADER_NAME)
    return app

app = create_app()
