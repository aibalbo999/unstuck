import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import runtime_logging  # noqa: E402


def test_runtime_trace_context_propagates_into_async_tasks():
    async def read_trace_from_task():
        return runtime_logging.get_current_trace_id()

    async def run():
        with runtime_logging.runtime_trace_context("trace-test-123"):
            task = asyncio.create_task(read_trace_from_task())
            return await task

    assert asyncio.run(run()) == "trace-test-123"


def test_trace_runtime_operation_records_async_duration_and_token_usage(monkeypatch):
    spans = []

    class FakeSpan:
        def __init__(self, name):
            self.name = name
            self.attributes = {}
            self.exceptions = []

        def __enter__(self):
            spans.append(self)
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def record_exception(self, exc):
            self.exceptions.append(exc)

    class FakeTracer:
        def start_as_current_span(self, name, attributes=None):
            span = FakeSpan(name)
            for key, value in (attributes or {}).items():
                span.set_attribute(key, value)
            return span

    monkeypatch.setattr(runtime_logging, "_get_tracer", lambda: FakeTracer())

    @runtime_logging.trace_runtime_operation(
        "llm.openai.complete",
        attributes={"component": "llm", "provider": "openai"},
        token_usage_extractor=lambda result: result["usage"],
    )
    async def fake_llm_call():
        await asyncio.sleep(0)
        return {"usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}

    result = asyncio.run(fake_llm_call())

    assert result["usage"]["total_tokens"] == 18
    assert spans[0].name == "llm.openai.complete"
    assert spans[0].attributes["component"] == "llm"
    assert spans[0].attributes["provider"] == "openai"
    assert spans[0].attributes["llm.prompt_tokens"] == 11
    assert spans[0].attributes["llm.completion_tokens"] == 7
    assert spans[0].attributes["llm.total_tokens"] == 18
    assert spans[0].attributes["duration_ms"] >= 0
