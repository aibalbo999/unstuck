import importlib
import importlib.util
import json
import sqlite3
import threading
from pathlib import Path

import job_observability
import job_store


ROOT = Path(__file__).resolve().parents[1]


def test_job_update_assignment_records_running_and_terminal_fields():
    assert importlib.util.find_spec("job_store_updates") is not None
    updates = importlib.import_module("job_store_updates")

    running = updates.build_job_update_assignment(
        status="running",
        filename=None,
        error=None,
        data_snapshot=None,
        metrics_snapshot=None,
        now=42.0,
        terminal_statuses={"done", "error", "cancelled"},
    )

    assert running.set_clauses == [
        "status = ?",
        "filename = COALESCE(?, filename)",
        "error = ?",
        "updated_at = ?",
        "started_at = COALESCE(started_at, ?)",
    ]
    assert running.params == ["running", None, None, 42.0, 42.0]

    terminal = updates.build_job_update_assignment(
        status="done",
        filename="2330.html",
        error="ok",
        data_snapshot={"price": 123},
        metrics_snapshot={"latency_ms": 456},
        now=84.0,
        terminal_statuses={"done", "error", "cancelled"},
    )

    assert terminal.set_clauses[:5] == [
        "status = ?",
        "filename = COALESCE(?, filename)",
        "error = ?",
        "updated_at = ?",
        "finished_at = COALESCE(finished_at, ?)",
    ]
    assert terminal.params[:5] == ["done", "2330.html", "ok", 84.0, 84.0]
    assert json.loads(terminal.params[5]) == {"price": 123}
    assert json.loads(terminal.params[6]) == {"latency_ms": 456}


def test_abandoned_job_update_rows_share_cancelled_transition_shape():
    assert importlib.util.find_spec("job_store_updates") is not None
    updates = importlib.import_module("job_store_updates")
    assert hasattr(updates, "abandoned_job_update_rows")

    rows = updates.abandoned_job_update_rows([" job-a ", "", "job-b"], "restart cleanup", 42.0)

    assert rows == [
        ("restart cleanup", 42.0, 42.0, 42.0, "job-a"),
        ("restart cleanup", 42.0, 42.0, 42.0, "job-b"),
    ]


def test_job_cancel_update_plan_sanitizes_and_splits_queued_running_updates():
    assert importlib.util.find_spec("job_store_cancellation") is not None
    cancellation = importlib.import_module("job_store_cancellation")

    queued = cancellation.build_cancel_job_update(
        "queued",
        job_id="job-a",
        reason="api_key=secret-token\nstop now",
        now=42.0,
    )
    running = cancellation.build_cancel_job_update(
        "running",
        job_id="job-b",
        reason="stop now",
        now=84.0,
    )

    assert "status = 'cancelled'" in queued.sql
    assert queued.params == (42.0, 42.0, "api_key=[redacted] stop now", 42.0, "job-a")
    assert "finished_at" not in running.sql
    assert running.params == (84.0, "stop now", 84.0, "job-b")
    assert cancellation.should_emit_cancel_event("waiting_retry", ("queued", "running", "waiting_retry")) is True
    assert cancellation.should_emit_cancel_event("done", ("queued", "running", "waiting_retry")) is False


def test_job_store_event_writer_appends_event_and_refreshes_active_jobs():
    assert importlib.util.find_spec("job_store_event_writer") is not None
    writer = importlib.import_module("job_store_event_writer")
    schema = importlib.import_module("job_store_schema")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    schema.init_job_store_schema(conn)
    conn.execute(
        """
        INSERT INTO analysis_jobs (job_id, ticker, pipeline_id, status, created_at, updated_at)
        VALUES ('job-a', '2330.TW', 'v1', 'running', 1.0, 1.0)
        """
    )

    usage_calls = []
    log_calls = []
    payload = {"type": "status", "phase": "model_call", "level": "info", "message": "running"}
    writer.append_job_event(
        lambda: conn,
        threading.Lock(),
        ("queued", "running", "waiting_retry"),
        "jobs.sqlite3",
        "job-a",
        payload,
        now_fn=lambda: 42.0,
        usage_recorder=lambda job_id, event_payload, **kwargs: usage_calls.append(
            (job_id, event_payload, kwargs)
        ),
        event_logger=lambda job_id, event_payload: log_calls.append((job_id, event_payload)),
    )

    event = conn.execute("SELECT * FROM analysis_events WHERE job_id = 'job-a'").fetchone()
    job = conn.execute("SELECT updated_at FROM analysis_jobs WHERE job_id = 'job-a'").fetchone()

    assert json.loads(event["payload"]) == payload
    assert event["created_at"] == 42.0
    assert event["event_type"] == "status"
    assert event["phase"] == "model_call"
    assert event["level"] == "info"
    assert job["updated_at"] == 42.0
    assert usage_calls == [("job-a", payload, {"created_at": 42.0, "db_path": "jobs.sqlite3"})]
    assert log_calls == [("job-a", payload)]


