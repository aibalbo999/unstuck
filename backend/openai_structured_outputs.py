"""OpenAI-specific Structured Outputs helpers."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from pydantic import BaseModel


_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def openai_json_schema_response_format(name: str, model: type[BaseModel]) -> dict[str, Any]:
    """Build a strict Chat Completions response_format without mutating the base schema."""
    if _SCHEMA_NAME_RE.fullmatch(name) is None:
        raise ValueError("schema name must be 1-64 characters using only letters, digits, '_' or '-'")

    schema = deepcopy(model.model_json_schema(by_alias=True))
    _force_no_extra_properties(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


def _force_no_extra_properties(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties)
        for value in node.values():
            _force_no_extra_properties(value)
    elif isinstance(node, list):
        for value in node:
            _force_no_extra_properties(value)
