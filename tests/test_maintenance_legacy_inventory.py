"""Private SQLite diagnostics; empty queues/terminal jobs are NOT drain proof."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = "758242290e795146520f58f68ffa113cac35e52c"


def entry():
    spec = importlib.util.spec_from_file_location("legacy_inventory_entry_test", ROOT / "scripts/maintenance_entry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def configured(tmp_path):
    db = tmp_path / "operational.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE watchlist_items (ticker TEXT, pipeline TEXT, enabled INTEGER,
                schedule_slots_json TEXT, last_run_dates_json TEXT, created_at TEXT, updated_at TEXT,
                PRIMARY KEY (ticker, pipeline));
            CREATE TABLE watchlist_item_triggers (ticker TEXT, pipeline TEXT, triggers_json TEXT, updated_at TEXT);
            CREATE TABLE watchlist_trigger_events (ticker TEXT, pipeline TEXT, trigger_key TEXT,
                evaluation_date TEXT, trigger_type TEXT, matched INTEGER, pipeline_selected TEXT,
                job_id TEXT, created_at TEXT);
            CREATE TABLE watchlist_meta (key TEXT, value TEXT);
            CREATE TABLE analysis_jobs (job_id TEXT, ticker TEXT, pipeline_id TEXT, status TEXT,
                created_at REAL, updated_at REAL, claimed_at REAL, worker_instance_id TEXT);
            CREATE TABLE analysis_events (id INTEGER, job_id TEXT, event_type TEXT, phase TEXT, created_at REAL);
        """)
    module = entry()
    manifest = {"schema_version": "stock-agent.legacy-dispatch-inventory.v1",
        "backend_revision": BASELINE, "control_sha256": module.control_digest(),
        "paths": {"watchlist_db": str(db), "task_db": str(db),
                  "legacy_watchlist_db": str(tmp_path / "absent-legacy.sqlite3"),
                  "legacy_watchlist_json": str(tmp_path / "absent-watchlist.json")}}
    return module, manifest, db


def invoke(configured, tmp_path, monkeypatch, capsys):
    module, manifest, db = configured
    path = tmp_path / "inventory-manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setenv("STOCK_AGENT_MAINTENANCE_DIR", str(tmp_path / "not-initialized-maintenance"))
    code = module.main(["--maintenance-legacy-inventory", str(path)])
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def test_real_entry_reports_ambiguous_claim_without_mutating_db_or_control(configured, tmp_path, monkeypatch, capsys):
    module, manifest, db = configured
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO watchlist_items VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2330.TW", "v4", 0, '["post_market"]', '{"post_market": "2026-09-14"}',
             "2026-09-14T15:30:00+08:00", "2026-09-14T15:30:00+08:00"))
        conn.execute("INSERT INTO watchlist_trigger_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2412.TW", "v1", "monthly", "2026-09-01", "revenue_record_high", 1, "v2", "",
             "2026-09-14T15:31:00+08:00"))
    before = db.read_bytes()
    code, result, stderr = invoke(configured, tmp_path, monkeypatch, capsys)
    assert code == 0 and not stderr
    assert result["readback_complete"] is True
    assert result["settlement_proven"] is False and result["legacy_handover_verified"] is False
    assert result["pending_count"] is None and result["history_complete"] is False
    assert result["observed_ambiguous_claims"] == 2
    assert result["schedule_marks"][0]["enabled"] is False
    event, = result["trigger_events"]
    assert event["orphan_item"] is True
    assert event["evaluation_date"] == "2026-09-01"
    assert event["pipeline"] == "v1" and event["pipeline_selected"] == "v2"
    assert event["dispatch_status"] == "unknown"
    assert result["queue_readback_performed"] is False
    assert db.read_bytes() == before
    assert not (tmp_path / "not-initialized-maintenance").exists()


