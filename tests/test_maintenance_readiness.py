"""No live endpoints: private SQLite and raw Redis-command boundary fixtures only."""
from functools import lru_cache
from hashlib import sha256
import importlib.util
from pathlib import Path
import json
import sqlite3
import subprocess
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "758242290e795146520f58f68ffa113cac35e52c"
PINS = {
    "runtime_health": "ea13409e9e3f7b6cf985103c42750f3a483f418b04b1bfab01c6b5ec8ab313e4",
    "storage_inventory": "c9561636f5f726bc825e3dcdc9a7de9c17afbf93ef4b054b85b39fbd722f1b4e",
    "queue_observability": "c8156c88777af83a3330d7db4a453162bbbbb8ef86e1942df2559a47ef9b7c28",
}


@lru_cache(maxsize=1)
def module():
    spec = importlib.util.spec_from_file_location(
        "maintenance_readiness_tested", ROOT / "scripts" / "maintenance_readiness.py"
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def baseline(name):
    source = subprocess.check_output(["git", "show", f"{BASELINE}:backend/{name}.py"], cwd=ROOT)
    assert sha256(source).hexdigest() == PINS[name]
    value = ModuleType(f"baseline_probe_{name}")
    exec(compile(source, f"{BASELINE}:backend/{name}.py", "exec"), value.__dict__)
    return value


class RawRedis:
    def __init__(self):
        self.calls = []

    def ping(self):
        self.calls.append(("PING",))
        return True

    def llen(self, key):
        self.calls.append(("LLEN", key))
        return 2

    def zcard(self, key):
        self.calls.append(("ZCARD", key))
        return 3


class ExactQueue:
    def __init__(self, name, connection):
        self.name, self.connection = name, connection
        self.key = f"rq:queue:{name}"

    def __getattr__(self, name):
        raise AssertionError(f"No RQ registry properties, jobs or count: {name}")


def task_queue(names=("canary.s0",)):
    redis = RawRedis()
    queues = {name: ExactQueue(name, redis) for name in names}
    return SimpleNamespace(redis=redis, queue=queues[names[0]], queues=queues)


@pytest.fixture
def configured(tmp_path):
    directories = {name: tmp_path / name for name in
                   ("output_dir", "cache_dir", "market_calendar_dir", "yfinance_cache_dir")}
    for path in directories.values():
        path.mkdir()
    paths = {name: tmp_path / f"{name}.sqlite3" for name in
             ("cache_db", "task_db", "decision_tracking_db", "watchlist_db", "checkpoint_db")}
    for path in paths.values():
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE expected (id INTEGER PRIMARY KEY)")
    kwargs = {"directories": directories, "sqlite_paths": paths,
              "required_tables": {name: ["expected"] for name in paths},
              "queue_names": ("canary.s0",)}
    settings = SimpleNamespace(output_dir=str(directories["output_dir"]),
                               cache_db_path=str(paths["cache_db"]),
                               checkpoint_backend="sqlite", checkpoint_path=str(paths["checkpoint_db"]))
    return kwargs, settings


def storage_args(settings):
    return {name: getattr(settings, name) for name in
            ("output_dir", "cache_db_path", "checkpoint_backend", "checkpoint_path")}


def file_state(root):
    return {str(path.relative_to(root)): (path.stat().st_mtime_ns, sha256(path.read_bytes()).hexdigest())
            for path in root.rglob("*") if path.is_file()}


def test_existing_rollback_storage_schema_probe_has_no_file_changes(configured, tmp_path):
    kwargs, settings = configured
    before = file_state(tmp_path)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))
    assert result["success"] is True
    assert result["storage_semantics"] == "logical_readonly_sqlite"
    assert result["writeability_verified"] is False
    assert file_state(tmp_path) == before


def test_missing_database_is_rejected_without_creation(configured, tmp_path):
    kwargs, settings = configured
    kwargs["sqlite_paths"]["watchlist_db"].unlink()
    before = file_state(tmp_path)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))
    assert result["success"] is False
    assert result["error_resource"] == "watchlist_db"
    assert result["sqlite_paths"]["watchlist_db"] == "failed"
    assert result["sqlite_paths"]["checkpoint_db"] == "not_checked"
    assert file_state(tmp_path) == before


def test_raw_queue_only_uses_exact_read_commands(configured):
    kwargs, _ = configured
    queue = task_queue()
    result = module().ReadOnlyMaintenanceProbe(**kwargs).queue_snapshotter(queue)
    assert result["available"] is True and result["depth"] == 2
    assert queue.redis.calls == [
        ("PING",), ("LLEN", "rq:queue:canary.s0"),
        ("ZCARD", "rq:wip:canary.s0"), ("ZCARD", "rq:deferred:canary.s0"),
        ("ZCARD", "rq:failed:canary.s0"), ("ZCARD", "rq:scheduled:canary.s0"),
    ]
    assert result["job_identity_verified"] is False
    assert result["registry_cleanup_performed"] is False


