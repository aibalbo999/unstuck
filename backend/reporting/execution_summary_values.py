"""Execution summary value extraction for rendered reports."""

from __future__ import annotations

from typing import Any

from analysis_types import AnalysisContext
from config import format_model_routes
from data_trust import normalize_data_trust, trust_status_label
from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number
from pipeline_modes import get_pipeline_definition

from .text_tokens import is_missing_text_token


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _agent_sequence(context: AnalysisContext, pipeline_def: dict) -> list[int]:
    raw_sequence = context.get("agent_sequence") or pipeline_def.get("agents") or []
    if not isinstance(raw_sequence, (list, tuple)):
        raw_sequence = pipeline_def.get("agents") or []
    sequence: list[int] = []
    for item in raw_sequence:
        if isinstance(item, (bool, bytes, bytearray, memoryview)):
            continue
        try:
            sequence.append(int(item))
        except (TypeError, ValueError):
            continue
    return sequence or list(pipeline_def.get("agents") or [])


def _status(value: Any, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def build_execution_summary_values(context: AnalysisContext, *, model_routes: str | None = None) -> dict:
    """Build deterministic execution trace values shared by HTML and Markdown."""
    context = _as_dict(context)
    data = _as_dict(dict.get(context, "data"))
    pipeline_def = get_pipeline_definition(dict.get(context, "pipeline_id", "v1"))
    agent_sequence = _agent_sequence(context, pipeline_def)
    final_audit = _as_dict(dict.get(context, "final_audit"))
    evidence_gate = _as_dict(dict.get(context, "evidence_exit_gate"))
    report_conformance = _as_dict(dict.get(context, "report_conformance"))
    report_lint = _as_dict(dict.get(context, "report_lint"))
    data_trust = normalize_data_trust(dict.get(data, "data_trust"))
    structured_agents = _as_dict(dict.get(pipeline_def, "structured_agents"))
    return {
        "pipeline": f"V{str(dict.get(pipeline_def, 'id', 'v1')).lstrip('v').upper()}",
        "pipeline_label": dict.get(pipeline_def, "label", "N/A"),
        "agent_count": len(agent_sequence),
        "agent_sequence": agent_sequence,
        "structured_agent_count": len(structured_agents),
        "model_routes": _status(model_routes or format_model_routes(pipeline_id=dict.get(pipeline_def, "id", "v1"))),
        "data_trust": trust_status_label(str(dict.get(data_trust, "status") or "unknown")),
        "data_trust_raw": str(dict.get(data_trust, "status") or "unknown"),
        "final_audit": _status(dict.get(final_audit, "status"), "not_recorded"),
        "evidence_gate": _status(dict.get(evidence_gate, "verdict"), "not_recorded"),
        "evidence_summary": _status(dict.get(evidence_gate, "summary"), ""),
        "report_conformance": _status(dict.get(report_conformance, "status"), "not_recorded"),
        "conformance_summary": _status(dict.get(report_conformance, "summary"), ""),
        "report_lint": _status(dict.get(report_lint, "status"), "not_recorded"),
        "prompt_version": _status(dict.get(context, "prompt_version"), "N/A"),
        "model_id": _status(_model_id(context), "N/A"),
    }


def _model_id(context: dict) -> Any:
    return (
        dict.get(context, "model_id")
        or dict.get(context, "decision_model_id")
        or dict.get(context, "final_model_id")
    )


__all__ = ["build_execution_summary_values"]
