"""Decision values for report reading notices."""

from __future__ import annotations

from typing import Any

from data_trust_scoring import normalize_data_trust, trust_status_label
from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number

from .snapshot_integrity_notice import (
    snapshot_integrity,
    snapshot_integrity_detail,
    snapshot_integrity_invalid,
    snapshot_integrity_label,
    snapshot_integrity_verified,
)
from .text_tokens import is_missing_text_token


_STATE_LABELS = {
    "pending": "品質 gate 尚未記錄",
    "warning": "品質 gate 有警示",
    "blocked": "品質 gate 未通過",
    "passed": "已通過已知檢查",
}

_STATE_NOTES = {
    "pending": "目前沒有完整的報告品質 gate 紀錄，請先人工核對來源與限制；請勿把結論當成可執行指令。",
    "warning": "報告仍可供研究，但請先查看警示與來源審計，再引用報告結論。",
    "blocked": "報告存在阻斷問題，先處理品質警示，再引用報告結論。",
    "passed": "綠燈只代表已知自動檢查通過，不代表投資語意一定正確，也不代表未來結果有保證。",
}


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _gate(context: dict, key: str) -> dict:
    return _as_dict(dict.get(context, key))


def _gate_recorded(context: dict, key: str) -> bool:
    return key in context and safe_mapping_dict(dict.get(context, key)) is not None


def _status(value: Any, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _quality_state(context: dict, trust: dict) -> str:
    conformance = _gate(context, "report_conformance")
    evidence = _gate(context, "evidence_exit_gate")
    content = _gate(context, "content_credibility")
    integrity = snapshot_integrity(context)
    conformance_status = _status(dict.get(conformance, "status"))
    evidence_status = _status(dict.get(evidence, "verdict"))
    content_status = _status(dict.get(content, "status"))

    if snapshot_integrity_invalid(integrity):
        return "blocked"
    if conformance_status in {"blocked", "failed", "rejected"}:
        return "blocked"
    if evidence_status in {"blocked", "failed", "rejected"} or content_status in {"blocked", "failed", "rejected"}:
        return "blocked"

    quality_gate_keys = ("report_conformance", "evidence_exit_gate", "content_credibility")
    has_quality_gate = any(_gate_recorded(context, key) for key in quality_gate_keys)
    if not has_quality_gate:
        return "pending"
    if not all(_gate_recorded(context, key) for key in quality_gate_keys):
        return "warning"
    if integrity and not snapshot_integrity_verified(integrity):
        return "warning"
    if (
        conformance_status != "passed"
        or evidence_status != "approved"
        or content_status != "passed"
        or _status(dict.get(trust, "status"), "unknown") != "fresh"
    ):
        return "warning"
    return "passed"


def _evidence_label(verdict: str) -> str:
    return {
        "approved": "已通過",
        "rejected": "拒絕",
        "caution": "需人工確認",
        "warning": "需人工確認",
        "not_recorded": "未記錄",
        "": "未記錄",
    }.get(verdict, verdict or "未記錄")


def _content_label(status: str) -> str:
    return {
        "passed": "已通過",
        "blocked": "阻斷",
        "warning": "有警示",
        "not_recorded": "未記錄",
        "": "未記錄",
    }.get(status, status or "未記錄")


def _conformance_label(status: str) -> str:
    return {
        "passed": "已通過",
        "blocked": "阻斷",
        "warning": "有警示",
        "not_recorded": "未記錄",
        "": "未記錄",
    }.get(status, status or "未記錄")


def build_report_reading_notice_values(context: dict) -> dict[str, Any]:
    """Build deterministic user-facing state values for report reading notices."""
    context = _as_dict(context)
    data = _as_dict(dict.get(context, "data"))
    trust = normalize_data_trust(dict.get(data, "data_trust"))
    evidence = _gate(context, "evidence_exit_gate")
    content = _gate(context, "content_credibility")
    conformance = _gate(context, "report_conformance")
    integrity = snapshot_integrity(context)
    state = _quality_state(context, trust)
    state_note = _STATE_NOTES[state]
    integrity_detail = snapshot_integrity_detail(integrity)
    if snapshot_integrity_invalid(integrity) and integrity_detail:
        state_note = f"{state_note} {integrity_detail}"
    elif state == "warning" and integrity and not snapshot_integrity_verified(integrity) and integrity_detail:
        state_note = f"{state_note} {integrity_detail}"
    checks = [
        ("資料可信度", trust_status_label(_status(dict.get(trust, "status"), "unknown"))),
        ("證據抽查", _evidence_label(_status(dict.get(evidence, "verdict"), "not_recorded"))),
        ("內容一致性", _content_label(_status(dict.get(content, "status"), "not_recorded"))),
        ("輸出契約", _conformance_label(_status(dict.get(conformance, "status"), "not_recorded"))),
    ]
    if integrity:
        checks.append(("資料快照完整性", snapshot_integrity_label(integrity)))
    return {
        "state": state,
        "state_label": _STATE_LABELS[state],
        "state_note": state_note,
        "checks": checks,
    }
