"""Offline AFC admission tests through real httpx request hooks."""

import asyncio
import importlib
import json
from contextlib import nullcontext
from types import SimpleNamespace as NS

import httpx
import pytest
from google import genai
from google.genai import types
from google.genai.errors import ServerError

import llm_rate_limit_buckets
import llm_rate_limits
import llm_transport
from agent_runtime import llm_calls
from llm_input_capacity import InputCapacityExceededError, estimate_input_tokens


MODEL = "google:gemini-tool-test"
KEY = "fake-tool-credential"
TEXT = "A complete evidence-backed analysis. " * 10
REAL_SDK_CLIENT = genai.Client


def body(result=""):
    return {
        "contents": [{"role": "user", "parts": [{"text": "prompt"}, {
            "functionResponse": {"name": "lookup", "response": {"result": result}},
        }]}],
        "systemInstruction": {"parts": [{"text": "system instructions"}]},
        "tools": [{"functionDeclarations": [{"name": "lookup", "description": "evidence"}]}],
        "generationConfig": {"responseSchema": {"type": "OBJECT"}, "maxOutputTokens": 999999},
    }


def estimate(payload):
    inputs = {key: payload[key] for key in ("contents", "systemInstruction", "tools")}
    inputs["generationConfig"] = {"responseSchema": payload["generationConfig"]["responseSchema"]}
    return estimate_input_tokens(json.dumps(inputs, ensure_ascii=False))


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, delay):
        assert delay > 0
        self.sleeps.append(delay)
        self.now += delay + 0.000001

    async def asleep(self, delay):
        self.sleep(delay)


class FakeSDK:
    """Only simulates SDK tool rounds; HTTP hooks are dispatched by httpx."""

    def __init__(self, payloads, clock):
        self.payloads = payloads
        self.clock = clock
        self.sent = []
        self.clients = []
        self.stream_closed = 0

    def client(self, *, api_key, http_options=None):
        options = http_options
        sync_args = dict(getattr(options, "client_args", None) or {})
        async_args = dict(getattr(options, "async_client_args", None) or {})
        configured_async_transport = async_args.get("transport")

        def handle(request):
            self.sent.append((api_key, request.url.path, self.clock.now, json.loads(request.content)))
            return httpx.Response(200, json={"ok": True})

        sync_args["transport"] = httpx.MockTransport(handle)
        async_args["transport"] = httpx.MockTransport(handle)
        sync = httpx.Client(**sync_args)
        asynchronous = httpx.AsyncClient(**async_args)

        def url(model, stream=False):
            action = "streamGenerateContent" if stream else "generateContent"
            return f"https://sdk.invalid/v1beta/models/{model}:{action}"

        def generate_content(*, model, **kwargs):
            for payload in self.payloads:
                sync.post(url(model), json=payload)
            return NS(text=TEXT)

        async def generate_content_async(*, model, **kwargs):
            for payload in self.payloads:
                await asynchronous.post(url(model), json=payload)
            return NS(text=TEXT)

        async def generate_content_stream(*, model, **kwargs):
            try:
                for payload in self.payloads:
                    async with asynchronous.stream("POST", url(model, True), json=payload):
                        yield NS(text=TEXT)
            finally:
                self.stream_closed += 1

        async def aclose():
            await asynchronous.aclose()
            if configured_async_transport is not None:
                await configured_async_transport.aclose()

        client = NS(
            models=NS(generate_content=generate_content),
            aio=NS(models=NS(generate_content=generate_content_async,
                             generate_content_stream=generate_content_stream), aclose=aclose),
            close=sync.close, sync=sync, asynchronous=asynchronous, options=options,
        )
        self.clients.append(client)
        return client


