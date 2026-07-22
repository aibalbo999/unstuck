"""Evidence-matrix source status and limitation summaries."""

from __future__ import annotations

from typing import Any

from data_trust_audit import source_label
from data_trust_scoring import trust_status_label
from mapping_fields import safe_mapping_dict, safe_text, safe_text_list
from numeric_safety import is_non_finite_number

from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _as_notes(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return safe_text_list(value)
    if text := _text(value, "").strip():
        return [text]
    return []


def _text(value: Any, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    if is_missing_text_token(value):
        return default
    text = sanitize_report_plain_text(safe_text(value)).strip()
    return text or default


def _safe_bool_flag(value: Any) -> bool:
    return value if isinstance(value, bool) else False


def unique_evidence_texts(values: list[Any]) -> list[str]:
    seen = []
    for value in values:
        item = _text(value, "").strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def latest_evidence_fetched_at(rows: list[dict]) -> str:
    values = []
    for row in rows:
        row_map = _as_dict(row)
        fetched_at = _text(row_map.get("fetched_at"), "").strip()
        if fetched_at and fetched_at != "N/A":
            values.append(fetched_at)
    values = sorted(values)
    return values[-1] if values else "N/A"


def combined_evidence_status(rows: list[dict], trust_status: str) -> str:
    statuses = [_text(_as_dict(row).get("status"), "unknown") for row in rows]
    if any(status == "error" for status in statuses) or trust_status == "error":
        return "error"
    if not statuses:
        return "unknown"
    if all(status in {"success", "skipped_fresh_cache"} for status in statuses):
        return "success"
    if any(status in {"success", "skipped_fresh_cache"} for status in statuses):
        return "degraded_enrichment"
    return statuses[-1] if statuses else "unknown"


def evidence_data_limitations(data: dict, trust: dict, rows: list[dict]) -> str:
    notes = _as_notes(data.get("data_source_notes"))
    trust_status = str(trust.get("status") or "unknown")
    if trust_status != "fresh":
        notes.append(f"資料可信度：{trust_status_label(trust_status)}。")
    stale_source_values = []
    for row in rows:
        row_map = _as_dict(row)
        if _safe_bool_flag(row_map.get("stale")):
            stale_source_values.append(row_map.get("source_label"))
    stale_sources = unique_evidence_texts(stale_source_values)
    if stale_sources:
        notes.append("過期來源：" + "、".join(stale_sources) + "。")
    critical = unique_evidence_texts([source_label(source) for source in trust.get("critical_failures", []) or []])
    if critical:
        notes.append("核心異常：" + "、".join(critical) + "。")
    return "；".join(notes) if notes else "未記錄額外資料限制。"