def test_exact_baseline_builder_receives_explicit_probes_not_default_writers(configured, tmp_path):
    kwargs, settings = configured
    before = file_state(tmp_path)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).build_payload(
        baseline("runtime_health").build_readiness_payload,
        runtime_settings=settings, task_queue=task_queue(),
    )
    assert result["schema_version"] == "stock-agent.maintenance-readonly-probe.v1"
    assert result["status"] == "probe_pass" and result["production_ready"] is False
    assert result["probe_details"]["storage"]["writeability_verified"] is False
    assert [check["status"] for check in result["checks"]] == ["pass", "pass"]
    assert file_state(tmp_path) == before


def old_storage_probe(tmp_path):
    old = baseline("storage_inventory")
    touched = []
    old._configure_yfinance_cache = lambda path: touched.append(path)
    paths = {name: str(tmp_path / name) for name in (
        "output_dir", "cache_dir", "cache_db_path", "task_db_path", "checkpoint_path",
        "decision_tracking_db_path", "watchlist_db_path", "yfinance_cache_dir", "market_calendar_dir")}
    result = old.ensure_runtime_storage(**paths, checkpoint_backend="sqlite")
    return result, touched


def old_queue_probe():
    from rq.registry import FailedJobRegistry

    class Redis(RawRedis):
        def zremrangebyscore(self, *args):
            self.calls.append(("ZREMRANGEBYSCORE", *args))
            return 1

    connection = Redis()
    queue = SimpleNamespace(name="canary.s0", count=0,
                            failed_job_registry=FailedJobRegistry(name="canary.s0", connection=connection))
    result = baseline("queue_observability").snapshot_task_queue(
        SimpleNamespace(queue=queue, redis=connection, queues={"canary.s0": queue})
    )
    return result, connection.calls


def test_original_storage_checker_is_documented_as_mutating_private_files(tmp_path):
    result, touched = old_storage_probe(tmp_path)
    assert result["success"] is True and touched
    assert all(Path(path).is_file() for path in result["sqlite_paths"].values())


def test_original_queue_snapshot_executes_real_rq_registry_cleanup():
    result, calls = old_queue_probe()
    assert result["available"] is True
    assert any(call[0] == "ZREMRANGEBYSCORE" for call in calls)


@pytest.mark.parametrize("kind", ["corrupt", "schema", "symlink", "wal", "shm", "journal"])
def test_storage_rejects_unverified_database_without_modifying_it(configured, tmp_path, kind):
    kwargs, settings = configured
    path = kwargs["sqlite_paths"]["task_db"]
    if kind == "corrupt":
        path.write_bytes(b"not-sqlite")
    elif kind == "schema":
        kwargs["required_tables"]["task_db"] = ["absent"]
    elif kind == "symlink":
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
    else:
        Path(str(path) + "-" + kind).write_bytes(b"must not remove or overwrite")
    before = file_state(tmp_path)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))
    assert result["success"] is False
    assert str(tmp_path) not in json.dumps(result)
    assert file_state(tmp_path) == before


@pytest.mark.parametrize("kind", ["missing_directory", "symlink_parent", "wrong_output", "wrong_cache", "wrong_checkpoint", "postgres", "unknown_backend"])
def test_runtime_paths_and_backend_are_explicit_no_defaults(configured, tmp_path, kind):
    kwargs, settings = configured
    if kind == "missing_directory":
        kwargs["directories"]["yfinance_cache_dir"].rmdir()
    elif kind == "symlink_parent":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        kwargs["sqlite_paths"]["task_db"] = alias / "task_db.sqlite3"
    elif kind.startswith("wrong_"):
        field = {"wrong_output": "output_dir", "wrong_cache": "cache_db_path", "wrong_checkpoint": "checkpoint_path"}[kind]
        setattr(settings, field, str(tmp_path / "not_created"))
    else:
        settings.checkpoint_backend = "postgres" if kind == "postgres" else "unknown"
    before = file_state(tmp_path)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))
    assert result["success"] is False
    assert file_state(tmp_path) == before


