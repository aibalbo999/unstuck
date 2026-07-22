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


def test_analysis_task_id_malformed_job_id_uses_safe_empty_text():
    from analysis_job_service import analysis_task_id

    assert analysis_task_id("analysis-safe-job") == "analysis:analysis-safe-job"
    assert analysis_task_id(memoryview(b"unsafe-task-id")) == "analysis:"


def test_analysis_task_id_path_like_job_id_uses_safe_empty_segment():
    from analysis_job_service import analysis_task_id

    for job_id in (
        "analysis/unsafe",
        "analysis?unsafe=1",
        "analysis%2Funsafe",
        "analysis%252Funsafe",
        "analysis unsafe",
    ):
        assert analysis_task_id(job_id) == "analysis:"


def test_task_queue_has_task_malformed_task_id_uses_safe_empty_text():
    from analysis_job_service import task_queue_has_task

    seen_task_ids = []

    class TrackingQueue:
        queue = None

        def fetch_job(self, task_id):
            seen_task_ids.append(task_id)
            return None

    assert task_queue_has_task(TrackingQueue(), memoryview(b"analysis:unsafe-task")) is False
    assert seen_task_ids == [""]


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


def test_task_queue_has_task_malformed_rq_status_uses_safe_inactive_fallback():
    from analysis_job_service import task_queue_has_task

    class BrokenRqStatus:
        def __str__(self):
            raise RuntimeError("rq status string conversion failed")

    queue = RecordingQueue()
    queue.jobs["analysis:malformed-status"] = FakeRqJob(BrokenRqStatus())

    assert task_queue_has_task(queue, "analysis:malformed-status") is False


def test_task_queue_has_task_rq_status_fetch_failure_returns_unknown():
    from analysis_job_service import task_queue_has_task

    class BrokenStatusJob:
        def get_status(self, refresh=True):
            raise RuntimeError("rq status fetch failed")

    queue = RecordingQueue()
    queue.jobs["analysis:broken-status-fetch"] = BrokenStatusJob()

    assert task_queue_has_task(queue, "analysis:broken-status-fetch") is None


def test_task_queue_has_task_rq_status_accessor_failure_returns_unknown():
    from analysis_job_service import task_queue_has_task

    class BrokenStatusAccessorJob:
        @property
        def get_status(self):
            raise RuntimeError("rq status accessor failed")

    queue = RecordingQueue()
    queue.jobs["analysis:broken-status-accessor"] = BrokenStatusAccessorJob()

    assert task_queue_has_task(queue, "analysis:broken-status-accessor") is None


def test_task_queue_has_task_rq_status_property_failure_returns_unknown():
    from analysis_job_service import task_queue_has_task

    class BrokenStatusPropertyJob:
        @property
        def status(self):
            raise RuntimeError("rq status property failed")

    queue = RecordingQueue()
    queue.jobs["analysis:broken-status-property"] = BrokenStatusPropertyJob()

    assert task_queue_has_task(queue, "analysis:broken-status-property") is None


def test_task_queue_has_task_returns_unknown_when_inspection_fails():
    from analysis_job_service import task_queue_has_task

    class BrokenQueue:
        queue = None

        def fetch_job(self, _task_id):
            raise RuntimeError("redis unavailable")

    assert task_queue_has_task(BrokenQueue(), "analysis:any") is None


def test_task_queue_has_task_queue_metadata_failure_returns_unknown():
    from analysis_job_service import task_queue_has_task

    class BrokenQueueMetadata:
        @property
        def queues(self):
            raise RuntimeError("queue metadata unavailable")

    assert task_queue_has_task(BrokenQueueMetadata(), "analysis:any") is None


def test_task_queue_has_task_child_queue_fetch_job_metadata_failure_returns_unknown():
    from analysis_job_service import task_queue_has_task

    class BrokenChildQueue:
        @property
        def fetch_job(self):
            raise RuntimeError("child queue fetch_job unavailable")

    class QueueWithBrokenChild:
        queues = {"broken": BrokenChildQueue()}
        queue = None

    assert task_queue_has_task(QueueWithBrokenChild(), "analysis:any") is None


def test_task_queue_has_task_child_queue_equality_failure_still_inspects_primary_queue():
    from analysis_job_service import task_queue_has_task

    class EqualityBombChildQueue:
        def __eq__(self, _other):
            raise RuntimeError("child queue equality failed")

        def fetch_job(self, _task_id):
            return None

    primary_queue = RecordingQueue()
    primary_queue.jobs["analysis:queued"] = FakeRqJob("queued")

    class QueueWithEqualityBombChild:
        queues = {"child": EqualityBombChildQueue()}
        queue = primary_queue

    assert task_queue_has_task(QueueWithEqualityBombChild(), "analysis:queued") is True


def test_serialize_analysis_job_malformed_job_row_uses_safe_empty_payload():
    from analysis_job_service import serialize_analysis_job

    body = serialize_analysis_job(["malformed", "analysis-job"])

    assert body["job_id"] == ""
    assert body["pipeline_id"] == "v1"
    assert body["status"] == ""
    assert body["report_path"] is None
    assert body["events_url"] is None
    assert body["status_url"] is None


def test_serialize_analysis_job_malformed_status_uses_safe_text_fallback():
    from analysis_job_service import serialize_analysis_job

    class BrokenStatus:
        def __bool__(self):
            raise RuntimeError("status truthiness failed")

        def __str__(self):
            raise RuntimeError("status string conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-status",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": BrokenStatus(),
        }
    )

    assert body["job_id"] == "analysis-malformed-status"
    assert body["status"] == ""


def test_serialize_analysis_job_padded_status_maps_public_status():
    from analysis_job_service import serialize_analysis_job

    cases = {
        " done ": "completed",
        "\twaiting_retry\n": "running",
    }
    for raw_status, expected in cases.items():
        body = serialize_analysis_job(
            {
                "job_id": f"analysis-padded-status-{expected}",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": raw_status,
            }
        )

        assert body["job_id"] == f"analysis-padded-status-{expected}"
        assert body["status"] == expected


def test_serialize_analysis_job_known_status_case_maps_public_status():
    from analysis_job_service import serialize_analysis_job

    cases = {
        "DONE": "completed",
        "Waiting_Retry": "running",
        "ERROR": "failed",
    }
    for raw_status, expected in cases.items():
        body = serialize_analysis_job(
            {
                "job_id": f"analysis-case-status-{expected}",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": raw_status,
            }
        )

        assert body["job_id"] == f"analysis-case-status-{expected}"
        assert body["status"] == expected


def test_serialize_analysis_job_malformed_job_id_uses_safe_empty_identity():
    from analysis_job_service import serialize_analysis_job

    class BrokenIdentity:
        def __bool__(self):
            raise RuntimeError("job id truthiness failed")

        def __str__(self):
            raise RuntimeError("job id string conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": BrokenIdentity(),
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "queued",
        }
    )

    assert body["job_id"] == ""
    assert body["status"] == "queued"
    assert body["events_url"] is None
    assert body["status_url"] is None


def test_serialize_analysis_job_path_like_job_id_omits_job_urls():
    from analysis_job_service import serialize_analysis_job

    for job_id in ("analysis/unsafe", "analysis?unsafe=1", "analysis%2Funsafe", "analysis\nunsafe"):
        body = serialize_analysis_job(
            {
                "job_id": job_id,
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "queued",
            }
        )

        assert body["job_id"] == job_id
        assert body["status"] == "queued"
        assert body["events_url"] is None
        assert body["status_url"] is None


def test_serialize_analysis_job_whitespace_url_segments_omit_public_urls():
    from analysis_job_service import serialize_analysis_job

    body = serialize_analysis_job(
        {
            "job_id": "analysis unsafe",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "done",
            "filename": "report name.html",
        }
    )

    assert body["job_id"] == "analysis unsafe"
    assert body["status"] == "completed"
    assert body["events_url"] is None
    assert body["status_url"] is None
    assert body["report_path"] is None


def test_serialize_analysis_job_double_encoded_url_segments_omit_public_urls():
    from analysis_job_service import serialize_analysis_job

    body = serialize_analysis_job(
        {
            "job_id": "analysis%252Funsafe",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "done",
            "filename": "report%253Fdownload.html",
        }
    )

    assert body["job_id"] == "analysis%252Funsafe"
    assert body["status"] == "completed"
    assert body["events_url"] is None
    assert body["status_url"] is None
    assert body["report_path"] is None


def test_serialize_analysis_job_malformed_filename_uses_safe_empty_report_path():
    from analysis_job_service import serialize_analysis_job

    class BrokenFilename:
        def __bool__(self):
            raise RuntimeError("filename truthiness failed")

        def __str__(self):
            raise RuntimeError("filename string conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-filename",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "done",
            "filename": BrokenFilename(),
        }
    )

    assert body["job_id"] == "analysis-malformed-filename"
    assert body["status"] == "completed"
    assert body["report_path"] is None


