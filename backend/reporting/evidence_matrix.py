"""Conclusion-level evidence matrix for rendered reports and snapshots."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict

from .evidence import build_key_evidence_rows
from .evidence_matrix_payload import build_payload as build_evidence_matrix_payload_from_rows
from .evidence_matrix_rendering import render_evidence_matrix_html, render_evidence_matrix_markdown
from .evidence_matrix_rows import build_rows_from_context


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def build_evidence_matrix_rows(context: dict) -> list[dict]:
    """Build conclusion-to-evidence rows shared by HTML, Markdown, and snapshots."""
    context = _as_dict(context)
    data = _as_dict(context.get("data"))
    return build_rows_from_context(context, build_key_evidence_rows(data))


def build_evidence_matrix_payload(context: dict) -> dict:
    rows = build_evidence_matrix_rows(context)
    return build_evidence_matrix_payload_from_rows(context, rows)


def build_evidence_matrix_html(context: dict) -> str:
    return render_evidence_matrix_html(build_evidence_matrix_rows(context))


def build_evidence_matrix_markdown(context: dict) -> list[str]:
    return render_evidence_matrix_markdown(build_evidence_matrix_rows(context))
