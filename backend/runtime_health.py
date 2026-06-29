"""Runtime liveness and readiness payload builders."""

from __future__ import annotations

from typing import Any, Callable

from queue_observability import snapshot_task_queue
from security_sanitizer import sanitize_error_message
from storage_inventory import ensure_runtime_storage


def build_health_payload() -> dict:
    return {"status": "ok"}


def build_readiness_payload(
    *,
    runtime_settings: Any,
    task_queue: Any,
    warnings: list[str] | None = None,
    storage_checker: Callable[..., dict] = ensure_runtime_storage,
    queue_snapshotter: Callable[[Any], dict] = snapshot_task_queue,
) -> dict:
    checks = []
    checks.extend(_warning_checks(warnings or []))
    checks.append(_storage_check(runtime_settings, storage_checker))
    checks.append(_queue_check(task_queue, queue_snapshotter))
    status = "ready" if all(check["status"] != "fail" for check in checks) else "not_ready"
    return {"status": status, "checks": checks}


def _warning_checks(warnings: list[str]) -> list[dict]:
    return [
        {
            "name": "runtime_settings",
            "status": "warn",
            "message": sanitize_error_message(warning),
        }
        for warning in warnings
    ]


def _storage_check(runtime_settings: Any, storage_checker: Callable[..., dict]) -> dict:
    try:
        result = storage_checker(
            output_dir=runtime_settings.output_dir,
            cache_db_path=runtime_settings.cache_db_path,
            checkpoint_path=runtime_settings.checkpoint_path,
        )
    except Exception as exc:
        return {
            "name": "storage",
            "status": "fail",
            "message": sanitize_error_message(exc),
        }
    return {
        "name": "storage",
        "status": "pass" if result.get("success") else "fail",
        "message": "",
        "details": {
            "directories": result.get("directories", {}),
            "sqlite_paths": result.get("sqlite_paths", {}),
        },
    }


def _queue_check(task_queue: Any, queue_snapshotter: Callable[[Any], dict]) -> dict:
    snapshot = queue_snapshotter(task_queue)
    if snapshot.get("available"):
        return {
            "name": "queue",
            "status": "pass",
            "message": "",
            "details": snapshot,
        }
    return {
        "name": "queue",
        "status": "fail",
        "message": sanitize_error_message(snapshot.get("error") or "task queue unavailable"),
        "details": snapshot,
    }
