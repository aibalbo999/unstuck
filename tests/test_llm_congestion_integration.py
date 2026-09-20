"""Offline behavior checks for congestion admission and real-provider boundaries."""

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

import llm_transport as transport
from agent_runtime import gemma_evidence_runtime as gemma
from agent_runtime import llm_calls as calls


class ScopeRejected(RuntimeError):
    pass


class ScopeSpy:
    def __init__(self, reject=False):
        self.events = []
        self.reject = reject
        self.depth = 0

    @contextmanager
    def scope(self, model, key, *, record_outcome=True):
        if not self.depth:
            self.events.append("admit")
            if self.reject:
                raise ScopeRejected("local congestion")
        self.depth += 1
        try:
            yield
        except BaseException:
            if record_outcome:
                self.events.append("failure")
            raise
        else:
            if record_outcome:
                self.events.append("success")
        finally:
            self.depth -= 1
            if not self.depth:
                self.events.append("close")


def _response(text="provider text"):
    return SimpleNamespace(text=text, usage_metadata=None)


def _transport(monkeypatch, spy, sync=None, async_call=None, stream=None):
    monkeypatch.setattr(transport, "provider_attempt_scope", spy.scope, raising=False)
    monkeypatch.setattr(transport, "get_cached_llm_response", lambda *_: None)
    monkeypatch.setattr(transport, "store_llm_response", lambda *a, **k: None)
    monkeypatch.setattr(transport, "sanitize_google_generation_config", lambda value: value)
    monkeypatch.setattr(transport, "sanitize_google_prompt", lambda value: value)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=sync),
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=async_call,
                                                  generate_content_stream=stream)))
    monkeypatch.setattr(transport, "generation_client", lambda *a: client)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_transport_raw_success_records_one_admission_and_outcome(monkeypatch, asynchronous):
    spy = ScopeSpy()
    async def generate(**kwargs):
        return _response()
    _transport(monkeypatch, spy, sync=lambda **kw: _response(), async_call=generate)
    result = asyncio.run(transport.generate_content_async("key", "gemma-test", "prompt", None)) if asynchronous else transport.generate_content("key", "gemma-test", "prompt", None)
    assert result.text == "provider text"
    assert spy.events == ["admit", "success", "close"]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_transport_cache_hit_never_admits_or_marks_probe_success(monkeypatch, asynchronous):
    spy = ScopeSpy()
    _transport(monkeypatch, spy)
    monkeypatch.setattr(transport, "get_cached_llm_response", lambda *a: {"text": "cached", "usage": {}})
    result = asyncio.run(transport.generate_content_async("key", "gemma-test", "prompt", None)) if asynchronous else transport.generate_content("key", "gemma-test", "prompt", None)
    assert result.text == "cached"
    assert spy.events == []


def test_non_google_transport_does_not_enter_google_congestion_scope(monkeypatch):
    spy = ScopeSpy()
    _transport(monkeypatch, spy)
    monkeypatch.setattr(transport, "generate_openai_content", lambda *a: _response())
    transport.generate_content("key", "openai:gpt-test", "prompt", None)
    assert spy.events == []


@pytest.mark.parametrize("cancel", [False, True])
def test_transport_failure_preserves_exception_and_releases_scope(monkeypatch, cancel):
    spy = ScopeSpy()
    error = asyncio.CancelledError() if cancel else RuntimeError("429 provider")
    async def generate(**kwargs):
        raise error
    _transport(monkeypatch, spy, async_call=generate)
    with pytest.raises(type(error)) as caught:
        asyncio.run(transport.generate_content_async("key", "gemma-test", "prompt", None))
    assert caught.value is error
    assert spy.events == ["admit", "failure", "close"]


@pytest.mark.parametrize("ending", ["complete", "error", "cancel"])
def test_stream_records_success_only_after_complete_consumption(monkeypatch, ending):
    spy = ScopeSpy()
    error = asyncio.CancelledError() if ending == "cancel" else RuntimeError("429 interrupted stream")
    async def stream(**kwargs):
        yield _response("part")
        assert "success" not in spy.events
        if ending != "complete":
            raise error
    _transport(monkeypatch, spy, stream=stream)
    call = transport.generate_content_stream_async("key", "gemma-test", "prompt", None)
    if ending == "complete":
        assert asyncio.run(call).text == "part"
    else:
        with pytest.raises(type(error)) as caught:
            asyncio.run(call)
        assert caught.value is error
    assert spy.events == ["admit", "success" if ending == "complete" else "failure", "close"]


class ToolScope:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False


def _raise(exc, *args, **kwargs):
    raise exc