def test_current_control_digest_cannot_execute_preloaded_foreign_inventory(configured, tmp_path, monkeypatch, capsys):
    calls = []
    foreign = ModuleType("maintenance_legacy_inventory")
    foreign.__file__ = "/another-checkout/maintenance_legacy_inventory.py"
    def unsafe(manifest):
        calls.append("foreign")
        return {"readback_complete": True, "production_ready": True, "settlement_proven": True}
    foreign.read_legacy_inventory = unsafe
    monkeypatch.setitem(sys.modules, "maintenance_legacy_inventory", foreign)
    code, result, stderr = invoke(configured, tmp_path, monkeypatch, capsys)
    assert code == 0 and not stderr
    assert calls == []
    assert result["production_ready"] is False and result["settlement_proven"] is False
    assert sys.modules["maintenance_legacy_inventory"] is foreign


def test_source_changed_after_manifest_check_is_never_executed(configured, tmp_path, monkeypatch, capsys):
    sentinel = ModuleType("legacy_inventory_drift_sentinel")
    sentinel.calls = []
    monkeypatch.setitem(sys.modules, "legacy_inventory_drift_sentinel", sentinel)
    source_path = ROOT / "scripts/maintenance_legacy_inventory.py"
    module, manifest, _ = configured
    original = module._control_source
    count = 0
    def changed(path):
        nonlocal count
        source = original(path)
        if path == source_path:
            count += 1
            if count >= 2:  # _read_plan saw the approved bytes; loader now sees drift.
                source += b'\nimport sys\nsys.modules["legacy_inventory_drift_sentinel"].calls.append("unbound")\n'
        return source
    monkeypatch.setattr(module, "_control_source", changed)
    path = tmp_path / "drift-manifest.json"
    path.write_text(json.dumps(manifest))
    code = module.main(["--maintenance-legacy-inventory", str(path)])
    captured = capsys.readouterr()
    assert sentinel.calls == []
    assert code == 75 and captured.out == "" and captured.err


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("legacy_inventory_tested", ROOT / "scripts/maintenance_legacy_inventory.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put_event(db, *, key="daily", day="2026-09-14", selected="v4", job_id="", matched=1):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO watchlist_trigger_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("2330.TW", "v1", key, day, "daily_screener", matched, selected, job_id,
             "2026-09-15T00:01:00+08:00"))


def put_job(db, job_id="job-one", status="done", mode="v4"):
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, "2330.TW", mode, status, 100.0, 200.0, None, None))


@pytest.mark.parametrize("status", ["done", "error", "cancelled", "queued", "running", "waiting_retry"])
def test_matching_job_never_resolves_ambiguous_record(configured, reader, status):
    _, manifest, db = configured
    put_job(db, status=status)
    put_event(db)
    result = reader.read_legacy_inventory(manifest)
    event, = result["trigger_events"]
    assert event["candidate_job_ids"] == ["job-one"]
    assert event["dispatch_status"] == "unknown" and event["candidate_links_proven"] is False
    assert result["readback_complete"] is True
    assert result["pending_count"] is None and result["settlement_proven"] is False


@pytest.mark.parametrize("job_id,status,mode,expected", [
    ("job-one", "done", "v4", "present_terminal"),
    ("job-one", "running", "v4", "present_active"),
    ("job-one", "done", "v2", "identity_mismatch"),
    ("missing", "done", "v4", "missing_job"),
])
def test_explicit_job_reference_is_observation_not_settlement(configured, reader, job_id, status, mode, expected):
    _, manifest, db = configured
    put_job(db, status=status, mode=mode)
    put_event(db, job_id=job_id)
    result = reader.read_legacy_inventory(manifest)
    assert result["trigger_events"][0]["job_reference_status"] == expected
    assert result["observed_ambiguous_claims"] == 1
    assert result["pending_count"] is None


