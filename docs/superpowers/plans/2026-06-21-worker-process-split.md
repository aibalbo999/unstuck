# API and Worker Process Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make FastAPI a lightweight RQ producer and run analysis, schedulers, and maintenance in independently managed worker processes.

**Architecture:** Web mode requires Redis-backed RQ and never starts consumers. `worker_main.py` exposes focused process roles and an `all` supervisor that uses multiprocessing `spawn`; every child creates and closes its own runtime dependencies.

**Tech Stack:** Python 3.13, FastAPI lifespan, RQ 1.16, redis-py, asyncio, multiprocessing spawn, pytest.

---

## File Structure

- Modify `backend/task_queue.py`: distinguish API producer from local embedded queue and configure RQ retries.
- Modify `backend/settings/runtime_limits.py`: default queue backend and retry settings.
- Modify `backend/settings/app_config.py`: validate queue configuration.
- Modify `backend/api.py`: remove worker/scheduler/maintenance startup and local runtime lock lifecycle.
- Create `backend/worker_main.py`: queue, schedulers, maintenance, and all roles.
- Modify `backend/runtime_dependencies.py`: process-owned worker resources from the repository plan.
- Modify `backend/job_store.py`: allow `waiting_retry` as a non-terminal active status.
- Modify `backend/watchlist_scheduler.py` and `backend/decision_tracking_scheduler.py`: cancellation-safe run functions used by worker_main.
- Test `tests/test_task_queue_boundaries.py`, `tests/test_api_lifespan.py`, and `tests/test_worker_main.py`.

### Task 1: Enforce a cross-process queue at the API boundary

**Files:**
- Modify: `backend/task_queue.py`
- Modify: `backend/settings/runtime_limits.py`
- Modify: `backend/settings/app_config.py`
- Test: `tests/test_task_queue_boundaries.py`

- [ ] **Step 1: Write failing queue boundary tests**

```python
import pytest

import task_queue


def test_api_queue_rejects_process_local_backend(monkeypatch):
    monkeypatch.setattr(task_queue, "TASK_QUEUE_BACKEND", "local")
    with pytest.raises(RuntimeError, match="Redis.*RQ"):
        task_queue.create_api_task_queue()


def test_api_queue_builds_rq_producer(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(task_queue, "TASK_QUEUE_BACKEND", "rq")
    monkeypatch.setattr(task_queue, "RQTaskQueue", lambda: sentinel)
    assert task_queue.create_api_task_queue() is sentinel


def test_rq_queue_adds_delayed_retry(monkeypatch):
    fake_queue = FakeRqQueue()
    queue = task_queue.RQTaskQueue(redis_client=FakeRedis(), queue=fake_queue)
    queue.enqueue("job-1", importable_job, "arg")
    assert fake_queue.kwargs["retry"].max == task_queue.RQ_JOB_MAX_RETRIES
    assert fake_queue.kwargs["retry"].intervals == task_queue.RQ_JOB_RETRY_INTERVALS
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_task_queue_boundaries.py -q
```

Expected: `create_api_task_queue` and injectable RQ constructor do not exist.

- [ ] **Step 3: Add runtime settings**

In `backend/settings/runtime_limits.py`:

```python
TASK_QUEUE_BACKEND = os.getenv("TASK_QUEUE_BACKEND", "rq").strip().lower()
RQ_JOB_MAX_RETRIES = int(os.getenv("RQ_JOB_MAX_RETRIES", "4"))
RQ_JOB_RETRY_INTERVALS = tuple(
    int(value.strip())
    for value in os.getenv("RQ_JOB_RETRY_INTERVALS", "60,300,900,1800").split(",")
    if value.strip()
)
```

Validate `TASK_QUEUE_BACKEND in {"local", "rq"}`, positive retry counts, and an interval count sufficient for configured retries.

- [ ] **Step 4: Implement producer/consumer-safe queue constructors**

Update `RQTaskQueue.__init__` to accept optional `redis_client` and `queue`, add `close()`, and configure `rq.Retry(max=RQ_JOB_MAX_RETRIES, interval=list(RQ_JOB_RETRY_INTERVALS))` in `enqueue_call`.

Add:

```python
def create_api_task_queue():
    if TASK_QUEUE_BACKEND != "rq":
        raise RuntimeError(
            "FastAPI requires Redis + RQ because LocalAsyncQueue cannot cross process boundaries."
        )
    return RQTaskQueue()
```

Keep `create_task_queue()` for embedded tests, but do not call it from `api.py`.