def test_serialize_analysis_job_path_like_filename_uses_empty_report_path():
    from analysis_job_service import serialize_analysis_job

    for filename in ("../report.html", "/tmp/report.html", "2026-07/2330/report.html"):
        body = serialize_analysis_job(
            {
                "job_id": "analysis-path-like-filename",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "done",
                "filename": filename,
            }
        )

        assert body["job_id"] == "analysis-path-like-filename"
        assert body["status"] == "completed"
        assert body["report_path"] is None


def test_serialize_analysis_job_url_like_filename_uses_empty_report_path():
    from analysis_job_service import serialize_analysis_job

    for filename in ("report.html?download=1", "report.html#section", "report%2Fsecret.html", "report%5Csecret.html"):
        body = serialize_analysis_job(
            {
                "job_id": "analysis-url-like-filename",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "done",
                "filename": filename,
            }
        )

        assert body["job_id"] == "analysis-url-like-filename"
        assert body["status"] == "completed"
        assert body["report_path"] is None


def test_serialize_analysis_job_encoded_delimiter_filename_uses_empty_report_path():
    from analysis_job_service import serialize_analysis_job

    for filename in ("report%3Fdownload=1.html", "report%23section.html", "report%00extra.html", "report%0Aextra.html"):
        body = serialize_analysis_job(
            {
                "job_id": "analysis-encoded-delimiter-filename",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "done",
                "filename": filename,
            }
        )

        assert body["job_id"] == "analysis-encoded-delimiter-filename"
        assert body["status"] == "completed"
        assert body["report_path"] is None


def test_serialize_analysis_job_control_character_filename_uses_empty_report_path():
    from analysis_job_service import serialize_analysis_job

    for filename in ("report.html\nextra", "report.html\rextra", "report.html\textra", "report.html\x00extra"):
        body = serialize_analysis_job(
            {
                "job_id": "analysis-control-filename",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "done",
                "filename": filename,
            }
        )

        assert body["job_id"] == "analysis-control-filename"
        assert body["status"] == "completed"
        assert body["report_path"] is None


def test_serialize_analysis_job_malformed_pipeline_id_uses_default_pipeline():
    from analysis_job_service import serialize_analysis_job

    class BrokenPipeline:
        def __bool__(self):
            raise RuntimeError("pipeline id truthiness failed")

        def __str__(self):
            raise RuntimeError("pipeline id string conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-pipeline",
            "ticker": "2330.TW",
            "pipeline_id": BrokenPipeline(),
            "status": "queued",
        }
    )

    assert body["job_id"] == "analysis-malformed-pipeline"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"


def test_serialize_analysis_job_malformed_ticker_uses_safe_empty_text():
    from analysis_job_service import serialize_analysis_job

    class BrokenTicker:
        def __bool__(self):
            raise RuntimeError("ticker truthiness failed")

        def __str__(self):
            raise RuntimeError("ticker string conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-ticker",
            "ticker": BrokenTicker(),
            "pipeline_id": "v1",
            "status": "queued",
        }
    )

    assert body["job_id"] == "analysis-malformed-ticker"
    assert body["ticker"] == ""
    json.dumps(body)


def test_serialize_analysis_job_malformed_timestamps_use_safe_none():
    from analysis_job_service import serialize_analysis_job

    class BrokenTimestamp:
        def __float__(self):
            raise RuntimeError("timestamp float conversion failed")

    timestamp_fields = ("created_at", "updated_at", "started_at", "finished_at")
    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-timestamps",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "queued",
            **{field: BrokenTimestamp() for field in timestamp_fields},
        }
    )

    assert body["job_id"] == "analysis-malformed-timestamps"
    for field in timestamp_fields:
        assert body[field] is None
    json.dumps(body)


def test_serialize_analysis_job_malformed_timestamp_equality_uses_safe_none():
    from analysis_job_service import serialize_analysis_job

    class BrokenTimestampEquality:
        def __eq__(self, other):
            raise RuntimeError("timestamp equality failed")

        def __float__(self):
            raise RuntimeError("timestamp float conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-timestamp-equality",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "queued",
            "created_at": BrokenTimestampEquality(),
        }
    )

    assert body["job_id"] == "analysis-malformed-timestamp-equality"
    assert body["created_at"] is None
    json.dumps(body)


def test_serialize_analysis_job_malformed_error_uses_safe_none():
    from analysis_job_service import serialize_analysis_job

    class BrokenError:
        def __str__(self):
            raise RuntimeError("error string conversion failed")

    body = serialize_analysis_job(
        {
            "job_id": "analysis-malformed-error",
            "ticker": "2330.TW",
            "pipeline_id": "v1",
            "status": "error",
            "error": BrokenError(),
        }
    )

    assert body["job_id"] == "analysis-malformed-error"
    assert body["status"] == "failed"
    assert body["error"] is None
    json.dumps(body)


def test_build_analysis_job_id_malformed_inputs_use_safe_slug_fallback():
    from analysis_job_service import build_analysis_job_id

    job_id = build_analysis_job_id(memoryview(b"2330.TW"), memoryview(b"mode_a"))

    assert job_id.startswith("analysis-job-job-")
    assert "<memory" not in job_id
    assert "2330" not in job_id
    assert "mode" not in job_id
    assert len(job_id.rsplit("-", 1)[-1]) == 8


def test_build_analysis_job_id_malformed_force_flag_uses_conservative_false():
    from analysis_job_service import build_analysis_job_id

    class BrokenForce:
        def __bool__(self):
            raise RuntimeError("job id force flag truthiness failed")

    job_id = build_analysis_job_id("2330.TW", "v1", force=BrokenForce())

    assert job_id.startswith("analysis-2330tw-v1-")
    assert len(job_id.rsplit("-", 1)[-1]) == 8


def test_create_or_attach_analysis_job_malformed_lifecycle_job_returns_safe_empty_payload(monkeypatch):
    import analysis_job_service

    queue = RecordingQueue()
    monkeypatch.setattr(
        analysis_job_service,
        "create_or_attach_active_job",
        lambda *args, **kwargs: {"created": True, "job": ["malformed", "analysis-job"]},
    )

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="mode_a",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["job_id"] == ""
    assert body["pipeline_id"] == "v1"
    assert body["status"] == ""
    assert body["events_url"] is None
    assert body["status_url"] is None
    assert queue.calls == []


def test_create_or_attach_analysis_job_malformed_lifecycle_job_id_does_not_enqueue(monkeypatch):
    import analysis_job_service

    class BrokenIdentity:
        def __bool__(self):
            raise RuntimeError("lifecycle job id truthiness failed")

        def __str__(self):
            raise RuntimeError("lifecycle job id string conversion failed")

    queue = RecordingQueue()
    monkeypatch.setattr(
        analysis_job_service,
        "create_or_attach_active_job",
        lambda *args, **kwargs: {
            "created": True,
            "job": {
                "job_id": BrokenIdentity(),
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "queued",
            },
        },
    )

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="mode_a",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["job_id"] == ""
    assert body["status"] == "queued"
    assert body["events_url"] is None
    assert body["status_url"] is None
    assert queue.calls == []


def test_create_analysis_job_malformed_handler_result_returns_safe_empty_payload(mutation_headers):
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    from analysis_job_service import serialize_analysis_job
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "fallback-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                create_or_attach_analysis_job=lambda **kwargs: ["malformed", kwargs["ticker"]],
                serialize_analysis_job=serialize_analysis_job,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
        headers=mutation_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "",
        "ticker": "",
        "pipeline_id": "v1",
        "status": "",
        "created_at": None,
        "updated_at": None,
        "started_at": None,
        "finished_at": None,
        "report_path": None,
        "error": None,
        "events_url": None,
        "status_url": None,
    }


def test_create_analysis_job_malformed_handler_field_uses_serializer_fallback(mutation_headers):
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    from analysis_job_service import serialize_analysis_job
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "fallback-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                create_or_attach_analysis_job=lambda **kwargs: {
                    "job_id": "create-malformed-field",
                    "ticker": kwargs["ticker"],
                    "pipeline_id": memoryview(b"mode-a"),
                    "status": "queued",
                },
                serialize_analysis_job=serialize_analysis_job,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
        headers=mutation_headers,
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == "create-malformed-field"
    assert response.json()["ticker"] == "2330.TW"
    assert response.json()["pipeline_id"] == "v1"
    assert response.json()["status"] == "queued"
    assert response.json()["events_url"] == "/api/analysis-jobs/create-malformed-field/events"
    assert response.json()["status_url"] == "/api/analysis-jobs/create-malformed-field"


def test_create_analysis_job_malformed_normalized_pipeline_uses_v1_before_handler():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    seen_pipeline_ids = []

    def create_or_attach_analysis_job(**kwargs):
        seen_pipeline_ids.append(kwargs["pipeline_id"])
        return {
            "job_id": "create-malformed-normalized-pipeline",
            "ticker": kwargs["ticker"],
            "pipeline_id": kwargs["pipeline_id"],
            "status": "queued",
        }

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: memoryview(b"mode-a"),
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "fallback-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                create_or_attach_analysis_job=create_or_attach_analysis_job,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
    )

    assert response.status_code == 200
    assert response.json()["pipeline_id"] == "v1"
    assert seen_pipeline_ids == ["v1"]