def test_waiting_retry_job_remains_active():
    job_id = job_store.create_job("2330.TW", "v1")

    job_store.update_job(job_id, "waiting_retry", error="429")
    found = job_store.find_active_job("2330.TW", "v1")

    assert found["job_id"] == job_id
    assert found["status"] == "waiting_retry"


def test_waiting_retry_can_return_to_running_and_clear_error():
    job_id = job_store.create_job("2330.TW", "v1")

    job_store.update_job(job_id, "waiting_retry", error="429")
    job_store.update_job(job_id, "running", error=None)

    job = job_store.get_job(job_id)
    assert job["status"] == "running"
    assert job["error"] is None


def test_waiting_retry_events_keep_job_fresh(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "waiting_retry", error="429")
    before = float(job_store.get_job(job_id)["updated_at"])
    later = before + 10

    monkeypatch.setattr(job_store.time, "time", lambda: later)
    job_store.append_event(job_id, {"type": "status", "message": "retry later"})

    assert job_store.get_job(job_id)["updated_at"] == later


def test_waiting_retry_cancel_records_cancelling_event():
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "waiting_retry", error="429")

    assert job_store.request_job_cancel(job_id, "stop retry") is True

    events = [event["payload"] for event in job_store.get_events_since(job_id)]
    assert any(event.get("phase") == "cancelling" and event.get("message") == "stop retry" for event in events)


def test_waiting_retry_job_is_abandoned_by_worker_cleanup():
    job_id = job_store.create_job("2330.TW", "v1", worker_instance_id="worker-a")
    job_store.update_job(job_id, "waiting_retry", error="429")

    abandoned = job_store.mark_incomplete_jobs_abandoned("restart cleanup", worker_instance_id="worker-a")

    assert abandoned == 1
    assert job_store.get_job(job_id)["status"] == "error"


def test_mark_jobs_abandoned_only_updates_active_jobs():
    active_job_id = job_store.create_job("2330.TW", "v1")
    completed_job_id = job_store.create_job("2454.TW", "v1")
    job_store.update_job(completed_job_id, "done", filename="2454.html")

    abandoned = job_store.mark_jobs_abandoned([active_job_id, completed_job_id], "missing rq job")

    assert abandoned == 1
    active_job = job_store.get_job(active_job_id)
    completed_job = job_store.get_job(completed_job_id)
    assert active_job["status"] == "error"
    assert active_job["error"] == "missing rq job"
    assert completed_job["status"] == "done"
    events = [event["payload"] for event in job_store.get_events_since(active_job_id)]
    assert any(event.get("phase") == "queue_abandoned" and event.get("message") == "missing rq job" for event in events)


def test_waiting_retry_visible_in_active_job_observability():
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "waiting_retry", error="429")

    snapshot = job_observability.build_active_jobs_snapshot(limit=10)

    assert snapshot["active_count"] == 1
    assert snapshot["jobs"][0]["job_id"] == job_id
    assert snapshot["jobs"][0]["status"] == "waiting_retry"


def test_active_jobs_panel_treats_waiting_retry_as_active():
    source = (ROOT / "backend" / "static" / "active_jobs_panel.js").read_text(encoding="utf-8")

    assert "if (job.status === 'waiting_retry') return '等待重試';" in source
    assert "['queued', 'running', 'waiting_retry'].includes(job.status)" in source
    assert "['running', 'waiting_retry'].includes(job.status) ? 'warning'" in source


def test_job_store_uses_short_busy_timeout_for_worker_contention():
    job_store.reset_job_store_for_tests()

    with job_store._connect() as conn:
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == 3000


def test_create_or_attach_active_job_is_atomic_for_concurrent_requests():
    barrier = threading.Barrier(6)
    results = []
    errors = []
    lock = threading.Lock()

    def worker(index):
        try:
            barrier.wait(timeout=5)
            result = job_store.create_or_attach_active_job("2330.TW", "v1", job_id=f"job-{index}")
            with lock:
                results.append(result["job"]["job_id"])
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert errors == []
    assert len(results) == 6
    assert len(set(results)) == 1
    active = job_store.list_active_jobs()
    assert len(active) == 1
    assert active[0]["ticker"] == "2330.TW"
