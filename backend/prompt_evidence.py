"""Non-mutating projection of evidence across the prompt boundary."""

from __future__ import annotations

import copy
from dataclasses import fields, is_dataclass
from typing import Any

from pydantic import BaseModel


INTERNAL_PROMPT_KEYS = frozenset({"rag_index", "embedding", "embeddings", "vector", "vectors"})


def is_internal_prompt_key(key: Any) -> bool:
    return isinstance(key, str) and key.lower().lstrip("_") in INTERNAL_PROMPT_KEYS


def prompt_evidence_copy(value: Any) -> Any:
    """Drop internal fields before traversing them; keep evidence paths and values."""
    if isinstance(value, BaseModel):
        model_values = {name: getattr(value, name) for name in type(value).model_fields if not is_internal_prompt_key(name)}
        model_values.update(value.model_extra or {})
        value = model_values
    elif is_dataclass(value) and not isinstance(value, type):
        value = {field.name: getattr(value, field.name) for field in fields(value) if not is_internal_prompt_key(field.name)}
    if isinstance(value, dict):
        return {key: prompt_evidence_copy(item) for key, item in dict.items(value) if not is_internal_prompt_key(key)}
    if isinstance(value, list):
        return [prompt_evidence_copy(item) for item in list.__iter__(value)]
    if isinstance(value, tuple):
        return tuple(prompt_evidence_copy(item) for item in tuple.__iter__(value))
    if isinstance(value, (set, frozenset)):
        iterator = set.__iter__(value) if isinstance(value, set) else frozenset.__iter__(value)
        return [prompt_evidence_copy(item) for item in sorted(iterator, key=repr)]
    return copy.deepcopy(value)