def test_legacy_create_enqueue_malformed_created_job_id_returns_empty_payload():
    from api_routes.analysis import AnalysisRouteDeps, _legacy_create_and_enqueue_via_deps
    from analysis_job_service import serialize_analysis_job
    import threading

    class BrokenIdentity:
        def __bool__(self):
            raise RuntimeError("legacy create fallback job id truthiness failed")

        def __str__(self):
            raise RuntimeError("legacy create fallback job id string failed")

    queue = RecordingQueue()

    def fail_job_lookup(job_id):
        raise AssertionError("legacy create fallback should not inspect a malformed job id")

    body = _legacy_create_and_enqueue_via_deps(
        AnalysisRouteDeps(
            active_analyses_lock=threading.Lock(),
            get_analysis_task_queue=lambda: queue,
            run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
            has_api_keys=lambda: True,
            api_key_setup_message=lambda: "",
            normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
            get_pipeline_run_sequence=lambda pipeline_id: (),
            get_pipeline_run_label=lambda pipeline_id: pipeline_id,
            get_pipeline_run_agent_total=lambda pipeline_id: 0,
            get_job=fail_job_lookup,
            find_active_job=lambda ticker, pipeline_id: {},
            create_job=lambda ticker, pipeline_id: BrokenIdentity(),
            get_events_since=lambda job_id, after_id=0: [],
            update_job=lambda *args, **kwargs: None,
            append_event=lambda *args, **kwargs: None,
            request_job_cancel=lambda job_id, reason: False,
            print_streamed_event=lambda job_id, payload: None,
            require_mutation_authorized=lambda request: None,
            serialize_analysis_job=serialize_analysis_job,
        ),
        "2449.TW",
        "v1",
    )

    assert body["job_id"] == ""
    assert body["pipeline_id"] == "v1"
    assert body["events_url"] is None
    assert body["status_url"] is None
    assert queue.calls == []


def test_legacy_create_enqueue_malformed_queue_exception_persists_safe_error():
    from api_routes.analysis import AnalysisRouteDeps, _legacy_create_and_enqueue_via_deps
    from analysis_job_service import serialize_analysis_job
    import threading

    class BrokenQueueError(Exception):
        def __str__(self):
            raise RuntimeError("legacy create fallback queue error string failed")

    class FailingQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise BrokenQueueError()

    queue = FailingQueue()
    updates = []
    events = []

    body = _legacy_create_and_enqueue_via_deps(
        AnalysisRouteDeps(
            active_analyses_lock=threading.Lock(),
            get_analysis_task_queue=lambda: queue,
            run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
            has_api_keys=lambda: True,
            api_key_setup_message=lambda: "",
            normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
            get_pipeline_run_sequence=lambda pipeline_id: (),
            get_pipeline_run_label=lambda pipeline_id: pipeline_id,
            get_pipeline_run_agent_total=lambda pipeline_id: 0,
            get_job=lambda job_id: {
                "job_id": job_id,
                "ticker": "2449.TW",
                "pipeline_id": "v1",
                "status": "error",
            },
            find_active_job=lambda ticker, pipeline_id: {},
            create_job=lambda ticker, pipeline_id: "legacy-fallback-queue-error",
            get_events_since=lambda job_id, after_id=0: [],
            update_job=lambda *args, **kwargs: updates.append((args, kwargs)),
            append_event=lambda *args, **kwargs: events.append((args, kwargs)),
            request_job_cancel=lambda job_id, reason: False,
            print_streamed_event=lambda job_id, payload: None,
            require_mutation_authorized=lambda request: None,
            serialize_analysis_job=serialize_analysis_job,
        ),
        "2449.TW",
        "v1",
    )

    assert body["job_id"] == "legacy-fallback-queue-error"
    assert body["status"] == "failed"
    assert updates == [(("legacy-fallback-queue-error", "error"), {"error": "分析任務送入佇列失敗"})]
    assert events == [(("legacy-fallback-queue-error", {"type": "error", "message": "分析任務送入佇列失敗"}), {})]
    assert queue.calls[0][0][0] == "analysis:legacy-fallback-queue-error"


def test_legacy_create_route_malformed_serializer_field_uses_json_safe_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "queued",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "legacy-create-malformed-field",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                create_or_attach_analysis_job=None,
                serialize_analysis_job=lambda job: {
                    "job_id": job["job_id"],
                    "ticker": job["ticker"],
                    "pipeline_id": memoryview(b"v1"),
                    "status": "queued",
                    "events_url": f"/api/analysis-jobs/{job['job_id']}/events",
                    "status_url": f"/api/analysis-jobs/{job['job_id']}",
                },
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/analysis-jobs",
        json={"ticker": "2330.TW", "pipeline_id": "mode_a"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "legacy-create-malformed-field",
        "ticker": "2330.TW",
        "pipeline_id": "v1",
        "status": "queued",
        "events_url": "/api/analysis-jobs/legacy-create-malformed-field/events",
        "status_url": "/api/analysis-jobs/legacy-create-malformed-field",
    }


def test_create_or_attach_analysis_job_malformed_lifecycle_status_does_not_requeue(monkeypatch):
    import analysis_job_service

    class BrokenStatus:
        def __bool__(self):
            raise RuntimeError("lifecycle status truthiness failed")

        def __str__(self):
            raise RuntimeError("lifecycle status string conversion failed")

    queue = RecordingQueue()
    monkeypatch.setattr(
        analysis_job_service,
        "create_or_attach_active_job",
        lambda *args, **kwargs: {
            "created": False,
            "job": {
                "job_id": "attached-malformed-status",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": BrokenStatus(),
            },
        },
    )

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="mode_a",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["job_id"] == "attached-malformed-status"
    assert body["status"] == ""
    assert queue.calls == []


def test_create_or_attach_analysis_job_malformed_enqueue_exception_marks_job_failed(monkeypatch):
    import analysis_job_service

    class BrokenQueueException(Exception):
        def __str__(self):
            raise RuntimeError("queue exception string conversion failed")

    class BrokenEnqueueQueue(RecordingQueue):
        def enqueue(self, *args, **kwargs):
            raise BrokenQueueException()

    queue = BrokenEnqueueQueue()
    job_id = job_store.create_job("2357.TW", "v1")
    monkeypatch.setattr(
        analysis_job_service,
        "create_or_attach_active_job",
        lambda *args, **kwargs: {
            "created": True,
            "job": {
                "job_id": job_id,
                "ticker": "2357.TW",
                "pipeline_id": "v1",
                "status": "queued",
            },
        },
    )

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2357.TW",
        pipeline_id="v1",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["job_id"] == job_id
    assert body["status"] == "failed"
    assert body["error"] == "分析任務送入佇列失敗"
    events = [event["payload"] for event in job_store.get_events_since(job_id)]
    assert any(event.get("type") == "error" and event.get("message") == "分析任務送入佇列失敗" for event in events)
    json.dumps(body)


def test_create_or_attach_analysis_job_malformed_input_pipeline_uses_default_pipeline(monkeypatch):
    import analysis_job_service

    class BrokenPipeline:
        def __bool__(self):
            raise RuntimeError("input pipeline truthiness failed")

        def __str__(self):
            raise RuntimeError("input pipeline string conversion failed")

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id=BrokenPipeline(),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")


def test_create_or_attach_analysis_job_malformed_input_ticker_returns_safe_empty_payload(monkeypatch):
    import analysis_job_service

    class BrokenTicker:
        def __bool__(self):
            raise RuntimeError("input ticker truthiness failed")

        def __str__(self):
            raise RuntimeError("input ticker string conversion failed")

    def unexpected_create_or_attach(*args, **kwargs):
        raise AssertionError("malformed input ticker should not reach job store")

    queue = RecordingQueue()
    monkeypatch.setattr(analysis_job_service, "create_or_attach_active_job", unexpected_create_or_attach)

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker=BrokenTicker(),
        pipeline_id="v1",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["job_id"] == ""
    assert body["pipeline_id"] == "v1"
    assert body["status"] == ""
    assert body["events_url"] is None
    assert body["status_url"] is None
    assert queue.calls == []


def test_create_or_attach_analysis_job_malformed_force_flag_uses_conservative_false():
    import analysis_job_service

    class BrokenForce:
        def __bool__(self):
            raise RuntimeError("force flag truthiness failed")

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=BrokenForce(),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_arbitrary_truthy_force_flag_uses_conservative_false():
    import analysis_job_service

    class TruthyForce:
        def __bool__(self):
            return True

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=TruthyForce(),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_binary_force_flag_uses_conservative_false():
    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=memoryview(b"force"),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_string_false_force_flag_uses_conservative_false():
    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force="false",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_non_finite_force_flag_uses_conservative_false():
    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=float("nan"),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_fractional_numeric_force_flag_uses_conservative_false():
    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=0.5,
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_fraction_force_flag_uses_conservative_false():
    from fractions import Fraction

    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=Fraction(1, 2),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_decimal_fractional_force_flag_uses_conservative_false():
    from decimal import Decimal

    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=Decimal("1.0000000000000000001"),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_decimal_nan_force_flag_uses_conservative_false():
    from decimal import Decimal

    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=Decimal("NaN"),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_complex_force_flag_uses_conservative_false():
    import analysis_job_service

    queue = RecordingQueue()
    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        force=complex(1, 0),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert queue.calls[0][0][0] == f"analysis:{body['job_id']}"
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")
    assert len(queue.calls[0][0]) == 5