@pytest.mark.parametrize("kind", ["missing_db", "missing_dir", "empty_tables", "table_as_string", "unknown_db", "relative_path", "empty_queues", "duplicate_queues", "unsafe_queue"])
def test_unknown_manifest_is_not_filled_from_environment(configured, kind):
    kwargs, _ = configured
    if kind == "missing_db": del kwargs["sqlite_paths"]["watchlist_db"]
    if kind == "missing_dir": del kwargs["directories"]["cache_dir"]
    if kind == "empty_tables": kwargs["required_tables"]["task_db"] = []
    if kind == "table_as_string": kwargs["required_tables"]["task_db"] = "expected"
    if kind == "unknown_db": kwargs["sqlite_paths"]["extra"] = kwargs["sqlite_paths"]["task_db"]
    if kind == "relative_path": kwargs["directories"]["output_dir"] = "relative"
    if kind == "empty_queues": kwargs["queue_names"] = []
    if kind == "duplicate_queues": kwargs["queue_names"] = ["canary.s0", "canary.s0"]
    if kind == "unsafe_queue": kwargs["queue_names"] = ["canary:*password"]
    with pytest.raises(module().ProbeUnavailable):
        module().ReadOnlyMaintenanceProbe(**kwargs)


@pytest.mark.parametrize("kind", ["missing", "extra_queue", "missing_queue", "wrong_default", "wrong_key", "wrong_connection", "wrong_name"])
def test_queue_binding_fails_before_any_io(configured, kind):
    kwargs, _ = configured
    queue = task_queue()
    connection = queue.redis
    if kind == "extra_queue": queue.queues["analysis.high"] = ExactQueue("analysis.high", connection)
    if kind == "missing_queue": queue.queues.clear()
    if kind == "wrong_default": queue.queue = ExactQueue("analysis.high", connection)
    if kind == "wrong_key": queue.queue.key = "rq:queue:analysis.high"
    if kind == "wrong_connection": queue.queue.connection = RawRedis()
    if kind == "wrong_name": queue.queue.name = "analysis.high"
    result = module().ReadOnlyMaintenanceProbe(**kwargs).queue_snapshotter(None if kind == "missing" else queue)
    assert result["available"] is False and result["depth"] is None
    assert connection.calls == []


@pytest.mark.parametrize("value", [None, True, -1, "0", 1.5])
@pytest.mark.parametrize("method", ["llen", "zcard"])
def test_unknown_raw_counts_are_not_coerced_to_healthy_zero(configured, method, value):
    kwargs, _ = configured
    queue = task_queue()
    setattr(queue.redis, method, lambda key: value)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).queue_snapshotter(queue)
    assert result["available"] is False and result["depth"] is None


@pytest.mark.parametrize("method", ["ping", "llen", "zcard"])
def test_driver_failure_is_fail_closed_and_secret_safe(configured, method):
    kwargs, _ = configured
    queue = task_queue()
    def fail(*args):
        raise RuntimeError("redis://private-user:super-secret@formal-host:6379/0")
    setattr(queue.redis, method, fail)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).queue_snapshotter(queue)
    assert result["available"] is False
    assert all(value not in json.dumps(result) for value in ("super-secret", "formal-host", "private-user"))


def test_probe_preserves_input_configuration_after_caller_mutation(configured):
    kwargs, settings = configured
    probe = module().ReadOnlyMaintenanceProbe(**kwargs)
    kwargs["required_tables"]["task_db"].append("missing")
    kwargs["directories"].clear()
    kwargs["sqlite_paths"].clear()
    assert probe.storage_checker(**storage_args(settings))["success"] is True


def test_connections_explicitly_readonly_query_only_and_closed(configured, monkeypatch):
    kwargs, settings = configured
    connect = sqlite3.connect
    calls, connections = [], []
    def capture(path, **options):
        assert path.endswith("?mode=ro") and options["uri"] is True
        connection = connect(path, **options)
        connection.set_trace_callback(calls.append)
        connections.append(connection)
        return connection
    monkeypatch.setattr(module().sqlite3, "connect", capture)
    assert module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))["success"] is True
    assert calls.count("PRAGMA query_only=ON") == 5
    assert all(not sql.startswith(("CREATE", "INSERT", "UPDATE", "DELETE")) for sql in calls)
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


def test_existing_live_wal_is_logically_readonly_without_new_files(configured, tmp_path):
    kwargs, settings = configured
    path = kwargs["sqlite_paths"]["task_db"]
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO expected VALUES (7)")
        writer.commit()
        before = file_state(tmp_path)
        result = module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))
        after = file_state(tmp_path)
        assert result["success"] is True
        assert result["sqlite_modes"]["task_db"] == "wal"
        assert set(before) == set(after)
        assert {name: value for name, value in before.items() if not name.endswith("-shm")} == {
            name: value for name, value in after.items() if not name.endswith("-shm")}
        assert writer.execute("SELECT id FROM expected").fetchall() == [(7,)]
    finally:
        writer.close()