def test_no_latest_only_date_or_terminal_filter_and_events_preserved(configured, reader):
    _, manifest, db = configured
    put_job(db)
    put_event(db, key="monthly", day="2026-09-01", selected="v2")
    put_event(db, key="yesterday", day="2026-09-14")
    put_event(db, key="today", day="2026-09-15", matched=0)
    with sqlite3.connect(db) as conn:
        conn.executemany("INSERT INTO analysis_events VALUES (?, ?, ?, ?, ?)", [
            (1, "job-one", "status", "data_fetch", 100.0),
            (2, "job-one", "done", None, 200.0),
            (3, "deleted-job", "error", "cancelled", 90.0),
        ])
        conn.execute("INSERT INTO watchlist_meta VALUES (?, ?)", ("screener_last_run", "2026-09-14"))
    result = reader.read_legacy_inventory(manifest)
    assert {e["evaluation_date"] for e in result["trigger_events"]} == {"2026-09-01", "2026-09-14", "2026-09-15"}
    assert result["job_event_counts"]["job-one"] == {"count": 2, "job_present": True,
        "types": {"status": 1, "done": 1}, "phases": {"data_fetch": 1, "unknown": 1},
        "first_created_at": 100.0, "last_created_at": 200.0}
    assert result["job_event_counts"]["deleted-job"]["job_present"] is False
    assert result["meta_markers"][0]["kind"] == "screener"
    assert result["observed_ambiguous_claims"] == 2


def test_empty_retained_history_is_not_no_pending_claims(configured, reader):
    result = reader.read_legacy_inventory(configured[1])
    assert result["readback_complete"] is True and result["observed_ambiguous_claims"] == 0
    assert result["history_complete"] is False and result["pending_count"] is None
    assert result["settlement_proven"] is False and result["queue_readback_performed"] is False


@pytest.mark.parametrize("mutation", ["missing_file", "missing_table", "view", "missing_column", "journal", "symlink"])
def test_incomplete_storage_fails_closed_and_never_migrates(configured, reader, tmp_path, mutation):
    _, manifest, db = configured
    if mutation == "missing_file":
        db.rename(tmp_path / "retained-original.sqlite3")
    elif mutation == "symlink":
        saved = tmp_path / "retained-original.sqlite3"
        db.rename(saved)
        db.symlink_to(saved)
    elif mutation == "journal":
        Path(str(db) + "-journal").write_bytes(b"unconfirmed journal")
    else:
        with sqlite3.connect(db) as conn:
            conn.execute("DROP TABLE watchlist_meta")
            if mutation == "view":
                conn.execute("CREATE VIEW watchlist_meta AS SELECT 'k' AS key, 'v' AS value")
            elif mutation == "missing_column":
                conn.execute("CREATE TABLE watchlist_meta (key TEXT)")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir() if p.is_file()}
    result = reader.read_legacy_inventory(manifest)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir() if p.is_file()}
    assert result["readback_complete"] is False and result["errors"]
    assert result["pending_count"] is None
    assert before == after


@pytest.mark.parametrize("marks", ['{"post_market":"2026-09-15","post_market":"2026-09-14"}',
    'broken', '[]', '{"post_market": NaN}', '{"post_market":"not-a-date"}'])
def test_corrupt_claim_json_not_normalized_to_empty(configured, reader, marks):
    _, manifest, db = configured
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO watchlist_items VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("2330.TW", "v4", 1, '["post_market"]', marks, "now", "now"))
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is False
    assert result["errors"][0]["table"] == "watchlist_items"
    assert result["pending_count"] is None


def test_shared_legacy_path_is_not_double_counted(configured, reader):
    _, manifest, db = configured
    manifest["paths"]["legacy_watchlist_db"] = str(db)
    put_event(db)
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is True
    assert len(result["trigger_events"]) == result["observed_ambiguous_claims"] == 1
    assert result["resources"]["legacy_watchlist_db"]["alias_of"] == "watchlist_db"


@pytest.mark.parametrize("limit", ["rows", "bytes"])
def test_bounded_projection_reports_partial_not_empty_success(configured, reader, monkeypatch, limit):
    _, manifest, db = configured
    for index in range(4):
        put_job(db, job_id=f"job-{index}")
    if limit == "rows":
        monkeypatch.setattr(reader, "MAX_ROWS", 2)
    else:
        monkeypatch.setattr(reader, "MAX_PROJECTION_BYTES", 100)
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is False
    assert len(result["jobs"]) < 4
    receipt = result["resources"]["task_db"]
    assert receipt["table_counts"]["analysis_jobs"] == 4
    assert "analysis_jobs" in receipt["truncated_tables"]
    assert receipt["projection_bytes"] <= receipt["projection_byte_limit"]
    assert result["pending_count"] is None


