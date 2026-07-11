"""User-facing report usage and quality-status notice."""

from __future__ import annotations

from html import escape
from typing import Any

from data_trust_scoring import normalize_data_trust, trust_status_label


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
    return value if isinstance(value, dict) else {}


def _gate(context: dict, key: str) -> dict:
    return _as_dict(dict.get(context, key))


def _gate_recorded(context: dict, key: str) -> bool:
    return key in context and isinstance(dict.get(context, key), dict)


def _quality_state(context: dict, trust: dict) -> str:
    conformance = _gate(context, "report_conformance")
    evidence = _gate(context, "evidence_exit_gate")
    content = _gate(context, "content_credibility")
    conformance_status = str(dict.get(conformance, "status") or "")
    evidence_status = str(dict.get(evidence, "verdict") or "")
    content_status = str(dict.get(content, "status") or "")

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
    if (
        conformance_status != "passed"
        or evidence_status != "approved"
        or content_status != "passed"
        or str(dict.get(trust, "status") or "unknown") != "fresh"
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
    state = _quality_state(context, trust)
    return {
        "state": state,
        "state_label": _STATE_LABELS[state],
        "state_note": _STATE_NOTES[state],
        "checks": [
            ("資料可信度", trust_status_label(str(dict.get(trust, "status") or "unknown"))),
            ("證據抽查", _evidence_label(str(dict.get(evidence, "verdict") or "not_recorded"))),
            ("內容一致性", _content_label(str(dict.get(content, "status") or "not_recorded"))),
            ("輸出契約", _conformance_label(str(dict.get(conformance, "status") or "not_recorded"))),
        ],
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