def test_create_or_attach_analysis_job_malformed_resume_flag_uses_conservative_true(monkeypatch):
    import analysis_job_service

    class BrokenResume:
        def __bool__(self):
            raise RuntimeError("resume flag truthiness failed")

    observed = {}
    queue = RecordingQueue()
    original_create_or_attach = analysis_job_service.create_or_attach_active_job

    def recording_create_or_attach(*args, **kwargs):
        observed["resume"] = kwargs.get("resume")
        return original_create_or_attach(*args, **kwargs)

    monkeypatch.setattr(analysis_job_service, "create_or_attach_active_job", recording_create_or_attach)

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="v1",
        resume=BrokenResume(),
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["ticker"] == "2330.TW"
    assert body["pipeline_id"] == "v1"
    assert body["status"] == "queued"
    assert observed["resume"] is True
    assert queue.calls[0][0][2:] == (body["job_id"], "2330.TW", "v1")


def test_create_or_attach_analysis_job_malformed_created_flag_does_not_requeue(monkeypatch):
    import analysis_job_service

    class BrokenCreatedFlag:
        def __bool__(self):
            raise RuntimeError("created flag truthiness failed")

    queue = RecordingQueue()
    monkeypatch.setattr(
        analysis_job_service,
        "create_or_attach_active_job",
        lambda *args, **kwargs: {
            "created": BrokenCreatedFlag(),
            "job": {
                "job_id": "attached-malformed-created",
                "ticker": "2330.TW",
                "pipeline_id": "v1",
                "status": "queued",
            },
        },
    )

    body = analysis_job_service.create_or_attach_analysis_job(
        ticker="2330.TW",
        pipeline_id="mode_a",
        task_queue=queue,
        run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
    )

    assert body["job_id"] == "attached-malformed-created"
    assert body["status"] == "queued"
    assert queue.calls == []


def test_serialize_node_telemetry_malformed_row_collection_uses_empty_list(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: None,
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-malformed-row-collection")

    assert body == {"job_id": "telemetry-malformed-row-collection", "telemetry": []}


def test_serialize_node_telemetry_row_collection_preserves_valid_rows_before_iterator_failure(monkeypatch):
    import analysis_job_service

    class BrokenTelemetryRows:
        def __iter__(self):
            yield {
                "id": 1,
                "started_at": None,
                "finished_at": None,
                "node_name": "analysis",
                "error": None,
            }
            raise RuntimeError("telemetry row iterator failed")

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: BrokenTelemetryRows(),
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-partial-row-collection")

    assert body["job_id"] == "telemetry-partial-row-collection"
    assert body["telemetry"] == [
        {
            "id": 1,
            "started_at": None,
            "finished_at": None,
            "node_name": "analysis",
            "error": None,
        }
    ]
    json.dumps(body)


def test_serialize_node_telemetry_malformed_row_uses_safe_empty_row(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [["malformed", job_id]],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-malformed-row")

    assert body["job_id"] == "telemetry-malformed-row"
    assert body["telemetry"] == [{"started_at": None, "finished_at": None, "error": None}]


def test_serialize_node_telemetry_malformed_requested_job_id_uses_safe_empty_text(monkeypatch):
    import analysis_job_service

    seen_job_ids = []
    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: seen_job_ids.append(job_id) or [],
    )

    body = analysis_job_service.serialize_node_telemetry(memoryview(b"telemetry-job-id"))

    assert body == {"job_id": "", "telemetry": []}
    assert seen_job_ids == [""]
    json.dumps(body)


def test_serialize_node_telemetry_malformed_text_fields_use_safe_empty_text(monkeypatch):
    import analysis_job_service

    class BrokenTelemetryText:
        def __str__(self):
            raise RuntimeError("telemetry text conversion failed")

    text_fields = ("job_id", "ticker", "pipeline_id", "node_name", "model", "status")
    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                **{field: BrokenTelemetryText() for field in text_fields},
                "started_at": None,
                "finished_at": None,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-malformed-text")

    assert body["job_id"] == "telemetry-malformed-text"
    row = body["telemetry"][0]
    for field in text_fields:
        assert row[field] == ""
    json.dumps(body)


def test_serialize_node_telemetry_arbitrary_numeric_timestamp_fields_use_none(monkeypatch):
    import analysis_job_service

    class NumericTelemetryTimestamp:
        def __float__(self):
            return 1_700_000_000.0

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": NumericTelemetryTimestamp(),
                "finished_at": NumericTelemetryTimestamp(),
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-arbitrary-numeric-timestamps")

    row = body["telemetry"][0]
    assert row["started_at"] is None
    assert row["finished_at"] is None
    json.dumps(body)


def test_serialize_node_telemetry_malformed_metric_fields_use_safe_fallback(monkeypatch):
    import analysis_job_service

    class BrokenTelemetryMetric:
        def __bool__(self):
            raise RuntimeError("telemetry metric truthiness failed")

        def __float__(self):
            raise RuntimeError("telemetry metric float conversion failed")

        def __int__(self):
            raise RuntimeError("telemetry metric integer conversion failed")

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "id": BrokenTelemetryMetric(),
                "started_at": None,
                "finished_at": None,
                "latency_ms": BrokenTelemetryMetric(),
                "retry_count": BrokenTelemetryMetric(),
                "input_tokens": BrokenTelemetryMetric(),
                "output_tokens": BrokenTelemetryMetric(),
                "cache_hit": BrokenTelemetryMetric(),
                "quality_gate_pass": BrokenTelemetryMetric(),
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-malformed-metrics")

    assert body["job_id"] == "telemetry-malformed-metrics"
    row = body["telemetry"][0]
    assert row["id"] is None
    assert row["latency_ms"] is None
    assert row["retry_count"] == 0
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    assert row["cache_hit"] is False
    assert row["quality_gate_pass"] is False
    json.dumps(body)


def test_serialize_node_telemetry_fractional_optional_metric_fields_use_none(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "id": 1.5,
                "latency_ms": 2.5,
                "input_tokens": 3.5,
                "output_tokens": 4.5,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-fractional-optional-metrics")

    row = body["telemetry"][0]
    assert row["id"] is None
    assert row["latency_ms"] is None
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    json.dumps(body)


def test_serialize_node_telemetry_fractional_exact_optional_metric_fields_use_none(monkeypatch):
    from decimal import Decimal
    import analysis_job_service

    fractional = Decimal("1.0000000000000000001")
    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "id": fractional,
                "latency_ms": fractional,
                "input_tokens": fractional,
                "output_tokens": fractional,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-fractional-exact-optional-metrics")

    row = body["telemetry"][0]
    assert row["id"] is None
    assert row["latency_ms"] is None
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    json.dumps(body)


def test_serialize_node_telemetry_arbitrary_numeric_optional_metric_fields_use_none(monkeypatch):
    import analysis_job_service

    class NumericTelemetryMetric:
        def __float__(self):
            return 1.0

        def __int__(self):
            return 1

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "id": NumericTelemetryMetric(),
                "latency_ms": NumericTelemetryMetric(),
                "input_tokens": NumericTelemetryMetric(),
                "output_tokens": NumericTelemetryMetric(),
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-arbitrary-numeric-optional-metrics")

    row = body["telemetry"][0]
    assert row["id"] is None
    assert row["latency_ms"] is None
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    json.dumps(body)


def test_serialize_node_telemetry_negative_optional_metric_fields_use_none(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "id": -1,
                "latency_ms": -2,
                "input_tokens": -3,
                "output_tokens": -4,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-negative-optional-metrics")

    row = body["telemetry"][0]
    assert row["id"] is None
    assert row["latency_ms"] is None
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None
    json.dumps(body)


def test_serialize_node_telemetry_fractional_retry_count_uses_zero(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "retry_count": 1.5,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-fractional-retry-count")

    row = body["telemetry"][0]
    assert row["retry_count"] == 0
    json.dumps(body)


def test_serialize_node_telemetry_negative_retry_count_uses_zero(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "retry_count": -1,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-negative-retry-count")

    row = body["telemetry"][0]
    assert row["retry_count"] == 0
    json.dumps(body)


def test_serialize_node_telemetry_binary_or_container_bool_fields_use_false(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "cache_hit": memoryview(b"true"),
                "quality_gate_pass": {"passed": True},
                "error": None,
            },
            {
                "started_at": None,
                "finished_at": None,
                "cache_hit": "yes",
                "quality_gate_pass": 1,
                "error": None,
            },
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-bool-fields")

    first, second = body["telemetry"]
    assert first["cache_hit"] is False
    assert first["quality_gate_pass"] is False
    assert second["cache_hit"] is True
    assert second["quality_gate_pass"] is True
    json.dumps(body)


def test_serialize_node_telemetry_out_of_range_numeric_bool_fields_use_false(monkeypatch):
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "cache_hit": 2,
                "quality_gate_pass": 0.5,
                "error": None,
            }
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-out-of-range-bool-fields")

    row = body["telemetry"][0]
    assert row["cache_hit"] is False
    assert row["quality_gate_pass"] is False
    json.dumps(body)


def test_serialize_node_telemetry_exact_numeric_bool_fields_use_explicit_zero_one(monkeypatch):
    from decimal import Decimal
    from fractions import Fraction
    import analysis_job_service

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "cache_hit": Decimal("1"),
                "quality_gate_pass": Fraction(1, 1),
                "error": None,
            },
            {
                "started_at": None,
                "finished_at": None,
                "cache_hit": Decimal("0"),
                "quality_gate_pass": Fraction(0, 1),
                "error": None,
            },
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-exact-numeric-bool-fields")

    first, second = body["telemetry"]
    assert first["cache_hit"] is True
    assert first["quality_gate_pass"] is True
    assert second["cache_hit"] is False
    assert second["quality_gate_pass"] is False
    json.dumps(body)


def test_serialize_node_telemetry_arbitrary_truthy_bool_fields_use_false(monkeypatch):
    import analysis_job_service

    class TruthyTelemetryBool:
        def __bool__(self):
            return True

    monkeypatch.setattr(
        analysis_job_service,
        "list_node_telemetry",
        lambda job_id: [
            {
                "started_at": None,
                "finished_at": None,
                "cache_hit": TruthyTelemetryBool(),
                "quality_gate_pass": TruthyTelemetryBool(),
                "error": None,
            },
        ],
    )

    body = analysis_job_service.serialize_node_telemetry("telemetry-truthy-bool-fields")

    row = body["telemetry"][0]
    assert row["cache_hit"] is False
    assert row["quality_gate_pass"] is False
    json.dumps(body)


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
    assert queue.calls[1][0][5] is True


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


def test_analysis_job_status_missing_returns_not_found():
    client = TestClient(api.app)
    response = client.get("/api/analysis-jobs/missing-analysis-status")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis job not found"


def test_analysis_job_status_malformed_job_row_returns_not_found(monkeypatch):
    job_id = "malformed-analysis-status"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return ["malformed", candidate_job_id]

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/analysis-jobs/{job_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis job not found"


def test_analysis_job_status_malformed_serializer_field_uses_json_safe_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "running",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "status-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                serialize_analysis_job=lambda job: {
                    "job_id": job["job_id"],
                    "ticker": job["ticker"],
                    "pipeline_id": memoryview(b"v1"),
                    "status": "running",
                    "events_url": f"/api/analysis-jobs/{job['job_id']}/events",
                    "status_url": f"/api/analysis-jobs/{job['job_id']}",
                },
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/analysis-jobs/malformed-status-field")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "malformed-status-field",
        "ticker": "2330.TW",
        "pipeline_id": None,
        "status": "running",
        "events_url": "/api/analysis-jobs/malformed-status-field/events",
        "status_url": "/api/analysis-jobs/malformed-status-field",
    }


def test_analysis_job_telemetry_malformed_job_row_returns_not_found(monkeypatch):
    job_id = "malformed-analysis-telemetry"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return ["malformed", candidate_job_id]

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/analysis-jobs/{job_id}/telemetry")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis job not found"


def test_analysis_job_telemetry_malformed_serializer_result_returns_empty_payload():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "running",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "telemetry-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                serialize_node_telemetry=lambda job_id: ["malformed", job_id],
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/analysis-jobs/malformed-telemetry-result/telemetry")

    assert response.status_code == 200
    assert response.json() == {"job_id": "malformed-telemetry-result", "telemetry": []}


def test_analysis_job_telemetry_malformed_serializer_field_uses_json_safe_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "running",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "telemetry-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                serialize_node_telemetry=lambda job_id: {
                    "job_id": job_id,
                    "telemetry": [
                        {
                            "job_id": job_id,
                            "node_name": "agent_1",
                            "pipeline_id": memoryview(b"v1"),
                        }
                    ],
                    "diagnostic": memoryview(b"unsafe telemetry diagnostic"),
                },
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/analysis-jobs/malformed-telemetry-field/telemetry")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "malformed-telemetry-field",
        "telemetry": [
            {
                "job_id": "malformed-telemetry-field",
                "node_name": "agent_1",
                "pipeline_id": None,
            }
        ],
        "diagnostic": None,
    }


