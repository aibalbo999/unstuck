import asyncio
from types import SimpleNamespace
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from agent_runtime import AgentExecutor, AgentRunRequest  # noqa: E402
from data_fetch import FetchRequest, StockDataService  # noqa: E402
import data_fetch.service as data_fetch_service  # noqa: E402
from data_fetch.providers import (  # noqa: E402
    CallableProvider,
    FinMindProvider,
    FmpProvider,
    FreeNewsWaterfallProvider,
    InstitutionalTradingProvider,
    MonthlyRevenueProvider,
    PeRiverChartProvider,
    ProviderRegistry,
    TwseOfficialProvider,
    infer_market,
)
from reporting import ReportRenderer, ReportRequest  # noqa: E402


def test_stock_data_service_returns_typed_fetch_result_from_fake_provider():
    async def fake_fetcher(request):
        return {
            "ticker": request.ticker,
            "company_name": "Fixture",
            "source_audit": [
                {
                    "source": "market_data",
                    "provider": "fake",
                    "status": "success",
                    "duration_ms": 3,
                    "record_count": 1,
                }
            ],
            "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        }

    result = asyncio.run(StockDataService(fetcher=fake_fetcher).fetch_async(FetchRequest.from_ticker("aapl")))

    assert result.request.ticker == "AAPL"
    assert result.data["ticker"] == "AAPL"
    assert result.provider_results[0].provider == "fake"
    assert result.provider_results[0].status == "success"


def test_stock_data_service_can_skip_system_provider_sla_recording(monkeypatch):
    recorded = []

    async def fake_fetcher(request):
        return {
            "ticker": request.ticker,
            "source_audit": [
                {"source": "market_data", "provider": "fake", "status": "success", "record_count": 1}
            ],
        }

    monkeypatch.setattr(data_fetch_service, "record_source_audit_entries", lambda entries: recorded.append(list(entries)))

    result = asyncio.run(
        StockDataService(fetcher=fake_fetcher).fetch_async(
            FetchRequest.from_ticker("aapl", record_provider_sla=False)
        )
    )

    assert result.provider_results[0].provider == "fake"
    assert recorded == []


def test_provider_registry_routes_by_market():
    provider = CallableProvider(
        source="monthly_revenue",
        name="tw-only",
        markets={"tw"},
        callback=lambda request: None,
    )
    registry = ProviderRegistry([provider])

    assert infer_market("2330.TW") == "tw"
    assert registry.provider_names(FetchRequest.from_ticker("2330.TW")) == ["tw-only"]
    assert registry.provider_names(FetchRequest.from_ticker("AAPL")) == []


def test_default_core_provider_registry_exposes_expected_source_routes():
    registry = ProviderRegistry([
        FinMindProvider(),
        FmpProvider(),
        MonthlyRevenueProvider(),
        InstitutionalTradingProvider(),
        TwseOfficialProvider(),
        PeRiverChartProvider(),
    ])
    tw_request = FetchRequest.from_ticker("2330.TW")
    us_request = FetchRequest.from_ticker("AAPL")

    assert registry.provider_names(tw_request, source="financial_statements") == ["FinMind"]
    assert registry.provider_names(tw_request, source="monthly_revenue") == ["FinMind TaiwanStockMonthRevenue"]
    assert registry.provider_names(tw_request, source="institutional_trading") == ["FinMind"]
    assert registry.provider_names(tw_request, source="twse_official") == ["FinMind TWSE official"]
    assert registry.provider_names(tw_request, source="pe_river_chart") == ["FinMind/default multiples"]
    assert registry.provider_names(tw_request, source="market_data") == []
    assert registry.provider_names(us_request, source="monthly_revenue") == []
    assert registry.provider_names(us_request, source="institutional_trading") == []
    assert registry.provider_names(us_request, source="twse_official") == []
    assert registry.provider_names(us_request, source="market_data") == ["FMP stable quote"]
    assert registry.first_provider(us_request, source="market_data") is None


def test_default_registry_prefers_free_news_waterfall():
    registry = ProviderRegistry()

    assert registry.provider_names(FetchRequest.from_ticker("2330.TW"), source="recent_catalysts")[0] == "Free news waterfall"


def test_agent_executor_uses_split_runtime(monkeypatch):
    import agent_runtime.executor as executor_module

    async def fake_run_single_agent_async(agent_num, data, context, rotator, max_retries=3):
        context.setdefault("structured_outputs", {})[agent_num] = {"ok": True}
        return "## Agent Output\n" + ("content " * 30)

    monkeypatch.setattr(executor_module, "run_single_agent_async", fake_run_single_agent_async)
    monkeypatch.setattr(executor_module, "get_runtime_model_sequence", lambda agent_num, context: ["fake-model"])

    context = {"structured_outputs": {}}
    result = asyncio.run(
        AgentExecutor().run_async(
            AgentRunRequest(
                agent_num=7,
                data={"ticker": "AAPL", "company_name": "Apple"},
                context=context,
                rotator=object(),
            )
        )
    )

    assert result.agent_num == 7
    assert result.model_id == "fake-model"
    assert result.structured_output == {"ok": True}
    assert result.duration_ms >= 0


def test_single_agent_async_honors_context_cancel_check(monkeypatch):
    import agent_runtime.single_agent as single_agent_module
    from agent_runtime.cancellation import attach_cancel_check

    class CancelledForTest(Exception):
        pass

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("LLM call should not start after cancellation")

    context = {"structured_outputs": {}}
    attach_cancel_check(context, lambda: (_ for _ in ()).throw(CancelledForTest("cancelled")))
    monkeypatch.setattr(single_agent_module, "build_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(single_agent_module, "get_runtime_model_sequence", lambda *_args, **_kwargs: ["fake-model"])
    monkeypatch.setattr(single_agent_module, "_run_agent_once_async", fail_if_called)

    try:
        asyncio.run(
            single_agent_module.run_single_agent_async(
                7,
                {"ticker": "AAPL", "company_name": "Apple"},
                context,
                object(),
            )
        )
    except CancelledForTest:
        pass
    else:
        raise AssertionError("cancel check should abort single-agent execution")


def test_workflow_retry_policy_classifies_transient_agent_errors():
    from agent_runtime.retry_policy import AgentRateLimitError, AgentServerError, AgentTransientError
    from workflow_graph import is_retryable_workflow_error

    assert is_retryable_workflow_error(AgentRateLimitError("429", 0, 60)) is True
    assert is_retryable_workflow_error(AgentServerError("503 UNAVAILABLE")) is True
    assert is_retryable_workflow_error(AgentTransientError("timeout")) is True
    assert is_retryable_workflow_error(ValueError("bad input")) is False


def test_single_agent_async_uses_configured_primary_timeout_before_fallback(monkeypatch):
    import agent_runtime.single_agent as single_agent_module
    from agent_runtime.retry_policy import AgentTransientError

    calls = []

    async def fake_run_once(agent_num, context, rotator, model_id, prompt, quota_default=1, timeout_seconds=None):
        calls.append((model_id, timeout_seconds))
        if model_id == "primary-model":
            raise AgentTransientError("primary timeout")
        return "fallback result " * 20

    monkeypatch.setattr(single_agent_module, "build_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(single_agent_module, "get_runtime_model_sequence", lambda *_args, **_kwargs: ["primary-model", "fallback-model"])
    monkeypatch.setattr(single_agent_module, "_run_agent_once_async", fake_run_once)

    result = asyncio.run(
        single_agent_module.run_single_agent_async(
            7,
            {"ticker": "AAPL", "company_name": "Apple"},
            {"structured_outputs": {}},
            object(),
        )
    )

    assert "fallback result" in result
    assert calls == [("primary-model", 360.0), ("fallback-model", 120.0)]


def test_single_agent_async_reuses_agent_step_cache(monkeypatch):
    import agent_runtime.single_agent as single_agent_module
    import cache_store
    from cache_backends import InMemoryCache

    calls = []

    async def fake_run_once(agent_num, context, rotator, model_id, prompt, quota_default=1, timeout_seconds=None):
        calls.append((agent_num, model_id, prompt))
        context.setdefault("structured_outputs", {})[agent_num] = {"recommendation": {"建議": "持有"}}
        return "cached agent result " * 20

    try:
        cache_store.set_cache_backend(InMemoryCache())
        monkeypatch.setattr(single_agent_module, "build_prompt", lambda *_args, **_kwargs: "stable prompt")
        monkeypatch.setattr(single_agent_module, "get_runtime_model_sequence", lambda *_args, **_kwargs: ["cache-model"])
        monkeypatch.setattr(single_agent_module, "_run_agent_once_async", fake_run_once)

        data = {"ticker": "AAPL", "company_name": "Apple", "data_snapshot_hash": "snapshot-1"}
        first_context = {"structured_outputs": {}, "prompt_version": "runtime-rules:test"}
        second_context = {"structured_outputs": {}, "prompt_version": "runtime-rules:test"}

        first = asyncio.run(single_agent_module.run_single_agent_async(7, data, first_context, object()))
        second = asyncio.run(single_agent_module.run_single_agent_async(7, data, second_context, object()))

        assert first == second
        assert calls == [(7, "cache-model", "stable prompt")]
        assert second_context["structured_outputs"][7] == {"recommendation": {"建議": "持有"}}
        assert any(event.get("phase") == "agent_step_cache_hit" for event in second_context["_runtime_events"])
    finally:
        cache_store.reset_cache_store_for_tests()


def test_agent_step_cache_key_changes_when_prompt_changes():
    from agent_runtime.step_cache import build_agent_step_cache_key

    data = {"ticker": "AAPL", "data_snapshot_hash": "snapshot-1"}
    context = {"prompt_version": "runtime-rules:test"}

    first_key = build_agent_step_cache_key(7, data, context, "cache-model", "prompt v1")
    second_key = build_agent_step_cache_key(7, data, context, "cache-model", "prompt v2")

    assert first_key != second_key


def test_single_agent_async_retries_primary_5xx_before_fallback(monkeypatch):
    import agent_runtime.single_agent as single_agent_module
    from agent_runtime.retry_policy import AgentServerError

    calls = []

    async def fake_run_once(agent_num, context, rotator, model_id, prompt, quota_default=1, timeout_seconds=None):
        calls.append((model_id, timeout_seconds))
        if len(calls) < 3:
            raise AgentServerError("503 UNAVAILABLE high demand")
        return "primary recovered result " * 20

    monkeypatch.setattr(single_agent_module, "build_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(single_agent_module, "get_runtime_model_sequence", lambda *_args, **_kwargs: ["primary-model", "fallback-model"])
    monkeypatch.setattr(single_agent_module, "_agent_retry_wait", lambda _retry_state: 0)
    monkeypatch.setattr(single_agent_module, "_run_agent_once_async", fake_run_once)

    result = asyncio.run(
        single_agent_module.run_single_agent_async(
            7,
            {"ticker": "AAPL", "company_name": "Apple"},
            {"structured_outputs": {}},
            object(),
        )
    )

    assert "primary recovered result" in result
    assert calls == [("primary-model", 360.0), ("primary-model", 360.0), ("primary-model", 360.0)]


def test_single_agent_async_exhausts_quota_across_all_keys_before_fallback(monkeypatch):
    import agent_runtime.single_agent as single_agent_module
    from agent_runtime.retry_policy import AgentRateLimitError

    class FakeRotator:
        keys = ["k1", "k2", "k3", "k4"]

    calls = []

    async def fake_run_once(agent_num, context, rotator, model_id, prompt, quota_default=1, timeout_seconds=None):
        calls.append((model_id, timeout_seconds))
        if model_id == "primary-model":
            raise AgentRateLimitError("429", 0, 60)
        return "fallback result " * 20

    monkeypatch.setattr(single_agent_module, "build_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr(single_agent_module, "get_runtime_model_sequence", lambda *_args, **_kwargs: ["primary-model", "fallback-model"])
    monkeypatch.setattr(single_agent_module, "_agent_retry_wait", lambda _retry_state: 0)
    monkeypatch.setattr(single_agent_module, "_run_agent_once_async", fake_run_once)

    result = asyncio.run(
        single_agent_module.run_single_agent_async(
            7,
            {"ticker": "AAPL", "company_name": "Apple"},
            {"structured_outputs": {}},
            FakeRotator(),
        )
    )

    assert "fallback result" in result
    assert calls == [
        ("primary-model", 360.0),
        ("primary-model", 360.0),
        ("primary-model", 360.0),
        ("primary-model", 360.0),
        ("fallback-model", 120.0),
    ]


def test_llm_async_call_timeout_becomes_retryable(monkeypatch):
    import agent_runtime.llm_calls as llm_calls

    class FakeRotator:
        async def async_get_key(self, model_id, estimated_tokens=0):
            return "fake-key"

        def penalize(self, *_args, **_kwargs):
            pass

    async def slow_generate(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        return object()

    monkeypatch.setattr(llm_calls, "LLM_AGENT_CALL_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(llm_calls, "_generate_content_async", slow_generate)

    context = {
        "agent_positions": {7: 1},
        "agent_total": 1,
        "pipeline_id": "v1",
        "pipeline_label": "test",
        "structured_outputs": {},
    }

    try:
        asyncio.run(
            llm_calls._run_agent_once_async(
                7,
                context,
                FakeRotator(),
                "fake-model",
                "prompt",
                timeout_seconds=0.001,
            )
        )
    except llm_calls.AgentTransientError as exc:
        assert "timeout" in str(exc).lower()
        error_event = context["_runtime_events"][-1]
        assert error_event["metadata"]["timeout_seconds"] == 0.001
    else:
        raise AssertionError("LLM timeout should become AgentTransientError")


def test_llm_async_call_streams_deltas_and_processes_full_response(monkeypatch):
    import agent_runtime.llm_calls as llm_calls
    from runtime_events import RUNTIME_EVENT_CALLBACK_KEY

    class FakeRotator:
        keys = ["fake-key"]

        async def async_get_key(self, model_id, estimated_tokens=0):
            return "fake-key"

        def penalize(self, *_args, **_kwargs):
            pass

    async def fake_stream(*_args, on_delta=None, **_kwargs):
        await on_delta("stream chunk one ")
        await on_delta("stream chunk two ")
        return SimpleNamespace(text=("stream chunk one stream chunk two " * 8))

    async def fail_full_call(*_args, **_kwargs):
        raise AssertionError("streaming path should be used when a runtime callback is present")

    emitted = []

    async def callback(event):
        emitted.append(event)

    monkeypatch.setattr(llm_calls, "_generate_content_stream_async", fake_stream, raising=False)
    monkeypatch.setattr(llm_calls, "_generate_content_async", fail_full_call)
    monkeypatch.setattr(llm_calls, "_response_text", lambda response: response.text)

    context = {
        "agent_positions": {1: 1},
        "agent_total": 1,
        "pipeline_id": "v1",
        "pipeline_label": "test",
        "structured_outputs": {},
        RUNTIME_EVENT_CALLBACK_KEY: callback,
    }

    result = asyncio.run(
        llm_calls._run_agent_once_async(
            1,
            context,
            FakeRotator(),
            "gemini-test",
            "prompt",
            timeout_seconds=1.0,
        )
    )

    stream_events = [event for event in emitted if event.get("type") == "llm_stream_delta"]
    assert [event["delta"] for event in stream_events] == ["stream chunk one ", "stream chunk two "]
    assert "stream chunk one stream chunk two" in result
    assert context["_runtime_events"][-1]["phase"] == "llm_model_response"


def test_llm_call_event_helpers_capture_metadata_usage_and_stream_gate():
    from agent_runtime.llm_call_events import (
        _key_slot_fields,
        _model_event_fields,
        _record_llm_token_usage,
        _should_stream_llm_response,
    )
    from runtime_events import RUNTIME_EVENT_CALLBACK_KEY

    class FakeRotator:
        keys = ["first-key", "second-key"]

    context = {
        "agent_positions": {3: 2},
        "agent_total": 5,
        "pipeline_id": "v1",
        "pipeline_label": "test",
    }

    fields = _model_event_fields(context, 3, "gemini-test", "prompt", timeout_seconds=1.5)
    assert fields["current"] == 2
    assert fields["total"] == 5
    assert fields["metadata"]["model_id"] == "gemini-test"
    assert fields["metadata"]["timeout_seconds"] == 1.5
    assert fields["metadata"]["estimated_tokens"] > 0
    assert _key_slot_fields(FakeRotator(), "second-key") == {"key_count": 2, "key_slot": 2}
    assert _key_slot_fields(FakeRotator(), "missing-key") == {"key_count": 2}

    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=11,
            candidates_token_count=7,
            total_token_count=18,
        )
    )
    _record_llm_token_usage(context, 3, response)
    assert context["llm_token_usage"][3] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }
    assert _should_stream_llm_response(context) is False

    context[RUNTIME_EVENT_CALLBACK_KEY] = object()
    assert _should_stream_llm_response(context) is True


def test_llm_sync_call_records_timeout_metadata_without_name_error(monkeypatch):
    import agent_runtime.llm_calls as llm_calls

    class FakeRotator:
        keys = ["fake-key", "backup-key"]

        def get_key(self, model_id, estimated_tokens=0):
            return "fake-key"

        def penalize(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(llm_calls, "_generate_content", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(llm_calls, "_response_text", lambda _response: "sync result " * 20)

    context = {
        "agent_positions": {7: 1},
        "agent_total": 1,
        "pipeline_id": "v1",
        "pipeline_label": "test",
        "structured_outputs": {},
    }
    result = llm_calls._run_agent_once(
        7,
        context,
        FakeRotator(),
        "fake-model",
        "prompt",
        timeout_seconds=1.0,
    )

    assert "sync result" in result
    assert context["_runtime_events"][0]["metadata"]["timeout_seconds"] == 1.0
    assert context["_runtime_events"][-1]["metadata"]["key_slot"] == 1
    assert context["_runtime_events"][-1]["metadata"]["key_count"] == 2
    assert context["_runtime_events"][-1]["metadata"]["output_chars"] == len(result)


def test_genai_client_receives_request_timeout(monkeypatch):
    import llm_client

    captured = {}

    class FakeModels:
        def generate_content(self, **_kwargs):
            return object()

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.models = FakeModels()

        def close(self):
            pass

    monkeypatch.setattr(llm_client, "LLM_AGENT_CALL_TIMEOUT_SECONDS", 12.5)
    monkeypatch.setattr(llm_client.genai, "Client", FakeClient)

    llm_client.generate_content("fake-key", "fake-model", "prompt", object())

    assert captured["http_options"].timeout == 12500


def test_report_renderer_returns_bundle_with_snapshot(monkeypatch):
    import reporting.renderer as renderer_module

    async def fake_html(context):
        return "<html>ok</html>"

    monkeypatch.setattr(renderer_module, "generate_html_report_async", fake_html)
    monkeypatch.setattr(renderer_module, "generate_markdown_report", lambda context: "# ok")

    context = {
        "ticker": "AAPL",
        "company_name": "Apple",
        "pipeline_id": "v1",
        "data": {
            "ticker": "AAPL",
            "company_name": "Apple",
            "data_schema_version": 4,
            "source_audit": [],
            "data_trust": {"status": "unknown", "critical_failures": [], "stale_sources": [], "notes": []},
        },
    }
    bundle = asyncio.run(ReportRenderer().render_async(ReportRequest(context=context, pipeline_id="v1", filename="a.html")))

    assert bundle.html == "<html>ok</html>"
    assert bundle.markdown == "# ok"
    assert bundle.data_snapshot["ticker"] == "AAPL"
    assert bundle.metadata["filename"] == "a.html"
