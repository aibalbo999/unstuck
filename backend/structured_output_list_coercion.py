"""List and confidence-basis coercion helpers for structured outputs."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_sequence_items
from structured_output_normalizer_basic import _string_field_line


def coerce_reasoning_steps(value: Any, minimum: int = 0) -> list[str]:
    if value is None:
        return ["待補推論步驟" for _ in range(minimum)]
    has_sequence_items = False
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = safe_sequence_items(value)
        has_sequence_items = True
    else:
        return ["待補推論步驟" for _ in range(minimum)]
    steps = []
    for item in candidates:
        text = _string_field_line(item)
        if text:
            steps.append(text)
    while has_sequence_items and len(steps) < minimum:
        steps.append("待補推論步驟")
    return steps


def coerce_required_text_list(value: Any, minimum: int, fallback: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return [fallback for _ in range(minimum)]
    texts = coerce_string_text_list(value)
    while len(texts) < minimum:
        texts.append(fallback)
    return texts


def coerce_string_text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    texts = []
    for item in safe_sequence_items(value):
        text = _string_field_line(item)
        if text:
            texts.append(text)
    return texts


def coerce_confidence_basis(value: Any) -> Any:
    basis = safe_mapping_dict(value)
    if basis is None:
        return value
    return {
        **basis,
        "evidence_items": coerce_required_text_list(basis.get("evidence_items"), 3, "待補具體佐證"),
        "key_risks_acknowledged": coerce_required_text_list(basis.get("key_risks_acknowledged"), 2, "待補已納入風險"),
        "data_gaps": coerce_string_text_list(basis.get("data_gaps")),
    }