def test_analysis_job_events_404_does_not_create_job():
    client = TestClient(api.app)
    response = client.get("/api/analysis-jobs/missing-job/events")

    assert response.status_code == 404
    assert job_store.list_active_jobs() == []


def test_analysis_job_events_malformed_setup_job_row_returns_not_found(monkeypatch):
    job_id = "malformed-analysis-events"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return ["malformed", candidate_job_id]

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get(f"/api/analysis-jobs/{job_id}/events")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis job not found"


def test_analysis_job_events_malformed_intro_identity_uses_safe_text(monkeypatch):
    class BrokenIdentity:
        def __str__(self):
            raise RuntimeError("analysis event intro identity string failed")

    job_id = "malformed-analysis-event-intro"

    def fake_get_job(candidate_job_id):
        assert candidate_job_id == job_id
        return {
            "job_id": job_id,
            "ticker": BrokenIdentity(),
            "pipeline_id": BrokenIdentity(),
            "status": "running",
        }

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        return [{"id": 1, "payload": {"type": "done", "filename": "report.html"}}]

    monkeypatch.setattr(api, "get_job", fake_get_job)
    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "job"' in text
    assert '"ticker": ""' in text
    assert '"pipeline_id": "v1"' in text
    assert '"type": "done"' in text


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


def test_analysis_job_events_malformed_replay_event_id_uses_integer_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {"id": b"1", "payload": {"type": "status", "message": "不應信任二進位分析事件 id"}},
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "status"' in text
    assert "略過格式異常的分析任務事件" in text
    assert "不應信任二進位分析事件 id" not in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_message_uses_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {"id": 1, "payload": {"type": "status", "message": memoryview(b"unsafe analysis message")}},
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "status"' in text
    assert '"message": ""' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_payload_type_uses_status_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {"id": 1, "payload": {"type": memoryview(b"status"), "message": "不應信任二進位分析事件 type"}},
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "status"' in text
    assert "略過格式異常的分析任務事件" in text
    assert "不應信任二進位分析事件 type" not in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_done_identity_uses_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "done",
                        "filename": memoryview(b"report.html"),
                        "pipeline_id": memoryview(b"v1"),
                        "last_pipeline_id": memoryview(b"v1"),
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "done"' in text
    assert '"filename": ""' in text
    assert '"pipeline_id": ""' in text
    assert '"last_pipeline_id": ""' in text


def test_analysis_job_events_malformed_replay_control_fields_use_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "error", error="failed")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "error",
                        "phase": memoryview(b"cancelled"),
                        "level": memoryview(b"warning"),
                        "message": "failed",
                    },
                },
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "error"' in text
    assert '"phase": ""' in text
    assert '"level": ""' in text
    assert '"message": "failed"' in text


def test_analysis_job_events_malformed_replay_count_fields_use_integer_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "progress",
                        "current": memoryview(b"1"),
                        "total": memoryview(b"7"),
                        "agent_num": memoryview(b"3"),
                        "pipeline_current": memoryview(b"1"),
                        "pipeline_total": memoryview(b"4"),
                        "message": "progress",
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "progress"' in text
    assert '"current": 0' in text
    assert '"total": 0' in text
    assert '"agent_num": 0' in text
    assert '"pipeline_current": 0' in text
    assert '"pipeline_total": 0' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_pipeline_count_fields_use_integer_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "pipeline_start",
                        "message": "pipeline start",
                        "pipeline_index": memoryview(b"1"),
                        "pipeline_total": memoryview(b"4"),
                        "agent_total": memoryview(b"7"),
                        "agent_offset": memoryview(b"3"),
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "pipeline_start"' in text
    assert '"pipeline_index": 0' in text
    assert '"pipeline_total": 0' in text
    assert '"agent_total": 0' in text
    assert '"agent_offset": 0' in text
    assert '"type": "done"' in text


