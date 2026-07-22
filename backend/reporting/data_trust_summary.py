"""Plain data-trust summary values for report renderers."""

from __future__ import annotations

from data_trust import normalize_data_trust, source_label, trust_status_label, unknown_data_trust
from mapping_fields import safe_mapping_dict, safe_text

from .text_tokens import is_missing_text_token


def _safe_text(value, default: str = "") -> str:
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return text


def _markdown_cell(value, default: str = "N/A") -> str:
    text = _safe_text(value, default).replace("|", "/")
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _as_notes(value) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := _safe_text(item))]
    text = _safe_text(value)
    if text:
        return [text]
    return []


def _reason_label(code: str) -> str:
    code = _safe_text(code)
    if not code:
        return ""
    source = ""
    if ":" in code:
        code, source = code.split(":", 1)
        source = _safe_text(source)
    labels = {
        "fresh_core_sources": "核心資料新鮮",
        "critical_sources_error": "核心來源異常",
        "missing_usable_critical_data": "缺少可用核心資料",
        "data_source_notes_present": "含資料口徑註記",
        "provider_sla_critical": "系統來源當時不穩",
        "provider_sla_core_health_notice": "核心來源穩定度提醒",
        "provider_sla_optional_critical": "補充來源穩定度提醒",
        "provider_sla_warning_note": "來源穩定度提醒",
        "missing_data_trust_snapshot": "未記錄報告資料狀態",
        "source_error": "來源異常",
        "source_stale": "來源過期",
        "optional_source_error": "補充來源異常",
        "optional_source_stale": "補充來源過期",
        "optional_source_degraded": "補充來源降級",
        "optional_source_not_configured": "補充來源未設定",
    }
    label = labels.get(code, code)
    if source:
        label = f"{label}：{source_label(source)}"
    return label


def _reason_labels(trust: dict, limit: int = 4) -> list[str]:
    return [label for code in (trust.get("reason_codes", []) or [])[:limit] if (label := _reason_label(code))]


def build_data_trust_summary(data: dict) -> dict:
    data = safe_mapping_dict(data) or {}
    trust = normalize_data_trust(data.get("data_trust"))
    status = _safe_text(trust.get("status"), "unknown")
    notes = _as_notes(trust.get("notes")) or unknown_data_trust()["notes"]
    critical = trust.get("critical_failures", []) or []
    stale = trust.get("stale_sources", []) or []
    last_market_data_at = _safe_text(trust.get("last_market_data_at"))
    detail_parts = []
    if last_market_data_at:
        detail_parts.append(f"市場資料：{last_market_data_at}")
    if critical:
        detail_parts.append("核心異常：" + "、".join(source_label(source) for source in critical[:4]))
    if stale:
        detail_parts.append("過期：" + "、".join(source_label(source) for source in stale[:4]))
    reasons = _reason_labels(trust)
    if reasons:
        detail_parts.append("原因：" + "、".join(reasons))
    return {
        "trust": trust,
        "status": status,
        "status_label": trust_status_label(status),
        "notes": notes,
        "detail_parts": detail_parts,
        "markdown_last_market_data_at": _markdown_cell(trust.get("last_market_data_at"), "N/A"),
        "markdown_notes": [_markdown_cell(note, "") for note in notes if _markdown_cell(note, "")],
        "markdown_reason_labels": [_markdown_cell(reason, "") for reason in _reason_labels(trust, limit=8)],
        "markdown_critical_sources": [_markdown_cell(source_label(source), "") for source in critical],
        "markdown_stale_sources": [_markdown_cell(source_label(source), "") for source in stale],
    }
