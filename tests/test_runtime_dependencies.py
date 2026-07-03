from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from cache_backends import InMemoryCache, LocalRedisCache, SqliteCacheBackend
from storage.report_storage import InMemoryStorage, LocalFileStorage


def test_runtime_settings_for_tests_uses_tmp_path_defaults(tmp_path):
    from runtime_dependencies import RuntimeSettings

    settings = RuntimeSettings.for_tests(tmp_path)

    assert Path(settings.output_dir).is_relative_to(tmp_path)
    assert Path(settings.cache_db_path).is_relative_to(tmp_path)
    assert Path(settings.checkpoint_path) == tmp_path / "langgraph_checkpoints.sqlite3"
    assert settings.report_storage_backend == "local"
    assert settings.cache_backend == "sqlite"
    assert settings.cache_namespace == "test"
    assert settings.redis_url == "redis://localhost:6379/15"


def test_runtime_settings_from_environment_reads_settings_at_call_time(monkeypatch):
    from settings import runtime_limits, storage
    from runtime_dependencies import RuntimeSettings

    monkeypatch.setattr(storage, "OUTPUT_DIR", "/tmp/onstock-output")
    monkeypatch.setattr(storage, "CACHE_DB_PATH", "/tmp/onstock-cache.sqlite3")
    monkeypatch.setattr(storage, "REPORT_STORAGE_BACKEND", "memory")
    monkeypatch.setattr(storage, "CACHE_BACKEND", "memory")
    monkeypatch.setattr(storage, "CACHE_NAMESPACE", "patched")
    monkeypatch.setattr(storage, "LANGGRAPH_CHECKPOINT_PATH", "/tmp/checkpoints.sqlite3")
    monkeypatch.setattr(runtime_limits, "REDIS_URL", "redis://localhost:6379/9")

    settings = RuntimeSettings.from_environment()

    assert settings.output_dir == "/tmp/onstock-output"
    assert settings.cache_db_path == "/tmp/onstock-cache.sqlite3"
    assert settings.report_storage_backend == "memory"
    assert settings.cache_backend == "memory"
    assert settings.cache_namespace == "patched"
    assert settings.checkpoint_path == "/tmp/checkpoints.sqlite3"
    assert settings.redis_url == "redis://localhost:6379/9"


def test_create_report_storage_selects_explicit_backends(tmp_path):
    from runtime_dependencies import RuntimeSettings, create_report_storage

    local = create_report_storage(RuntimeSettings.for_tests(tmp_path, report_storage_backend="local"))
    memory = create_report_storage(RuntimeSettings.for_tests(tmp_path, report_storage_backend="memory"))

    assert isinstance(local, LocalFileStorage)
    assert (tmp_path / "output").is_dir()
    assert isinstance(memory, InMemoryStorage)


def test_create_report_storage_rejects_unknown_backend(tmp_path):
    from runtime_dependencies import RuntimeSettings, create_report_storage

    settings = RuntimeSettings.for_tests(tmp_path, report_storage_backend="s3")

    with pytest.raises(ValueError, match="REPORT_STORAGE_BACKEND"):
        create_report_storage(settings)


def test_create_cache_backend_selects_memory_and_sqlite(tmp_path):
    from runtime_dependencies import RuntimeSettings, create_cache_backend

    memory = create_cache_backend(RuntimeSettings.for_tests(tmp_path, cache_backend="memory"))
    sqlite = create_cache_backend(RuntimeSettings.for_tests(tmp_path, cache_backend="sqlite"))

    assert isinstance(memory, InMemoryCache)
    assert isinstance(sqlite, SqliteCacheBackend)
    sqlite.set_json("key", {"ok": True}, ttl_seconds=60)
    assert sqlite.get_json("key") == {"ok": True}
    sqlite.close()


def test_create_cache_backend_selects_redis_without_real_network(monkeypatch, tmp_path):
    from runtime_dependencies import RuntimeSettings, create_cache_backend

    captured = {}

    class FakeRedisClient:
        def __init__(self):
            self.values = {}

        def set(self, name, value, ex):
            self.values[name] = value.encode("utf-8")
            return True

        def get(self, name):
            return self.values.get(name)

        def delete(self, name):
            return int(self.values.pop(name, None) is not None)

        def close(self):
            captured["closed"] = True

    class RedisFactory:
        @staticmethod
        def from_url(redis_url):
            captured["redis_url"] = redis_url
            captured["client"] = FakeRedisClient()
            return captured["client"]

    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=RedisFactory))
    settings = RuntimeSettings.for_tests(
        tmp_path,
        cache_backend="redis",
        cache_namespace="runtime:test",
        redis_url="redis://localhost:6379/14",
    )

    cache = create_cache_backend(settings)

    assert isinstance(cache, LocalRedisCache)
    assert captured["redis_url"] == "redis://localhost:6379/14"
    cache.set_json("quote", {"ticker": "2330"}, ttl_seconds=60)
    assert cache.get_json("quote") == {"ticker": "2330"}
    cache.close()
    assert captured["closed"] is True