def test_analysis_sse_payload_helper_sanitizes_replay_payload_fields():
    from api_routes.analysis_sse_payloads import sanitize_replay_payload

    payload = sanitize_replay_payload(
        {
            "type": "progress",
            "message": memoryview(b"unsafe-message"),
            "phase": memoryview(b"phase"),
            "filename": memoryview(b"report.html"),
            "current": memoryview(b"1"),
            "total": "7",
            "latency_ms": float("nan"),
            "retry_count": b"2",
            "quality_gate_pass": "yes",
            "metadata": {"token": "secret", "safe": 1},
            "reports": [{"filename": "safe.html"}],
        },
        job_id="job-sanitize",
    )

    assert payload["type"] == "progress"
    assert payload["message"] == ""
    assert payload["phase"] == ""
    assert payload["filename"] == ""
    assert payload["current"] == 0
    assert payload["total"] == 7
    assert payload["latency_ms"] == 0.0
    assert payload["retry_count"] == 0
    assert payload["quality_gate_pass"] is True
    assert payload["metadata"] == {"safe": 1}
    assert payload["reports"] == [{"filename": "safe.html"}]
    assert sanitize_replay_payload({"type": memoryview(b"done"), "message": "unsafe"}, job_id="job") == {
        "type": "status",
        "level": "warning",
        "message": "略過格式異常的分析任務事件",
        "job_id": "job",
    }


def test_analysis_job_events_malformed_replay_progress_text_fields_use_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "progress",
                        "current": 1,
                        "total": 7,
                        "name": memoryview(b"Agent 1"),
                        "detail": memoryview(b"V1 Agent 1"),
                        "pipeline_label": memoryview(b"Pipeline V1"),
                        "message": "progress",
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "progress"' in text
    assert '"name": ""' in text
    assert '"detail": ""' in text
    assert '"pipeline_label": ""' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_metadata_uses_snapshot_safe_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "status",
                        "message": "context digest",
                        "metadata": {"model_id": memoryview(b"gemini"), "task": "context_digest"},
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "status"' in text
    assert '"metadata": {"model_id": "", "task": "context_digest"}' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_structured_report_fields_use_snapshot_safe_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "report_done",
                        "filename": "report.html",
                        "data_trust": {"status": memoryview(b"fresh"), "score": 80},
                        "audit": {"status": memoryview(b"passed"), "message": "ok"},
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "report_done"' in text
    assert '"data_trust": {"status": "", "score": 80}' in text
    assert '"audit": {"status": "", "message": "ok"}' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_report_artifact_filename_fields_use_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "report_done",
                        "filename": "report.html",
                        "md_filename": memoryview(b"report.md"),
                        "data_filename": memoryview(b"report.data.json"),
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "report_done"' in text
    assert '"md_filename": ""' in text
    assert '"data_filename": ""' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_done_aggregate_fields_use_snapshot_safe_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "done",
                        "filename": "report.html",
                        "filenames": [memoryview(b"report.html")],
                        "reports": [
                            {
                                "filename": memoryview(b"report.html"),
                                "audit": {"status": memoryview(b"passed")},
                            }
                        ],
                        "pipeline_sequence": [memoryview(b"v1")],
                    },
                }
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "done"' in text
    assert '"filenames": [""]' in text
    assert '"reports": [{"filename": "", "audit": {"status": ""}}]' in text
    assert '"pipeline_sequence": [""]' in text


def test_analysis_job_events_malformed_replay_telemetry_text_fields_use_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "telemetry",
                        "node_name": memoryview(b"agent_1"),
                        "model": memoryview(b"gemini"),
                        "status": memoryview(b"ok"),
                        "error": memoryview(b"none"),
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "telemetry"' in text
    assert '"node_name": ""' in text
    assert '"model": ""' in text
    assert '"status": ""' in text
    assert '"error": ""' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_workflow_retry_thread_id_uses_safe_text_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "status",
                        "phase": "workflow_retry",
                        "level": "warning",
                        "message": "LLM API 暫時達到速率限制，等待 RQ 延遲重試。",
                        "error": memoryview(b"rate limited"),
                        "thread_id": memoryview(b"job:v1"),
                        "pipeline_id": "v1",
                        "pipeline_label": "V1",
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "status"' in text
    assert '"phase": "workflow_retry"' in text
    assert '"thread_id": ""' in text
    assert '"error": ""' in text
    assert '"type": "done"' in text


def test_analysis_job_events_malformed_replay_telemetry_metric_fields_use_safe_fallback(monkeypatch):
    job_id = job_store.create_job("2330.TW", "v1")
    job_store.update_job(job_id, "done", filename="report.html")

    def fake_get_events_since(candidate_job_id, after_id=0):
        assert candidate_job_id == job_id
        if after_id == 0:
            return [
                {
                    "id": 1,
                    "payload": {
                        "type": "telemetry",
                        "latency_ms": memoryview(b"120"),
                        "retry_count": memoryview(b"2"),
                        "quality_gate_pass": memoryview(b"true"),
                    },
                },
                {"id": 2, "payload": {"type": "done", "filename": "report.html"}},
            ]
        return []

    monkeypatch.setattr(api, "get_events_since", fake_get_events_since)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", f"/api/analysis-jobs/{job_id}/events") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "telemetry"' in text
    assert '"latency_ms": 0.0' in text
    assert '"retry_count": 0' in text
    assert '"quality_gate_pass": false' in text
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


def test_cancel_analysis_job_service_malformed_job_row_returns_none(monkeypatch):
    import analysis_job_service

    queue = RecordingQueue()
    requested_cancellations = []
    monkeypatch.setattr(analysis_job_service, "get_job", lambda job_id: ["malformed", job_id])
    monkeypatch.setattr(
        analysis_job_service,
        "request_job_cancel",
        lambda job_id, reason: requested_cancellations.append((job_id, reason)),
    )

    result = analysis_job_service.cancel_analysis_job("malformed-service-cancel", task_queue=queue)

    assert result is None
    assert queue.cancelled == []
    assert requested_cancellations == []


def test_cancel_analysis_job_service_malformed_requested_job_id_uses_safe_empty_text(monkeypatch):
    import analysis_job_service

    queue = RecordingQueue()
    seen_job_ids = []
    requested_cancellations = []
    monkeypatch.setattr(
        analysis_job_service,
        "get_job",
        lambda job_id: seen_job_ids.append(job_id) or {},
    )
    monkeypatch.setattr(
        analysis_job_service,
        "request_job_cancel",
        lambda job_id, reason: requested_cancellations.append((job_id, reason)) or True,
    )

    result = analysis_job_service.cancel_analysis_job(memoryview(b"cancel-job-id"), task_queue=queue)

    assert result is None
    assert seen_job_ids == [""]
    assert queue.cancelled == []
    assert requested_cancellations == []


def test_cancel_analysis_job_service_malformed_status_equality_uses_safe_text(monkeypatch):
    import analysis_job_service

    class EqualityBombQueuedStatus:
        def __eq__(self, _other):
            raise RuntimeError("cancel status equality failed")

        def __str__(self):
            return "queued"

    queue = RecordingQueue()
    requested_cancellations = []
    job = {
        "job_id": "cancel-status-equality",
        "ticker": "2330.TW",
        "pipeline_id": "v1",
        "status": EqualityBombQueuedStatus(),
    }
    monkeypatch.setattr(analysis_job_service, "get_job", lambda _job_id: job)
    monkeypatch.setattr(
        analysis_job_service,
        "request_job_cancel",
        lambda job_id, reason: requested_cancellations.append((job_id, reason)) or True,
    )

    result = analysis_job_service.cancel_analysis_job("cancel-status-equality", task_queue=queue)

    assert result["status"] == "queued"
    assert queue.cancelled == ["analysis:cancel-status-equality"]
    assert requested_cancellations == [("cancel-status-equality", "使用者要求取消分析任務。")]


def test_cancel_analysis_job_service_queue_cancel_accessor_failure_still_requests_cancel(monkeypatch):
    import analysis_job_service

    class BrokenCancelQueue:
        @property
        def cancel(self):
            raise RuntimeError("queue cancel accessor failed")

    requested_cancellations = []
    job = {
        "job_id": "cancel-accessor-failure",
        "ticker": "2330.TW",
        "pipeline_id": "v1",
        "status": "queued",
    }
    monkeypatch.setattr(analysis_job_service, "get_job", lambda _job_id: job)
    monkeypatch.setattr(
        analysis_job_service,
        "request_job_cancel",
        lambda job_id, reason: requested_cancellations.append((job_id, reason)) or True,
    )

    result = analysis_job_service.cancel_analysis_job("cancel-accessor-failure", task_queue=BrokenCancelQueue())

    assert result["status"] == "queued"
    assert requested_cancellations == [("cancel-accessor-failure", "使用者要求取消分析任務。")]


def test_cancel_analysis_job_by_id_malformed_job_row_returns_not_found(monkeypatch, mutation_headers):
    import analysis_job_service

    def fail_service_lookup(job_id):
        raise AssertionError("cancel service should not inspect a malformed route job row")

    monkeypatch.setattr(api, "get_job", lambda job_id: ["malformed", job_id])
    monkeypatch.setattr(analysis_job_service, "get_job", fail_service_lookup)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/api/analysis-jobs/malformed-analysis-cancel/cancel", headers=mutation_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis job not found"