@pytest.fixture
def rig(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(llm_rate_limit_buckets, "time", NS(monotonic=lambda: clock.now))
    monkeypatch.setattr(llm_rate_limits, "time", NS(sleep=clock.sleep))
    monkeypatch.setattr(llm_rate_limits, "create_shared_llm_limiter", lambda: None)
    monkeypatch.setattr(llm_rate_limits, "RPM_LIMITS", {MODEL: 1})
    monkeypatch.setattr(llm_rate_limits, "TPM_LIMITS", {MODEL: 100000})
    monkeypatch.setattr(llm_rate_limits, "MODEL_INPUT_TOKEN_LIMITS", {})
    monkeypatch.setattr(llm_rate_limits, "emit_log", lambda *args: None)
    try:
        guard = importlib.import_module("llm_tool_rate_guard")
    except ModuleNotFoundError:
        guard = None
    if guard is not None:
        monkeypatch.setattr(guard, "time", NS(sleep=clock.sleep))
        monkeypatch.setattr(guard, "_sleep_async", clock.asleep)
    rotator = llm_rate_limits.KeyRotator([KEY])
    daily = []
    monkeypatch.setattr(rotator, "_daily_remaining", lambda model: {})
    monkeypatch.setattr(rotator, "_reserve_daily_budget", lambda key, model, request_units=1: daily.append(request_units) or True)
    monkeypatch.setattr(llm_transport, "_client_cache", {})
    monkeypatch.setattr(llm_transport, "get_cached_llm_response", lambda *args: None)
    monkeypatch.setattr(llm_transport, "store_llm_response", lambda *args, **kwargs: None)
    monkeypatch.setattr(llm_calls, "estimate_agent_input_tokens", lambda *args: 10)
    monkeypatch.setattr(llm_calls, "process_agent_response", lambda agent, text, context: text)
    sdk = FakeSDK([body(), body("tool result " * 100), body("tool result " * 200)], clock)
    monkeypatch.setattr(llm_transport.genai, "Client", sdk.client)
    yield NS(clock=clock, rotator=rotator, daily=daily, sdk=sdk, guard=guard)
    for client in sdk.clients:
        client.close()
        asyncio.run(client.aio.aclose())


def run(rig, mode, *, agent=2, model=MODEL, context=None):
    context = {} if context is None else context
    if mode == "stream":
        context["_runtime_event_callback"] = lambda event: None
    args = (agent, context, rig.rotator, model, "prompt")
    if mode == "sync":
        return llm_calls._run_agent_once(*args)
    return asyncio.run(llm_calls._run_agent_once_async(*args, timeout_seconds=0))


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_low_rpm_tool_rounds_wait_per_actual_http_request(rig, mode):
    run(rig, mode)
    assert [sent[2] for sent in rig.sdk.sent] == pytest.approx([0, 60, 120], abs=0.001)
    assert rig.daily == [6]
    assert len(rig.clock.sleeps) == 2
    assert {sent[0] for sent in rig.sdk.sent} == {KEY}
    assert rig.sdk.clients[0].sync.is_closed
    assert rig.sdk.clients[0].asynchronous.is_closed
    assert not llm_transport._client_cache


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_agent_entry_routes_local_tool_guard_errors_through_configuration_policy(rig, mode):
    from agent_runtime.retry_policy import AgentConfigurationError
    rig.sdk.payloads = [body()] * 7
    with pytest.raises(AgentConfigurationError, match="Tool request budget exhausted"):
        run(rig, mode)
    assert len(rig.sdk.sent) == 6
    assert rig.daily == [6]
    assert rig.guard.current_tool_scope(KEY) is None


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_followup_tpm_accounts_for_tool_results_and_input_config(rig, monkeypatch, mode):
    monkeypatch.setattr(llm_rate_limits, "RPM_LIMITS", {MODEL: 100})
    reservations = []
    reserve = rig.rotator._reserve_for_key

    def record(key, model, tokens=0):
        reservations.append(tokens)
        return reserve(key, model, tokens)

    monkeypatch.setattr(rig.rotator, "_reserve_for_key", record)
    run(rig, mode)
    assert reservations == [10, *(estimate(payload) for payload in rig.sdk.payloads[1:])]
    assert reservations[2] > reservations[1] > reservations[0]
    assert not rig.clock.sleeps


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_followup_that_exceeds_tpm_fails_before_send_or_wait(rig, monkeypatch, mode):
    monkeypatch.setattr(llm_rate_limits, "TPM_LIMITS", {MODEL: 500})
    with pytest.raises(InputCapacityExceededError):
        run(rig, mode)
    assert len(rig.sdk.sent) == 1
    assert not rig.clock.sleeps
    assert rig.daily == [6]
    assert all(client.sync.is_closed and client.asynchronous.is_closed for client in rig.sdk.clients)


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_sdk_seventh_request_is_blocked_and_internal_retry_is_disabled(rig, mode):
    from agent_runtime.retry_policy import AgentConfigurationError

    rig.sdk.payloads = [body()] * 7
    with pytest.raises(AgentConfigurationError, match="request budget") as error:
        run(rig, mode)
    assert isinstance(error.value.__cause__, rig.guard.ToolRequestGuardError)
    assert len(rig.sdk.sent) == 6
    assert rig.daily == [6]
    assert rig.sdk.clients[0].options.retry_options.attempts == 1


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_first_request_not_double_counted_and_scope_cleared(rig, mode):
    rig.sdk.payloads = [body()]
    run(rig, mode)
    assert rig.daily == [6]
    assert not rig.clock.sleeps
    assert rig.rotator._rpm_buckets[(KEY, MODEL)].tokens == 0
    guarded = rig.sdk.clients[0]
    ordinary = llm_transport._get_client(KEY)
    assert ordinary is not guarded
    assert ordinary is llm_transport._get_client(KEY)
    assert not getattr(ordinary.options, "retry_options", None)


def test_stream_callback_failure_closes_generator_immediately(rig):
    async def scenario():
        def fail(delta):
            raise ValueError("callback failed")

        scope = rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6) if rig.guard else nullcontext()
        rig.rotator.get_key(MODEL, 10, request_units=6)
        async with scope:
            with pytest.raises(ValueError, match="callback failed"):
                await llm_transport.generate_content_stream_async(KEY, MODEL, "prompt", None, on_delta=fail)
            assert rig.sdk.stream_closed == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("streaming", [False, True])