- [ ] **Step 5: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_task_queue_boundaries.py tests/test_reviewed_bug_fixes.py -q
```

Expected: queue tests pass, including existing LocalAsyncQueue await behavior.

- [ ] **Step 6: Commit**

```bash
git add backend/task_queue.py backend/settings/runtime_limits.py backend/settings/app_config.py tests/test_task_queue_boundaries.py
git commit -m "refactor: enforce RQ at API boundary"
```

### Task 2: Strip background execution from FastAPI lifespan

**Files:**
- Modify: `backend/api.py`
- Test: `tests/test_api_lifespan.py`
- Modify: `tests/test_runtime_observability.py`

- [ ] **Step 1: Write a behavioral lifespan test**

The test must enter the actual app lifespan with fakes and prove no background factory is called:

```python
from fastapi.testclient import TestClient

import api


def test_api_lifespan_never_starts_workers_or_schedulers(monkeypatch):
    forbidden = []
    monkeypatch.setattr(api, "validate_runtime_settings", lambda: [])
    monkeypatch.setattr(api, "analysis_task_queue", FakeProducer())
    monkeypatch.setattr(api, "create_watchlist_scheduler_task", lambda **kwargs: forbidden.append("watchlist"), raising=False)
    monkeypatch.setattr(api, "create_decision_tracking_scheduler_task", lambda **kwargs: forbidden.append("decision"), raising=False)

    with TestClient(api.create_app()) as client:
        assert client.get("/api/client-config").status_code == 200

    assert forbidden == []
    assert api.analysis_task_queue.started == 0
    assert api.analysis_task_queue.stopped == 0
```

Add a source-boundary assertion that `api.py` contains none of `_cleanup_reports_forever`, `_mark_abandoned_local_jobs`, `start_workers`, `create_watchlist_scheduler_task`, or `create_decision_tracking_scheduler_task`.

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_api_lifespan.py -q
```

Expected: forbidden startup behavior is observed or source assertions fail.

- [ ] **Step 3: Simplify api.py lifecycle**

Remove imports and globals for `asyncio`, `suppress`, schedulers, maintenance loop, runtime instance lock, `StockDataService`, and local abandoned-job cleanup.

Construct the queue with `create_api_task_queue()`. The lifespan becomes:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    for warning in validate_runtime_settings():
        emit_log(f"設定檢查警告：{warning}")
    runtime = create_api_runtime(RuntimeSettings.from_environment())
    app.state.runtime = runtime
    try:
        yield
    finally:
        await close_cached_clients_async()
        runtime.close()
```

Do not call `close_job_store()` from API shutdown; thread-local stores close naturally at process shutdown and Worker owns its own lifecycle. Queue producer Redis is closed by `ApiRuntime.close()`.

- [ ] **Step 4: Update old source-contract test**

Keep assertions that FastAPI uses lifespan and routers, but replace the old implicit background expectations with explicit absence checks.

- [ ] **Step 5: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_api_lifespan.py tests/test_runtime_observability.py tests/test_report_preview.py -q
```

Expected: selected API tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/api.py tests/test_api_lifespan.py tests/test_runtime_observability.py
git commit -m "refactor: keep FastAPI lifespan lightweight"
```

### Task 3: Create worker role entry points

**Files:**
- Create: `backend/worker_main.py`
- Modify: `backend/watchlist_scheduler.py`
- Modify: `backend/decision_tracking_scheduler.py`
- Test: `tests/test_worker_main.py`

- [ ] **Step 1: Write failing role-isolation tests**

Use dependency injection rather than launching real processes:

```python
import asyncio

import worker_main


def test_queue_role_only_runs_rq_worker(monkeypatch):
    calls = []
    runtime = FakeWorkerRuntime(calls)
    monkeypatch.setattr(worker_main, "create_worker_runtime", lambda *_: runtime)
    monkeypatch.setattr(worker_main, "run_rq_worker", lambda value: calls.append("queue"))

    worker_main.run_role("queue")

    assert calls == ["queue", "close"]


def test_scheduler_role_creates_both_tasks_and_cancels_them(monkeypatch):
    calls = []
    monkeypatch.setattr(worker_main, "run_scheduler_process", lambda runtime: calls.append("schedulers"))
    worker_main.run_role("schedulers", runtime_factory=lambda: FakeWorkerRuntime(calls))
    assert calls == ["schedulers", "close"]


def test_all_role_uses_spawn_and_three_children(monkeypatch):
    context = FakeSpawnContext()
    monkeypatch.setattr(worker_main.multiprocessing, "get_context", lambda method: context.assert_method(method))
    worker_main.run_all_roles()
    assert context.roles == ["queue", "schedulers", "maintenance"]
    assert all(process.joined for process in context.processes)
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_worker_main.py -q
```

Expected: `worker_main` does not exist.

- [ ] **Step 3: Expose cancellation-safe scheduler coroutines**

In both scheduler modules, retain `create_*_task()` for compatibility and add public `run_*_scheduler(...)` async functions that await the existing forever loop. Ensure `asyncio.CancelledError` is re-raised rather than caught by `except Exception` on Python versions where necessary.

- [ ] **Step 4: Implement worker_main role dispatch**

Create a module-level, spawn-pickleable API:

```python
ROLES = ("queue", "schedulers", "maintenance", "all")


