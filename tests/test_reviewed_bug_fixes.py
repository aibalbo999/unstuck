import asyncio
import inspect
import sys
import threading
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_local_task_queue_awaits_coroutine_jobs():
    from task_queue import LocalAsyncQueue

    queue = LocalAsyncQueue(max_concurrent=1)
    seen = []

    async def job(value):
        seen.append(value)

    async def run_once():
        queue._running = True
        worker = asyncio.create_task(queue._worker())
        queue.enqueue("job-1", job, "awaited")
        await queue.queue.join()
        queue._running = False
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)

    asyncio.run(run_once())

    assert seen == ["awaited"]


def test_run_stock_analysis_job_local_returns_awaitable(monkeypatch):
    import analysis_jobs
    import config

    monkeypatch.setattr(config, "TASK_QUEUE_BACKEND", "local")
    monkeypatch.setattr(analysis_jobs, "run_stock_analysis_job_async", lambda *args: asyncio.sleep(0, result="ok"))

    result = analysis_jobs.run_stock_analysis_job("job-1", "2308.TW", "v1")

    assert inspect.isawaitable(result)
    assert asyncio.run(result) == "ok"


def test_run_stock_analysis_job_force_refresh_reaches_data_fetch(monkeypatch):
    import analysis_jobs

    captured = {}

    class FakeStockDataService:
        async def fetch_async(self, request):
            captured["force_refresh"] = request.options.force_refresh
            return type("Result", (), {"data": {"ticker": request.ticker, "current_price": 100}})()

    monkeypatch.setattr(analysis_jobs, "has_api_keys", lambda: True)
    monkeypatch.setattr(analysis_jobs, "STOCK_DATA_SERVICE", FakeStockDataService())
    monkeypatch.setattr(analysis_jobs, "update_job", lambda *args, **kwargs: None)
    monkeypatch.setattr(analysis_jobs, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        analysis_jobs,
        "build_data_fetch_blocking_notice",
        lambda _result: {"message": "stop after data fetch", "data_trust": {}},
    )

    result = asyncio.run(
        analysis_jobs.run_stock_analysis_job_async(
            "job-force",
            "2330.TW",
            "v1",
            force_refresh=True,
        )
    )

    assert result == ""
    assert captured["force_refresh"] is True


def test_key_rotator_advances_index_once_per_selected_key(monkeypatch):
    import llm_rate_limits

    monkeypatch.setattr(llm_rate_limits, "emit_log", lambda message: None)
    rotator = llm_rate_limits.KeyRotator(["k1", "k2", "k3"])

    assert rotator.get_key("test-model") == "k1"
    assert rotator.index == 1
    assert rotator.get_key("test-model") == "k2"
    assert rotator.index == 2


def test_key_rotator_async_advances_index_once_per_selected_key(monkeypatch):
    import llm_rate_limits

    monkeypatch.setattr(llm_rate_limits, "emit_log", lambda message: None)
    rotator = llm_rate_limits.KeyRotator(["k1", "k2", "k3"])

    async def run():
        first = await rotator.async_get_key("test-model")
        second = await rotator.async_get_key("test-model")
        return first, second, rotator.index

    assert asyncio.run(run()) == ("k1", "k2", 2)


def test_analysis_done_fallback_handles_empty_pipeline_sequence():
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router

    router = create_analysis_router(AnalysisRouteDeps(
        active_analyses_lock=threading.Lock(),
        get_analysis_task_queue=lambda: None,
        run_stock_analysis_job=lambda job_id, ticker, pipeline: None,
        has_api_keys=lambda: True,
        api_key_setup_message=lambda: "",
        normalize_pipeline_run_id=lambda pipeline: pipeline,
        get_pipeline_run_sequence=lambda pipeline: (),
        get_pipeline_run_label=lambda pipeline: pipeline,
        get_pipeline_run_agent_total=lambda pipeline: 0,
        get_job=lambda job_id: {"job_id": job_id, "ticker": "2308.TW", "pipeline_id": "empty", "status": "done", "filename": "done.html"},
        find_active_job=lambda ticker, pipeline: {"job_id": "job-1"},
        create_job=lambda ticker, pipeline: "job-1",
        get_events_since=lambda job_id, after_id: [],
        update_job=lambda *args, **kwargs: None,
        append_event=lambda *args, **kwargs: None,
        request_job_cancel=lambda *args, **kwargs: False,
        print_streamed_event=lambda *args, **kwargs: None,
        require_mutation_authorized=lambda request: None,
    ))
    route = next(route for route in router.routes if getattr(route.endpoint, "__name__", "") == "analyze_stock")

    class Request:
        headers = {}

        async def is_disconnected(self):
            return False

    response = asyncio.run(
        route.endpoint(
            "2308.TW",
            Request(),
            job_id="job-1",
            last_event_id=0,
            pipeline="empty",
            cancel_on_disconnect=False,
        )
    )
    generator = response.body_iterator
    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert '"last_pipeline_id": "empty"' in second["data"]