def test_create_cache_backend_rejects_unknown_backend_and_blank_redis_namespace(tmp_path):
    from runtime_dependencies import RuntimeSettings, create_cache_backend

    with pytest.raises(ValueError, match="CACHE_BACKEND"):
        create_cache_backend(RuntimeSettings.for_tests(tmp_path, cache_backend="disk"))

    with pytest.raises(ValueError, match="CACHE_NAMESPACE"):
        create_cache_backend(
            RuntimeSettings.for_tests(tmp_path, cache_backend="redis", cache_namespace="")
        )


def test_fastapi_helpers_read_runtime_from_request_state(tmp_path):
    from runtime_dependencies import (
        ApiRuntime,
        RuntimeSettings,
        get_api_runtime,
        get_cache_backend_from_request,
        get_report_storage,
    )

    settings = RuntimeSettings.for_tests(tmp_path, report_storage_backend="memory", cache_backend="memory")
    runtime = ApiRuntime(settings=settings, report_storage=InMemoryStorage(), cache_backend=InMemoryCache())
    request = types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace(runtime=runtime)))

    assert get_api_runtime(request) is runtime
    assert get_report_storage(request) is runtime.report_storage
    assert get_cache_backend_from_request(request) is runtime.cache_backend


class RecordingCache:
    def __init__(self):
        self.close_count = 0

    def get_json(self, key):
        return None

    def set_json(self, key, value, *, ttl_seconds):
        return None

    def delete(self, key):
        return False

    def cleanup_expired(self):
        return 0

    def close(self):
        self.close_count += 1


class FailingCloseCache(RecordingCache):
    def close(self):
        self.close_count += 1
        raise RuntimeError("cache close failed")


class RecordingTaskQueue:
    def __init__(self):
        self.close_count = 0

    def close(self):
        self.close_count += 1


class FalsyTaskQueue(RecordingTaskQueue):
    def __bool__(self):
        return False


def test_api_runtime_close_is_idempotent_and_closes_owned_cache(monkeypatch, tmp_path):
    import cache_store
    import job_store
    from runtime_dependencies import ApiRuntime, RuntimeSettings

    process_closes = []
    monkeypatch.setattr(cache_store, "close_cache_store", lambda: process_closes.append("cache"))
    monkeypatch.setattr(job_store, "close_job_store", lambda: process_closes.append("job"))
    owned_cache = RecordingCache()
    runtime = ApiRuntime(
        settings=RuntimeSettings.for_tests(tmp_path),
        report_storage=InMemoryStorage(),
        cache_backend=owned_cache,
    )

    runtime.close()
    runtime.close()

    assert owned_cache.close_count == 1
    assert process_closes == ["cache"]


def test_api_runtime_close_closes_owned_task_queue(monkeypatch, tmp_path):
    import cache_store
    import job_store
    from runtime_dependencies import ApiRuntime, RuntimeSettings

    monkeypatch.setattr(cache_store, "close_cache_store", lambda: None)
    monkeypatch.setattr(job_store, "close_job_store", lambda: None)
    task_queue = RecordingTaskQueue()
    runtime = ApiRuntime(
        settings=RuntimeSettings.for_tests(tmp_path),
        report_storage=InMemoryStorage(),
        cache_backend=RecordingCache(),
        task_queue=task_queue,
    )

    runtime.close()
    runtime.close()

    assert task_queue.close_count == 1


def test_api_runtime_close_does_not_close_job_store_when_owned_cache_close_fails(
    monkeypatch,
    tmp_path,
):
    import cache_store
    import job_store
    from runtime_dependencies import ApiRuntime, RuntimeSettings

    process_closes = []
    monkeypatch.setattr(cache_store, "close_cache_store", lambda: process_closes.append("cache"))
    monkeypatch.setattr(job_store, "close_job_store", lambda: process_closes.append("job"))
    owned_cache = FailingCloseCache()
    runtime = ApiRuntime(
        settings=RuntimeSettings.for_tests(tmp_path),
        report_storage=InMemoryStorage(),
        cache_backend=owned_cache,
    )

    with pytest.raises(RuntimeError, match="cache close failed"):
        runtime.close()

    assert owned_cache.close_count == 1
    assert process_closes == ["cache"]

    with pytest.raises(RuntimeError, match="cache close failed"):
        runtime.close()

    assert owned_cache.close_count == 2
    assert process_closes == ["cache", "cache"]


def test_worker_runtime_close_is_idempotent_and_exposes_checkpoint(monkeypatch, tmp_path):
    import cache_store
    import job_store
    from runtime_dependencies import RuntimeSettings, WorkerRuntime

    process_closes = []
    monkeypatch.setattr(cache_store, "close_cache_store", lambda: process_closes.append("cache"))
    monkeypatch.setattr(job_store, "close_job_store", lambda: process_closes.append("job"))
    settings = RuntimeSettings.for_tests(tmp_path)
    owned_cache = RecordingCache()
    runtime = WorkerRuntime(
        settings=settings,
        report_storage=InMemoryStorage(),
        cache_backend=owned_cache,
    )

    runtime.close()
    runtime.close()

    assert runtime.checkpoint_path == settings.checkpoint_path
    assert owned_cache.close_count == 1
    assert process_closes == ["cache", "job"]