def run_rq_worker(runtime: WorkerRuntime) -> None:
    from rq import Worker
    Worker([runtime.task_queue.queue], connection=runtime.task_queue.redis).work(with_scheduler=True)


def run_role(role: str, runtime_factory=create_worker_runtime) -> None:
    runtime = runtime_factory(RuntimeSettings.from_environment())
    try:
        if role == "queue":
            run_rq_worker(runtime)
        elif role == "schedulers":
            asyncio.run(run_scheduler_process(runtime))
        elif role == "maintenance":
            asyncio.run(run_maintenance_process(runtime))
        else:
            raise ValueError(f"Unknown worker role: {role}")
    finally:
        runtime.close()


def child_main(role: str) -> None:
    run_role(role)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=ROLES, default="all")
    args = parser.parse_args(argv)
    if args.role == "all":
        run_all_roles()
    else:
        run_role(args.role)
    return 0
```

`run_scheduler_process()` creates `StockDataService` only through `WorkerRuntime`, starts both scheduler tasks, awaits them, and cancels both in `finally`. `run_maintenance_process()` owns the cleanup loop moved verbatim from API.

- [ ] **Step 5: Implement spawn supervisor and signal forwarding**

Use `multiprocessing.get_context("spawn")`; create exactly three children with target `child_main`. A parent signal handler calls `terminate()` only for live children. The normal path joins all children and returns non-zero if any child exits non-zero. Never create runtime resources in the parent.

- [ ] **Step 6: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_worker_main.py tests/test_watchlist_service.py tests/test_decision_tracking_workflow.py -q
```

Expected: role and existing scheduler tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/worker_main.py backend/watchlist_scheduler.py backend/decision_tracking_scheduler.py tests/test_worker_main.py
git commit -m "feat: add independent worker process roles"
```

### Task 4: Treat retry-waiting jobs as active

**Files:**
- Modify: `backend/job_store.py`
- Modify: `backend/job_store_schema.py`
- Create: `tests/test_job_store.py`

- [ ] **Step 1: Write failing status transition tests**

```python
def test_waiting_retry_job_remains_active(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "waiting_retry", error="429")
    found = job_store.find_active_job("2330.TW", "v1")
    assert found["job_id"] == job_id
    assert found["status"] == "waiting_retry"


def test_waiting_retry_can_return_to_running():
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "waiting_retry", error="429")
    job_store.update_job(job_id, "running", error=None)
    assert job_store.get_job(job_id)["status"] == "running"
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_job_store.py -q
```

Expected: `find_active_job` omits `waiting_retry`.

- [ ] **Step 3: Update active-state queries**

Define:

```python
ACTIVE_JOB_STATUSES = {"queued", "running", "waiting_retry"}
TERMINAL_JOB_STATUSES = {"done", "error", "cancelled"}
```

Use all three active statuses in `find_active_job`, event timestamp updates, cancellation, cleanup, and observability queries. No schema migration is required because status is text without a CHECK constraint.

- [ ] **Step 4: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_job_store.py tests/test_runtime_observability.py -q
```

Expected: job store and observability tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/job_store.py tests/test_job_store.py
git commit -m "feat: track jobs waiting for retry"
```

### Task 5: Operator documentation and process smoke test

**Files:**
- Modify: `README.md`
- Modify: `docs/operator-guide.md`
- Modify: `docs/architecture.md`
- Test: `tests/test_worker_process_smoke.py`

- [ ] **Step 1: Add a Redis/RQ smoke test**

Write an opt-in test marked `integration` that skips unless `REDIS_TEST_URL` is set. It must enqueue an importable no-op job, launch `python backend/worker_main.py --role queue` with a one-job burst option, wait for the RQ job to finish, then assert the API process never consumes it.

- [ ] **Step 2: Document startup and shutdown**

Add exact commands:

```bash
redis-server
python backend/worker_main.py --role all
uvicorn api:app --app-dir backend
```

Document separate production roles, required Redis health checks, RQ retry settings, SIGTERM behavior, and why `TASK_QUEUE_BACKEND=local` is rejected by Web mode.

- [ ] **Step 3: Run verification**

```bash
PYTHON_BIN=$(scripts/project_python.sh)
"$PYTHON_BIN" -m pytest tests/test_task_queue_boundaries.py tests/test_api_lifespan.py tests/test_worker_main.py tests/test_job_store.py -q
"$PYTHON_BIN" -m pytest -q
"$PYTHON_BIN" scripts/check_runtime.py
git diff --check
```

Expected: all commands exit 0 and diff check is silent.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/operator-guide.md docs/architecture.md tests/test_worker_process_smoke.py
git commit -m "docs: document split worker operations"
```
