# Storage and Cache Repositories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce cloud-neutral report storage and cache protocols, implement local file, SQLite, Redis, and in-memory backends, and inject them into report-producing and report-serving code.

**Architecture:** Keep the existing SQLite report metadata repository separate from report content storage. New code depends on `ReportStorage` and `CacheBackend` protocols; settings factories select concrete local implementations, while compatibility facades preserve existing callers during migration.

**Tech Stack:** Python 3.13, `typing.Protocol`, `dataclasses`, `pathlib`, SQLite, redis-py, FastAPI, pytest.

---

## File Structure

- Create `backend/storage/report_storage.py`: report content protocol, value objects, local filesystem and memory implementations.
- Create `backend/cache_backends.py`: cache protocol plus Redis, SQLite, and memory implementations.
- Create `backend/runtime_dependencies.py`: settings value object, factories, API/Worker runtime containers, FastAPI dependency helpers.
- Modify `backend/settings/storage.py`: backend selection and checkpoint path settings.
- Modify `backend/cache_store.py`: compatibility facade backed by an injectable `CacheBackend`.
- Modify `backend/report_persistence.py`: persist rendered report bundles through `ReportStorage` before metadata indexing.
- Modify `backend/analysis_jobs.py`: inject storage/cache through the job runtime.
- Modify `backend/api_routes/reports.py` and `backend/report_history_service.py`: read/delete report content through `ReportStorage`.
- Modify `backend/api.py`: attach `ApiRuntime` to `app.state` and pass storage dependencies to the reports router.
- Modify `main.py`: use `LocalFileStorage` rather than direct `open()` calls.
- Test `tests/test_report_storage.py`, `tests/test_cache_backends.py`, `tests/test_runtime_dependencies.py`, and existing report tests.

### Task 1: ReportStorage contract and local implementations

**Files:**
- Create: `backend/storage/report_storage.py`
- Modify: `backend/storage/__init__.py`
- Test: `tests/test_report_storage.py`

- [ ] **Step 1: Write failing behavioral tests**

Create `tests/test_report_storage.py` with tests that define the public contract:

```python
from pathlib import Path

import pytest

from storage.report_storage import InMemoryStorage, LocalFileStorage


def test_local_file_storage_round_trip_is_atomic_and_lists_metadata(tmp_path):
    storage = LocalFileStorage(tmp_path)
    saved = storage.save_report("2330/report.html", b"<h1>TSMC</h1>", content_type="text/html")

    assert saved.key == "2330/report.html"
    assert saved.size == len(b"<h1>TSMC</h1>")
    assert storage.get_report(saved.key).content == b"<h1>TSMC</h1>"
    assert [item.key for item in storage.list_reports(prefix="2330/")] == [saved.key]
    assert list(tmp_path.rglob("*.tmp")) == []


@pytest.mark.parametrize("key", ["../secret", "/tmp/secret", "a/../../secret", ""])
def test_local_file_storage_rejects_unsafe_keys(tmp_path, key):
    storage = LocalFileStorage(tmp_path)
    with pytest.raises(ValueError, match="report key"):
        storage.save_report(key, b"x", content_type="text/plain")


def test_in_memory_storage_copies_content_and_supports_delete():
    storage = InMemoryStorage()
    payload = bytearray(b"report")
    storage.save_report("report.md", payload, content_type="text/markdown")
    payload[:] = b"changed"

    assert storage.get_report("report.md").content == b"report"
    assert storage.delete_report("report.md") is True
    assert storage.get_report("report.md") is None
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_report_storage.py -q
```

Expected: collection fails with `ModuleNotFoundError: storage.report_storage`.

- [ ] **Step 3: Implement the protocol and value objects**

Create `backend/storage/report_storage.py` with these concrete public types and method signatures:

```python
from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class StoredReport:
    key: str
    size: int
    content_type: str
    updated_at: datetime


@dataclass(frozen=True)
class StoredReportContent:
    metadata: StoredReport
    content: bytes


@runtime_checkable
class ReportStorage(Protocol):
    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport: ...
    def get_report(self, key: str) -> StoredReportContent | None: ...
    def delete_report(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def list_reports(self, *, prefix: str = "") -> list[StoredReport]: ...


def normalize_report_key(key: str) -> str:
    raw = str(key or "").replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Invalid report key")
    return path.as_posix()
```

- [ ] **Step 4: Implement LocalFileStorage and InMemoryStorage**

