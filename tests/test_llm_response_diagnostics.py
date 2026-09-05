import asyncio
import json
from types import SimpleNamespace as NS

import pytest
from google.genai import types

import llm_transport


def chunk(text=None, *, reason=None, calls=(), usage=None, candidates=True, block=None):
    parts = ([NS(text=text)] if text is not None else []) + [
        NS(function_call=NS(name=name, args={"private": "argument-secret"})) for name in calls
    ]
    return NS(
        candidates=[NS(content=NS(parts=parts), finish_reason=reason)] if candidates else [],
        usage_metadata=usage,
        prompt_feedback=NS(block_reason=block, block_reason_message="private-feedback"),
    )


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected external provider or cache access")

    monkeypatch.setattr(llm_transport, "_get_client", forbidden)
    monkeypatch.setattr(llm_transport, "generate_content_async", forbidden)


def install_stream(monkeypatch, chunks, *, error=None, mode="async"):
    async def stream(**kwargs):
        for item in chunks:
            yield item
        if error is not None:
            raise error

    async def awaitable_stream(**kwargs):
        return stream(**kwargs)

    call = stream if mode == "async" else awaitable_stream
    if mode == "sync":
        call = lambda **kwargs: iter(chunks)
    client = NS(aio=NS(models=NS(generate_content_stream=call)))
    monkeypatch.setattr(llm_transport, "_get_client", lambda _: client)


def generate(**kwargs):
    return llm_transport.generate_content_stream_async("test-credential", "google:test", "prompt", None, **kwargs)


@pytest.mark.parametrize("mode", ["async", "sync", "awaitable"])
def test_stream_preserves_metadata_across_empty_final_chunks(monkeypatch, mode):
    install_stream(monkeypatch, [
        chunk("hello ", usage=NS(prompt_token_count=10, candidates_token_count=1, total_token_count=11)),
        chunk("world", reason=types.FinishReason.STOP,
              usage=NS(prompt_token_count=10, candidates_token_count=4, total_token_count=14)),
        NS(candidates=None, usage_metadata=None),
    ], mode=mode)
    deltas = []
    result = asyncio.run(generate(on_delta=deltas.append))
    assert result.text == "hello world"
    assert deltas == ["hello ", "world"]
    assert llm_transport.extract_usage(result) == {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}
    assert result.diagnostics["finish_reasons"] == ["STOP"]
    assert result.diagnostics["candidate_count"] == 1
    assert result.diagnostics["stream_chunk_count"] == 3
    assert result.diagnostics["stream_completed"] is True


@pytest.mark.parametrize("item, expected", [
    (chunk(calls=["lookup_metric", "lookup_price"], reason="STOP"),
     {"function_call_count": 2, "function_call_names": ["lookup_metric", "lookup_price"], "candidate_count": 1}),
    (chunk(candidates=False, block="SAFETY"), {"block_reason": "SAFETY", "candidate_count": 0}),
    (chunk(candidates=False), {"candidate_count": 0, "finish_reasons": [], "block_reason": None}),
    (NS(candidates=None), {"candidate_count": None, "function_call_count": 0, "block_reason": None}),
])
def test_nontext_stream_reports_only_observed_metadata(monkeypatch, item, expected):
    install_stream(monkeypatch, [item])
    response = asyncio.run(generate())
    assert response.text == ""
    diagnostics = getattr(response, "diagnostics", None)
    assert diagnostics is not None
    for name, value in expected.items():
        assert diagnostics[name] == value
    serialized = json.dumps(diagnostics)
    for private in ("argument-secret", "private-feedback", "test-credential", "root_cause"):
        assert private not in serialized


def test_stream_diagnostics_are_bounded_and_do_not_retain_sdk_objects(monkeypatch):
    items = [chunk(calls=[f"lookup_{index}_" + "x" * 150], reason="STOP") for index in range(200)]
    install_stream(monkeypatch, items)
    response = asyncio.run(generate())
    diagnostics = getattr(response, "diagnostics", None)
    assert diagnostics is not None
    assert diagnostics["function_call_count"] == 200
    assert len(diagnostics["function_call_names"]) <= 16
    assert all(len(name) <= 64 for name in diagnostics["function_call_names"])
    assert len(json.dumps(diagnostics)) < 4096


def test_thought_text_is_neither_returned_nor_emitted(monkeypatch):
    response = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(parts=[
        types.Part(text="private-reasoning", thought=True),
        types.Part(text="public answer"),
    ]))])
    install_stream(monkeypatch, [response])
    deltas = []
    result = asyncio.run(generate(on_delta=deltas.append))
    assert result.text == "public answer"
    assert deltas == ["public answer"]
    assert "private-reasoning" not in json.dumps(result.diagnostics)
    assert llm_transport.response_text(response) == "public answer"


