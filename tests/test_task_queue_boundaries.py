import asyncio
import importlib
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_api_task_queue_rejects_local_backend(monkeypatch):
    import task_queue

    monkeypatch.setattr(task_queue, "TASK_QUEUE_BACKEND", "local")

    with pytest.raises(RuntimeError, match="Redis.*RQ|RQ.*Redis"):
        task_queue.create_api_task_queue()


def test_api_task_queue_builds_rq_producer(monkeypatch):
    import task_queue

    built = {"queue_names": []}

    class FakeRedisClient:
        pass

    class RedisFactory:
        @staticmethod
        def from_url(redis_url):
            built["redis_url"] = redis_url
            return FakeRedisClient()

    class FakeQueue:
        def __init__(self, name, connection):
            self.name = name
            built["queue_names"].append(name)
            built["connection"] = connection

    monkeypatch.setattr(task_queue, "TASK_QUEUE_BACKEND", "rq")
    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(Redis=RedisFactory))
    monkeypatch.setitem(sys.modules, "rq", types.SimpleNamespace(Queue=FakeQueue))

    queue = task_queue.create_api_task_queue()

    assert isinstance(queue, task_queue.RQTaskQueue)
    assert task_queue.TASK_QUEUE_NAME in built["queue_names"]
    assert queue.queue.name == task_queue.TASK_QUEUE_NAME
    assert isinstance(built["connection"], FakeRedisClient)


def test_rq_enqueue_passes_retry_settings_to_queue(monkeypatch):
    import task_queue

    captured = {}

    class FakeRetry:
        def __init__(self, max, interval):
            self.max = max
            self.interval = interval

    class FakeQueue:
        def enqueue_call(self, **kwargs):
            captured.update(kwargs)
            return "queued-job"

    def job(value):
        return value

    monkeypatch.setattr(task_queue, "RQ_JOB_MAX_RETRIES", 3)
    monkeypatch.setattr(task_queue, "RQ_JOB_RETRY_INTERVALS", (5, 10, 30))
    monkeypatch.setattr(task_queue, "RQ_JOB_TIMEOUT_SECONDS", 7200)
    monkeypatch.setitem(sys.modules, "rq", types.SimpleNamespace(Retry=FakeRetry))

    queue = task_queue.RQTaskQueue(redis_client=object(), queue=FakeQueue())

    assert queue.enqueue("task-1", job, "payload", flag=True) == "queued-job"
    assert captured["func"] is job
    assert captured["args"] == ("payload",)
    assert captured["kwargs"] == {"flag": True}
    assert captured["job_id"] == "task-1"
    assert captured["timeout"] == 7200
    assert captured["retry"].max == 3
    assert captured["retry"].interval == [5, 10, 30]


def test_rq_enqueue_routes_analysis_and_rerun_to_separate_queues(monkeypatch):
    import task_queue

    calls = []

    class FakeRetry:
        def __init__(self, max, interval):
            self.max = max
            self.interval = interval

    class FakeQueue:
        def __init__(self, name):
            self.name = name

        def enqueue_call(self, **kwargs):
            calls.append((self.name, kwargs["job_id"]))
            return f"{self.name}:{kwargs['job_id']}"

    monkeypatch.setitem(sys.modules, "rq", types.SimpleNamespace(Retry=FakeRetry))

    queue = task_queue.RQTaskQueue(
        redis_client=object(),
        queues={
            "analysis.high": FakeQueue("analysis.high"),
            "analysis.normal": FakeQueue("analysis.normal"),
            "watchlist": FakeQueue("watchlist"),
        },
        queue_routes={
            "analysis": "analysis.high",
            "report-rerun": "analysis.normal",
            "watchlist": "watchlist",
        },
    )

    assert queue.enqueue("analysis:job-a", lambda: None) == "analysis.high:analysis:job-a"
    assert queue.enqueue("report-rerun:job-b", lambda: None) == "analysis.normal:report-rerun:job-b"
    assert queue.enqueue("watchlist:job-c", lambda: None) == "watchlist:watchlist:job-c"
    assert calls == [
        ("analysis.high", "analysis:job-a"),
        ("analysis.normal", "report-rerun:job-b"),
        ("watchlist", "watchlist:job-c"),
    ]


