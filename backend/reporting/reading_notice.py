"""User-facing report usage and quality-status notice."""

from __future__ import annotations

from html import escape
from typing import Any

from data_trust_scoring import normalize_data_trust, trust_status_label
from mapping_fields import safe_mapping_dict, safe_text, safe_text_list


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

_GENERIC_SNAPSHOT_INTEGRITY_ERRORS = {
    "資料快照完整性未通過，不能直接引用報告結論。",
}


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _gate(context: dict, key: str) -> dict:
    return _as_dict(dict.get(context, key))


def _gate_recorded(context: dict, key: str) -> bool:
    return key in context and safe_mapping_dict(dict.get(context, key)) is not None


def _status(value: Any, default: str = "") -> str:
    text = safe_text(value).strip()
    if not text:
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _snapshot_integrity(context: dict) -> dict:
    integrity = _gate(context, "snapshot_integrity")
    data = _as_dict(dict.get(context, "data"))
    nested_integrity = _as_dict(dict.get(data, "snapshot_integrity"))
    invalid_candidates = [
        candidate
        for candidate in (integrity, nested_integrity)
        if _snapshot_integrity_invalid(candidate)
    ]
    if invalid_candidates:
        return max(invalid_candidates, key=_snapshot_integrity_detail_specificity)
    return integrity or nested_integrity


def _snapshot_integrity_detail_specificity(integrity: dict) -> int:
    errors = safe_text_list(dict.get(integrity, "errors"))
    if not errors:
        text = safe_text(dict.get(integrity, "errors")).strip()
        errors = [text] if text else []
    errors = _unique_texts(errors)
    if _specific_snapshot_integrity_errors(errors):
        return 3
    if _snapshot_integrity_hash_mismatch_error(integrity):
        return 2
    if errors:
        return 1
    return 0


def _snapshot_integrity_invalid(integrity: dict) -> bool:
    status = _status(dict.get(integrity, "status")).lower()
    return status == "invalid" or dict.get(integrity, "valid") is False


def _snapshot_integrity_verified(integrity: dict) -> bool:
    return _status(dict.get(integrity, "status")).lower() == "verified"


def _snapshot_integrity_label(integrity: dict) -> str:
    if _snapshot_integrity_invalid(integrity):
        return "未通過"
    status = _status(dict.get(integrity, "status"), "not_recorded").lower()
    return {
        "verified": "已驗證",
        "unverified": "未驗證",
        "not_recorded": "未記錄",
        "": "未記錄",
    }.get(status, status or "未記錄")


def _snapshot_integrity_detail(integrity: dict) -> str:
    errors = safe_text_list(dict.get(integrity, "errors"))
    if not errors:
        text = safe_text(dict.get(integrity, "errors")).strip()
        errors = [text] if text else []
    mismatch_error = _snapshot_integrity_hash_mismatch_error(integrity)
    if not errors and mismatch_error:
        return mismatch_error
    errors = _unique_texts(errors)
    specific_errors = _specific_snapshot_integrity_errors(errors)
    if specific_errors:
        errors = specific_errors
    elif mismatch_error:
        return mismatch_error
    return "；".join(errors)


def _snapshot_integrity_hash_mismatch_error(integrity: dict) -> str:
    hash_value = safe_text(dict.get(integrity, "hash")).strip()
    expected_hash = safe_text(dict.get(integrity, "expected_hash")).strip()
    if hash_value and expected_hash and hash_value != expected_hash:
        return "snapshot_hash mismatch"
    return ""


def _specific_snapshot_integrity_errors(errors: list[str]) -> list[str]:
    return [error for error in errors if error not in _GENERIC_SNAPSHOT_INTEGRITY_ERRORS]