def test_builder_cannot_claim_pass_without_executing_both_explicit_probes(configured):
    kwargs, settings = configured
    def no_checks(**unused):
        return {"status": "ready", "checks": [{"name": "storage", "status": "pass"},
                                               {"name": "queue", "status": "pass"}]}
    result = module().ReadOnlyMaintenanceProbe(**kwargs).build_payload(
        no_checks, runtime_settings=settings, task_queue=task_queue())
    assert result["status"] == "probe_fail"


def test_builder_reports_wal_reason_without_secret_absolute_paths(configured):
    kwargs, settings = configured
    Path(str(kwargs["sqlite_paths"]["task_db"]) + "-wal").write_bytes(b"unverified")
    result = module().ReadOnlyMaintenanceProbe(**kwargs).build_payload(
        baseline("runtime_health").build_readiness_payload,
        runtime_settings=settings, task_queue=task_queue())
    assert result["status"] == "probe_fail"
    assert result["probe_details"]["storage"]["error"] == "sqlite_sidecar_or_format_unverified"
    assert str(kwargs["sqlite_paths"]["task_db"].parent) not in json.dumps(result)


@pytest.mark.parametrize("present", [(), ("-wal",), ("-shm",)])
def test_wal_requires_both_existing_sidecars_before_connect(configured, monkeypatch, present):
    kwargs, settings = configured
    path = kwargs["sqlite_paths"]["task_db"]
    with sqlite3.connect(path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
    writer.close()
    for suffix in present:
        Path(str(path) + suffix).write_bytes(b"private fixture only")
    before = file_state(path.parent)
    connect = sqlite3.connect
    def checked(database, **options):
        assert not str(database).startswith(path.as_uri()), "Missing sidecar must reject before SQLite can create one"
        return connect(database, **options)
    monkeypatch.setattr(module().sqlite3, "connect", checked)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))
    assert result["success"] is False
    assert result["error"] == "wal_requires_existing_wal_and_shm"
    assert file_state(path.parent) == before


@pytest.mark.parametrize("value", [False, None, "PONG", 1])
def test_ping_requires_true_not_truthy_and_stops_before_counts(configured, value):
    kwargs, _ = configured
    queue = task_queue()
    queue.redis.ping = lambda: value
    result = module().ReadOnlyMaintenanceProbe(**kwargs).queue_snapshotter(queue)
    assert result["available"] is False and queue.redis.calls == []


def test_two_exact_queues_are_both_counted_without_registry_cleanup(configured):
    kwargs, _ = configured
    names = ("canary.s0", "canary.s0.second")
    kwargs["queue_names"] = names
    queue = task_queue(names)
    result = module().ReadOnlyMaintenanceProbe(**kwargs).queue_snapshotter(queue)
    assert result["available"] is True and result["depth"] == 4
    assert result["registries"] == {name: 6 for name in ("started", "deferred", "failed", "scheduled")}
    assert set(result["queues"]) == set(names)
    assert len(queue.redis.calls) == 11
    assert all(call[0] in ("PING", "LLEN", "ZCARD") for call in queue.redis.calls)


def test_exact_baseline_builder_reads_live_wal_and_keeps_business_bytes(configured, tmp_path):
    kwargs, settings = configured
    path = kwargs["sqlite_paths"]["task_db"]
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO expected VALUES (9)")
        writer.commit()
        before = file_state(tmp_path)
        result = module().ReadOnlyMaintenanceProbe(**kwargs).build_payload(
            baseline("runtime_health").build_readiness_payload,
            runtime_settings=settings, task_queue=task_queue())
        after = file_state(tmp_path)
        assert result["status"] == "probe_pass" and result["production_ready"] is False
        assert result["probe_details"]["storage"]["sqlite_modes"]["task_db"] == "wal"
        assert set(before) == set(after)
        assert all(after[name] == value for name, value in before.items() if not name.endswith("-shm"))
        assert writer.execute("SELECT id FROM expected").fetchall() == [(9,)]
    finally:
        writer.close()


def test_schema_only_present_in_wal_is_seen_not_stale_immutable_read(configured):
    kwargs, settings = configured
    path = kwargs["sqlite_paths"]["task_db"]
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute("CREATE TABLE wal_only (id INTEGER)")
        writer.commit()
        kwargs["required_tables"]["task_db"].append("wal_only")
        assert module().ReadOnlyMaintenanceProbe(**kwargs).storage_checker(**storage_args(settings))["success"] is True
    finally:
        writer.close()
