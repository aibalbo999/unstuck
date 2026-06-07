"""Google GenAI transport helpers."""

from __future__ import annotations

import threading
from contextlib import suppress
from inspect import isawaitable

from google import genai
from google.genai import types

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS


def response_text(response) -> str:
    """Extract text from a Google GenAI response without leaking object internals."""
    candidates = getattr(response, "candidates", None) or []
    parts = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    if parts:
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
    """Call Google GenAI synchronously with an isolated per-key client."""
    client = _get_client(api_key)
    return client.models.generate_content(model=model_id, contents=prompt, config=config)


async def generate_content_async(api_key: str, model_id: str, prompt: str, config):
    """Call Google GenAI through the async client implementation."""
    client = _get_client(api_key)
    return await client.aio.models.generate_content(model=model_id, contents=prompt, config=config)


def embed_content(api_key: str, model_id: str, contents, config):
    """Call Google GenAI embeddings synchronously with an isolated per-key client."""
    client = _get_client(api_key)
    return client.models.embed_content(model=model_id, contents=contents, config=config)


async def embed_content_async(api_key: str, model_id: str, contents, config):
    """Call Google GenAI embeddings through the async client implementation."""
    client = _get_client(api_key)
    return await client.aio.models.embed_content(model=model_id, contents=contents, config=config)


def generate_images(api_key: str, model_id: str, prompt: str, config):
    """Call Imagen synchronously with an isolated per-key client."""
    client = _get_client(api_key)
    return client.models.generate_images(model=model_id, prompt=prompt, config=config)


async def generate_images_async(api_key: str, model_id: str, prompt: str, config):
    """Call Imagen through the async client implementation."""
    client = _get_client(api_key)
    return await client.aio.models.generate_images(model=model_id, prompt=prompt, config=config)
