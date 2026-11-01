"""Logically read-only SQLite and raw RQ probes, NOT full production readiness.

The controller supplies exact actual paths, expected table names, queue bindings,
and the independently verified legacy payload builder. No backend/env imports,
resource creation, schema migration, job deserialization or registry cleanup.

SQLite mode=ro still updates read-coordination marks in an existing SHM. That is
not a business-data write. WAL mode requires existing WAL and SHM, so a missing
sidecar is rejected before connecting. No immutable flag is used on live data.
The controller owns actual paths, excludes file replacement/deletion during the
probe, and supplies bounded Redis timeouts. This is neither a filesystem sandbox
nor a cross-resource transaction, and it does not test database writeability.
"""
from pathlib import Path
import os
import re
import sqlite3
import stat


DIRECTORIES = ("output_dir", "cache_dir", "market_calendar_dir", "yfinance_cache_dir")
DATABASES = ("cache_db", "task_db", "decision_tracking_db", "watchlist_db", "checkpoint_db")
REGISTRIES = {"started": "wip", "deferred": "deferred", "failed": "failed", "scheduled": "scheduled"}
LIMITATIONS = [
    "logical_readonly_not_filesystem_inert; existing_SHM_read_marks_may_change",
    "WAL_requires_existing_WAL_and_SHM; Postgres_unverified",
    "table_presence_not_full_schema_version_or_writeability",
    "raw_queue_counts_not_atomic; may_include_expired_or_missing_jobs",
    "job_identity_payload_callbacks_worker_health_and_drain_unverified",
    "controller_must_bind_actual_paths_revision_resources_and_timeouts",
]


class ProbeUnavailable(ValueError):
    """A probe prerequisite failed; messages contain labels, never supplied paths."""


def _path(value):
    try:
        path = Path(os.fspath(value))
    except (TypeError, ValueError):
        raise ProbeUnavailable("explicit_absolute_path_required") from None
    if not path.is_absolute() or ".." in path.parts:
        raise ProbeUnavailable("explicit_absolute_path_required")
    return path


def _existing(path, *, directory=False):
    for item in (path, *path.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ProbeUnavailable("symlink_path_rejected")
    info = path.stat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode):
        raise ProbeUnavailable("unexpected_path_type")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _sqlite_family(path):
    if os.path.lexists(str(path) + "-journal"):
        raise ProbeUnavailable("sqlite_journal_recovery_unverified")
    with path.open("rb") as stream:
        header = stream.read(100)
    if len(header) != 100 or header[:16] != b"SQLite format 3\x00":
        raise ProbeUnavailable("invalid_sqlite_header")
    versions = header[18:20]
    wal, shm = Path(str(path) + "-wal"), Path(str(path) + "-shm")
    if versions == b"\x02\x02":
        if not all(os.path.lexists(item) for item in (wal, shm)):
            raise ProbeUnavailable("wal_requires_existing_wal_and_shm")
        return "wal", _existing(wal), _existing(shm)
    if versions != b"\x01\x01" or any(os.path.lexists(item) for item in (wal, shm)):
        raise ProbeUnavailable("sqlite_sidecar_or_format_unverified")
    return "rollback", None, None


def _database_schema(path, required):
    before = _existing(path)
    family = _sqlite_family(path)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        if not set(required).issubset(tables):
            raise ProbeUnavailable("required_schema_table_missing")
    finally:
        connection.close()
    after_family = _sqlite_family(path)
    if _existing(path) != before:
        raise ProbeUnavailable("storage_changed_during_probe")
    # DB/WAL content metadata must be unchanged. SHM can update coordination marks,
    # but must remain the same existing regular file, never a new/replaced sidecar.
    if (after_family[:2] != family[:2]
            or (family[2] is not None and after_family[2][:2] != family[2][:2])):
        raise ProbeUnavailable("storage_changed_during_probe")
    return family[0]


def _count(value):
    if type(value) is not int or value < 0:
        raise ProbeUnavailable("unknown_queue_count")
    return value