def test_analysis_stream_replays_from_last_event_id_header():
    from api_routes.analysis import AnalysisRouteDeps, create_analysis_router

    seen_after_ids = []

    router = create_analysis_router(AnalysisRouteDeps(
        active_analyses_lock=threading.Lock(),
        get_analysis_task_queue=lambda: None,
        run_stock_analysis_job=lambda job_id, ticker, pipeline: None,
        has_api_keys=lambda: True,
        api_key_setup_message=lambda: "",
        normalize_pipeline_run_id=lambda pipeline: pipeline,
        get_pipeline_run_sequence=lambda pipeline: (pipeline,),
        get_pipeline_run_label=lambda pipeline: pipeline,
        get_pipeline_run_agent_total=lambda pipeline: 1,
        get_job=lambda job_id: {"job_id": job_id, "ticker": "2308.TW", "pipeline_id": "v1", "status": "running"},
        find_active_job=lambda ticker, pipeline: {"job_id": "job-1"},
        create_job=lambda ticker, pipeline: "job-1",
        get_events_since=lambda job_id, after_id: (
            seen_after_ids.append(after_id)
            or [{"id": 6, "payload": {"type": "done", "filename": "done.html"}, "created_at": "now"}]
        ),
        update_job=lambda *args, **kwargs: None,
        append_event=lambda *args, **kwargs: None,
        request_job_cancel=lambda *args, **kwargs: False,
        print_streamed_event=lambda *args, **kwargs: None,
        require_mutation_authorized=lambda request: None,
    ))
    route = next(route for route in router.routes if getattr(route.endpoint, "__name__", "") == "analyze_stock")

    class Request:
        headers = {"last-event-id": "5"}

        async def is_disconnected(self):
            return False

    response = asyncio.run(
        route.endpoint(
            "2308.TW",
            Request(),
            job_id=None,
            last_event_id=None,
            pipeline="v1",
            cancel_on_disconnect=False,
        )
    )
    generator = response.body_iterator
    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"resume_after_id": 5' in first["data"]
    assert seen_after_ids == [5]
    assert second["id"] == "6"
    assert '"type": "done"' in second["data"]


def test_analysis_stream_malformed_since_id_falls_back_to_last_event_id_header():
    from api_routes.analysis_sse import resolve_resume_after_id

    class Request:
        headers = {"last-event-id": "6"}

    assert resolve_resume_after_id(Request(), last_event_id=None, since_id="malformed") == 6


def test_analysis_stream_negative_since_id_falls_back_to_last_event_id_header():
    from api_routes.analysis_sse import resolve_resume_after_id

    class Request:
        headers = {"last-event-id": "6"}

    assert resolve_resume_after_id(Request(), last_event_id=None, since_id=-2) == 6


def test_analysis_stream_boolean_since_id_falls_back_to_last_event_id_header():
    from api_routes.analysis_sse import resolve_resume_after_id

    class Request:
        headers = {"last-event-id": "6"}

    assert resolve_resume_after_id(Request(), last_event_id=None, since_id=True) == 6


def test_analysis_stream_does_not_persist_client_disconnect_noise():
    from api_routes.analysis_sse import analysis_event_generator

    appended = []

    class Deps:
        def append_event(self, job_id, payload):
            appended.append((job_id, payload))

        def request_job_cancel(self, job_id, reason):
            appended.append((job_id, {"type": "cancel", "message": reason}))

        def get_events_since(self, job_id, after_id):
            return []

        def get_job(self, job_id):
            return {"job_id": job_id, "status": "running", "pipeline_id": "v1"}

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return True

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-disconnect",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    with pytest.raises(StopAsyncIteration):
        asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert appended == []


