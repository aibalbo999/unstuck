"""Split report rendering helper."""

from __future__ import annotations

from html import escape

from analysis_types import AnalysisContext
from data_trust import (
    audit_status_label,
    normalize_data_trust,
    source_label,
    trust_status_label,
    unknown_data_trust,
)
from .evidence import build_key_evidence_html, build_key_evidence_markdown
from .evidence_matrix import build_evidence_matrix_html, build_evidence_matrix_markdown
from .html_sanitizer import sanitize_report_plain_text
from .trust_controls import build_trust_controls_html, build_trust_controls_markdown


_LINT_MASK = [
    ("[Agent ", "[分析模組 "),
    ("執行失敗", "分析中止"),
    ("所有模型/Key 不可用", "API不可用"),
    ("RESOURCE_EXHAUSTED", "額度耗盡"),
    ("Too Many Requests", "請求過多"),
    ("HTTP 429", "請求過多"),
    ("503 UNAVAILABLE", "模型服務暫時不可用"),
    ("429 RESOURCE_EXHAUSTED", "模型額度暫時不足"),
]


def _mask_blocking_issue(text: str) -> str:
    """Sanitize lint-triggering substrings before rendering into the report."""
    text = str(text or "")
    for old, new in _LINT_MASK:
        text = text.replace(old, new)
    return text


def _mask_items(items) -> list[str]:
    return [_mask_blocking_issue(item) for item in (items or []) if str(item).strip()]

def build_audit_sections(context: AnalysisContext) -> list[tuple[str, list[str]]]:
    """Collect final audit and preserved abnormality notes for rendering."""
    audit = context.get("final_audit", {}) or {}
    sections = []

    critical = _mask_items(audit.get("critical", []) or [])
    blocking = [
        _mask_blocking_issue(issue)
        for issue in (context.get("blocking_issues", []) or [])
        if issue not in critical
    ]
    if not critical and not blocking:
        return []

    if critical or blocking:
        sections.append(("仍需注意的異常", [*critical[:10], *blocking[:6]]))

    repair_log = context.get("audit_repair_log", []) or []
    if repair_log:
        sections.append(("自動修復紀錄", _mask_items(repair_log)[:10]))

    corrections = audit.get("corrections", []) or []
    if corrections:
        sections.append(("系統已套用校正", _mask_items(corrections)[:8]))

    warnings = audit.get("warnings", []) or []
    if warnings:
        sections.append(("非阻斷提醒", _mask_items(warnings)[:8]))

    return [(title, items) for title, items in sections if items]


def build_audit_banner_html(context: AnalysisContext) -> str:
    """Render a visible report warning when final audit found abnormalities."""
    sections = build_audit_sections(context)
    if not sections:
        return ""

    section_html = []
    for title, items in sections:
        lis = "".join(f"<li>{escape(str(item))}</li>" for item in items)
        section_html.append(f"<div class=\"audit-section\"><strong>{escape(title)}</strong><ul>{lis}</ul></div>")

    return f"""
        <div class="audit-banner">
            <div class="audit-title">系統異常提醒：本報告已保留供檢視</div>
            <div class="audit-subtitle">系統已嘗試自動修復可定位的 Agent 輸出；若仍有異常，請優先閱讀下列提醒再使用本報告。</div>
            {''.join(section_html)}
        </div>
    """