def test_cancellation_while_waiting_closes_clients_and_does_not_send(rig, monkeypatch, streaming):
    async def scenario():
        waiting = asyncio.Event()

        async def wait_forever(delay):
            waiting.set()
            await asyncio.Event().wait()

        if rig.guard:
            monkeypatch.setattr(rig.guard, "_sleep_async", wait_forever)
        context = {"_runtime_event_callback": lambda event: None} if streaming else {}
        task = asyncio.create_task(llm_calls._run_agent_once_async(2, context, rig.rotator, MODEL, "prompt", timeout_seconds=0))
        for _ in range(50):
            await asyncio.sleep(0)
            if waiting.is_set() or task.done():
                break
        assert waiting.is_set(), "AFC follow-up must enter the async limiter"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(rig.sdk.sent) == 1
        assert rig.sdk.clients[0].sync.is_closed
        assert rig.sdk.clients[0].asynchronous.is_closed
        assert rig.daily == [6]
        assert not llm_transport._client_cache
        assert rig.sdk.stream_closed == int(streaming)

    asyncio.run(scenario())


def test_different_model_uses_ordinary_client_without_inheriting_scope(rig):
    rig.sdk.payloads = [body()]
    scope = rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6)
    with scope:
        llm_transport.generate_content(KEY, "google:other-model", "prompt", None)
        assert rig.guard.current_tool_scope(KEY) is scope
        assert llm_transport._client_cache[KEY] is rig.sdk.clients[0]
        assert not getattr(rig.sdk.clients[0].options, "retry_options", None)
    assert not rig.sdk.clients[0].sync.is_closed


def test_nested_non_tool_call_masks_then_restores_outer_scope(rig):
    outer = rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6)
    with outer:
        with rig.guard.tool_request_scope(rig.rotator, KEY, MODEL):
            assert rig.guard.current_tool_scope(KEY) is None
        assert rig.guard.current_tool_scope(KEY) is outer
    assert rig.guard.current_tool_scope(KEY) is None


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_shared_refusal_does_not_double_reserve_local_tokens(rig, monkeypatch, mode):
    monkeypatch.setattr(llm_rate_limits, "RPM_LIMITS", {MODEL: 100})
    reserve = rig.rotator._reserve_for_key
    local = []
    shared = []
    waits = iter([0, 5, 0, 0])

    def reserve_local(key, model, tokens=0):
        local.append(tokens)
        return reserve(key, model, tokens)

    def reserve_shared(key, model, tokens=0):
        shared.append((key, model, tokens))
        return next(waits)

    monkeypatch.setattr(rig.rotator, "_reserve_for_key", reserve_local)
    monkeypatch.setattr(rig.rotator, "_reserve_shared_for_key", reserve_shared)
    run(rig, mode)
    assert local == [10, *map(estimate, rig.sdk.payloads[1:])]
    assert len(shared) == 4
    assert all(item[:2] == (KEY, MODEL) for item in shared)
    assert rig.clock.sleeps == [5]
    assert rig.daily == [6]


