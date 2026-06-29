import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import api  # noqa: E402
import job_store  # noqa: E402


class RecordingQueue:
    def __init__(self):
        self.queue = self
        self.calls = []
        self.cancelled = []
        self.jobs = {}

    def enqueue(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        task = {"id": args[0]}
        self.jobs[args[0]] = task
        return task

    def fetch_job(self, task_id):
        return self.jobs.get(task_id)

    def cancel(self, task_id):
        self.cancelled.append(task_id)
        return True


class FakeRqJob:
    def __init__(self, status):
        self.status = status

    def get_status(self, refresh=True):
        return self.status


def test_create_analysis_job_requires_mutation_token(monkeypatch):
    monkeypatch.setattr(api, "MUTATION_API_TOKEN", "required-token")

    client = TestClient(api.app)
    response = client.post("/api/analysis-jobs", json={"ticker": "2330.TW", "pipeline_id": "mode_a"})

    assert response.status_code == 403


def test_create_analysis_job_returns_contract_and_enqueues_once(monkeypatch, mutation_headers):
    queue = RecordingQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)
    monkeypatch.setattr(api, "has_api_keys", lambda: True)

    client = TestClient(api.app)
    response = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a", "force": False, "resume": True},
        headers=mutation_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert body["events_url"] == f"/api/analysis-jobs/{body['job_id']}/events"
    assert body["status_url"] == f"/api/analysis-jobs/{body['job_id']}"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")


def test_create_analysis_job_attaches_existing_active_job_without_duplicate_enqueue(monkeypatch, mutation_headers):
    queue = RecordingQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)
    monkeypatch.setattr(api, "has_api_keys", lambda: True)

    client = TestClient(api.app)
    first = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
        headers=mutation_headers,
    ).json()
    second = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
        headers=mutation_headers,
    ).json()

    assert second["job_id"] == first["job_id"]
    assert len(queue.calls) == 1


def test_create_analysis_job_requeues_orphaned_queued_job(monkeypatch, mutation_headers):
    queue = RecordingQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    orphan_job_id = job_store.create_job("2317.TW", "v1")

    client = TestClient(api.app)
    response = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2317.TW", "pipeline_id": "mode_a"},
        headers=mutation_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == orphan_job_id
    assert queue.calls[0][0][0] == f"analysis:{orphan_job_id}"
    events = [event["payload"] for event in job_store.get_events_since(orphan_job_id)]
    assert any(event.get("phase") == "queue_recovered" for event in events)


def test_queue_aware_active_job_marks_sqlite_job_missing_from_rq_abandoned(monkeypatch):
    queue = RecordingQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)
    orphan_job_id = job_store.create_job("2408.TW", "v1")

    active = api.find_queue_backed_active_job("2408.TW", "v1")

    assert active == {}
    orphan = job_store.get_job(orphan_job_id)
    assert orphan["status"] == "error"
    events = [event["payload"] for event in job_store.get_events_since(orphan_job_id)]
    assert any(event.get("phase") == "queue_abandoned" for event in events)


def test_task_queue_has_task_rejects_terminal_rq_jobs():
    from analysis_job_service import task_queue_has_task

    queue = RecordingQueue()
    queue.jobs["analysis:failed"] = FakeRqJob("failed")
    queue.jobs["analysis:finished"] = FakeRqJob("finished")
    queue.jobs["analysis:scheduled"] = FakeRqJob("scheduled")

    assert task_queue_has_task(queue, "analysis:failed") is False
    assert task_queue_has_task(queue, "analysis:finished") is False
    assert task_queue_has_task(queue, "analysis:scheduled") is True


def test_task_queue_has_task_returns_unknown_when_inspection_fails():
    from analysis_job_service import task_queue_has_task

    class BrokenQueue:
        queue = None

        def fetch_job(self, _task_id):
            raise RuntimeError("redis unavailable")

    assert task_queue_has_task(BrokenQueue(), "analysis:any") is None


def test_force_create_analysis_job_cancels_old_active_job(monkeypatch, mutation_headers):
    queue = RecordingQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)
    monkeypatch.setattr(api, "has_api_keys", lambda: True)

    client = TestClient(api.app)
    first = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
        headers=mutation_headers,
    ).json()
    forced = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a", "force": True},
        headers=mutation_headers,
    ).json()

    assert forced["job_id"] != first["job_id"]
    assert job_store.get_job(first["job_id"])["status"] == "cancelled"
    assert job_store.get_job(forced["job_id"])["status"] == "queued"
    assert len(queue.calls) == 2


def test_analysis_job_status_maps_internal_status_without_internal_path():
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="2330_TW_v1_report.html")

    client = TestClient(api.app)
    response = client.get(f"/api/analysis-jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["report_path"] == "/api/report/2330_TW_v1_report.html"
    assert "backend/cache" not in json.dumps(body)


def test_analysis_job_events_404_does_not_create_job():
    client = TestClient(api.app)
    response = client.get("/api/analysis-jobs/missing-job/events")

    assert response.status_code == 404
    assert job_store.list_active_jobs() == []


def test_analysis_job_events_resume_from_since_id_and_end_on_terminal():
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.append_event(job_id, {"type": "status", "message": "first"})
    job_store.append_event(job_id, {"type": "done", "filename": "report.html"})
    job_store.update_job(job_id, "done", filename="report.html")

    client = TestClient(api.app)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events?since_id=1") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert "id: 1" not in text
    assert "id: 2" in text
    assert '"type": "done"' in text


def test_cancel_analysis_job_marks_queued_cancelled_and_uses_queue(monkeypatch, mutation_headers):
    queue = RecordingQueue()
    monkeypatch.setattr(api, "analysis_task_queue", queue)
    job_id = job_store.create_job("2330.TW", "v1")

    client = TestClient(api.app)
    response = client.post(f"/api/analysis-jobs/{job_id}/cancel", headers=mutation_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert job_store.get_job(job_id)["status"] == "cancelled"
    assert queue.cancelled == [f"analysis:{job_id}"]


def test_legacy_analyze_endpoint_is_deprecated_but_streams_existing_job(monkeypatch):
    job_id = job_store.create_job("2449.TW", "v1")
    job_store.append_event(job_id, {"type": "done", "filename": "legacy.html"})
    job_store.update_job(job_id, "done", filename="legacy.html")
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {"job_id": job_id})
    monkeypatch.setattr(api, "get_job", lambda requested_job_id: job_store.get_job(requested_job_id or job_id))

    client = TestClient(api.app)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"deprecated": true' in text


def test_sse_idle_poll_interval_backs_off_and_resets():
    from api_routes.analysis import next_sse_poll_interval

    interval = 0.5
    interval = next_sse_poll_interval(had_events=False, current_interval=interval)
    assert interval == 1.0
    interval = next_sse_poll_interval(had_events=False, current_interval=interval)
    assert interval == 2.0
    interval = next_sse_poll_interval(had_events=False, current_interval=interval)
    assert interval == 5.0
    assert next_sse_poll_interval(had_events=False, current_interval=interval) == 5.0
    assert next_sse_poll_interval(had_events=True, current_interval=interval) == 0.5
