"""Runtime dependency settings and factories."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from fastapi import Request

from cache_backends import CacheBackend, InMemoryCache, LocalRedisCache, SqliteCacheBackend
from storage.report_storage import InMemoryStorage, LocalFileStorage, ReportStorage


@dataclass(frozen=True)
class RuntimeSettings:
    output_dir: str
    cache_db_path: str
    redis_url: str
    report_storage_backend: str
    cache_backend: str
    cache_namespace: str
    checkpoint_backend: str
    checkpoint_path: str
    checkpoint_postgres_dsn: str

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        from settings import runtime_limits, storage

        return cls(
            output_dir=str(storage.OUTPUT_DIR),
            cache_db_path=str(storage.CACHE_DB_PATH),
            redis_url=str(runtime_limits.REDIS_URL),
            report_storage_backend=str(storage.REPORT_STORAGE_BACKEND),
            cache_backend=str(storage.CACHE_BACKEND),
            cache_namespace=str(storage.CACHE_NAMESPACE),
            checkpoint_backend=str(storage.LANGGRAPH_CHECKPOINT_BACKEND),
            checkpoint_path=str(storage.LANGGRAPH_CHECKPOINT_PATH),
            checkpoint_postgres_dsn=str(storage.LANGGRAPH_CHECKPOINT_POSTGRES_DSN),
        )

    @classmethod
    def for_tests(cls, tmp_path: str | Path, **overrides: object) -> "RuntimeSettings":
        root = Path(tmp_path)
        settings = cls(
            output_dir=str(root / "output"),
            cache_db_path=str(root / "stock_agent_cache.sqlite3"),
            redis_url="redis://localhost:6379/15",
            report_storage_backend="local",
            cache_backend="sqlite",
            cache_namespace="test",
            checkpoint_backend="sqlite",
            checkpoint_path=str(root / "langgraph_checkpoints.sqlite3"),
            checkpoint_postgres_dsn="",
        )
        if not overrides:
            return settings
        return replace(settings, **overrides)


@dataclass
class ApiRuntime:
    settings: RuntimeSettings
    report_storage: ReportStorage
    cache_backend: CacheBackend
    task_queue: Any | None = None
    data_refresh_service: Any | None = None
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        _close_runtime(self, close_job_store=False)


@dataclass
class WorkerRuntime:
    settings: RuntimeSettings
    report_storage: ReportStorage
    cache_backend: CacheBackend
    task_queue: Any | None = None
    data_refresh_service: Any | None = None
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def checkpoint_path(self) -> str:
        return self.settings.checkpoint_path

    @property
    def checkpoint_backend(self) -> str:
        return self.settings.checkpoint_backend

    @property
    def checkpoint_postgres_dsn(self) -> str:
        return self.settings.checkpoint_postgres_dsn

    def close(self) -> None:
        _close_runtime(self, close_job_store=True)


def create_report_storage(settings: RuntimeSettings) -> ReportStorage:
    if settings.report_storage_backend == "local":
        return LocalFileStorage(settings.output_dir)
    if settings.report_storage_backend == "memory":
        return InMemoryStorage()
    raise ValueError(f"Unsupported REPORT_STORAGE_BACKEND: {settings.report_storage_backend}")


def create_cache_backend(settings: RuntimeSettings) -> CacheBackend:
    if settings.cache_backend == "sqlite":
        return SqliteCacheBackend(settings.cache_db_path)
    if settings.cache_backend == "redis":
        namespace = str(settings.cache_namespace or "").strip().strip(":")
        if not namespace:
            raise ValueError("CACHE_NAMESPACE must not be blank for redis cache backend")
        return LocalRedisCache(settings.redis_url, namespace=namespace)
    if settings.cache_backend == "memory":
        return InMemoryCache()
    raise ValueError(f"Unsupported CACHE_BACKEND: {settings.cache_backend}")


def create_data_refresh_service() -> Any:
    from data_fetch import StockDataService

    return StockDataService()


def create_api_runtime(
    settings: RuntimeSettings | None = None,
    *,
    task_queue: Any | None = None,
    data_refresh_service: Any | None = None,
) -> ApiRuntime:
    runtime_settings = settings or RuntimeSettings.from_environment()
    return ApiRuntime(
        settings=runtime_settings,
        report_storage=create_report_storage(runtime_settings),
        cache_backend=create_cache_backend(runtime_settings),
        task_queue=task_queue,
        data_refresh_service=data_refresh_service or create_data_refresh_service(),
    )


def create_worker_runtime(
    settings: RuntimeSettings | None = None,
    *,
    task_queue: Any | None = None,
    data_refresh_service: Any | None = None,
) -> WorkerRuntime:
    from task_queue import create_task_queue

    runtime_settings = settings or RuntimeSettings.from_environment()
    return WorkerRuntime(
        settings=runtime_settings,
        report_storage=create_report_storage(runtime_settings),
        cache_backend=create_cache_backend(runtime_settings),
        task_queue=task_queue if task_queue is not None else create_task_queue(),
        data_refresh_service=data_refresh_service or create_data_refresh_service(),
    )


def runtime_settings_for_output_dir(output_dir: str) -> RuntimeSettings:
    settings = RuntimeSettings.from_environment()
    if settings.output_dir != output_dir:
        settings = replace(settings, output_dir=output_dir)
    return settings


def create_report_storage_for_output_dir(output_dir: str) -> ReportStorage:
    return create_report_storage(runtime_settings_for_output_dir(output_dir))


def create_worker_runtime_for_output_dir(output_dir: str) -> WorkerRuntime:
    return create_worker_runtime(runtime_settings_for_output_dir(output_dir))


def attach_api_runtime(app: Any, output_dir: str, *, task_queue: Any | None = None) -> None:
    app.state.runtime = create_api_runtime(runtime_settings_for_output_dir(output_dir), task_queue=task_queue)


def get_report_storage_for_output_dir(app: Any, output_dir: str) -> ReportStorage:
    runtime = getattr(app.state, "runtime", None)
    if runtime is None:
        attach_api_runtime(app, output_dir)
        runtime = app.state.runtime
    settings = getattr(runtime, "settings", None)
    if (
        settings is not None
        and settings.report_storage_backend == "local"
        and settings.output_dir != output_dir
    ):
        runtime.report_storage = LocalFileStorage(output_dir)
        runtime.settings = replace(settings, output_dir=output_dir)
    return runtime.report_storage


def _close_runtime(runtime: ApiRuntime | WorkerRuntime, *, close_job_store: bool) -> None:
    if runtime._closed:
        return

    import cache_store

    errors: list[Exception] = []
    task_queue_close = getattr(getattr(runtime, "task_queue", None), "close", None)
    if callable(task_queue_close):
        _close_collecting_errors(task_queue_close, errors)
    _close_collecting_errors(runtime.cache_backend.close, errors)
    process_cache = getattr(cache_store, "_backend", None)
    if process_cache is not runtime.cache_backend:
        _close_collecting_errors(cache_store.close_cache_store, errors)
    if close_job_store:
        import job_store

        _close_collecting_errors(job_store.close_job_store, errors)
    if errors:
        raise errors[0]
    runtime._closed = True


def _close_collecting_errors(close, errors: list[Exception]) -> None:
    try:
        close()
    except Exception as exc:
        errors.append(exc)


def get_api_runtime(request: Request) -> ApiRuntime:
    return request.app.state.runtime


def get_report_storage(request: Request) -> ReportStorage:
    return get_api_runtime(request).report_storage


def get_cache_backend_from_request(request: Request) -> CacheBackend:
    return get_api_runtime(request).cache_backend