def _agent(monkeypatch, spy, events):
    monkeypatch.setattr(calls, "provider_attempt_scope", spy.scope, raising=False)
    monkeypatch.setattr(calls, "acquire_key", lambda *a, **k: "key")
    async def acquire(*a, **k): return "key"
    monkeypatch.setattr(calls, "acquire_key_async", acquire)
    monkeypatch.setattr(calls, "agent_request_budget_options", lambda *a: {})
    monkeypatch.setattr(calls, "estimate_agent_input_tokens", lambda *a: 1)
    monkeypatch.setattr(calls, "tool_request_scope", lambda *a, **k: ToolScope())
    monkeypatch.setattr(calls, "_record_llm_token_usage", lambda *a: None)
    monkeypatch.setattr(calls, "process_agent_response", lambda a, text, c, **kwargs: text)
    monkeypatch.setattr(calls, "_validate_agent_result", lambda *a: None)
    monkeypatch.setattr(calls, "_should_stream_llm_response", lambda *a: False)
    monkeypatch.setattr(calls, "_generate_content", lambda key, model, agent, prompt: transport.generate_content(key, model, prompt, None))
    async def generate(key, model, agent, prompt):
        return await transport.generate_content_async(key, model, prompt, None)
    monkeypatch.setattr(calls, "_generate_content_async", generate)
    for name, value in (("llm_model_call_event", "call"), ("llm_provider_request_event", "request"), ("llm_model_response_event", "response")):
        monkeypatch.setattr(calls, name, lambda *a, _value=value, **k: _value)
    monkeypatch.setattr(calls, "emit_context_event", lambda context, event, **k: events.append(event))
    async def emit(context, event, **kwargs): events.append(event)
    monkeypatch.setattr(calls, "emit_context_event_async", emit)
    monkeypatch.setattr(calls, "emit_context_error", lambda *a, **k: None)
    async def error(*a, **kwargs): pass
    monkeypatch.setattr(calls, "emit_context_error_async", error)
    monkeypatch.setattr(calls, "llm_model_error_fields", lambda *a, **k: {})
    monkeypatch.setattr(calls, "_agent_error_category", lambda exc: "local_guard")
    monkeypatch.setattr(calls, "_raise_agent_call_error", _raise)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("reject", [False, True])
def test_agent_admits_before_request_event_and_nested_transport_counts_once(monkeypatch, asynchronous, reject):
    spy, events = ScopeSpy(reject), []
    def generate(**kwargs):
        assert events == ["call", "request"]
        return _response()
    async def generate_async(**kwargs): return generate(**kwargs)
    _transport(monkeypatch, spy, sync=generate, async_call=generate_async)
    _agent(monkeypatch, spy, events)
    def run():
        if asynchronous:
            return asyncio.run(calls._run_agent_once_async(22, {}, object(), "gemma-test", "prompt"))
        return calls._run_agent_once(22, {}, object(), "gemma-test", "prompt")
    if reject:
        with pytest.raises(ScopeRejected): run()
        assert events == ["call"]
        assert spy.events == ["admit"]
    else:
        assert run() == "provider text"
        assert spy.events == ["admit", "success", "close"]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("reject", [False, True])
def test_gemma_admits_before_request_event_and_nested_transport_counts_once(monkeypatch, asynchronous, reject):
    spy, events = ScopeSpy(reject), []
    async def generate(**kwargs): return _response()
    _transport(monkeypatch, spy, sync=lambda **kw: _response(), async_call=generate)
    monkeypatch.setattr(gemma, "provider_attempt_scope", spy.scope, raising=False)
    monkeypatch.setattr(gemma, "acquire_key", lambda *a, **k: "key")
    async def acquire(*a, **k): return "key"
    monkeypatch.setattr(gemma, "acquire_key_async", acquire)
    monkeypatch.setattr(gemma, "event", lambda context, batch, phase, *a, **k: events.append(phase))
    monkeypatch.setattr(gemma, "batch_input_tokens", lambda batch: 1)
    monkeypatch.setattr(gemma, "batch_prompt", lambda batch: "prompt")
    monkeypatch.setattr(gemma, "config", lambda: None)
    monkeypatch.setattr(gemma, "generate_content", transport.generate_content)
    monkeypatch.setattr(gemma, "generate_content_async", transport.generate_content_async)
    monkeypatch.setattr(gemma, "finish_response", lambda *a: "valid")
    monkeypatch.setattr(gemma, "provider_error", lambda batch, context, rotator, key, exc: _raise(exc))
    def run():
        return asyncio.run(gemma.call_batch_async({}, {}, object())) if asynchronous else gemma.call_batch({}, {}, object())
    if reject:
        with pytest.raises(ScopeRejected): run()
        assert events == ["gemma_evidence_call"]
        assert spy.events == ["admit"]
    else:
        assert run() == "valid"
        assert events == ["gemma_evidence_call", "gemma_evidence_request"]
        assert spy.events == ["admit", "success", "close"]


def test_agent_cached_response_does_not_close_circuit_as_provider_success(monkeypatch):
    spy, events = ScopeSpy(), []
    _transport(monkeypatch, spy)
    _agent(monkeypatch, spy, events)
    monkeypatch.setattr(transport, "get_cached_llm_response", lambda *a: {"text": "cached", "usage": {}})
    assert calls._run_agent_once(22, {}, object(), "gemma-test", "prompt") == "cached"
    assert spy.events == ["admit", "close"]


