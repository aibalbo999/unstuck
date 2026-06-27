"""Generation config and provider call helpers for agent LLM requests."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Optional

from google.genai import types

from config import LLM_AGENT_CALL_TIMEOUT_SECONDS
from llm_client import generate_content, generate_content_async, response_text
from structured_outputs import STRUCTURED_AGENT_INSTRUCTIONS, get_structured_response_schema

from .prompt_config import SYSTEM_PROMPTS
from .retry_policy import AgentTransientError
from .routing import get_agent_function_tools


def _strip_additional_properties(node: Any) -> Any:
    """Recursively remove 'additionalProperties' from a JSON-schema dict.

    Google GenAI's response_schema API rejects schemas that contain
    additionalProperties (produced by Pydantic when extra="forbid" is set),
    raising 400 INVALID_ARGUMENT: Unknown name "additional_properties".
    Stripping the key makes the schema compatible without changing the
    semantics for the model's output constraints.
    """
    if isinstance(node, dict):
        node.pop("additionalProperties", None)
        for value in node.values():
            _strip_additional_properties(value)
    elif isinstance(node, list):
        for item in node:
            _strip_additional_properties(item)
    return node


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
        response_schema_cls = get_structured_response_schema(agent_num)
        if response_schema_cls and _generate_config_supports("response_schema"):
            # Build a sanitized plain-dict schema: strip additionalProperties so
            # Google GenAI does not reject it with 400 INVALID_ARGUMENT.
            try:
                schema_dict = deepcopy(response_schema_cls.model_json_schema(by_alias=True))
                _strip_additional_properties(schema_dict)
                config_kwargs["response_schema"] = schema_dict
            except Exception:
                # Fall back to passing the class directly if schema extraction fails.
                config_kwargs["response_schema"] = response_schema_cls
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
    system_instruction = SYSTEM_PROMPTS.get(agent_num, "")
    if "gemini-2.5-flash" in model_id:
        system_instruction += "\n\nIMPORTANT: You are operating as a fallback model. You MUST provide a comprehensive, highly detailed, and complete analysis. Ensure your response is sufficiently long and detailed to form a formal report section. Do not provide a short or truncated response."
    config = build_generation_config(agent_num, system_instruction)
    return generate_content(api_key, model_id, prompt, config)


async def _generate_content_async(api_key: str, model_id: str, agent_num: int, prompt: str):
    system_instruction = SYSTEM_PROMPTS.get(agent_num, "")
    if "gemini-2.5-flash" in model_id:
        system_instruction += "\n\nIMPORTANT: You are operating as a fallback model. You MUST provide a comprehensive, highly detailed, and complete analysis. Ensure your response is sufficiently long and detailed to form a formal report section. Do not provide a short or truncated response."
    config = build_generation_config(agent_num, system_instruction)
    return await generate_content_async(api_key, model_id, prompt, config)


async def _await_with_agent_timeout(coro, *, model_id: str, timeout_seconds: float | None = None):
    timeout = float(LLM_AGENT_CALL_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds)
    if timeout <= 0:
        return await coro
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise AgentTransientError(f"LLM timeout after {timeout:.1f}s for model {model_id}") from exc