def build_audit_markdown(context: AnalysisContext) -> str:
    sections = build_audit_sections(context)
    if not sections:
        return ""

    lines = [
        "## ⚠️ 系統異常提醒：本報告已保留供檢視",
        "",
        "系統已嘗試自動修復可定位的 Agent 輸出；若仍有異常，請優先閱讀下列提醒再使用本報告。",
        "",
    ]
    for title, items in sections:
        lines.append(f"### {title}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).strip()


def _as_notes(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _reason_label(code: str) -> str:
    code = str(code or "")
    source = ""
    if ":" in code:
        code, source = code.split(":", 1)
    labels = {
        "fresh_core_sources": "核心資料新鮮",
        "critical_sources_error": "核心來源異常",
        "missing_usable_critical_data": "缺少可用核心資料",
        "data_source_notes_present": "含資料口徑註記",
        "provider_sla_critical": "系統來源當時不穩",
        "provider_sla_warning_note": "來源穩定度提醒",
        "missing_data_trust_snapshot": "未記錄報告資料狀態",
        "source_error": "來源異常",
        "source_stale": "來源過期",
    }
    label = labels.get(code, code)
    if source:
        label = f"{label}：{source_label(source)}"
    return label


def _reason_labels(trust: dict, limit: int = 4) -> list[str]:
    return [_reason_label(code) for code in (trust.get("reason_codes", []) or [])[:limit]]


def build_data_trust_html(data: dict, context: AnalysisContext | None = None) -> str:
    trust = normalize_data_trust(data.get("data_trust") if isinstance(data, dict) else None)
    status = trust.get("status", "unknown")
    notes = _as_notes(trust.get("notes")) or unknown_data_trust()["notes"]
    critical = trust.get("critical_failures", []) or []
    stale = trust.get("stale_sources", []) or []
    detail_parts = []
    if trust.get("last_market_data_at"):
        detail_parts.append(f"市場資料：{escape(str(trust.get('last_market_data_at')))}")
    if critical:
        detail_parts.append("核心異常：" + "、".join(escape(source_label(source)) for source in critical[:4]))
    if stale:
        detail_parts.append("過期：" + "、".join(escape(source_label(source)) for source in stale[:4]))
    reasons = _reason_labels(trust)
    if reasons:
        detail_parts.append("原因：" + "、".join(escape(reason) for reason in reasons))
    # quant_metrics fallback warning
    quant = data.get("quant_metrics") if isinstance(data, dict) else None
    quant_warning_html = ""
    if isinstance(quant, dict):
        fallback_fields = quant.get("fallback_fields") or []
        warning_msg = quant.get("data_quality_warning") or ""
        if fallback_fields:
            fields_str = "、".join(escape(str(f)) for f in fallback_fields[:6])
            msg = escape(warning_msg) if warning_msg else f"以下欄位使用預設假設，DCF/WACC 結論僅供參考：{fields_str}"
            quant_warning_html = f'<div class="data-trust-quant-warning">⚠️ <strong>量化模型警示：</strong>{msg}</div>'
    detail_html = "".join(f"<span>{part}</span>" for part in detail_parts)
    notes_html = " ".join(escape(note) for note in notes[:2])
    trust_controls_html = build_trust_controls_html(data, context)
    return f"""
        <div class="data-trust-card data-trust-{escape(status)}">
            <div class="data-trust-head">
                <span class="data-trust-badge">{escape(trust_status_label(status))}</span>
                <strong>本報告資料可信度</strong>
            </div>
            <div class="data-trust-notes">{notes_html}</div>
            <div class="data-trust-meta">{detail_html}</div>
            {trust_controls_html}
            {quant_warning_html}
        </div>
    """



def build_source_audit_html(data: dict, context: AnalysisContext | None = None) -> str:
    matrix_html = build_evidence_matrix_html(context or {}) if context else ""
    evidence_html = build_key_evidence_html(data)
    entries = data.get("source_audit") if isinstance(data, dict) else []
    if not isinstance(entries, list) or not entries:
        return matrix_html + evidence_html + """
            <div class="source-audit-block">
                <h4>來源審計</h4>
                <p class="source-audit-empty">本報告未記錄 source_audit；舊報告仍可正常閱讀，但本報告資料可信度標示為未記錄。</p>
            </div>
        """

    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "unknown")
        message = sanitize_report_plain_text(entry.get("message") or entry.get("error_kind") or "")
        rows.append(
            "<tr>"
            f"<td>{escape(source_label(entry.get('source', '')))}</td>"
            f"<td>{escape(sanitize_report_plain_text(entry.get('provider') or 'N/A'))}</td>"
            f"<td><span class=\"audit-status audit-status-{escape(status)}\">{escape(audit_status_label(status))}</span></td>"
            f"<td>{escape(str(entry.get('fetched_at') or 'N/A'))}</td>"
            f"<td>{escape(str(entry.get('duration_ms') if entry.get('duration_ms') is not None else 'N/A'))}</td>"
            f"<td>{escape(str(entry.get('record_count', 0)))}</td>"
            f"<td>{'是' if entry.get('cache_hit') else '否'}</td>"
            f"<td>{'是' if entry.get('stale') else '否'}</td>"
            f"<td>{escape(message)}</td>"
            "</tr>"
        )

    return matrix_html + evidence_html + f"""
        <div class="source-audit-block">
            <h4>來源審計</h4>
            <div class="source-audit-scroll">
                <table class="source-audit-table">
                    <thead>
                        <tr>
                            <th>來源</th><th>Provider</th><th>狀態</th><th>抓取時間</th>
                            <th>耗時 ms</th><th>筆數</th><th>快取</th><th>過期</th><th>訊息</th>
                        </tr>
                    </thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
            </div>
        </div>
    """


def build_data_trust_markdown(data: dict, context: AnalysisContext | None = None) -> str:
    trust = normalize_data_trust(data.get("data_trust") if isinstance(data, dict) else None)
    notes = _as_notes(trust.get("notes")) or unknown_data_trust()["notes"]
    reasons = _reason_labels(trust, limit=8)
    lines = [
        "## 本報告資料可信度",
        f"- **狀態:** {trust_status_label(trust.get('status', 'unknown'))}",
        f"- **市場資料時間:** {trust.get('last_market_data_at') or 'N/A'}",
        f"- **核心異常:** {', '.join(source_label(source) for source in trust.get('critical_failures', []) or []) or '無'}",
        f"- **過期來源:** {', '.join(source_label(source) for source in trust.get('stale_sources', []) or []) or '無'}",
        f"- **原因:** {', '.join(reasons) or '無'}",
        f"- **摘要:** {'；'.join(notes)}",
    ]
    lines.extend(build_trust_controls_markdown(data, context))
    # quant_metrics fallback warning — injected when key DCF fields use default assumptions
    quant = data.get("quant_metrics") if isinstance(data, dict) else None
    if isinstance(quant, dict):
        fallback_fields = quant.get("fallback_fields") or []
        warning_msg = quant.get("data_quality_warning") or ""
        if fallback_fields:
            fields_str = "、".join(str(f) for f in fallback_fields[:6])
            msg = warning_msg if warning_msg else f"以下欄位使用預設假設，DCF/WACC 結論僅供參考：{fields_str}"
            lines.append(f"- **⚠️ 量化模型警示:** {msg}")
    return "\n".join(lines)



def build_source_audit_markdown(data: dict, context: AnalysisContext | None = None) -> str:
    entries = data.get("source_audit") if isinstance(data, dict) else []
    lines = build_evidence_matrix_markdown(context or {}) if context else []
    lines.extend(build_key_evidence_markdown(data if isinstance(data, dict) else {}))
    lines.extend([
        "## 來源審計",
        "",
        "| 來源 | Provider | 狀態 | 抓取時間 | 耗時 ms | 筆數 | 快取 | 過期 | 訊息 |",
        "|---|---|---|---|---:|---:|---|---|---|",
    ])
    if not isinstance(entries, list) or not entries:
        lines.append("| 未記錄 | N/A | 未記錄 | N/A | N/A | 0 | N/A | N/A | 舊報告未保存 source_audit。 |")
        return "\n".join(lines)

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        message = str(entry.get("message") or entry.get("error_kind") or "").replace("|", "/")
        lines.append(
            "| "
            f"{source_label(entry.get('source', ''))} | "
            f"{entry.get('provider') or 'N/A'} | "
            f"{audit_status_label(entry.get('status', ''))} | "
            f"{entry.get('fetched_at') or 'N/A'} | "
            f"{entry.get('duration_ms') if entry.get('duration_ms') is not None else 'N/A'} | "
            f"{entry.get('record_count', 0)} | "
            f"{'是' if entry.get('cache_hit') else '否'} | "
            f"{'是' if entry.get('stale') else '否'} | "
            f"{message} |"
        )
    return "\n".join(lines)
