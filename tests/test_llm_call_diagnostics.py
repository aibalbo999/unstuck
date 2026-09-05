import asyncio
import json
from types import SimpleNamespace as NS

import pytest

import agent_runtime.llm_calls as calls
import llm_transport


class FakeRotator:
    keys = ["test-credential"]

    def get_key(self, *args):
        return self.keys[0]

    async def async_get_key(self, *args):
        return self.get_key(*args)

    def penalize(self, *args):
        pass


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected external provider access")

    monkeypatch.setattr(llm_transport, "_get_client", forbidden)
    monkeypatch.setattr(calls, "_generate_content", forbidden)
    monkeypatch.setattr(calls, "_generate_content_async", forbidden)
    monkeypatch.setattr(calls, "_generate_content_stream_async", forbidden)


def run(context, *, asynchronous, timeout=1):
    args = (1, context, FakeRotator(), "google:test", "private-prompt")
    if asynchronous:
        return asyncio.run(calls._run_agent_once_async(*args, timeout_seconds=timeout))
    return calls._run_agent_once(*args, timeout_seconds=timeout)


def install_response(monkeypatch, text):
    response = NS(text=text, usage_metadata=NS(prompt_token_count=8, candidates_token_count=2, total_token_count=10))
    monkeypatch.setattr(calls, "_generate_content", lambda *args: response)

    async def generate(*args):
        return response

    monkeypatch.setattr(calls, "_generate_content_async", generate)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("text, kind", [("", "empty"), (" \n\t", "empty"), ("a" * 100, "short")])
def test_empty_and_short_responses_emit_errors_without_changing_retry_type(monkeypatch, asynchronous, text, kind):
    install_response(monkeypatch, text)
    context = {}
    for _ in range(15):
        with pytest.raises(calls.AgentShortResponseError) as caught:
            run(context, asynchronous=asynchronous)
        assert type(caught.value) is calls.AgentShortResponseError
    errors = [event for event in context["_runtime_events"] if event["phase"] == "llm_model_error"]
    assert len(errors) == 15
    assert not any(event["phase"] == "llm_model_response" for event in context["_runtime_events"])
    metadata = errors[-1]["metadata"]
    assert metadata["response_kind"] == kind
    assert metadata["output_chars"] == len(text)
    assert metadata["error_kind"] == "AgentShortResponseError"
    assert metadata["response_diagnostics"]["usage"]["total_tokens"] == 10
    assert metadata["key_slot"] == 1
    assert context["llm_token_usage"][1]["total_tokens"] == 10
    assert "test-credential" not in json.dumps(errors)
    assert "private-prompt" not in json.dumps(errors)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_success_response_event_keeps_usage_and_diagnostics(monkeypatch, asynchronous):
    install_response(monkeypatch, "x" * 101)
    context = {}
    assert run(context, asynchronous=asynchronous) == "x" * 101
    metadata = context["_runtime_events"][-1]["metadata"]
    assert metadata["response_diagnostics"]["usage"]["total_tokens"] == 10
    assert metadata["response_kind"] == "text"


def install_transport(monkeypatch, stream):
    monkeypatch.setattr(llm_transport, "_get_client", lambda _: NS(aio=NS(models=NS(generate_content_stream=stream))))

    async def generate(api_key, model_id, agent_num, prompt, *, on_delta):
        return await llm_transport.generate_content_stream_async(api_key, model_id, prompt, None, on_delta=on_delta)

    monkeypatch.setattr(calls, "_generate_content_stream_async", generate)