def test_analysis_stream_malformed_replay_payload_uses_status_fallback():
    from api_routes.analysis_sse import analysis_event_generator

    events = [
        {"id": 1, "payload": ["malformed", "event"], "created_at": "now"},
        {"id": 2, "payload": {"type": "done", "filename": "done.html"}, "created_at": "now"},
    ]
    streamed = []

    class Deps:
        def append_event(self, job_id, payload):
            raise AssertionError("replay fallback should not persist a synthetic event")

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return [event for event in events if event["id"] > after_id]

        def get_job(self, job_id):
            return {"job_id": job_id, "status": "done", "pipeline_id": "v1", "filename": "done.html"}

        def print_streamed_event(self, job_id, payload):
            streamed.append(payload)

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-malformed-event",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())
    third = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert second["id"] == "1"
    assert '"type": "status"' in second["data"]
    assert "略過格式異常的分析任務事件" in second["data"]
    assert third["id"] == "2"
    assert '"type": "done"' in third["data"]
    assert streamed[0]["type"] == "status"


def test_analysis_stream_malformed_replay_event_row_uses_status_fallback():
    from api_routes.analysis_sse import analysis_event_generator

    events = [
        ["malformed", "event"],
        {"id": 2, "payload": {"type": "done", "filename": "done.html"}, "created_at": "now"},
    ]
    streamed = []

    class Deps:
        def append_event(self, job_id, payload):
            raise AssertionError("replay fallback should not persist a synthetic event")

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            if after_id == 0:
                return events
            return []

        def get_job(self, job_id):
            return {"job_id": job_id, "status": "done", "pipeline_id": "v1", "filename": "done.html"}

        def print_streamed_event(self, job_id, payload):
            streamed.append(payload)

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-malformed-event-row",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())
    third = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert "id" not in second
    assert '"type": "status"' in second["data"]
    assert "略過格式異常的分析任務事件" in second["data"]
    assert third["id"] == "2"
    assert '"type": "done"' in third["data"]
    assert streamed[0]["type"] == "status"


def test_analysis_stream_persists_terminal_fallback_with_event_id():
    from api_routes.analysis_sse import analysis_event_generator

    events = []

    class Deps:
        def append_event(self, job_id, payload):
            events.append({"id": len(events) + 1, "payload": payload, "created_at": "now"})

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return [event for event in events if event["id"] > after_id]

        def get_job(self, job_id):
            return {
                "job_id": job_id,
                "status": "done",
                "pipeline_id": "v1",
                "filename": "done.html",
            }

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-done",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert second["id"] == "1"
    assert '"type": "done"' in second["data"]
    assert events[0]["payload"]["filename"] == "done.html"


def test_analysis_terminal_event_presence_accepts_mapping_event_rows():
    from collections.abc import Mapping

    from api_routes.analysis_sse import persist_terminal_event_if_missing

    class ReadOnlyMapping(Mapping):
        def __init__(self, values):
            self._values = values

        def __getitem__(self, key):
            return self._values[key]

        def __iter__(self):
            return iter(self._values)

        def __len__(self):
            return len(self._values)

    existing_terminal_event = ReadOnlyMapping(
        {
            "id": 1,
            "payload": ReadOnlyMapping({"type": "done", "filename": "done.html"}),
        }
    )
    appended = []

    class Deps:
        def get_events_since(self, job_id, after_id):
            return [existing_terminal_event]

        def append_event(self, job_id, payload):
            appended.append((job_id, payload))

    result = persist_terminal_event_if_missing(
        Deps(),
        "job-done",
        {"type": "done", "filename": "done.html"},
    )

    assert result is False
    assert appended == []


def test_analysis_stream_malformed_event_collection_uses_terminal_fallback():
    from api_routes.analysis_sse import analysis_event_generator

    class Deps:
        def append_event(self, job_id, payload):
            raise AssertionError("malformed event collection should not persist a synthetic event")

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return None

        def get_job(self, job_id):
            return {
                "job_id": job_id,
                "status": "done",
                "pipeline_id": "v1",
                "filename": "done.html",
            }

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-malformed-event-collection",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert "id" not in second
    assert '"type": "done"' in second["data"]
    assert '"filename": "done.html"' in second["data"]


def test_analysis_stream_missing_job_row_uses_terminal_error_fallback():
    from api_routes.analysis_sse import analysis_event_generator

    class Deps:
        def append_event(self, job_id, payload):
            raise RuntimeError("missing job fallback persistence unavailable")

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return []

        def get_job(self, job_id):
            return None

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-missing-row",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert "id" not in second
    assert '"type": "error"' in second["data"]
    assert '"phase": "missing_job"' in second["data"]
    assert "找不到分析任務" in second["data"]