def test_rq_constructor_accepts_injected_queue_and_close_closes_redis():
    import task_queue

    class FakeRedis:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    redis = FakeRedis()
    fake_queue = object()

    queue = task_queue.RQTaskQueue(redis_client=redis, queue=fake_queue)
    queue.close()

    assert queue.redis is redis
    assert queue.queue is fake_queue
    assert redis.closed is True


def test_local_async_queue_still_runs_async_jobs():
    from task_queue import LocalAsyncQueue

    queue = LocalAsyncQueue(max_concurrent=1)
    seen = []

    async def job(value):
        seen.append(value)

    async def run_once():
        queue._running = True
        worker = asyncio.create_task(queue._worker())
        queue.enqueue("job-1", job, "ok")
        await queue.queue.join()
        queue._running = False
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(run_once())

    assert seen == ["ok"]


def test_validate_runtime_settings_warns_for_invalid_queue_config(monkeypatch):
    from settings import app_config

    monkeypatch.setattr(app_config, "TASK_QUEUE_BACKEND", "celery")
    monkeypatch.setattr(app_config, "RQ_JOB_MAX_RETRIES", 3)
    monkeypatch.setattr(app_config, "RQ_JOB_RETRY_INTERVALS", (60, 0))
    monkeypatch.setattr(app_config, "RQ_JOB_TIMEOUT_SECONDS", 0)

    warnings = app_config.validate_runtime_settings()

    assert any("TASK_QUEUE_BACKEND" in warning and "celery" in warning for warning in warnings)
    assert any("RQ_JOB_RETRY_INTERVALS" in warning and "至少" in warning for warning in warnings)
    assert any("RQ_JOB_RETRY_INTERVALS" in warning and "大於 0" in warning for warning in warnings)
    assert any("RQ_JOB_TIMEOUT_SECONDS" in warning and "大於 0" in warning for warning in warnings)

    monkeypatch.setattr(app_config, "TASK_QUEUE_BACKEND", "rq")
    monkeypatch.setattr(app_config, "RQ_JOB_MAX_RETRIES", 0)
    monkeypatch.setattr(app_config, "RQ_JOB_RETRY_INTERVALS", (60,))

    warnings = app_config.validate_runtime_settings()

    assert any("RQ_JOB_MAX_RETRIES" in warning and "大於 0" in warning for warning in warnings)


def test_validate_runtime_settings_warns_for_unknown_queue_routes(monkeypatch):
    from settings import app_config

    monkeypatch.setattr(app_config, "TASK_QUEUE_BACKEND", "rq")
    monkeypatch.setattr(app_config, "TASK_QUEUE_NAMES", ("analysis.high",))
    monkeypatch.setattr(app_config, "TASK_QUEUE_ROUTES", {"analysis": "missing.queue"})

    warnings = app_config.validate_runtime_settings()

    assert any("TASK_QUEUE_ROUTES" in warning and "missing.queue" in warning for warning in warnings)


def test_malformed_rq_retry_env_is_reported_by_validation(monkeypatch):
    from settings import app_config, runtime_limits

    monkeypatch.setenv("RQ_JOB_MAX_RETRIES", "not-an-int")
    monkeypatch.setenv("RQ_JOB_RETRY_INTERVALS", "60,bad,300")

    importlib.reload(runtime_limits)
    importlib.reload(app_config)

    warnings = app_config.validate_runtime_settings()

    assert any("RQ_JOB_MAX_RETRIES" in warning and "整數" in warning for warning in warnings)
    assert any("RQ_JOB_RETRY_INTERVALS" in warning and "整數" in warning for warning in warnings)

    monkeypatch.delenv("RQ_JOB_MAX_RETRIES", raising=False)
    monkeypatch.delenv("RQ_JOB_RETRY_INTERVALS", raising=False)
    importlib.reload(runtime_limits)
    importlib.reload(app_config)


def test_api_module_uses_api_queue_constructor():
    api_source = (BACKEND / "api.py").read_text(encoding="utf-8")

    assert "from task_queue import create_api_task_queue" in api_source
    assert "create_task_queue()" not in api_source
