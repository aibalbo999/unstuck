"""Shared pipeline identity resolution for report artifacts and snapshots."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict
from pipeline_modes import normalize_pipeline_id
from report_index_parsing import parse_report_filename
from reporting.text_tokens import first_non_missing_text


def resolve_report_pipeline_id(
    filename: str,
    *,
    stored_pipeline: Any = None,
    snapshot: Any = None,
) -> str:
    snapshot_map = safe_mapping_dict(snapshot) or {}
    filename_pipeline = parse_report_filename(filename)["pipeline_id"]
    return normalize_pipeline_id(
        first_non_missing_text(
            stored_pipeline,
            dict.get(snapshot_map, "pipeline"),
            filename_pipeline,
        )
    )


__all__ = ["resolve_report_pipeline_id"]
