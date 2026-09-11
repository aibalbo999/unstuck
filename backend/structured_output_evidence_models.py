"""Shared evidence memo schema for dated research-support agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items
from structured_output_model_base import (
    _safe_string_text,
    _safe_string_text_list,
    AnalysisMarkdownMixin,
    StructuredModel,
)


class DatedEvidenceItem(StructuredModel):
    finding: str = Field(..., min_length=1)
    source_refs: list[str] = Field(..., min_length=1, max_length=6)
    freshness_note: str = Field(..., min_length=1)
    counterevidence: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_fields(cls, payload):
        item = safe_mapping_dict(payload) or {}
        return {
            **item,
            "finding": _safe_string_text(item.get("finding"), "資料不足"),
            "source_refs": _safe_string_text_list(item.get("source_refs"))[:6],
            "freshness_note": _safe_string_text(
                item.get("freshness_note"),
                "資料時點未提供",
            ),
            "counterevidence": _safe_string_text(
                item.get("counterevidence"),
                "資料不足",
            ),
        }


def _safe_evidence_items(value: Any) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        return []
    rows = []
    for item in safe_sequence_items(value)[:8]:
        row = safe_mapping_dict(item)
        if row is not None:
            rows.append(row)
    return rows


class DatedEvidenceMemoStructuredOutput(AnalysisMarkdownMixin):
    as_of_date: str = Field(..., min_length=1)
    confidence: Literal["high", "medium", "low", "unassessed"]
    evidence_items: list[DatedEvidenceItem] = Field(..., min_length=1, max_length=8)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_fields(cls, payload):
        root = safe_mapping_dict(payload) or {}
        confidence = _safe_string_text(root.get("confidence")).lower()
        if confidence not in {"high", "medium", "low", "unassessed"}:
            confidence = "unassessed"
        return {
            **root,
            "as_of_date": _safe_string_text(root.get("as_of_date"), "資料時點未提供"),
            "confidence": confidence,
            "evidence_items": _safe_evidence_items(root.get("evidence_items")),
        }