def test_analysis_stream_empty_job_row_uses_terminal_error_fallback():
    from api_routes.analysis_sse import analysis_event_generator

    class Deps:
        def append_event(self, job_id, payload):
            raise RuntimeError("missing job fallback persistence unavailable")

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return []

        def get_job(self, job_id):
            return {}

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-empty-row",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert "id" not in second
    assert '"type": "error"' in second["data"]
    assert '"phase": "missing_job"' in second["data"]
    assert "找不到分析任務" in second["data"]


def test_analysis_stream_done_terminal_fallback_uses_safe_identity_fields():
    from api_routes.analysis_sse import analysis_event_generator

    events = []
    requested_pipeline_ids = []

    class Deps:
        def append_event(self, job_id, payload):
            events.append({"id": len(events) + 1, "payload": payload, "created_at": "now"})

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return [event for event in events if event["id"] > after_id]

        def get_job(self, job_id):
            return {
                "job_id": job_id,
                "status": "done",
                "pipeline_id": memoryview(b"unsafe-pipeline"),
                "filename": memoryview(b"unsafe-report.html"),
            }

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            requested_pipeline_ids.append(pipeline_id)
            return (pipeline_id, memoryview(b"unsafe-last-pipeline"))

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-done-malformed",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert second["id"] == "1"
    assert '"type": "done"' in second["data"]
    assert requested_pipeline_ids == ["v1"]
    assert events[0]["payload"]["filename"] is None
    assert events[0]["payload"]["pipeline_id"] == "v1"
    assert events[0]["payload"]["last_pipeline_id"] == "v1"


def test_analysis_stream_malformed_job_status_does_not_interrupt_polling():
    from api_routes.analysis_sse import analysis_event_generator

    class BrokenStatus:
        def __eq__(self, _other):
            raise RuntimeError("status comparison failed")

        def __str__(self):
            raise RuntimeError("status string conversion failed")

    class Deps:
        def append_event(self, job_id, payload):
            raise AssertionError("malformed status should not synthesize terminal events")

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return []

        def get_job(self, job_id):
            return {"job_id": job_id, "status": BrokenStatus(), "pipeline_id": "v1"}

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-malformed-status",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert second["event"] == "ping"


def test_analysis_stream_error_terminal_fallback_uses_safe_message():
    from api_routes.analysis_sse import analysis_event_generator

    events = []

    class Deps:
        def append_event(self, job_id, payload):
            events.append({"id": len(events) + 1, "payload": payload, "created_at": "now"})

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return [event for event in events if event["id"] > after_id]

        def get_job(self, job_id):
            return {
                "job_id": job_id,
                "status": "error",
                "pipeline_id": "v1",
                "error": memoryview(b"unsafe-analysis-error"),
            }

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-error",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert second["id"] == "1"
    assert '"type": "error"' in second["data"]
    assert "分析任務失敗" in second["data"]
    assert events[0]["payload"]["message"] == "分析任務失敗"


def test_analysis_stream_cancelled_terminal_fallback_uses_safe_message():
    from api_routes.analysis_sse import analysis_event_generator

    events = []

    class Deps:
        def append_event(self, job_id, payload):
            events.append({"id": len(events) + 1, "payload": payload, "created_at": "now"})

        def request_job_cancel(self, job_id, reason):
            raise AssertionError("cancel should not be requested")

        def get_events_since(self, job_id, after_id):
            return [event for event in events if event["id"] > after_id]

        def get_job(self, job_id):
            return {
                "job_id": job_id,
                "status": "cancelled",
                "pipeline_id": "v1",
                "error": memoryview(b"unsafe-cancel-reason"),
            }

        def print_streamed_event(self, job_id, payload):
            pass

        def get_pipeline_run_sequence(self, pipeline_id):
            return (pipeline_id,)

    class Request:
        async def is_disconnected(self):
            return False

    generator = analysis_event_generator(
        Deps(),
        Request(),
        job_id="job-cancelled",
        resume_after_id=0,
        cancel_on_disconnect=False,
        intro_payload={"type": "job", "pipeline_id": "v1"},
    )

    first = asyncio.run(generator.__anext__())
    second = asyncio.run(generator.__anext__())

    assert '"type": "job"' in first["data"]
    assert second["id"] == "1"
    assert '"phase": "cancelled"' in second["data"]
    assert "分析任務已取消" in second["data"]
    assert events[0]["payload"]["message"] == "分析任務已取消"