def test_cancel_analysis_job_by_id_fallback_malformed_cancel_result_returns_not_found():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    class BrokenCancelResult:
        def __bool__(self):
            raise RuntimeError("analysis by-id fallback cancel result truthiness failed")

    requested_cancellations = []
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "queued",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "fallback-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: requested_cancellations.append((job_id, reason)) or BrokenCancelResult(),
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                cancel_analysis_job=None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/analysis-jobs/malformed-by-id-cancel-result/cancel")

    assert response.status_code == 200
    assert response.json() == {"job_id": "malformed-by-id-cancel-result", "status": "not_found"}
    assert requested_cancellations == [("malformed-by-id-cancel-result", "使用者要求取消分析任務。")]


def test_cancel_analysis_job_by_id_malformed_service_result_returns_not_found():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "queued",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "fallback-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: True,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                cancel_analysis_job=lambda job_id, task_queue=None: ["malformed", job_id],
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/analysis-jobs/malformed-by-id-service-result/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis job not found"


def test_cancel_analysis_job_by_id_malformed_service_field_uses_json_safe_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 0,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2330.TW",
                    "pipeline_id": "v1",
                    "status": "queued",
                },
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "fallback-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: True,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                cancel_analysis_job=lambda job_id, task_queue=None: {
                    "job_id": job_id,
                    "status": "cancelled",
                    "pipeline_id": memoryview(b"v1"),
                    "events_url": f"/api/analysis-jobs/{job_id}/events",
                    "status_url": f"/api/analysis-jobs/{job_id}",
                },
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/analysis-jobs/malformed-by-id-service-field/cancel")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "malformed-by-id-service-field",
        "status": "cancelled",
        "pipeline_id": None,
        "events_url": "/api/analysis-jobs/malformed-by-id-service-field/events",
        "status_url": "/api/analysis-jobs/malformed-by-id-service-field",
    }


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