@pytest.mark.parametrize("failure", ["provider_timeout", "deadline", "cancel"])
def test_partial_stream_error_events_preserve_observations_and_cancellation(monkeypatch, failure):
    async def stream(**kwargs):
        yield NS(text="partial", usage_metadata=NS(total_token_count=17))
        if failure == "deadline":
            await asyncio.sleep(10)
        if failure == "cancel":
            raise asyncio.CancelledError()
        raise TimeoutError("provider timeout")

    install_transport(monkeypatch, stream)
    emitted = []
    context = {"_runtime_event_callback": emitted.append}
    error_type = asyncio.CancelledError if failure == "cancel" else calls.AgentTransientError
    with pytest.raises(error_type):
        run(context, asynchronous=True, timeout=0.01 if failure == "deadline" else 1)
    errors = [event for event in emitted if event["phase"] == "llm_model_error"]
    assert len(errors) == 1
    metadata = errors[0]["metadata"]
    diagnostics = metadata["response_diagnostics"]
    assert diagnostics["stream_completed"] is False
    assert diagnostics["output_chars"] == 7
    assert diagnostics["usage"]["total_tokens"] == 17
    assert context["llm_token_usage"][1]["total_tokens"] == 17
    if failure == "cancel":
        assert metadata["error_category"] == "cancelled"
    assert not any(event["phase"] == "llm_model_response" for event in emitted)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("message, expected", [
    ("503 unavailable", "AgentServerError"),
    ("400 INVALID_ARGUMENT", "AgentConfigurationError"),
    ("404 model not found", "AgentMissingModelError"),
    ("429 resource_exhausted", "AgentRateLimitError"),
    ("401 unauthorized", "AgentAuthError"),
])
def test_provider_error_classification_is_unchanged_and_event_omits_payload(monkeypatch, asynchronous, message, expected):
    def fail(*args):
        raise RuntimeError(message + " test-credential private-reasoning private-args")

    async def fail_async(*args):
        return fail(*args)

    monkeypatch.setattr(calls, "_generate_content", fail)
    monkeypatch.setattr(calls, "_generate_content_async", fail_async)
    context = {}
    with pytest.raises(Exception) as caught:
        run(context, asynchronous=asynchronous)
    assert caught.value.__class__.__name__ == expected
    errors = [event for event in context["_runtime_events"] if event["phase"] == "llm_model_error"]
    assert len(errors) == 1
    serialized = json.dumps(errors)
    for secret in ("test-credential", "private-reasoning", "private-args"):
        assert secret not in serialized


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("case", ["function_call", "blocked", "empty_candidates", "unknown"])
def test_empty_response_observations_reach_runtime_events(monkeypatch, streaming, case):
    response = NS(candidates=None)
    if case == "function_call":
        part = NS(function_call=NS(name="lookup_metric", args={"secret": "private-args"}))
        response.candidates = [NS(content=NS(parts=[part]), finish_reason="STOP")]
    elif case == "blocked":
        response.prompt_feedback = NS(block_reason="SAFETY")
        response.candidates = []
    elif case == "empty_candidates":
        response.candidates = []

    async def stream(**kwargs):
        yield response

    async def full(*args):
        return response

    install_transport(monkeypatch, stream)
    monkeypatch.setattr(calls, "_generate_content_async", full)
    context = {"_runtime_event_callback": lambda event: None} if streaming else {}
    with pytest.raises(calls.AgentShortResponseError):
        run(context, asynchronous=True)
    metadata = context["_runtime_events"][-1]["metadata"]
    assert metadata["response_kind"] == "empty"
    diagnostics = metadata["response_diagnostics"]
    assert diagnostics["function_call_count"] == int(case == "function_call")
    assert diagnostics["block_reason"] == ("SAFETY" if case == "blocked" else None)
    assert diagnostics["candidate_count"] == (None if case == "unknown" else 1 if case == "function_call" else 0)
    assert diagnostics["afc_history_present"] is False
    assert "private-args" not in json.dumps(metadata)


def test_external_task_cancellation_propagates_and_records_partial_stream(monkeypatch):
    async def scenario():
        ready = asyncio.Event()

        async def stream(**kwargs):
            yield NS(text="partial")
            ready.set()
            await asyncio.Event().wait()

        install_transport(monkeypatch, stream)
        context = {"_runtime_event_callback": lambda event: None}
        task = asyncio.create_task(calls._run_agent_once_async(
            1, context, FakeRotator(), "google:test", "prompt", timeout_seconds=1,
        ))
        await ready.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()
        metadata = context["_runtime_events"][-1]["metadata"]
        assert metadata["error_category"] == "cancelled"
        assert metadata["response_diagnostics"]["output_chars"] == 7

    asyncio.run(scenario())