def test_parallel_scopes_keep_original_key_model_and_reset_on_error(rig, monkeypatch):
    other_model, other_key = "google:other-model", "fake-other-credential"
    monkeypatch.setattr(llm_rate_limits, "RPM_LIMITS", {"*": 100})
    observed = []
    reserve = rig.rotator._reserve_for_key

    def record(key, model, tokens=0):
        observed.append((key, model))
        return reserve(key, model, tokens)

    monkeypatch.setattr(rig.rotator, "_reserve_for_key", record)

    async def scenario():
        entered = asyncio.Event()
        count = 0

        async def one(key, model):
            nonlocal count
            async with rig.guard.tool_request_scope(rig.rotator, key, model, request_units=6):
                count += 1
                if count == 2:
                    entered.set()
                await entered.wait()
                await llm_transport.generate_content_async(key, model, "prompt", None)
            assert rig.guard.current_tool_scope(key) is None

        await asyncio.gather(one(KEY, MODEL), one(other_key, other_model))
        assert rig.guard.current_tool_scope(KEY) is None

    asyncio.run(scenario())
    assert observed.count((KEY, MODEL)) == 2
    assert observed.count((other_key, other_model)) == 2
    assert len(observed) == 4
    assert len(rig.sdk.clients) == 2
    assert not llm_transport._client_cache


def test_scope_is_not_reused_across_event_loops(rig, monkeypatch):
    monkeypatch.setattr(llm_rate_limits, "RPM_LIMITS", {MODEL: 100})
    rig.sdk.payloads = [body()]
    run(rig, "async")
    run(rig, "async")
    assert len(rig.sdk.clients) == 2
    assert all(client.asynchronous.is_closed for client in rig.sdk.clients)
    assert not llm_transport._client_cache


def test_sync_scope_can_close_inside_running_event_loop(rig):
    async def scenario():
        llm_calls._run_agent_once(2, {}, rig.rotator, MODEL, "prompt")
        assert rig.sdk.clients[0].asynchronous.is_closed
        assert rig.guard.current_tool_scope(KEY) is None

    asyncio.run(scenario())


@pytest.mark.parametrize("agent", [2, 13, 18])
def test_each_tool_agent_uses_call_scoped_hooks(rig, agent):
    run(rig, "sync", agent=agent)
    assert len(rig.clock.sleeps) == 2
    assert rig.daily == [6]


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
@pytest.mark.parametrize("status", [200, 503])
def test_installed_sdk_uses_public_httpx_hooks_with_mock_transport(rig, monkeypatch, mode, status):
    observed = []
    clients = []
    tool_result = "offline evidence " * 200

    def lookup() -> str:
        """Fetch offline evidence."""
        return tool_result

    def handler(request):
        observed.append((rig.clock.now, json.loads(request.content)))
        if status == 503:
            return httpx.Response(503, json={"error": {"code": 503, "message": "offline unavailable", "status": "UNAVAILABLE"}})
        part = {"functionCall": {"name": "lookup", "args": {}}} if len(observed) < 3 else {"text": TEXT}
        response = {"candidates": [{"content": {"role": "model", "parts": [part]}, "finishReason": "STOP"}]}
        if "streamGenerateContent" in request.url.path:
            return httpx.Response(200, content="data: " + json.dumps(response) + "\n\n", headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json=response)

    def factory(*, api_key, http_options):
        assert http_options.retry_options.attempts == 1
        assert isinstance(http_options.async_client_args["transport"], httpx.AsyncHTTPTransport)
        sync_args = dict(http_options.client_args, transport=httpx.MockTransport(handler))
        async_args = dict(http_options.async_client_args, transport=httpx.MockTransport(handler))
        client = REAL_SDK_CLIENT(api_key=api_key, http_options=http_options.model_copy(update={
            "base_url": "https://sdk.invalid", "client_args": sync_args, "async_client_args": async_args,
        }))
        clients.append(client)
        assert not client._api_client._use_aiohttp()
        return client

    monkeypatch.setattr(llm_transport.genai, "Client", factory)
    config = types.GenerateContentConfig(tools=[lookup], system_instruction="system",
                                        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6))
    scope = rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6)
    rig.rotator.get_key(MODEL, 10, request_units=6)
    with pytest.raises(ServerError) if status == 503 else nullcontext():
        if mode == "sync":
            with scope:
                response = llm_transport.generate_content(KEY, MODEL, "prompt", config)
        else:
            async def scenario():
                async with scope:
                    generate = llm_transport.generate_content_stream_async if mode == "stream" else llm_transport.generate_content_async
                    return await generate(KEY, MODEL, "prompt", config)

            response = asyncio.run(scenario())
    if status == 200:
        assert llm_transport.response_text(response) == TEXT
        assert [item[0] for item in observed] == pytest.approx([0, 60, 120], abs=0.001)
        assert tool_result in json.dumps(observed[1][1])
    else:
        assert len(observed) == 1
        assert not rig.clock.sleeps
    assert rig.daily == [6]
    assert clients[0]._api_client._httpx_client.is_closed
    assert clients[0]._api_client._async_httpx_client.is_closed


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_followup_waits_for_tpm_refill_without_truncating_evidence(rig, monkeypatch, mode):
    monkeypatch.setattr(llm_rate_limits, "RPM_LIMITS", {MODEL: 100})
    monkeypatch.setattr(llm_rate_limits, "TPM_LIMITS", {MODEL: 1000})
    run(rig, mode)
    wait = (10 + sum(map(estimate, rig.sdk.payloads[1:])) - 1000) * 60 / 1000
    assert [item[2] for item in rig.sdk.sent] == pytest.approx([0, 0, wait], abs=0.001)
    assert [item[3] for item in rig.sdk.sent] == rig.sdk.payloads
    assert rig.daily == [6]


