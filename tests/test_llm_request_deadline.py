"""The SDK deadline follows the admitted route, without mutating shared clients."""
import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

import llm_transport
from agent_runtime.llm_waiting import await_response


def install_transport(monkeypatch, response):
    async def generate(**kwargs):
        return await response(kwargs["config"])

    async def stream(**kwargs):
        yield await response(kwargs["config"])

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(
        generate_content=generate, generate_content_stream=stream)))
    monkeypatch.setattr(llm_transport, "_get_client", lambda key: client)
    monkeypatch.setattr(llm_transport, "get_cached_llm_response", lambda *a: None)
    monkeypatch.setattr(llm_transport, "store_llm_response", lambda *a, **k: None)
    import llm_congestion
    monkeypatch.setattr(llm_congestion.config, "LLM_CONGESTION_GUARD_ENABLED", False)


@pytest.mark.parametrize("streaming", [False, True])
def test_primary_deadline_reaches_sdk_instead_of_global_120_seconds(monkeypatch, streaming):
    seen = []

    async def response(config):
        seen.append(config.http_options.timeout if config.http_options else None)
        return SimpleNamespace(text="complete")

    install_transport(monkeypatch, response)
    config = types.GenerateContentConfig(max_output_tokens=6144)
    call = llm_transport.generate_content_stream_async if streaming else llm_transport.generate_content_async
    asyncio.run(await_response(call("fake", "gemini-test", "evidence", config), model_id="gemini-test", timeout=360))
    assert seen == [360000]
    assert config.http_options is None
    assert llm_transport._genai_http_options().timeout == 120000


def test_parallel_deadlines_are_isolated_and_do_not_leak_to_next_request(monkeypatch):
    seen = []

    async def response(config):
        await asyncio.sleep(0)
        seen.append(config.http_options.timeout if config.http_options else None)
        return SimpleNamespace(text="complete")

    install_transport(monkeypatch, response)
    config = types.GenerateContentConfig()

    async def run():
        def call():
            return llm_transport.generate_content_async("fake", "gemini-test", "evidence", config)
        await asyncio.gather(*(await_response(call(), model_id="gemini-test", timeout=t) for t in (360, 120)))
        await call()

    asyncio.run(run())
    assert sorted(seen[:2]) == [120000, 360000]
    assert seen[2] is None


def test_request_specific_shorter_deadline_and_headers_are_preserved(monkeypatch):
    seen = []

    async def response(config):
        seen.append(config.http_options)
        return SimpleNamespace(text="complete")

    install_transport(monkeypatch, response)
    config = types.GenerateContentConfig(http_options=types.HttpOptions(timeout=45000, headers={"x-test": "local"}))
    asyncio.run(await_response(llm_transport.generate_content_async("fake", "gemini-test", "evidence", config),
                               model_id="gemini-test", timeout=360))
    assert seen[0].timeout == 45000
    assert seen[0].headers == {"x-test": "local", "X-Server-Timeout": "45"}


def test_cancelled_stream_stays_incomplete_and_scope_is_restored(monkeypatch):
    from agent_runtime.retry_policy import AgentTransientError
    from llm_response_diagnostics import response_diagnostics
    from llm_request_deadline import current_response_timeout

    async def response(config):
        await asyncio.sleep(1)
        return SimpleNamespace(text="never accepted")

    install_transport(monkeypatch, response)
    with pytest.raises(AgentTransientError) as exc:
        asyncio.run(await_response(llm_transport.generate_content_stream_async(
            "fake", "gemini-test", "evidence", types.GenerateContentConfig()), model_id="gemini-test", timeout=.01))
    assert response_diagnostics(error=exc.value)["stream_completed"] is False
    assert current_response_timeout() is None


def test_installed_sdk_builds_route_deadline_header_without_changing_cached_default():
    from google import genai
    from llm_request_deadline import apply_response_timeout, response_timeout_scope

    client = genai.Client(api_key="fake-test-key", http_options=types.HttpOptions(timeout=120000))
    try:
        first = client._api_client._build_request("POST", "models/gemini-test:generateContent", {})
        assert first.headers["X-Server-Timeout"] == "120"
        with response_timeout_scope(360):
            config = apply_response_timeout(types.GenerateContentConfig())
            request = client._api_client._build_request("POST", "models/gemini-test:generateContent", {}, config.http_options)
        assert request.timeout == 360
        assert request.headers["X-Server-Timeout"] == "360"
        normal = client._api_client._build_request("POST", "models/gemini-test:generateContent", {})
        assert normal.timeout == 120
        assert normal.headers["X-Server-Timeout"] == "120"
    finally:
        client.close()


def test_explicit_shorter_server_header_is_preserved_without_case_duplicates():
    from llm_request_deadline import apply_response_timeout, response_timeout_scope

    config = types.GenerateContentConfig(http_options=types.HttpOptions(
        headers={"x-server-timeout": "30", "x-test": "local"}))
    with response_timeout_scope(360):
        request_config = apply_response_timeout(config)
    assert request_config.http_options.timeout == 30000
    assert request_config.http_options.headers == {"X-Server-Timeout": "30", "x-test": "local"}
    assert config.http_options.headers == {"x-server-timeout": "30", "x-test": "local"}


@pytest.mark.parametrize("config", [None, {"max_output_tokens": 100}])
def test_optional_sdk_config_keeps_route_deadline(config):
    from llm_request_deadline import apply_response_timeout, response_timeout_scope

    with response_timeout_scope(360):
        actual = apply_response_timeout(config)
    assert actual.http_options.timeout == 360000
    assert actual.http_options.headers["X-Server-Timeout"] == "360"
    assert actual.max_output_tokens == (100 if config else None)
