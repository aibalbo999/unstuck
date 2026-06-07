"""Generation config and provider call helpers for agent LLM requests."""

from __future__ import annotations

import asyncio
from typing import Optional

from google.genai import types

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from llm_client import generate_content, generate_content_async, response_text
from structured_outputs import STRUCTURED_AGENT_INSTRUCTIONS, get_structured_response_schema

from .prompt_config import SYSTEM_PROMPTS
from .retry_policy import AgentTransientError
from .routing import get_agent_function_tools


def _generate_config_supports(field_name: str) -> bool:
    fields = getattr(types.GenerateContentConfig, "model_fields", {}) or {}
    return field_name in fields


def build_generation_config(agent_num: int, system_instruction: Optional[str] = None):
    """Build Google GenAI generation config, using JSON MIME type where supported."""
    config_kwargs = {
        "temperature": 0.7,
        "top_p": 0.95,
        "max_output_tokens": 8192,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if agent_num in STRUCTURED_AGENT_INSTRUCTIONS:
        config_kwargs["response_mime_type"] = "application/json"
        response_schema = get_structured_response_schema(agent_num)
        if response_schema and _generate_config_supports("response_schema"):
            config_kwargs["response_schema"] = response_schema
    function_tools = get_agent_function_tools(agent_num)
    if function_tools:
        config_kwargs["tools"] = function_tools
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(maximum_remote_calls=6)

    try:
        return types.GenerateContentConfig(**config_kwargs)
    except TypeError:
        if "response_schema" in config_kwargs:
            config_kwargs.pop("response_schema", None)
            try:
                return types.GenerateContentConfig(**config_kwargs)
            except TypeError:
                pass
        config_kwargs.pop("response_mime_type", None)
        config_kwargs.pop("automatic_function_calling", None)
        config_kwargs.pop("tools", None)
        return types.GenerateContentConfig(**config_kwargs)


def _response_text(response) -> str:
    return response_text(response)


def _generate_content(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num])
    return generate_content(api_key, model_id, prompt, config)


async def _generate_content_async(api_key: str, model_id: str, agent_num: int, prompt: str):
    config = build_generation_config(agent_num, SYSTEM_PROMPTS[agent_num])
    return await generate_content_async(api_key, model_id, prompt, config)


async def _await_with_agent_timeout(coro, *, model_id: str):
    timeout = float(LLM_AGENT_CALL_TIMEOUT_SECONDS or 0)
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTransientError(f"LLM timeout after {timeout:.1f}s for model {model_id}") from exc
