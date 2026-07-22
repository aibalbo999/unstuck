"""Data-trust step builder for report conformance gates."""

from __future__ import annotations

from typing import Any

from data_trust import normalize_data_trust, trust_status_label
from mapping_fields import safe_mapping_dict, safe_text

from .conformance_step_result import step, step_result
from .text_tokens import is_missing_text_token


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _text(value: Any, default: str = "") -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return text or default


def build_data_trust_conformance_step(*, context: dict, snapshot: dict) -> dict:
    """Build the data-trust decision-tree step and warning bucket."""
    context = _as_dict(context)
    snapshot = _as_dict(snapshot)
    data_trust = normalize_data_trust(
        dict.get(snapshot, "data_trust") or dict.get(_as_dict(dict.get(context, "data")), "data_trust")
    )
    trust_status = _text(dict.get(data_trust, "status"), "unknown")
    if trust_status == "fresh":
        return step_result(step("data_trust", "passed", "資料可信度為 fresh。"))
    label = trust_status_label(trust_status)
    data_trust_details = {**data_trust, "status": trust_status}
    return step_result(
        step("data_trust", "warning", f"資料可信度為 {label}（{trust_status}），報告需保留限制說明。", data_trust_details),
        issue_kind="warning",
    )