def test_stream_unavailable_uses_one_normal_transport_scope(monkeypatch):
    spy = ScopeSpy()
    async def generate(**kwargs): return _response()
    _transport(monkeypatch, spy, async_call=generate)
    result = asyncio.run(transport.generate_content_stream_async("key", "gemma-test", "prompt", None))
    assert result.text == "provider text"
    assert spy.events == ["admit", "success", "close"]


def test_cache_storage_error_does_not_reclassify_raw_provider_success(monkeypatch):
    spy = ScopeSpy()
    _transport(monkeypatch, spy, sync=lambda **kw: _response())
    monkeypatch.setattr(transport, "store_llm_response", lambda *a, **k: _raise(RuntimeError("cache failed")))
    with pytest.raises(RuntimeError, match="cache failed"):
        transport.generate_content("key", "gemma-test", "prompt", None)
    assert spy.events == ["admit", "success", "close"]


def test_agent_cancel_preserves_cancellation_and_closes_nested_scope(monkeypatch):
    spy, events = ScopeSpy(), []
    error = asyncio.CancelledError()
    async def generate(**kwargs): raise error
    _transport(monkeypatch, spy, async_call=generate)
    _agent(monkeypatch, spy, events)
    with pytest.raises(asyncio.CancelledError) as caught:
        asyncio.run(calls._run_agent_once_async(22, {}, object(), "gemma-test", "prompt"))
    assert caught.value is error
    assert spy.events == ["admit", "failure", "close"]


def test_real_facade_trips_after_distinct_key_429s_before_third_provider_send(monkeypatch):
    import config
    import llm_congestion
    from llm_congestion_store import CongestionStore
    from llm_model_circuits import ModelCircuitOpenError

    clock = [1000.0]
    monkeypatch.setattr(config, "LLM_CONGESTION_GUARD_ENABLED", True)
    monkeypatch.setattr(llm_congestion, "_store", CongestionStore(
        redis_client=None, clock=lambda: clock[0], jitter=lambda: 0))
    sends = []
    class Provider429(RuntimeError):
        status_code = 429
    error = Provider429("429 RESOURCE_EXHAUSTED: provider rate limit")
    def generate(**kwargs):
        sends.append(kwargs["model"])
        raise error
    _transport(monkeypatch, ScopeSpy(), sync=generate)
    monkeypatch.setattr(transport, "provider_attempt_scope", llm_congestion.provider_attempt_scope)
    for key in ("synthetic-slot-a", "synthetic-slot-b"):
        with pytest.raises(Provider429) as caught:
            transport.generate_content(key, "gemma-4-26b-a4b-it", "prompt", None)
        assert caught.value is error
        clock[0] += 1
    with pytest.raises(ModelCircuitOpenError):
        transport.generate_content("synthetic-slot-c", "gemma-4-26b-a4b-it", "prompt", None)
    assert sends == ["gemma-4-26b-a4b-it"] * 2


@pytest.mark.parametrize("timeout", [120, 0, -1])
def test_cached_google_client_disables_sdk_hidden_retries_for_all_call_styles(monkeypatch, timeout):
    """One adapter attempt must be one SDK attempt, even without a tool scope."""
    spy = ScopeSpy()
    monkeypatch.setattr(transport, "provider_attempt_scope", spy.scope)
    monkeypatch.setattr(transport, "LLM_AGENT_CALL_TIMEOUT_SECONDS", timeout)
    monkeypatch.setattr(transport, "_client_cache", {})
    monkeypatch.setattr(transport, "get_cached_llm_response", lambda *args: None)
    monkeypatch.setattr(transport, "store_llm_response", lambda *args, **kwargs: None)
    constructed, sends = [], []
    def sync_generate(**kwargs):
        sends.append("sync")
        return _response()
    async def async_generate(**kwargs):
        sends.append("async")
        return _response()
    async def stream_generate(**kwargs):
        sends.append("stream")
        yield _response()
    def factory(*, api_key, http_options):
        constructed.append(http_options)
        return SimpleNamespace(models=SimpleNamespace(generate_content=sync_generate),
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=async_generate,
                                                      generate_content_stream=stream_generate)))
    monkeypatch.setattr(transport.genai, "Client", factory)
    transport.generate_content("synthetic-no-tools", "gemma-test", "prompt", None)
    asyncio.run(transport.generate_content_async("synthetic-no-tools", "gemma-test", "prompt", None))
    asyncio.run(transport.generate_content_stream_async("synthetic-no-tools", "gemma-test", "prompt", None))
    assert sends == ["sync", "async", "stream"]
    assert len(constructed) == 1
    options = constructed[0]
    assert options is not None
    assert options.retry_options is not None
    assert options.retry_options.attempts == 1
    assert options.timeout == (timeout * 1000 if timeout > 0 else None)
