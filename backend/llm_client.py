"""Compatibility facade for GenAI transport, key rotation, and quota helpers."""

from __future__ import annotations

from google import genai
from google.genai import types

import llm_transport as _transport
from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from llm_errors import (
    describe_quota_or_rate_error,
    is_auth_error,
    is_missing_model_error,
    is_quota_or_rate_error,
    retry_delay_seconds,
)
from llm_rate_limits import KeyRotator, TokenBucket, estimate_text_tokens


def _sync_transport_seams() -> None:
    # Compatibility: existing tests/scripts monkeypatch llm_client.genai or the
    # timeout constant. The split transport module should observe those changes.
    _transport.genai = genai
    _transport.LLM_AGENT_CALL_TIMEOUT_SECONDS = LLM_AGENT_CALL_TIMEOUT_SECONDS


def response_text(response) -> str:
    return _transport.response_text(response)


def extract_usage(response) -> dict[str, int] | None:
    return _transport.extract_usage(response)


def generate_content(api_key: str, model_id: str, prompt: str, config):
    _sync_transport_seams()
    return _transport.generate_content(api_key, model_id, prompt, config)


async def generate_content_async(api_key: str, model_id: str, prompt: str, config):
    _sync_transport_seams()
    return await _transport.generate_content_async(api_key, model_id, prompt, config)


async def generate_content_stream_async(api_key: str, model_id: str, prompt: str, config, *, on_delta=None):
    _sync_transport_seams()
    return await _transport.generate_content_stream_async(api_key, model_id, prompt, config, on_delta=on_delta)


def embed_content(api_key: str, model_id: str, contents, config):
    _sync_transport_seams()
    return _transport.embed_content(api_key, model_id, contents, config)


async def embed_content_async(api_key: str, model_id: str, contents, config):
    _sync_transport_seams()
    return await _transport.embed_content_async(api_key, model_id, contents, config)


def generate_images(api_key: str, model_id: str, prompt: str, config):
    _sync_transport_seams()
    return _transport.generate_images(api_key, model_id, prompt, config)


async def generate_images_async(api_key: str, model_id: str, prompt: str, config):
    _sync_transport_seams()
    return await _transport.generate_images_async(api_key, model_id, prompt, config)


__all__ = [
    "KeyRotator",
    "TokenBucket",
    "describe_quota_or_rate_error",
    "embed_content",
    "embed_content_async",
    "estimate_text_tokens",
    "extract_usage",
    "generate_content",
    "generate_content_async",
    "generate_content_stream_async",
    "generate_images",
    "generate_images_async",
    "genai",
    "is_auth_error",
    "is_missing_model_error",
    "is_quota_or_rate_error",
    "response_text",
    "retry_delay_seconds",
    "types",
]
