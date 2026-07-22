"""Google GenAI transport helpers."""

from __future__ import annotations

import threading
from contextlib import suppress
from inspect import isawaitable

from google import genai
from google.genai import types

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from google_prompt_safety import sanitize_google_generation_config, sanitize_google_prompt
from llm_http_providers import (
    TextLLMResponse,
    generate_anthropic_content,
    generate_anthropic_content_async,
    generate_openai_content,
    generate_openai_content_async,
)
from llm_semantic_cache import get_cached_llm_response, store_llm_response
from llm_usage import extract_usage
from llm_provider_routes import split_model_provider


def response_text(response) -> str:
    """Extract text from a Google GenAI response without leaking object internals."""
    if isinstance(response, TextLLMResponse):
        return response.text

    candidates = getattr(response, "candidates", None) or []
    parts = []
    saw_candidate_parts = False
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            saw_candidate_parts = True
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    if saw_candidate_parts:
        return "\n".join(parts)

    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    return text or ""


def _genai_http_options():
    timeout_seconds = float(LLM_AGENT_CALL_TIMEOUT_SECONDS or 0)
    if timeout_seconds <= 0:
        return None
    return types.HttpOptions(timeout=max(1, int(round(timeout_seconds * 1000))))


_client_cache: dict[str, genai.Client] = {}
_client_lock = threading.Lock()


def _get_client(api_key: str) -> genai.Client:
    with _client_lock:
        if api_key not in _client_cache:
            _client_cache[api_key] = genai.Client(api_key=api_key, http_options=_genai_http_options())
        return _client_cache[api_key]


def close_cached_clients() -> None:
    """Close cached sync clients and clear the process-local client cache."""
    with _client_lock:
        clients = list(_client_cache.values())
        _client_cache.clear()
    for client in clients:
        close = getattr(client, "close", None)
        if callable(close):
            with suppress(Exception):
                close()


async def close_cached_clients_async() -> None:
    """Close cached sync and async clients during app shutdown."""
    with _client_lock:
        clients = list(_client_cache.values())
        _client_cache.clear()
    for client in clients:
        close = getattr(client, "close", None)
        if callable(close):
            with suppress(Exception):
                close()
        aio_client = getattr(client, "aio", None)
        aclose = getattr(aio_client, "aclose", None)
        if callable(aclose):
            with suppress(Exception):
                result = aclose()
                if isawaitable(result):
                    await result


def generate_content(api_key: str, model_id: str, prompt: str, config):
    """Call the configured LLM provider synchronously with an isolated per-key client."""
    cached = get_cached_llm_response(model_id, prompt, config)
    if cached is not None:
        return TextLLMResponse(str(cached.get("text") or ""), cached.get("usage"))
    provider, provider_model = split_model_provider(model_id)
    if provider == "openai":
        return _cache_generated_response(
            model_id,
            prompt,
            config,
            generate_openai_content(api_key, provider_model, prompt, config),
        )
    if provider == "anthropic":
        return _cache_generated_response(
            model_id,
            prompt,
            config,
            generate_anthropic_content(api_key, provider_model, prompt, config),
        )
    if provider != "google":
        raise ValueError(f"Unsupported LLM provider: {provider}")
    client = _get_client(api_key)
    response = client.models.generate_content(
        model=provider_model,
        contents=sanitize_google_prompt(prompt),
        config=sanitize_google_generation_config(config),
    )
    return _cache_generated_response(model_id, prompt, config, response)


async def generate_content_async(api_key: str, model_id: str, prompt: str, config):
    """Call the configured LLM provider through an async client implementation."""
    cached = get_cached_llm_response(model_id, prompt, config)
    if cached is not None:
        return TextLLMResponse(str(cached.get("text") or ""), cached.get("usage"))
    provider, provider_model = split_model_provider(model_id)
    if provider == "openai":
        return _cache_generated_response(
            model_id,
            prompt,
            config,
            await generate_openai_content_async(api_key, provider_model, prompt, config),
        )
    if provider == "anthropic":
        return _cache_generated_response(
            model_id,
            prompt,
            config,
            await generate_anthropic_content_async(api_key, provider_model, prompt, config),
        )
    if provider != "google":
        raise ValueError(f"Unsupported LLM provider: {provider}")
    client = _get_client(api_key)
    response = await client.aio.models.generate_content(
        model=provider_model,
        contents=sanitize_google_prompt(prompt),
        config=sanitize_google_generation_config(config),
    )
    return _cache_generated_response(model_id, prompt, config, response)


async def generate_content_stream_async(api_key: str, model_id: str, prompt: str, config, *, on_delta=None):
    """Stream provider text deltas when supported, returning a full response object."""
    provider, provider_model = split_model_provider(model_id)
    if provider != "google":
        return await generate_content_async(api_key, model_id, prompt, config)

    client = _get_client(api_key)
    models = getattr(getattr(client, "aio", None), "models", None)
    stream_call = getattr(models, "generate_content_stream", None)
    if not callable(stream_call):
        return await generate_content_async(api_key, model_id, prompt, config)

    chunks: list[str] = []
    stream = stream_call(
        model=provider_model,
        contents=sanitize_google_prompt(prompt),
        config=sanitize_google_generation_config(config),
    )
    if isawaitable(stream):
        stream = await stream
    if hasattr(stream, "__aiter__"):
        async for chunk in stream:
            await _collect_stream_chunk(chunk, chunks, on_delta)
    else:
        for chunk in stream:
            await _collect_stream_chunk(chunk, chunks, on_delta)
    return TextLLMResponse("".join(chunks))


def embed_content(api_key: str, model_id: str, contents, config):
    """Call Google GenAI embeddings synchronously with an isolated per-key client."""
    client = _get_client(api_key)
    return client.models.embed_content(model=model_id, contents=contents, config=config)


async def embed_content_async(api_key: str, model_id: str, contents, config):
    """Call Google GenAI embeddings through the async client implementation."""
    client = _get_client(api_key)
    return await client.aio.models.embed_content(model=model_id, contents=contents, config=config)


def _cache_generated_response(model_id: str, prompt: str, config, response):
    text = response_text(response)
    store_llm_response(model_id, prompt, config, text=text, usage=extract_usage(response))
    return response


async def _emit_stream_delta(on_delta, delta: str) -> None:
    if not callable(on_delta):
        return
    result = on_delta(delta)
    if isawaitable(result):
        await result


async def _collect_stream_chunk(chunk, chunks: list[str], on_delta) -> None:
    delta = response_text(chunk)
    if not delta:
        return
    chunks.append(delta)
    await _emit_stream_delta(on_delta, delta)
