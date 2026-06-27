from pathlib import Path

import job_observability
import job_store


ROOT = Path(__file__).resolve().parents[1]


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