@pytest.mark.parametrize("mode", ["sync", "async", "stream"])
def test_invalid_followup_json_is_blocked_without_logging_request(rig, monkeypatch, caplog, mode):
    from agent_runtime.retry_policy import AgentConfigurationError

    rig.sdk.payloads[1] = "private tool result"
    context = {}
    with pytest.raises(AgentConfigurationError, match="Cannot estimate") as error:
        run(rig, mode, context=context)
    assert isinstance(error.value.__cause__, rig.guard.ToolRequestGuardError)
    assert len(rig.sdk.sent) == 1
    assert not rig.clock.sleeps
    for private in (KEY, "private tool result", "functionResponse", "systemInstruction"):
        assert private not in caplog.text
        assert private not in json.dumps(context.get("_runtime_events", []))
    assert rig.guard.current_tool_scope(KEY) is None


def test_inherited_scope_cannot_send_after_parent_exits(rig):
    async def scenario():
        go = asyncio.Event()

        async def child():
            await go.wait()
            await llm_transport.generate_content_async(KEY, MODEL, "prompt", None)

        async with rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6):
            task = asyncio.create_task(child())
        go.set()
        with pytest.raises(rig.guard.ToolRequestGuardError, match="scope is closed"):
            await task
        assert rig.guard.current_tool_scope(KEY) is None
        assert not rig.sdk.sent

    asyncio.run(scenario())


def test_repeated_cancellation_during_cleanup_waits_for_resources(rig, monkeypatch):
    async def scenario():
        waiting, closing, finish_close = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def wait_forever(delay):
            waiting.set()
            await asyncio.Event().wait()

        original_factory = rig.sdk.client

        def factory(**kwargs):
            client = original_factory(**kwargs)
            close = client.aio.aclose

            async def aclose():
                closing.set()
                await finish_close.wait()
                await close()

            client.aio.aclose = aclose
            return client

        monkeypatch.setattr(rig.guard, "_sleep_async", wait_forever)
        monkeypatch.setattr(llm_transport.genai, "Client", factory)
        task = asyncio.create_task(llm_calls._run_agent_once_async(2, {}, rig.rotator, MODEL, "prompt", timeout_seconds=0))
        await asyncio.wait_for(waiting.wait(), 1)
        task.cancel()
        await asyncio.wait_for(closing.wait(), 1)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        finish_close.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert rig.sdk.clients[0].sync.is_closed
        assert rig.sdk.clients[0].asynchronous.is_closed
        assert len(rig.sdk.sent) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_sdk_construction_failure_closes_transport_and_resets_scope(rig, monkeypatch, mode):
    closed = []

    async def close():
        closed.append(True)

    monkeypatch.setattr(rig.guard.httpx, "AsyncHTTPTransport", lambda: NS(aclose=close))

    def fail(**kwargs):
        raise ValueError("offline construction failed")

    monkeypatch.setattr(llm_transport.genai, "Client", fail)
    with pytest.raises(llm_calls.AgentTransientError, match="construction failed"):
        run(rig, mode)
    assert closed == [True]
    assert rig.guard.current_tool_scope(KEY) is None
    assert not rig.sdk.sent