def test_legacy_json_is_observed_not_migrated(configured, reader):
    _, manifest, db = configured
    path = Path(manifest["paths"]["legacy_watchlist_json"])
    path.write_text(json.dumps({"items": [{"ticker": "2412.TW", "pipeline": "v2", "enabled": False,
        "schedule_slots": [], "last_run_dates": {"post_market": "2026-09-01"}}]}))
    before = db.read_bytes(), path.read_bytes()
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is True
    assert result["schedule_marks"][0]["resource"] == "legacy_watchlist_json"
    assert result["schedule_marks"][0]["currently_scheduled"] is False
    assert result["resources"]["legacy_watchlist_json"]["source_sha256"] == hashlib.sha256(before[1]).hexdigest()
    assert (db.read_bytes(), path.read_bytes()) == before


def test_reader_connections_are_explicit_readonly_and_no_schema_or_business_writes(configured, reader, monkeypatch):
    connect = sqlite3.connect
    calls, statements = [], []
    def observed(database, *args, **kwargs):
        calls.append((database, kwargs))
        conn = connect(database, *args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn
    monkeypatch.setattr(reader.sqlite3, "connect", observed)
    assert reader.read_legacy_inventory(configured[1])["readback_complete"]
    assert len(calls) == 1  # shared task/watchlist DB, not repeated snapshots
    assert calls[0][0].endswith("?mode=ro") and calls[0][1]["uri"] is True
    assert "PRAGMA query_only=ON" in statements
    assert "PRAGMA temp_store=MEMORY" in statements
    assert not any(s.split()[0].upper() in {"CREATE", "ALTER", "INSERT", "UPDATE", "DELETE", "REPLACE", "ATTACH"} for s in statements)


@pytest.mark.parametrize("field,value", [
    ("created_at", "not-a-time"), ("created_at", None),
    ("trigger_type", "untrusted secret text"), ("job_id", None),
])
def test_invalid_trigger_metadata_cannot_be_reported_as_complete(configured, reader, field, value):
    _, manifest, db = configured
    put_event(db)
    with sqlite3.connect(db) as conn:
        conn.execute(f'UPDATE watchlist_trigger_events SET "{field}" = ?', (value,))
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is False
    assert result["trigger_events"] == []
    assert "untrusted secret text" not in json.dumps(result)
    assert result["pending_count"] is None


def test_exact_legacy_claim_and_completion_have_the_same_date_observation(configured, reader, tmp_path, monkeypatch):
    """Characterize the unchanged baseline store on real private WAL/schema."""
    import watchlist_store
    import watchlist_trigger_store
    from watchlist_claim_store import claim_due_watchlist_items
    from job_store_schema import init_job_store_schema
    from datetime import datetime

    for name in ("watchlist_claim_store", "watchlist_store", "watchlist_trigger_store", "job_store_schema"):
        original = subprocess.check_output(["git", "show", f"{BASELINE}:backend/{name}.py"], cwd=ROOT)
        if original != (ROOT / "backend" / f"{name}.py").read_bytes():
            pytest.skip('Exact 75824229 legacy checkout required; current main has durable intent/ACK semantics')
    _, manifest, _ = configured
    db = tmp_path / "baseline-private.sqlite3"
    manifest["paths"].update(watchlist_db=str(db), task_db=str(db))
    monkeypatch.setattr(watchlist_store, "WATCHLIST_DB_PATH", str(db))
    monkeypatch.setattr(watchlist_store, "WATCHLIST_PATH", Path(manifest["paths"]["legacy_watchlist_json"]))
    monkeypatch.setattr(watchlist_trigger_store, "LEGACY_WATCHLIST_DB_PATH", Path(manifest["paths"]["legacy_watchlist_db"]))
    watchlist_store.reset_watchlist_store_for_tests()
    try:
        watchlist_store.upsert_watchlist_item({"ticker": "2330.TW", "pipeline": "v4",
            "enabled": True, "schedule_slots": ["post_market"]})
        with watchlist_store._connect() as conn:
            watchlist_trigger_store._ensure_schema(conn)
            init_job_store_schema(conn)
        now = datetime(2026, 9, 15, 15, 35, tzinfo=watchlist_store.TAIPEI)
        claimed, = claim_due_watchlist_items(now)
        assert claimed["due_date"] == "2026-09-15"
        after_claim = reader.read_legacy_inventory(manifest)
        watchlist_store.mark_watchlist_run("2330.TW", "v4", "post_market", now=now)
        after_mark = reader.read_legacy_inventory(manifest)
        assert after_claim["readback_complete"] is True and after_mark["readback_complete"] is True
        assert after_claim["schedule_marks"] == after_mark["schedule_marks"]
        assert after_claim["schedule_marks"][0]["dispatch_status"] == "unknown"
        assert after_claim["pending_count"] is None and after_mark["pending_count"] is None
        assert after_mark["jobs"] == []
        assert after_mark["resources"]["task_db"]["sqlite_mode"] == "wal"
    finally:
        watchlist_store.reset_watchlist_store_for_tests()


@pytest.mark.parametrize("mutation", ["revision", "schema", "missing_path", "extra_path", "relative_path", "parent_path", "digest"])
def test_invalid_manifest_rejected_before_any_database_io(configured, reader, monkeypatch, mutation):
    _, manifest, _ = configured
    if mutation == "revision": manifest["backend_revision"] = "not-qualified"
    if mutation == "schema": manifest["schema_version"] = "unknown"
    if mutation == "missing_path": del manifest["paths"]["task_db"]
    if mutation == "extra_path": manifest["paths"]["unlisted_db"] = "/unlisted.sqlite3"
    if mutation == "relative_path": manifest["paths"]["task_db"] = "relative.sqlite3"
    if mutation == "parent_path": manifest["paths"]["task_db"] = "/private/tmp/../unlisted.sqlite3"
    if mutation == "digest": manifest["control_sha256"] = "invalid"
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid manifest must reject before path or DB access")
    monkeypatch.setattr(reader, "_optional_exists", forbidden)
    monkeypatch.setattr(reader.sqlite3, "connect", forbidden)
    with pytest.raises(reader.ProbeUnavailable):
        reader.read_legacy_inventory(manifest)


def test_entry_rejects_stale_digest_without_control_or_db_access(configured, tmp_path, monkeypatch, capsys):
    module, manifest, _ = configured
    manifest["control_sha256"] = "0" * 64
    path = tmp_path / "stale-manifest.json"
    path.write_text(json.dumps(manifest))
    def forbidden(*args, **kwargs):
        pytest.fail("Stale manifest must not access control state or DB")
    monkeypatch.setattr(module, "control_root", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    assert module.main(["--maintenance-legacy-inventory", str(path)]) == 75
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err
    assert str(tmp_path) not in captured.err


def test_entry_partial_result_retains_json_and_returns_nonzero(configured, tmp_path, monkeypatch, capsys):
    _, manifest, db = configured
    manifest["paths"]["task_db"] = str(tmp_path / "missing-task.sqlite3")
    put_event(db)
    code, result, stderr = invoke(configured, tmp_path, monkeypatch, capsys)
    assert code == 75 and not stderr
    assert result["readback_complete"] is False
    assert result["trigger_events"][0]["job_reference_status"] == "none"
    assert "盤點不完整" in result["summary_zh"]
    assert result["settlement_proven"] is False and result["pending_count"] is None
    assert not (tmp_path / "missing-task.sqlite3").exists()
    assert not (tmp_path / "not-initialized-maintenance").exists()


def test_existing_wal_sees_committed_rows_without_new_files_or_business_writes(configured, reader, tmp_path):
    _, manifest, db = configured
    writer = sqlite3.connect(db)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("INSERT INTO analysis_jobs VALUES ('wal-job', '2330.TW', 'v4', 'done', 1, 2, NULL, NULL)")
        writer.commit()
        before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
        result = reader.read_legacy_inventory(manifest)
        after = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
        assert result["readback_complete"] is True
        assert result["jobs"][0]["job_id"] == "wal-job"
        assert result["resources"]["task_db"]["sqlite_mode"] == "wal"
        assert set(before) == set(after)
        assert {key: value for key, value in before.items() if not key.endswith("-shm")} == {
            key: value for key, value in after.items() if not key.endswith("-shm")}
        assert result["filesystem_inert"] is False and result["settlement_proven"] is False
    finally:
        writer.close()


@pytest.mark.parametrize("present", [(), ("-wal",), ("-shm",)])
def test_missing_wal_sidecars_reject_before_connect_and_are_not_created(configured, reader, monkeypatch, tmp_path, present):
    _, manifest, db = configured
    with sqlite3.connect(db) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
    writer.close()
    for suffix in present:
        Path(str(db) + suffix).write_bytes(b"private fixture sidecar")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail("SQLite could create missing WAL sidecars; do not connect")
    monkeypatch.setattr(reader.sqlite3, "connect", forbidden)
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is False
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


@pytest.mark.parametrize("raw", ['{}', '{"items":null}', '{"items":[],"items":[]}',
    '{"items":[{"ticker":"2330.TW"}]}', '{"items":[null]}', '{"items":[NaN]}'])
def test_legacy_json_failure_never_means_absent_or_success(configured, reader, raw):
    _, manifest, _ = configured
    path = Path(manifest["paths"]["legacy_watchlist_json"])
    path.write_text(raw)
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is False
    assert result["resources"]["legacy_watchlist_json"]["status"] != "absent"
    assert result["errors"] and result["pending_count"] is None
    assert path.read_text() == raw


def test_separate_legacy_database_records_are_not_dropped_or_migrated(configured, reader):
    _, manifest, db = configured
    legacy = Path(manifest["paths"]["legacy_watchlist_db"])
    # The private source has additional irrelevant tables. Only the explicit
    # legacy trigger projection is read; no store/migration getter is invoked.
    legacy.write_bytes(db.read_bytes())
    put_event(legacy, key="old-removed-item", day="2026-08-01", selected="v2")
    before = db.read_bytes(), legacy.read_bytes()
    result = reader.read_legacy_inventory(manifest)
    event, = result["trigger_events"]
    assert event["resource"] == "legacy_watchlist_db" and event["orphan_item"] is True
    assert event["evaluation_date"] == "2026-08-01"
    assert result["readback_complete"] is True and result["settlement_proven"] is False
    assert (db.read_bytes(), legacy.read_bytes()) == before


def test_permission_failure_is_not_absent_and_does_not_leak_path(configured, reader, monkeypatch):
    _, manifest, _ = configured
    private = Path(manifest["paths"]["legacy_watchlist_json"])
    original = Path.lstat
    def denied(path, *args, **kwargs):
        if path == private:
            raise PermissionError("sensitive-source-path")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", denied)
    result = reader.read_legacy_inventory(manifest)
    assert result["readback_complete"] is False
    assert result["resources"]["legacy_watchlist_json"]["status"] == "unavailable"
    assert "sensitive-source-path" not in json.dumps(result)


@pytest.mark.parametrize("complete", [True, False])
def test_real_shell_inventory_exits_before_normal_start(configured, tmp_path, complete):
    _, manifest, db = configured
    if not complete:
        manifest["paths"]["task_db"] = str(tmp_path / "not-created.sqlite3")
    path = tmp_path / "shell-manifest.json"
    path.write_text(json.dumps(manifest))
    before = db.read_bytes()
    process = subprocess.run(["/bin/bash", str(ROOT / "start_mac.command"),
        "--maintenance-legacy-inventory", str(path)],
        env={"PATH": "/usr/bin:/bin", "PYTHON_BIN": sys.executable,
             "CACHE_DIR": str(tmp_path / "no-runtime-cache"),
             "STOCK_AGENT_MAINTENANCE_DIR": str(tmp_path / "no-maintenance-state")},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10)
    assert process.returncode == (0 if complete else 75), process.stderr
    result = json.loads(process.stdout)
    assert result["readback_complete"] is complete
    assert result["pending_count"] is None and result["legacy_handover_verified"] is False
    assert not process.stderr
    assert db.read_bytes() == before
    assert not (tmp_path / "no-runtime-cache").exists()
    assert not (tmp_path / "no-maintenance-state").exists()
    assert not (tmp_path / "not-created.sqlite3").exists()