class ReadOnlyMaintenanceProbe:
    """Explicit builder-compatible probes; successful output remains non-production."""

    def __init__(self, *, directories, sqlite_paths, required_tables, queue_names):
        for values, keys in ((directories, DIRECTORIES), (sqlite_paths, DATABASES),
                             (required_tables, DATABASES)):
            if type(values) is not dict or set(values) != set(keys):
                raise ProbeUnavailable("complete_explicit_storage_manifest_required")
        self._directories = {key: _path(value) for key, value in directories.items()}
        self._databases = {key: _path(value) for key, value in sqlite_paths.items()}
        self._tables = {}
        for key, tables in required_tables.items():
            if (type(tables) not in (list, tuple) or not tables
                    or any(type(name) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in tables)
                    or len(set(tables)) != len(tables)):
                raise ProbeUnavailable("explicit_schema_tables_required")
            self._tables[key] = tuple(tables)
        if (type(queue_names) not in (tuple, list) or not queue_names
                or any(type(name) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", name) for name in queue_names)
                or len(set(queue_names)) != len(queue_names)):
            raise ProbeUnavailable("explicit_exact_queue_names_required")
        self._queue_names = tuple(queue_names)

    def storage_checker(self, *, output_dir, cache_db_path, checkpoint_backend, checkpoint_path):
        result = {"success": False, "storage_semantics": "logical_readonly_sqlite",
                  "writeability_verified": False, "filesystem_inert": False,
                  "shared_memory_coordination": "existing_shm_read_marks_may_change",
                  "directories": {key: "not_checked" for key in DIRECTORIES},
                  "sqlite_paths": {key: "not_checked" for key in DATABASES}, "sqlite_modes": {}}
        resource = "runtime_binding"
        try:
            if checkpoint_backend != "sqlite":
                raise ProbeUnavailable("unsupported_checkpoint_backend")
            if (_path(output_dir) != self._directories["output_dir"]
                    or _path(cache_db_path) != self._databases["cache_db"]
                    or _path(checkpoint_path) != self._databases["checkpoint_db"]):
                raise ProbeUnavailable("runtime_storage_binding_mismatch")
            for label, path in self._directories.items():
                resource = label
                _existing(path, directory=True)
                result["directories"][label] = "existing_directory_only"
            for label, path in self._databases.items():
                resource = label
                result["sqlite_modes"][label] = _database_schema(path, self._tables[label])
                # Labels deliberately replace absolute data paths in the HTTP payload.
                result["sqlite_paths"][label] = "readonly_schema_tables_present"
            result["success"] = True
        except ProbeUnavailable as exc:
            result["error"] = str(exc)
        except (OSError, sqlite3.Error, ValueError, TypeError):
            result["error"] = "storage_unavailable_or_invalid"
        if not result["success"]:
            result["error_resource"] = resource
            for statuses in (result["directories"], result["sqlite_paths"]):
                if resource in statuses:
                    statuses[resource] = "failed"
        return result

    def queue_snapshotter(self, task_queue):
        result = {"backend": "rq", "available": False, "depth": None, "queues": {},
                  "registries": {}, "queue_semantics": "raw_non_atomic_counts",
                  "registry_cleanup_performed": False, "job_identity_verified": False}
        try:
            queues = task_queue.queues
            connection = task_queue.redis
            if type(queues) is not dict or set(queues) != set(self._queue_names) or connection is None:
                raise ProbeUnavailable("runtime_queue_binding_mismatch")
            if not any(task_queue.queue is queue for queue in queues.values()):
                raise ProbeUnavailable("default_queue_not_in_exact_manifest")
            # Validate every queue before any Redis I/O; do not touch registry properties.
            for name in self._queue_names:
                queue = queues[name]
                if (queue.name != name or queue.key != f"rq:queue:{name}"
                        or queue.connection is not connection):
                    raise ProbeUnavailable("runtime_queue_binding_mismatch")
            if connection.ping() is not True:
                raise ProbeUnavailable("queue_ping_unverified")
            for name in self._queue_names:
                result["queues"][name] = {
                    "depth": _count(connection.llen(f"rq:queue:{name}")),
                    "registries": {label: _count(connection.zcard(f"rq:{prefix}:{name}"))
                                   for label, prefix in REGISTRIES.items()},
                }
            result["depth"] = sum(item["depth"] for item in result["queues"].values())
            result["registries"] = {label: sum(item["registries"][label] for item in result["queues"].values())
                                    for label in REGISTRIES}
            result["available"] = True
        except ProbeUnavailable as exc:
            result["error"] = str(exc)
        except Exception:
            # Driver errors may include credentials/endpoints. Never emit them.
            result["error"] = "queue_unavailable_or_invalid"
        return result

    def build_payload(self, builder, *, runtime_settings, task_queue):
        """Inject both checks explicitly; never expose the legacy 'ready' status.

        The controller must verify this is its exact baseline builder. Lifespan,
        actual resource ownership, safe ASGI admission, and deadlines stay external.
        """
        result = {"schema_version": "stock-agent.maintenance-readonly-probe.v1",
                  "status": "probe_fail", "production_ready": False,
                  "limitations": list(LIMITATIONS), "checks": [], "probe_details": {}}
        observed = result["probe_details"]
        def storage(**kwargs):
            if "storage" in observed:
                raise ProbeUnavailable("duplicate_builder_probe")
            observed["storage"] = self.storage_checker(**kwargs)
            return observed["storage"]
        def queue(value):
            if "queue" in observed:
                raise ProbeUnavailable("duplicate_builder_probe")
            observed["queue"] = self.queue_snapshotter(value)
            return observed["queue"]
        try:
            legacy = builder(runtime_settings=runtime_settings, task_queue=task_queue,
                             storage_checker=storage, queue_snapshotter=queue)
            checks = legacy.get("checks")
            if (set(observed) != {"storage", "queue"} or type(checks) is not list or len(checks) != 2
                    or [item.get("name") for item in checks] != ["storage", "queue"]):
                raise ProbeUnavailable("unexpected_builder_payload")
            result["checks"] = checks
            if (legacy.get("status") == "ready" and all(item.get("status") == "pass" for item in checks)
                    and observed["storage"]["success"] is True and observed["queue"]["available"] is True):
                result["status"] = "probe_pass"
        except Exception:
            result["error"] = "probe_builder_unavailable_or_invalid"
        return result
