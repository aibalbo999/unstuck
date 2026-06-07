"""Google GenAI transport helpers."""

from __future__ import annotations

from contextlib import suppress

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


def generate_content(api_key: str, model_id: str, prompt: str, config):
    """Call Google GenAI synchronously with an isolated per-key client."""
    client = genai.Client(api_key=api_key, http_options=_genai_http_options())
    try:
        return client.models.generate_content(model=model_id, contents=prompt, config=config)
    finally:
        with suppress(Exception):
            client.close()


async def generate_content_async(api_key: str, model_id: str, prompt: str, config):
    """Call Google GenAI through the async client implementation."""
    client = genai.Client(api_key=api_key, http_options=_genai_http_options())
    try:
        return await client.aio.models.generate_content(model=model_id, contents=prompt, config=config)
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()


def embed_content(api_key: str, model_id: str, contents, config):
    """Call Google GenAI embeddings synchronously with an isolated per-key client."""
    client = genai.Client(api_key=api_key, http_options=_genai_http_options())
    try:
        return client.models.embed_content(model=model_id, contents=contents, config=config)
    finally:
        with suppress(Exception):
            client.close()


async def embed_content_async(api_key: str, model_id: str, contents, config):
    """Call Google GenAI embeddings through the async client implementation."""
    client = genai.Client(api_key=api_key, http_options=_genai_http_options())
    try:
        return await client.aio.models.embed_content(model=model_id, contents=contents, config=config)
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()


def generate_images(api_key: str, model_id: str, prompt: str, config):
    """Call Imagen synchronously with an isolated per-key client."""
    client = genai.Client(api_key=api_key, http_options=_genai_http_options())
    try:
        return client.models.generate_images(model=model_id, prompt=prompt, config=config)
    finally:
        with suppress(Exception):
            client.close()


async def generate_images_async(api_key: str, model_id: str, prompt: str, config):
    """Call Imagen through the async client implementation."""
    client = genai.Client(api_key=api_key, http_options=_genai_http_options())
    try:
        return await client.aio.models.generate_images(model=model_id, prompt=prompt, config=config)
    finally:
        with suppress(Exception):
            await client.aio.aclose()
        with suppress(Exception):
            client.close()