def test_legacy_analyze_endpoint_malformed_pipeline_sequence_uses_empty_intro_sequence():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    class BrokenPipelineSequence:
        def __iter__(self):
            raise RuntimeError("legacy intro pipeline sequence iteration failed")

    job_id = "legacy-malformed-pipeline-sequence"
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: BrokenPipelineSequence(),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda requested_job_id: {
                    "job_id": job_id,
                    "ticker": "2449",
                    "pipeline_id": "v1",
                    "status": "done",
                    "filename": "legacy.html",
                } if requested_job_id == job_id else {},
                find_active_job=lambda ticker, pipeline_id: {"job_id": job_id},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=lambda requested_job_id, after_id=0: [
                    {"id": 1, "payload": {"type": "done", "filename": "legacy.html", "pipeline_id": "v1"}}
                ] if requested_job_id == job_id else [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"pipeline_sequence": []' in text
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_pipeline_label_uses_empty_intro_label():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    class BrokenPipelineLabel:
        def __str__(self):
            raise RuntimeError("legacy intro pipeline label string failed")

    job_id = "legacy-malformed-pipeline-label"
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: BrokenPipelineLabel(),
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda requested_job_id: {
                    "job_id": job_id,
                    "ticker": "2449",
                    "pipeline_id": "v1",
                    "status": "done",
                    "filename": "legacy.html",
                } if requested_job_id == job_id else {},
                find_active_job=lambda ticker, pipeline_id: {"job_id": job_id},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=lambda requested_job_id, after_id=0: [
                    {"id": 1, "payload": {"type": "done", "filename": "legacy.html", "pipeline_id": "v1"}}
                ] if requested_job_id == job_id else [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"pipeline_label": ""' in text
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_agent_total_uses_zero_intro_count():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    job_id = "legacy-malformed-agent-total"
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: memoryview(b"7"),
                get_job=lambda requested_job_id: {
                    "job_id": job_id,
                    "ticker": "2449",
                    "pipeline_id": "v1",
                    "status": "done",
                    "filename": "legacy.html",
                } if requested_job_id == job_id else {},
                find_active_job=lambda ticker, pipeline_id: {"job_id": job_id},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=lambda requested_job_id, after_id=0: [
                    {"id": 1, "payload": {"type": "done", "filename": "legacy.html", "pipeline_id": "v1"}}
                ] if requested_job_id == job_id else [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"agent_total": 0' in text
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_negative_last_event_id_header_falls_back_before_replay():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    seen_after_ids = []
    job_id = "legacy-negative-resume-header"

    def get_events_since(requested_job_id, after_id=0):
        seen_after_ids.append(after_id)
        if requested_job_id != job_id:
            return []
        return [{"id": 1, "payload": {"type": "done", "filename": "legacy.html", "pipeline_id": "v1"}}]

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda requested_job_id: {
                    "job_id": job_id,
                    "ticker": "2449",
                    "pipeline_id": "v1",
                    "status": "done",
                    "filename": "legacy.html",
                } if requested_job_id == job_id else {},
                find_active_job=lambda ticker, pipeline_id: {"job_id": job_id},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=get_events_since,
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a", headers={"Last-Event-ID": "-5"}) as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"resume_after_id": 0' in text
    assert seen_after_ids[0] == 0
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_missing_key_message_uses_empty_error_text():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: False,
                api_key_setup_message=lambda: memoryview(b"missing api key"),
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda requested_job_id: {},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=lambda requested_job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "error"' in text
    assert '"message": ""' in text


def test_legacy_analyze_endpoint_malformed_api_key_readiness_uses_missing_key_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    queue = RecordingQueue()
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: queue,
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: memoryview(b"truthy but malformed"),
                api_key_setup_message=lambda: "請先設定 API key",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda requested_job_id: {},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "should-not-create",
                get_events_since=lambda requested_job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "error"' in text
    assert "請先設定 API key" in text
    assert queue.calls == []


def test_legacy_analyze_endpoint_malformed_normalized_pipeline_uses_v1_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    job_id = "legacy-malformed-normalized-pipeline"
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: memoryview(b"mode-a"),
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda requested_job_id: {
                    "job_id": job_id,
                    "ticker": "2449",
                    "pipeline_id": "v1",
                    "status": "done",
                    "filename": "legacy.html",
                } if requested_job_id == job_id else {},
                find_active_job=lambda ticker, pipeline_id: {"job_id": job_id},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=lambda requested_job_id, after_id=0: [
                    {"id": 1, "payload": {"type": "done", "filename": "legacy.html", "pipeline_id": "v1"}}
                ] if requested_job_id == job_id else [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"pipeline_id": "v1"' in text
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_requested_job_falls_back_to_active_job(monkeypatch):
    job_id = job_store.create_job("2449.TW", "v1")
    job_store.append_event(job_id, {"type": "done", "filename": "legacy.html"})
    job_store.update_job(job_id, "done", filename="legacy.html")
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {"job_id": job_id})

    def fake_get_job(requested_job_id):
        if requested_job_id == "malformed-legacy-request":
            return ["malformed", requested_job_id]
        return job_store.get_job(requested_job_id or job_id)

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a&job_id=malformed-legacy-request") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_requested_job_ticker_falls_back_to_active_job(monkeypatch):
    class EqualityBombTicker:
        def __eq__(self, _other):
            raise RuntimeError("legacy requested job ticker equality failed")

        def __str__(self):
            return "broken"

    job_id = job_store.create_job("2449.TW", "v1")
    job_store.append_event(job_id, {"type": "done", "filename": "legacy.html"})
    job_store.update_job(job_id, "done", filename="legacy.html")
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {"job_id": job_id})

    def fake_get_job(requested_job_id):
        if requested_job_id == "malformed-legacy-request-ticker":
            return {
                "job_id": "malformed-legacy-request-ticker",
                "ticker": EqualityBombTicker(),
                "pipeline_id": "v1",
            }
        return job_store.get_job(requested_job_id or job_id)

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a&job_id=malformed-legacy-request-ticker") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_requested_job_pipeline_falls_back_to_active_job(monkeypatch):
    class EqualityBombPipeline:
        def __eq__(self, _other):
            raise RuntimeError("legacy requested job pipeline equality failed")

        def __str__(self):
            return "broken"

    job_id = job_store.create_job("2449.TW", "v1")
    job_store.append_event(job_id, {"type": "done", "filename": "legacy.html"})
    job_store.update_job(job_id, "done", filename="legacy.html")
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {"job_id": job_id})

    def fake_get_job(requested_job_id):
        if requested_job_id == "malformed-legacy-request-pipeline":
            return {
                "job_id": "malformed-legacy-request-pipeline",
                "ticker": "2449",
                "pipeline_id": EqualityBombPipeline(),
            }
        return job_store.get_job(requested_job_id or job_id)

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a&job_id=malformed-legacy-request-pipeline") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_requested_job_id_falls_back_to_active_job(monkeypatch):
    class BrokenJobId:
        def __bool__(self):
            raise RuntimeError("legacy requested job id truthiness failed")

        def __str__(self):
            raise RuntimeError("legacy requested job id string failed")

    job_id = job_store.create_job("2449.TW", "v1")
    job_store.append_event(job_id, {"type": "done", "filename": "legacy.html"})
    job_store.update_job(job_id, "done", filename="legacy.html")
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {"job_id": job_id})

    def fake_get_job(requested_job_id):
        if requested_job_id == "malformed-legacy-request-job-id":
            return {
                "job_id": BrokenJobId(),
                "ticker": "2449",
                "pipeline_id": "v1",
            }
        return job_store.get_job(requested_job_id or job_id)

    monkeypatch.setattr(api, "get_job", fake_get_job)

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a&job_id=malformed-legacy-request-job-id") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_active_job_id_falls_back_to_created_job(monkeypatch):
    import analysis_job_service

    class BrokenJobId:
        def __bool__(self):
            raise RuntimeError("legacy active job id truthiness failed")

        def __str__(self):
            raise RuntimeError("legacy active job id string failed")

    fallback_job_id = job_store.create_job("2449.TW", "v1")
    job_store.append_event(fallback_job_id, {"type": "done", "filename": "legacy.html"})
    job_store.update_job(fallback_job_id, "done", filename="legacy.html")
    monkeypatch.setattr(api, "has_api_keys", lambda: True)
    monkeypatch.setattr(api, "find_queue_backed_active_job", lambda ticker, pipeline_id="v1": {"job_id": BrokenJobId()})
    monkeypatch.setattr(api, "get_job", lambda requested_job_id: job_store.get_job(requested_job_id or fallback_job_id))
    monkeypatch.setattr(
        analysis_job_service,
        "create_or_attach_active_job",
        lambda *args, **kwargs: {"created": False, "job": job_store.get_job(fallback_job_id)},
    )

    client = TestClient(api.app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"deprecated": true' in text
    assert '"type": "done"' in text


def test_legacy_analyze_endpoint_malformed_create_handler_result_falls_back_to_created_job():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    queue = RecordingQueue()
    fallback_job_id = "legacy-create-handler-fallback"

    def fake_get_job(candidate_job_id):
        if candidate_job_id == fallback_job_id:
            return {
                "job_id": fallback_job_id,
                "ticker": "2449",
                "pipeline_id": "v1",
                "status": "done",
                "filename": "legacy.html",
            }
        return {}

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: queue,
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=fake_get_job,
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: fallback_job_id,
                get_events_since=lambda job_id, after_id=0: [
                    {"id": 1, "payload": {"type": "done", "filename": "legacy.html", "pipeline_id": "v1"}}
                ] if job_id == fallback_job_id else [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                create_or_attach_analysis_job=lambda **kwargs: ["malformed", kwargs["ticker"]],
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"job_id": "legacy-create-handler-fallback"' in text
    assert '"deprecated": true' in text
    assert '"type": "done"' in text
    assert queue.calls[0][0][0] == f"analysis:{fallback_job_id}"
    assert queue.calls[0][0][2:] == (fallback_job_id, "2449", "v1")


def test_legacy_analyze_endpoint_malformed_fallback_enqueue_exception_streams_safe_error():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    class BrokenQueueError(Exception):
        def __str__(self):
            raise RuntimeError("legacy stream fallback enqueue exception string failed")

    class FailingQueue:
        def __init__(self):
            self.calls = []

        def enqueue(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise BrokenQueueError()

    queue = FailingQueue()
    fallback_job_id = "legacy-fallback-enqueue-error"
    updates = []
    events = []

    def fake_append_event(job_id, payload):
        events.append({"id": len(events) + 1, "payload": payload})

    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: queue,
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: "v1" if pipeline_id == "mode_a" else pipeline_id,
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda job_id: {
                    "job_id": job_id,
                    "ticker": "2449",
                    "pipeline_id": "v1",
                    "status": "error",
                    "error": "分析任務送入佇列失敗",
                } if job_id == fallback_job_id else {},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: fallback_job_id,
                get_events_since=lambda job_id, after_id=0: [event for event in events if event["id"] > after_id],
                update_job=lambda *args, **kwargs: updates.append((args, kwargs)),
                append_event=fake_append_event,
                request_job_cancel=lambda job_id, reason: False,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
                create_or_attach_analysis_job=lambda **kwargs: ["malformed", kwargs["ticker"]],
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("GET", "/api/analyze/2449?pipeline=mode_a") as response:
        text = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["deprecation"] == "true"
    assert '"job_id": "legacy-fallback-enqueue-error"' in text
    assert "分析任務送入佇列失敗" in text
    assert updates == [((fallback_job_id, "error"), {"error": "分析任務送入佇列失敗"})]
    assert events == [{"id": 1, "payload": {"type": "error", "message": "分析任務送入佇列失敗"}}]
    assert queue.calls[0][0][0] == f"analysis:{fallback_job_id}"


def test_legacy_cancel_analysis_endpoint_malformed_job_row_returns_not_found(monkeypatch, mutation_headers):
    cancelled = []
    monkeypatch.setattr(api, "get_job", lambda job_id: ["malformed", job_id])
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: cancelled.append((job_id, reason)) or True)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/api/analyze/2449/cancel?job_id=malformed-legacy-cancel&pipeline=mode_a", headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "找不到可取消的分析任務"}
    assert cancelled == []


def test_legacy_cancel_analysis_endpoint_malformed_ticker_returns_not_found(monkeypatch, mutation_headers):
    class EqualityBombTicker:
        def __eq__(self, _other):
            raise RuntimeError("legacy cancel ticker equality failed")

        def __str__(self):
            return "broken"

    cancelled = []
    monkeypatch.setattr(
        api,
        "get_job",
        lambda job_id: {"job_id": job_id, "ticker": EqualityBombTicker(), "pipeline_id": "v1"},
    )
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: cancelled.append((job_id, reason)) or True)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/api/analyze/2449/cancel?job_id=malformed-legacy-cancel-ticker&pipeline=mode_a", headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "找不到可取消的分析任務"}
    assert cancelled == []


def test_legacy_cancel_analysis_endpoint_malformed_pipeline_returns_not_found(monkeypatch, mutation_headers):
    class EqualityBombPipeline:
        def __eq__(self, _other):
            raise RuntimeError("legacy cancel pipeline equality failed")

        def __str__(self):
            return "broken"

    cancelled = []
    monkeypatch.setattr(
        api,
        "get_job",
        lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": EqualityBombPipeline()},
    )
    monkeypatch.setattr(api, "request_job_cancel", lambda job_id, reason: cancelled.append((job_id, reason)) or True)

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/api/analyze/2449/cancel?job_id=malformed-legacy-cancel-pipeline&pipeline=mode_a", headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {"ok": False, "message": "找不到可取消的分析任務"}
    assert cancelled == []


def test_legacy_cancel_analysis_endpoint_malformed_normalized_pipeline_uses_v1_fallback():
    from fastapi import FastAPI
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router
    import threading

    requested_cancellations = []
    app = FastAPI()
    app.include_router(
        create_analysis_router(
            AnalysisRouteDeps(
                active_analyses_lock=threading.Lock(),
                get_analysis_task_queue=lambda: RecordingQueue(),
                run_stock_analysis_job=lambda job_id, ticker, pipeline_id: None,
                has_api_keys=lambda: True,
                api_key_setup_message=lambda: "",
                normalize_pipeline_run_id=lambda pipeline_id: memoryview(b"mode-a"),
                get_pipeline_run_sequence=lambda pipeline_id: (pipeline_id,),
                get_pipeline_run_label=lambda pipeline_id: pipeline_id,
                get_pipeline_run_agent_total=lambda pipeline_id: 1,
                get_job=lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "v1"},
                find_active_job=lambda ticker, pipeline_id: {},
                create_job=lambda ticker, pipeline_id: "unused-job",
                get_events_since=lambda job_id, after_id=0: [],
                update_job=lambda *args, **kwargs: None,
                append_event=lambda *args, **kwargs: None,
                request_job_cancel=lambda job_id, reason: requested_cancellations.append((job_id, reason)) or True,
                print_streamed_event=lambda job_id, payload: None,
                require_mutation_authorized=lambda request: None,
            )
        )
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/analyze/2449/cancel?job_id=malformed-normalized-pipeline-cancel&pipeline=mode_a"
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "job_id": "malformed-normalized-pipeline-cancel",
        "status": "cancelling",
    }
    assert requested_cancellations == [("malformed-normalized-pipeline-cancel", "使用者要求取消分析任務。")]


def test_legacy_cancel_analysis_endpoint_malformed_cancel_result_returns_not_found(monkeypatch, mutation_headers):
    class BrokenCancelResult:
        def __bool__(self):
            raise RuntimeError("legacy cancel result truthiness failed")

    requested_cancellations = []
    monkeypatch.setattr(
        api,
        "get_job",
        lambda job_id: {"job_id": job_id, "ticker": "2449", "pipeline_id": "v1"},
    )
    monkeypatch.setattr(
        api,
        "request_job_cancel",
        lambda job_id, reason: requested_cancellations.append((job_id, reason)) or BrokenCancelResult(),
    )

    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.post("/api/analyze/2449/cancel?job_id=malformed-legacy-cancel-result&pipeline=mode_a", headers=mutation_headers)

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "job_id": "malformed-legacy-cancel-result",
        "status": "not_found",
    }
    assert requested_cancellations == [("malformed-legacy-cancel-result", "使用者要求取消分析任務。")]


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