def test_validate_runtime_settings_blocks_lan_without_mutation_token(monkeypatch):
    import settings.app_config as app_config

    monkeypatch.setattr(app_config, "DEPLOYMENT_MODE", "lan")
    monkeypatch.setattr(app_config, "MUTATION_API_TOKEN", "")

    with pytest.raises(RuntimeError, match="MUTATION_API_TOKEN"):
        app_config.validate_runtime_settings()


def test_validate_runtime_settings_blocks_network_profile_without_access_guard(monkeypatch):
    import settings.app_config as app_config
    import settings.security as security

    monkeypatch.setattr(app_config, "DEPLOYMENT_MODE", "lan")
    monkeypatch.setattr(app_config, "MUTATION_API_TOKEN", "mutation-token")
    monkeypatch.setattr(app_config, "ALLOWED_ORIGINS", ["http://localhost:8080"])
    monkeypatch.setattr(security, "BASIC_AUTH_USERNAME", "")
    monkeypatch.setattr(security, "BASIC_AUTH_PASSWORD", "")
    monkeypatch.setattr(security, "EXTERNAL_ACCESS_CONTROLLED", False)

    with pytest.raises(RuntimeError, match="BASIC_AUTH_USERNAME"):
        app_config.validate_runtime_settings()

    monkeypatch.setattr(security, "BASIC_AUTH_USERNAME", "operator")
    monkeypatch.setattr(security, "BASIC_AUTH_PASSWORD", "secret")

    assert isinstance(app_config.validate_runtime_settings(), list)


def test_list_reports_does_not_run_cleanup_on_read(monkeypatch, tmp_path):
    import report_history_service

    calls = []
    monkeypatch.setattr(report_history_service, "cleanup_expired_reports", lambda *args, **kwargs: calls.append("expired"))
    monkeypatch.setattr(report_history_service, "cleanup_orphan_markdown_reports", lambda *args, **kwargs: calls.append("orphan"))

    class EmptyRepository:
        def query(self, query):
            return [], 0

    report_history_service.list_reports(
        page=1,
        limit=10,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        output_dir=str(tmp_path),
        report_cache={},
        repository=EmptyRepository(),
    )

    assert calls == []


def test_create_app_warns_and_disables_credentials_for_wildcard_origin(monkeypatch):
    import api

    messages = []
    monkeypatch.setattr(api, "ALLOWED_ORIGINS", ["*"])
    monkeypatch.setattr(api, "emit_log", lambda message: messages.append(message))

    app = api.create_app()
    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")

    assert cors.kwargs["allow_credentials"] is False
    assert any("已停用 credentials 支援" in message for message in messages)


def test_create_app_uses_restricted_cors_methods_and_headers_in_production(monkeypatch):
    import api

    monkeypatch.setattr(api, "DEPLOYMENT_MODE", "production", raising=False)
    monkeypatch.setattr(api, "ALLOWED_ORIGINS", ["https://ui.example.com"])

    app = api.create_app()
    cors = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")

    assert cors.kwargs["allow_methods"] == ["GET", "POST", "DELETE", "OPTIONS"]
    assert cors.kwargs["allow_headers"] == ["Content-Type", "X-Mutation-Token", "X-Admin-Token", "Last-Event-ID"]


class RecordingLock:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1

    def __exit__(self, exc_type, exc, tb):
        return False


class NoopRepository:
    def delete(self, *args, **kwargs):
        return None


def test_cleanup_expired_reports_uses_report_cache_lock(tmp_path):
    import os
    import time

    import report_history_service

    old_report = tmp_path / "2308_TW_report.html"
    old_report.write_text("<html></html>", encoding="utf-8")
    old_time = time.time() - 10 * 24 * 60 * 60
    os.utime(old_report, (old_time, old_time))
    report_cache = {"2308.TW": old_report.name}
    lock = RecordingLock()

    deleted = report_history_service.cleanup_expired_reports(
        str(tmp_path),
        report_cache,
        retention_days=1,
        repository=NoopRepository(),
        report_cache_lock=lock,
    )

    assert deleted == [old_report.name]
    assert report_cache == {}
    assert lock.entered == 1


def test_delete_report_files_uses_report_cache_lock(tmp_path):
    import report_history_service

    report = tmp_path / "2308_TW_report.html"
    report.write_text("<html></html>", encoding="utf-8")
    report_cache = {"2308.TW": report.name}
    lock = RecordingLock()

    result = report_history_service.delete_report_files(
        report.name,
        str(tmp_path),
        report_cache,
        repository=NoopRepository(),
        report_cache_lock=lock,
    )

    assert result["success"] is True
    assert report_cache == {}
    assert lock.entered == 1