In the same file, implement `LocalFileStorage` with `_path_for()` resolving under `root`, `save_report()` using `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` followed by `os.replace`, MIME metadata inferred from the stored sidecar-free key, and sorted recursive listing. Implement `InMemoryStorage` with a `threading.RLock`, immutable `bytes(content)`, UTC timestamps, prefix filtering, and defensive value-object reconstruction on reads.

The constructor and helper API must be:

```python
class LocalFileStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        normalized = normalize_report_key(key)
        candidate = (self.root / normalized).resolve(strict=False)
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Invalid report key")
        return candidate


class InMemoryStorage:
    def __init__(self):
        self._items: dict[str, StoredReportContent] = {}
        self._lock = threading.RLock()
```

- [ ] **Step 5: Export and verify GREEN**

Export the five public types from `backend/storage/__init__.py`, then run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_report_storage.py -q
```

Expected: all report storage tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/storage/report_storage.py backend/storage/__init__.py tests/test_report_storage.py
git commit -m "feat: add report storage repositories"
```

### Task 2: CacheBackend implementations and compatibility facade

**Files:**
- Create: `backend/cache_backends.py`
- Modify: `backend/cache_store.py`
- Test: `tests/test_cache_backends.py`

- [ ] **Step 1: Write failing cache contract tests**

Create tests with a minimal Redis fake that records `set(name, value, ex=...)`, `get`, `delete`, and `close` calls:

```python
import time

import pytest

from cache_backends import InMemoryCache, LocalRedisCache, SqliteCacheBackend


def test_redis_cache_namespaces_json_and_sets_ttl():
    redis = FakeRedis()
    cache = LocalRedisCache(redis_client=redis, namespace="stock:test")
    cache.set_json("quote:2330", {"price": 1000}, ttl_seconds=60)

    assert redis.last_set[0] == "stock:test:quote:2330"
    assert redis.last_set[2] == 60
    assert cache.get_json("quote:2330") == {"price": 1000}


def test_redis_cache_does_not_hide_connection_failures():
    cache = LocalRedisCache(redis_client=FailingRedis(), namespace="stock:test")
    with pytest.raises(ConnectionError):
        cache.get_json("quote")


def test_in_memory_cache_expires_entries(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    cache = InMemoryCache()
    cache.set_json("k", {"v": 1}, ttl_seconds=5)
    now[0] = 106.0
    assert cache.get_json("k") is None


def test_sqlite_cache_round_trip_and_cleanup(tmp_path):
    cache = SqliteCacheBackend(tmp_path / "cache.sqlite3")
    cache.set_json("k", [1, 2], ttl_seconds=30)
    assert cache.get_json("k") == [1, 2]
    assert cache.delete("k") is True
    cache.close()
```

- [ ] **Step 2: Run and verify RED**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_cache_backends.py -q
```

Expected: import fails because `cache_backends` does not exist.

- [ ] **Step 3: Implement CacheBackend and Redis backend**

Create `backend/cache_backends.py` with:

```python
from __future__ import annotations

import copy
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    def get_json(self, key: str) -> object | None: ...
    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> bool: ...
    def cleanup_expired(self) -> int: ...
    def close(self) -> None: ...