def _unique_texts(values: list[str]) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        value = _status(value)
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _quality_state(context: dict, trust: dict) -> str:
    conformance = _gate(context, "report_conformance")
    evidence = _gate(context, "evidence_exit_gate")
    content = _gate(context, "content_credibility")
    integrity = _snapshot_integrity(context)
    conformance_status = _status(dict.get(conformance, "status"))
    evidence_status = _status(dict.get(evidence, "verdict"))
    content_status = _status(dict.get(content, "status"))

    if _snapshot_integrity_invalid(integrity):
        return "blocked"
    if conformance_status in {"blocked", "failed", "rejected"}:
        return "blocked"
    if evidence_status in {"blocked", "failed", "rejected"} or content_status in {"blocked", "failed", "rejected"}:
        return "blocked"

    quality_gate_keys = ("report_conformance", "evidence_exit_gate", "content_credibility")
    has_quality_gate = any(
        _gate_recorded(context, key)
        for key in quality_gate_keys
    )
    if not has_quality_gate:
        return "pending"
    if not all(_gate_recorded(context, key) for key in quality_gate_keys):
        return "warning"
    if integrity and not _snapshot_integrity_verified(integrity):
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


def _notice_values(context: dict) -> dict[str, Any]:
    context = _as_dict(context)
    data = _as_dict(dict.get(context, "data"))
    trust = normalize_data_trust(dict.get(data, "data_trust"))
    evidence = _gate(context, "evidence_exit_gate")
    content = _gate(context, "content_credibility")
    conformance = _gate(context, "report_conformance")
    integrity = _snapshot_integrity(context)
    state = _quality_state(context, trust)
    state_note = _STATE_NOTES[state]
    integrity_detail = _snapshot_integrity_detail(integrity)
    if _snapshot_integrity_invalid(integrity) and integrity_detail:
        state_note = f"{state_note} {integrity_detail}"
    elif state == "warning" and integrity and not _snapshot_integrity_verified(integrity) and integrity_detail:
        state_note = f"{state_note} {integrity_detail}"
    checks = [
        ("資料可信度", trust_status_label(_status(dict.get(trust, "status"), "unknown"))),
        ("證據抽查", _evidence_label(_status(dict.get(evidence, "verdict"), "not_recorded"))),
        ("內容一致性", _content_label(_status(dict.get(content, "status"), "not_recorded"))),
        ("輸出契約", _conformance_label(_status(dict.get(conformance, "status"), "not_recorded"))),
    ]
    if integrity:
        checks.append(("資料快照完整性", _snapshot_integrity_label(integrity)))
    return {
        "state": state,
        "state_label": _STATE_LABELS[state],
        "state_note": state_note,
        "checks": checks,
    }


def build_report_reading_notice_html(context: dict) -> str:
    """Build a prominent, deterministic usage notice for the HTML report."""
    values = _notice_values(context)
    checks_html = "".join(
        f'<li><span>{escape(label)}</span><strong>{escape(value)}</strong></li>'
        for label, value in values["checks"]
    )
    return f"""
        <section class="report-reading-notice report-reading-notice-{escape(values['state'])}" aria-labelledby="report-reading-notice-title">
            <div class="report-reading-notice-head">
                <div>
                    <div class="report-reading-notice-kicker">使用前先看</div>
                    <h2 id="report-reading-notice-title">報告使用範圍與判讀限制</h2>
                </div>
                <span class="report-reading-notice-status">{escape(values['state_label'])}</span>
            </div>
            <p>本報告提供研究摘要、資料整理與情境分析，不是即時下單訊號，也不保證未來報酬。</p>
            <ul class="report-reading-notice-checks">{checks_html}</ul>
            <p class="report-reading-notice-note">{escape(values['state_note'])}</p>
        </section>
    """


def build_report_reading_notice_markdown(context: dict) -> str:
    """Build the Markdown counterpart of the report usage notice."""
    values = _notice_values(context)
    checks_markdown = "\n".join(
        f"- **{label}:** {value}"
        for label, value in values["checks"]
    )
    return "\n".join(
        [
            "## 報告使用範圍與判讀限制",
            "",
            f"- **品質 gate 狀態:** {values['state_label']}",
            "- **報告用途:** 本報告提供研究摘要、資料整理與情境分析，不是即時下單訊號，也不保證未來報酬。",
            checks_markdown,
            f"> {values['state_note']}",
        ]
    )
