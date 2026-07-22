"""HTTP provider adapters for non-Google LLM routes."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from llm_usage import extract_usage


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


@dataclass(frozen=True)
class TextLLMResponse:
    text: str
    usage: dict[str, int] | None = None


def generate_openai_content(api_key: str, model_id: str, prompt: str, config) -> TextLLMResponse:
    payload = _openai_payload(model_id, prompt, config)
    response = httpx.post(
        OPENAI_RESPONSES_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=_provider_timeout_seconds(),
    )
    response.raise_for_status()
    payload = response.json()
    return TextLLMResponse(_openai_text(payload), extract_usage(payload))


async def generate_openai_content_async(api_key: str, model_id: str, prompt: str, config) -> TextLLMResponse:
    payload = _openai_payload(model_id, prompt, config)
    async with httpx.AsyncClient(timeout=_provider_timeout_seconds()) as client:
        response = await client.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
    payload = response.json()
    return TextLLMResponse(_openai_text(payload), extract_usage(payload))


def generate_anthropic_content(api_key: str, model_id: str, prompt: str, config) -> TextLLMResponse:
    payload = _anthropic_payload(model_id, prompt, config)
    response = httpx.post(
        ANTHROPIC_MESSAGES_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=_provider_timeout_seconds(),
    )
    response.raise_for_status()
    payload = response.json()
    return TextLLMResponse(_anthropic_text(payload), extract_usage(payload))


async def generate_anthropic_content_async(api_key: str, model_id: str, prompt: str, config) -> TextLLMResponse:
    payload = _anthropic_payload(model_id, prompt, config)
    async with httpx.AsyncClient(timeout=_provider_timeout_seconds()) as client:
        response = await client.post(
            ANTHROPIC_MESSAGES_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()
    payload = response.json()
    return TextLLMResponse(_anthropic_text(payload), extract_usage(payload))


def _provider_timeout_seconds() -> float:
    return max(1.0, float(LLM_AGENT_CALL_TIMEOUT_SECONDS or 60))


def _config_value(config, name: str, default):
    return getattr(config, name, default) if config is not None else default


def _openai_payload(model_id: str, prompt: str, config) -> dict:
    payload = {
        "model": model_id,
        "input": prompt,
        "max_output_tokens": int(_config_value(config, "max_output_tokens", 4096) or 4096),
    }
    temperature = _config_value(config, "temperature", None)
    if temperature is not None:
        payload["temperature"] = float(temperature)
    return payload


def _openai_text(payload: dict) -> str:
    text = payload.get("output_text")
    if isinstance(text, str):
        return text
    parts = []
    for item in payload.get("output", []) or []:
        for content in item.get("content", []) or []:
            content_text = content.get("text")
            if isinstance(content_text, str):
                parts.append(content_text)
    return "\n".join(parts)


def _anthropic_payload(model_id: str, prompt: str, config) -> dict:
    return {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": int(_config_value(config, "max_output_tokens", 4096) or 4096),
        "temperature": float(_config_value(config, "temperature", 0.2) or 0.0),
    }


def _anthropic_text(payload: dict) -> str:
    parts = []
    for item in payload.get("content", []) or []:
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
    return "\n".join(parts)