class LocalRedisCache:
    def __init__(self, redis_url: str | None = None, *, redis_client=None, namespace: str = "stock-agent"):
        if redis_client is None:
            from redis import Redis
            redis_client = Redis.from_url(str(redis_url), decode_responses=False)
        self._redis = redis_client
        self._namespace = namespace.strip(":")

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{str(key).strip()}"

    def get_json(self, key: str) -> object | None:
        raw = self._redis.get(self._key(key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._redis.set(self._key(key), json.dumps(value, ensure_ascii=False, default=str), ex=ttl_seconds)

    def delete(self, key: str) -> bool:
        return bool(self._redis.delete(self._key(key)))

    def cleanup_expired(self) -> int:
        return 0

    def close(self) -> None:
        close = getattr(self._redis, "close", None)
        if callable(close):
            close()
```

- [ ] **Step 4: Implement SQLite and memory backends**

Implement `SqliteCacheBackend` using `ThreadLocalSqliteResource`, the existing `cache_entries` schema, WAL, `busy_timeout`, short transactions, and the same JSON semantics. Implement `InMemoryCache` using `copy.deepcopy`, a monotonic expiry timestamp based on `time.time()`, a lock, and `cleanup_expired()`.

Expose `reset()` only on `SqliteCacheBackend` for tests; the protocol remains cloud-neutral.

- [ ] **Step 5: Convert cache_store.py to a compatibility facade**

Keep the existing public functions, but delegate to one replaceable backend:

```python
_backend: CacheBackend | None = None
_backend_lock = threading.Lock()


def get_cache_backend() -> CacheBackend:
    global _backend
    with _backend_lock:
        if _backend is None:
            _backend = SqliteCacheBackend(CACHE_DB_PATH)
        return _backend


def set_cache_backend(backend: CacheBackend) -> None:
    global _backend
    with _backend_lock:
        previous, _backend = _backend, backend
    if previous is not None and previous is not backend:
        previous.close()


def get_cache_json(cache_key: str):
    return get_cache_backend().get_json(cache_key)


def set_cache_json(cache_key: str, value: object, ttl_seconds: int) -> None:
    get_cache_backend().set_json(cache_key, value, ttl_seconds=ttl_seconds)
```

`close_cache_store`, `cleanup_expired_cache_entries`, and `reset_cache_store_for_tests` must delegate and clear `_backend` so existing `tests/conftest.py` path monkeypatching remains effective.

- [ ] **Step 6: Verify GREEN and regression compatibility**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_cache_backends.py tests/test_reviewed_bug_fixes.py tests/test_provider_workflow.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/cache_backends.py backend/cache_store.py tests/test_cache_backends.py
git commit -m "feat: abstract cache backends"
```

### Task 3: Runtime settings, factories, and FastAPI dependency helpers

**Files:**
- Modify: `backend/settings/storage.py`
- Create: `backend/runtime_dependencies.py`
- Test: `tests/test_runtime_dependencies.py`

- [ ] **Step 1: Write failing factory tests**

```python
from runtime_dependencies import RuntimeSettings, create_cache_backend, create_report_storage
from cache_backends import InMemoryCache, LocalRedisCache, SqliteCacheBackend
from storage.report_storage import InMemoryStorage, LocalFileStorage


def test_runtime_factories_select_explicit_backends(tmp_path):
    base = RuntimeSettings(
        output_dir=tmp_path / "reports",
        cache_db_path=tmp_path / "cache.sqlite3",
        redis_url="redis://localhost:6379/15",
        report_storage_backend="memory",
        cache_backend="memory",
        cache_namespace="test",
        checkpoint_path=tmp_path / "checkpoints.sqlite3",
    )
    assert isinstance(create_report_storage(base), InMemoryStorage)
    assert isinstance(create_cache_backend(base), InMemoryCache)


def test_unknown_backend_names_fail_fast(tmp_path):
    settings = RuntimeSettings.for_tests(tmp_path, report_storage_backend="s3")
    with pytest.raises(ValueError, match="REPORT_STORAGE_BACKEND"):
        create_report_storage(settings)
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_runtime_dependencies.py -q
```

Expected: `runtime_dependencies` import failure.

- [ ] **Step 3: Add settings constants**

Add to `backend/settings/storage.py`:

```python
REPORT_STORAGE_BACKEND = os.getenv("REPORT_STORAGE_BACKEND", "local").strip().lower()
CACHE_BACKEND = os.getenv("CACHE_BACKEND", "redis").strip().lower()
CACHE_NAMESPACE = os.getenv("CACHE_NAMESPACE", "stock-agent").strip().strip(":")
LANGGRAPH_CHECKPOINT_PATH = os.getenv(
    "LANGGRAPH_CHECKPOINT_PATH",
    str(CACHE_DIR / "langgraph_checkpoints.sqlite3"),
)
```

Extend `validate_runtime_settings()` to reject unsupported storage/cache names and a blank namespace.

- [ ] **Step 4: Implement explicit runtime factories**

Create an immutable `RuntimeSettings` dataclass with `from_environment()` and `for_tests()`. Implement `create_report_storage()` and `create_cache_backend()` with exact string dispatch. Add `ApiRuntime` and `WorkerRuntime` dataclasses whose idempotent `close()` methods close only owned cache clients and the existing process-local stores.

Provide FastAPI helpers:

```python
def get_api_runtime(request: Request) -> ApiRuntime:
    return request.app.state.runtime


def get_report_storage(request: Request) -> ReportStorage:
    return get_api_runtime(request).report_storage


def get_cache_backend_from_request(request: Request) -> CacheBackend:
    return get_api_runtime(request).cache_backend
```

- [ ] **Step 5: Verify GREEN**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_runtime_dependencies.py -q
```

Expected: all factory and close-idempotency tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/settings/storage.py backend/settings/app_config.py backend/runtime_dependencies.py tests/test_runtime_dependencies.py
git commit -m "feat: add runtime dependency factories"
```

### Task 4: Route report writes and reads through ReportStorage

**Files:**
- Create: `backend/report_persistence.py`
- Modify: `backend/report_rerun_rendering.py`
- Modify: `backend/analysis_jobs.py`
- Modify: `backend/report_history_service.py`
- Modify: `backend/api_routes/reports.py`
- Modify: `backend/api.py`
- Modify: `main.py`
- Test: `tests/test_report_storage_integration.py`

- [ ] **Step 1: Write failing integration tests**

Add tests that inject `InMemoryStorage` into `persist_report_bundle`, `get_report_file`, and `delete_report_files`. Assert HTML, Markdown, and data snapshot keys are written before metadata upsert; assert view repair is still applied; assert delete removes all three keys and updates the metadata repository.

Use this central test:

```python
def test_persist_bundle_writes_all_objects_before_index(monkeypatch):
    order = []
    storage = RecordingStorage(order)
    repository = RecordingRepository(order)

    result = persist_report_bundle(
        filename="2330_v1_report_20260621.html",
        bundle=FakeBundle(html="<html>x</html>", markdown="# x", data_snapshot={"x": 1}, data_trust={}),
        storage=storage,
        repository=repository,
    )

    assert order == ["save:html", "save:md", "save:data", "index"]
    assert result["filename"].endswith(".html")
```

- [ ] **Step 2: Run and verify RED**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_report_storage_integration.py -q
```

Expected: missing `report_persistence` and missing storage parameters.

- [ ] **Step 3: Create one persistence service**

`backend/report_persistence.py` must derive sibling keys from the HTML filename, JSON-encode the snapshot, call storage in HTML/MD/data order, then call `ReportRepository.upsert`. If any save fails, delete only keys saved by that call and do not index. Return keys and the HTML filename.

- [ ] **Step 4: Inject storage into jobs and CLI**

Change `render_and_persist_report()` to accept `storage: ReportStorage`; remove its direct file writes. In `analysis_jobs.py`, obtain the worker runtime inside `run_stock_analysis_job_async` and pass `runtime.report_storage`. In `main.py`, construct `LocalFileStorage(OUTPUT_DIR)` once and use `persist_report_bundle()`.

- [ ] **Step 5: Inject storage into report read/delete routes**

Add `get_report_storage: Callable[[], ReportStorage]` to `ReportRouteDeps`. Update `report_history_service.get_report_file`, `download_report_file`, and `delete_report_files` to accept storage. For binary downloads use `Response(content=item.content, media_type=item.metadata.content_type)` rather than `FileResponse`, because cloud storage has no local path.

Keep list/filter metadata queries on `ReportRepository`; do not scan cloud-neutral storage for list endpoints.

- [ ] **Step 6: Verify focused regressions**

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_report_storage_integration.py tests/test_report_preview.py tests/test_report_index_migrations.py tests/test_reviewed_bug_fixes.py -q
```

Expected: selected report tests pass without direct filesystem assumptions in the new integration tests.

- [ ] **Step 7: Commit**

```bash
git add backend/report_persistence.py backend/report_rerun_rendering.py backend/analysis_jobs.py backend/report_history_service.py backend/api_routes/reports.py backend/api.py main.py tests/test_report_storage_integration.py
git commit -m "refactor: inject report storage"
```

### Task 5: Documentation and full repository verification

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/operator-guide.md`
- Test: full suite

- [ ] **Step 1: Document backend selection**

Document `REPORT_STORAGE_BACKEND`, `CACHE_BACKEND`, `CACHE_NAMESPACE`, Redis failure behavior, local atomic writes, and memory backends being test-only. Explain that `report_repository.py` indexes metadata while `ReportStorage` owns content.

- [ ] **Step 2: Run full verification**

```bash
PYTHON_BIN=$(scripts/project_python.sh)
"$PYTHON_BIN" -m pytest -q
"$PYTHON_BIN" scripts/check_runtime.py
git diff --check
```

Expected: pytest exits 0, runtime check exits 0, and diff check prints nothing.

- [ ] **Step 3: Commit**

```bash
git add README.md docs/architecture.md docs/operator-guide.md
git commit -m "docs: explain storage and cache backends"
```