def test_worker_runtime_close_closes_owned_task_queue(monkeypatch, tmp_path):
    import cache_store
    import job_store
    from runtime_dependencies import RuntimeSettings, WorkerRuntime

    monkeypatch.setattr(cache_store, "close_cache_store", lambda: None)
    monkeypatch.setattr(job_store, "close_job_store", lambda: None)
    task_queue = RecordingTaskQueue()
    runtime = WorkerRuntime(
        settings=RuntimeSettings.for_tests(tmp_path),
        report_storage=InMemoryStorage(),
        cache_backend=RecordingCache(),
        task_queue=task_queue,
    )

    runtime.close()
    runtime.close()

    assert task_queue.close_count == 1


def test_create_worker_runtime_preserves_injected_falsy_task_queue(tmp_path):
    from runtime_dependencies import RuntimeSettings, create_worker_runtime

    task_queue = FalsyTaskQueue()
    runtime = create_worker_runtime(
        RuntimeSettings.for_tests(tmp_path, cache_backend="memory", report_storage_backend="memory"),
        task_queue=task_queue,
        data_refresh_service=object(),
    )

    assert runtime.task_queue is task_queue


def test_runtime_factory_helpers_wire_selected_dependencies(tmp_path):
    from runtime_dependencies import RuntimeSettings, create_api_runtime, create_worker_runtime

    settings = RuntimeSettings.for_tests(
        tmp_path,
        report_storage_backend="memory",
        cache_backend="memory",
    )

    api_runtime = create_api_runtime(settings)
    worker_runtime = create_worker_runtime(settings)

    assert api_runtime.settings is settings
    assert isinstance(api_runtime.report_storage, InMemoryStorage)
    assert isinstance(api_runtime.cache_backend, InMemoryCache)
    assert worker_runtime.settings is settings
    assert worker_runtime.checkpoint_path == settings.checkpoint_path
    assert isinstance(worker_runtime.report_storage, InMemoryStorage)
    assert isinstance(worker_runtime.cache_backend, InMemoryCache)
    api_runtime.close()
    worker_runtime.close()


def test_create_cache_backend_normalizes_and_rejects_effectively_blank_redis_namespace(
    monkeypatch,
    tmp_path,
):
    from runtime_dependencies import RuntimeSettings, create_cache_backend

    captured = {}

    class FakeRedisClient:
        def __init__(self):
            self.values = {}

        def set(self, name, value, ex):
            self.values[name] = value.encode("utf-8")
            return True

        def get(self, name):
            return self.values.get(name)

        def delete(self, name):
            return int(self.values.pop(name, None) is not None)

        def close(self):
            return None

    class RedisFactory:
        @staticmethod
        def from_url(redis_url):
            captured["redis_url"] = redis_url
            captured["client"] = FakeRedisClient()
            return captured["client"]

    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=RedisFactory))

    with pytest.raises(ValueError, match="CACHE_NAMESPACE"):
        create_cache_backend(
            RuntimeSettings.for_tests(tmp_path, cache_backend="redis", cache_namespace="::")
        )

    cache = create_cache_backend(
        RuntimeSettings.for_tests(
            tmp_path,
            cache_backend="redis",
            cache_namespace=" :runtime:test: ",
        )
    )

    cache.set_json("quote", {"ok": True}, ttl_seconds=60)
    assert cache.get_json("quote") == {"ok": True}
    assert "runtime:test:quote" in captured["client"].values
    cache.close()


def test_validate_runtime_settings_reports_runtime_dependency_misconfiguration(monkeypatch):
    from settings import app_config

    monkeypatch.setattr(app_config, "REPORT_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(app_config, "CACHE_BACKEND", "disk")
    monkeypatch.setattr(app_config, "CACHE_NAMESPACE", "")

    warnings = app_config.validate_runtime_settings()

    assert any("REPORT_STORAGE_BACKEND" in warning and "s3" in warning for warning in warnings)
    assert any("CACHE_BACKEND" in warning and "disk" in warning for warning in warnings)
    assert any("CACHE_NAMESPACE" in warning for warning in warnings)


def test_validate_runtime_settings_warns_for_sqlite_checkpoint_in_production(monkeypatch):
    from settings import app_config

    monkeypatch.setattr(app_config, "DEPLOYMENT_MODE", "production")
    monkeypatch.setattr(app_config, "MUTATION_API_TOKEN", "prod-token")
    monkeypatch.setattr(app_config, "ALLOWED_ORIGINS", ["https://app.example"])
    monkeypatch.setattr(app_config, "has_network_access_guard", lambda: True)
    monkeypatch.setattr(app_config, "LANGGRAPH_CHECKPOINT_PATH", "/srv/stock-agent/checkpoints.sqlite3")

    warnings = app_config.validate_runtime_settings()

    assert any("LANGGRAPH_CHECKPOINT_PATH" in warning and "PostgreSQL" in warning for warning in warnings)