@pytest.mark.parametrize("error_type", [TimeoutError, RuntimeError, asyncio.CancelledError])
@pytest.mark.parametrize("partial", [False, True])
def test_stream_failure_preserves_exception_identity_and_partial_diagnostics(monkeypatch, error_type, partial):
    original = error_type("provider interrupted")
    items = [chunk("partial", reason="MAX_TOKENS", usage=NS(total_token_count=19))] if partial else []
    install_stream(monkeypatch, items, error=original)
    with pytest.raises(error_type) as caught:
        asyncio.run(generate())
    assert caught.value is original
    diagnostics = getattr(caught.value, "llm_response_diagnostics", None)
    assert diagnostics is not None
    assert diagnostics["stream_completed"] is False
    assert diagnostics["stream_chunk_count"] == int(partial)
    assert diagnostics["output_chars"] == (7 if partial else 0)
    assert diagnostics["candidate_count"] == (1 if partial else None)


def test_afc_history_is_separate_observed_metadata_not_double_counted(monkeypatch):
    history = [NS(role="model", parts=[NS(function_call=NS(name="lookup_metric", args={"secret": "private-args"}))])]
    install_stream(monkeypatch, [NS(candidates=None, automatic_function_calling_history=history)] * 3)
    response = asyncio.run(generate())
    diagnostics = getattr(response, "diagnostics", None)
    assert diagnostics is not None
    assert diagnostics["function_call_count"] == 0
    assert diagnostics["afc_function_call_count"] == 1
    assert diagnostics["afc_function_call_names"] == ["lookup_metric"]
    assert "private-args" not in json.dumps(diagnostics)


def test_partial_usage_chunks_preserve_previously_observed_counters(monkeypatch):
    install_stream(monkeypatch, [
        chunk("answer", usage=NS(prompt_token_count=10, candidates_token_count=2)),
        NS(usage_metadata=NS(total_token_count=15)),
    ])
    response = asyncio.run(generate())
    assert response.usage == {"input_tokens": 10, "output_tokens": 2, "total_tokens": 15}


def test_invalid_optional_usage_does_not_fail_successful_stream(monkeypatch):
    install_stream(monkeypatch, [chunk("answer", usage=NS(prompt_token_count=float("inf")))])
    response = asyncio.run(generate())
    assert response.text == "answer"
    assert response.usage is None


def test_unreadable_optional_usage_does_not_fail_successful_stream(monkeypatch):
    class Response:
        text = "answer"

        @property
        def usage_metadata(self):
            raise ValueError("SDK optional metadata unavailable")

    install_stream(monkeypatch, [Response()])
    response = asyncio.run(generate())
    assert response.text == "answer"
    assert response.usage is None


def test_saved_diagnostics_are_revalidated_copied_and_bounded():
    from llm_response_diagnostics import response_diagnostics

    unsafe = {
        "function_call_count": 10 ** 100,
        "function_call_names": ["lookup"] * 10000,
        "finish_reasons": ["STOP"] * 10000,
        "candidate_count": 10 ** 100,
        "usage": {"input_tokens": 10 ** 100, "private": "private-usage"},
        "private": NS(args="private-args"),
    }
    response = NS(diagnostics=unsafe)
    bounded = response_diagnostics(response)
    assert bounded is not unsafe
    assert "private" not in bounded
    assert bounded["function_call_count"] <= (1 << 63) - 1
    assert bounded["candidate_count"] <= (1 << 63) - 1
    assert len(json.dumps(bounded)) < 4096


def test_empty_stream_has_no_claimed_candidate_or_afc_cause(monkeypatch):
    install_stream(monkeypatch, [])
    response = asyncio.run(generate())
    assert response.text == ""
    assert response.diagnostics["stream_chunk_count"] == 0
    assert response.diagnostics["candidate_count"] is None
    assert response.diagnostics["afc_history_present"] is False
    assert response.diagnostics["finish_reasons"] == []


@pytest.mark.parametrize("awaitable", [False, True])
def test_stream_setup_error_keeps_original_exception(monkeypatch, awaitable):
    original = TimeoutError("setup timeout")

    def fail(**kwargs):
        raise original

    async def fail_async(**kwargs):
        return fail(**kwargs)

    client = NS(aio=NS(models=NS(generate_content_stream=fail_async if awaitable else fail)))
    monkeypatch.setattr(llm_transport, "_get_client", lambda _: client)
    with pytest.raises(TimeoutError) as caught:
        asyncio.run(generate())
    assert caught.value is original
    assert caught.value.llm_response_diagnostics["stream_chunk_count"] == 0


def test_callback_failure_keeps_partial_metadata(monkeypatch):
    install_stream(monkeypatch, [chunk("answer", reason="STOP")])
    original = RuntimeError("callback failed")

    def callback(delta):
        raise original

    with pytest.raises(RuntimeError) as caught:
        asyncio.run(generate(on_delta=callback))
    assert caught.value is original
    assert caught.value.llm_response_diagnostics["output_chars"] == 6
    assert caught.value.llm_response_diagnostics["finish_reasons"] == ["STOP"]
