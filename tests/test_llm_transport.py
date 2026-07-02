import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import llm_transport  # noqa: E402


def test_response_text_does_not_access_sdk_text_when_parts_have_only_function_call():
    accessed = {"text": False}

    class FunctionCallPart:
        text = None
        function_call = {"name": "lookup_financial_metric"}

    class Content:
        parts = [FunctionCallPart()]

    class Candidate:
        content = Content()

    class Response:
        candidates = [Candidate()]

        @property
        def text(self):
            accessed["text"] = True
            return "SDK fallback text"

    assert llm_transport.response_text(Response()) == ""
    assert accessed["text"] is False


def test_response_text_joins_text_parts_without_accessing_sdk_text_for_mixed_parts():
    accessed = {"text": False}

    class TextPart:
        text = "正式分析段落"

    class FunctionCallPart:
        text = None
        function_call = {"name": "lookup_financial_metric"}

    class Content:
        parts = [TextPart(), FunctionCallPart()]

    class Candidate:
        content = Content()

    class Response:
        candidates = [Candidate()]

        @property
        def text(self):
            accessed["text"] = True
            return "SDK fallback text"

    assert llm_transport.response_text(Response()) == "正式分析段落"
    assert accessed["text"] is False


def test_extract_usage_reads_google_usage_metadata():
    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=123,
            candidates_token_count=45,
            total_token_count=168,
        )
    )

    assert llm_transport.extract_usage(response) == {
        "input_tokens": 123,
        "output_tokens": 45,
        "total_tokens": 168,
    }


def test_provider_wrappers_preserve_openai_and_anthropic_usage(monkeypatch):
    responses = [
        {
            "output_text": "OpenAI response text",
            "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        },
        {
            "content": [{"type": "text", "text": "Anthropic response text"}],
            "usage": {"input_tokens": 8, "output_tokens": 6},
        },
    ]

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_post(*_args, **_kwargs):
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr(llm_transport.httpx, "post", fake_post)

    openai_response = llm_transport.generate_content(
        "openai-key",
        "openai:gpt-4.1-mini",
        "請分析資料",
        SimpleNamespace(max_output_tokens=321, temperature=0.2),
    )
    anthropic_response = llm_transport.generate_content(
        "anthropic-key",
        "anthropic:claude-4-sonnet",
        "請分析資料",
        SimpleNamespace(max_output_tokens=654, temperature=0.1),
    )

    assert llm_transport.extract_usage(openai_response) == {
        "input_tokens": 10,
        "output_tokens": 4,
        "total_tokens": 14,
    }
    assert llm_transport.extract_usage(anthropic_response) == {
        "input_tokens": 8,
        "output_tokens": 6,
        "total_tokens": 14,
    }


def test_generate_content_routes_openai_prefixed_model_to_responses_api(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"output_text": "OpenAI response text"}

    def fake_post(url, *, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(llm_transport.httpx, "post", fake_post)

    response = llm_transport.generate_content(
        "openai-key",
        "openai:gpt-4.1-mini",
        "請分析資料",
        SimpleNamespace(max_output_tokens=321, temperature=0.2),
    )

    assert llm_transport.response_text(response) == "OpenAI response text"
    assert calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert calls[0]["headers"]["Authorization"] == "Bearer openai-key"
    assert calls[0]["json"]["model"] == "gpt-4.1-mini"
    assert calls[0]["json"]["input"] == "請分析資料"
    assert calls[0]["json"]["max_output_tokens"] == 321


def test_generate_content_routes_anthropic_prefixed_model_to_messages_api(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"content": [{"type": "text", "text": "Anthropic response text"}]}

    def fake_post(url, *, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(llm_transport.httpx, "post", fake_post)

    response = llm_transport.generate_content(
        "anthropic-key",
        "anthropic:claude-4-sonnet",
        "請分析資料",
        SimpleNamespace(max_output_tokens=654, temperature=0.1),
    )

    assert llm_transport.response_text(response) == "Anthropic response text"
    assert calls[0]["url"] == "https://api.anthropic.com/v1/messages"
    assert calls[0]["headers"]["x-api-key"] == "anthropic-key"
    assert calls[0]["json"]["model"] == "claude-4-sonnet"
    assert calls[0]["json"]["messages"] == [{"role": "user", "content": "請分析資料"}]
    assert calls[0]["json"]["max_tokens"] == 654


def test_generate_content_stream_async_emits_google_deltas(monkeypatch):
    class FakeModels:
        async def generate_content_stream(self, **_kwargs):
            for text in ("第一段", "第二段"):
                yield SimpleNamespace(text=text)

    class FakeClient:
        aio = SimpleNamespace(models=FakeModels())

    deltas = []
    monkeypatch.setattr(llm_transport, "_get_client", lambda _api_key: FakeClient())

    response = asyncio.run(
        llm_transport.generate_content_stream_async(
            "google-key",
            "google:gemini-test",
            "prompt",
            object(),
            on_delta=deltas.append,
        )
    )

    assert deltas == ["第一段", "第二段"]
    assert llm_transport.response_text(response) == "第一段第二段"


def test_generate_content_stream_async_accepts_sync_stream_iterable(monkeypatch):
    class FakeModels:
        def generate_content_stream(self, **_kwargs):
            return [SimpleNamespace(text="同步第一段"), SimpleNamespace(text="同步第二段")]

    class FakeClient:
        aio = SimpleNamespace(models=FakeModels())

    deltas = []
    monkeypatch.setattr(llm_transport, "_get_client", lambda _api_key: FakeClient())

    response = asyncio.run(
        llm_transport.generate_content_stream_async(
            "google-key",
            "google:gemini-test",
            "prompt",
            object(),
            on_delta=deltas.append,
        )
    )

    assert deltas == ["同步第一段", "同步第二段"]
    assert llm_transport.response_text(response) == "同步第一段同步第二段"
