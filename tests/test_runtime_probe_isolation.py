"""Critical read-only probes remain bounded when the default pool is busy."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread

from fastapi import FastAPI
import httpx
import pytest

from api_routes.health import HealthRouteDeps, create_health_router
from api_routes.observability import ObservabilityRouteDeps, create_observability_router


def test_ready_and_settings_do_not_wait_for_saturated_default_executor(monkeypatch):
    import api_routes.observability as observability

    monkeypatch.setattr(observability, "build_agent_settings_payload", lambda: {
        "snapshot_scope": "api_process", "effective_settings_sha256": "a" * 64,
    })
    app = FastAPI()
    app.include_router(create_health_router(HealthRouteDeps(
        build_health_payload=lambda: {"status": "ok"},
        build_readiness_payload=lambda: {"status": "ready", "checks": [{"name": "actual-check", "status": "pass"}]},
    )))
    app.include_router(create_observability_router(ObservabilityRouteDeps(
        get_provider_sla_summary=lambda _: [], get_provider_sla_alerts=lambda _: [], get_task_queue=lambda: None,
    )))

    async def run():
        gate, entered = Event(), Event()
        pool = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        previous_pool = loop._default_executor
        loop.set_default_executor(pool)
        def occupy():
            entered.set()
            gate.wait(3)
        occupied = loop.run_in_executor(None, occupy)
        assert entered.wait(1)
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    ready, settings = await asyncio.wait_for(asyncio.gather(
                        client.get("/readyz"), client.get("/api/observability/agent-settings"),
                    ), timeout=1.0)
                    assert not occupied.done()
                    assert ready.status_code == settings.status_code == 200
                    assert ready.json()["checks"] == [{"name": "actual-check", "status": "pass"}]
                    assert settings.json()["effective_settings_sha256"] == "a" * 64
        finally:
            gate.set()
            await occupied
            loop._default_executor = previous_pool
            pool.shutdown(wait=True)

    asyncio.run(run())


@pytest.mark.parametrize("caller_ends", ["timeout", "cancel"])
def test_expired_caller_keeps_slot_until_real_work_finishes(caller_ends):
    from runtime_probe_executor import BoundedProbeExecutor, ProbeUnavailable

    async def run():
        runner = BoundedProbeExecutor("test-expired-probe")
        gate = Event()
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()
        calls = []
        def blocked():
            calls.append("executed")
            loop.call_soon_threadsafe(entered.set)
            gate.wait(3)
            return "old-result"
        async with runner.lifespan(None):
            task = asyncio.create_task(runner.run(blocked, timeout_seconds=0.01 if caller_ends == "timeout" else 3))
            try:
                await asyncio.wait_for(entered.wait(), 1)
                if caller_ends == "cancel":
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                else:
                    with pytest.raises(ProbeUnavailable, match="probe_timeout"):
                        await task
                for _ in range(20):
                    with pytest.raises(ProbeUnavailable, match="probe_busy"):
                        await runner.run(lambda: calls.append("queued"), timeout_seconds=0.01)
                assert calls == ["executed"]
            finally:
                gate.set()
            # Wait for the real concurrent Future, not the expired caller.
            await asyncio.wrap_future(runner._inflight)
            assert await runner.run(lambda: "fresh-result", timeout_seconds=1) == "fresh-result"
        with pytest.raises(ProbeUnavailable, match="probe_closed"):
            await runner.run(lambda: "after-shutdown", timeout_seconds=1)

    asyncio.run(run())


def test_busy_readiness_is_503_while_settings_remains_fresh(monkeypatch):
    import api_routes.observability as observability

    gate = Event()
    snapshot_calls = []
    def settings_snapshot():
        snapshot_calls.append(1)
        return {"snapshot_scope": "api_process", "observed_value": len(snapshot_calls), "worker_settings_verified": False}
    monkeypatch.setattr(observability, "build_agent_settings_payload", settings_snapshot)

    async def run():
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()
        def readiness():
            loop.call_soon_threadsafe(entered.set)
            gate.wait(3)
            return {"status": "not_ready", "checks": [{"name": "queue", "status": "fail"}]}
        app = FastAPI()
        app.include_router(create_health_router(HealthRouteDeps(
            build_health_payload=lambda: {"status": "ok"}, build_readiness_payload=readiness,
        )))
        app.include_router(create_observability_router(ObservabilityRouteDeps(
            get_provider_sla_summary=lambda _: [], get_provider_sla_alerts=lambda _: [], get_task_queue=lambda: None,
        )))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                first = asyncio.create_task(client.get("/readyz"))
                try:
                    await asyncio.wait_for(entered.wait(), 1)
                    busy = await client.get("/readyz")
                    assert busy.status_code == 503
                    assert busy.json()["status"] == "not_ready"
                    assert busy.json()["reason"] == "probe_busy"
                    for expected in (1, 2):
                        snapshot = await client.get("/api/observability/agent-settings")
                        assert snapshot.status_code == 200
                        assert snapshot.json()["observed_value"] == expected
                        assert snapshot.json()["worker_settings_verified"] is False
                finally:
                    gate.set()
                result = await first
                assert result.status_code == 503
                assert result.json() == {"status": "not_ready", "checks": [{"name": "queue", "status": "fail"}]}

    asyncio.run(run())


@pytest.mark.parametrize("failure", [ValueError("operation-failed"), TimeoutError("operation-timeout")])
def test_operation_failure_is_not_masked_as_probe_timeout(failure):
    from runtime_probe_executor import BoundedProbeExecutor

    def fail():
        raise failure
    async def run():
        runner = BoundedProbeExecutor("test-failed-probe")
        async with runner.lifespan(None):
            with pytest.raises(type(failure), match=str(failure)):
                await runner.run(fail, timeout_seconds=1)
            assert await runner.run(lambda: "recovered", timeout_seconds=1) == "recovered"
    asyncio.run(run())


def test_lifespan_closes_workers_and_can_restart_on_another_event_loop():
    from runtime_probe_executor import BoundedProbeExecutor, ProbeUnavailable

    runner = BoundedProbeExecutor("test-probe-lifespan")
    threads = []
    async def cycle():
        async with runner.lifespan(None):
            threads.append(await runner.run(current_thread, timeout_seconds=1))
        with pytest.raises(ProbeUnavailable, match="probe_closed"):
            await runner.run(lambda: "closed", timeout_seconds=1)
    for _ in range(2):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(cycle())
        finally:
            loop.close()
        threads[-1].join(timeout=1)
        assert not threads[-1].is_alive()
    assert threads[0] is not threads[1]


def test_closing_running_probe_rejects_new_work_and_waits_for_real_completion():
    from runtime_probe_executor import BoundedProbeExecutor, ProbeUnavailable

    async def run():
        runner = BoundedProbeExecutor("test-running-close")
        gate, entered = Event(), asyncio.Event()
        loop = asyncio.get_running_loop()
        def blocked():
            loop.call_soon_threadsafe(entered.set)
            gate.wait(3)
            return "completed"
        task = asyncio.create_task(runner.run(blocked, timeout_seconds=2))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            runner.close()
            with pytest.raises(ProbeUnavailable, match="probe_closed"):
                await runner.run(lambda: "after-close", timeout_seconds=1)
            with pytest.raises(RuntimeError, match="previous probe lifespan"):
                async with runner.lifespan(None):
                    pass
        finally:
            gate.set()
        assert await task == "completed"
    asyncio.run(run())