def test_local_capacity_limit_stops_tool_result_before_reservation(rig, monkeypatch):
    monkeypatch.setattr(llm_rate_limits, "MODEL_INPUT_TOKEN_LIMITS", {MODEL: 500})
    with pytest.raises(InputCapacityExceededError) as caught:
        run(rig, "async")
    assert caught.value.basis == "local_input_budget"
    assert len(rig.sdk.sent) == 1
    assert not rig.clock.sleeps


def test_semantic_cache_hit_does_not_allocate_a_tool_client(rig, monkeypatch):
    monkeypatch.setattr(llm_transport, "get_cached_llm_response", lambda *args: {"text": TEXT})
    assert run(rig, "sync") == TEXT
    assert not rig.sdk.clients
    assert not rig.sdk.sent
    assert rig.guard.current_tool_scope(KEY) is None


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_cleanup_error_does_not_replace_primary_scope_error(rig, mode):
    rig.sdk.payloads = [body()]
    original = None

    def break_cleanup():
        nonlocal original
        client = rig.sdk.clients[0]
        original = client.close

        def close():
            original()
            raise RuntimeError("cleanup failed")

        client.close = close

    scope = rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6)
    error = rig.guard.ToolRequestGuardError("primary error") if mode == "sync" else asyncio.CancelledError()
    try:
        with pytest.raises(type(error)) as caught:
            if mode == "sync":
                with scope:
                    llm_transport.generate_content(KEY, MODEL, "prompt", None)
                    break_cleanup()
                    raise error
            else:
                async def scenario():
                    async with scope:
                        await llm_transport.generate_content_async(KEY, MODEL, "prompt", None)
                        break_cleanup()
                        raise error

                asyncio.run(scenario())
        assert caught.value is error
        assert rig.sdk.clients[0].asynchronous.is_closed
        assert rig.guard.current_tool_scope(KEY) is None
    finally:
        if original:
            rig.sdk.clients[0].close = original


@pytest.mark.parametrize("streaming", [False, True])
def test_agent_timeout_cancels_limiter_and_closes_scope(rig, monkeypatch, streaming):
    async def wait_forever(delay):
        await asyncio.Event().wait()

    monkeypatch.setattr(rig.guard, "_sleep_async", wait_forever)
    context = {"_runtime_event_callback": lambda event: None} if streaming else {}
    with pytest.raises(llm_calls.AgentTransientError, match="LLM timeout"):
        asyncio.run(llm_calls._run_agent_once_async(2, context, rig.rotator, MODEL, "prompt", timeout_seconds=0.01))
    assert len(rig.sdk.sent) == 1
    assert rig.sdk.clients[0].sync.is_closed
    assert rig.sdk.clients[0].asynchronous.is_closed
    assert rig.sdk.stream_closed == int(streaming)
    assert rig.daily == [6]


@pytest.mark.parametrize("mismatch", ["model", "key"])
def test_bound_http_hooks_reject_mismatched_key_or_model(rig, mismatch):
    rig.sdk.payloads = [body()]
    with rig.guard.tool_request_scope(rig.rotator, KEY, MODEL, request_units=6):
        llm_transport.generate_content(KEY, MODEL, "prompt", None)
        client = rig.sdk.clients[0].sync
        model = "other-model" if mismatch == "model" else "gemini-tool-test"
        headers = {"x-goog-api-key": "fake-other-key"} if mismatch == "key" else {}
        with pytest.raises(rig.guard.ToolRequestGuardError, match="match its scope"):
            client.post(f"https://sdk.invalid/v1beta/models/{model}:generateContent", json=body(), headers=headers)
    assert len(rig.sdk.sent) == 1


def test_stream_cleanup_error_preserves_cancellation(rig):
    async def scenario():
        async def close():
            raise RuntimeError("stream cleanup failed")

        error = asyncio.CancelledError()
        with pytest.raises(asyncio.CancelledError) as caught:
            async with rig.guard.closing_stream(NS(aclose=close)):
                raise error
        assert caught.value is error

    asyncio.run(scenario())
