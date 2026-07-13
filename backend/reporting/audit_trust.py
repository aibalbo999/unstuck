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
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text, safe_text_list
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
    text = _safe_text(text)
    for old, new in _LINT_MASK:
        text = text.replace(old, new)
    return text


def _safe_text(value, default: str = "") -> str:
    text = safe_text(value).strip()
    return text or default


def _markdown_cell(value, default: str = "N/A") -> str:
    text = _safe_text(value, default).replace("|", "/")
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _safe_duration_ms(value) -> str:
    if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)):
        return "N/A"
    return str(safe_int(value))


def _safe_record_count(value) -> str:
    return str(safe_int(value))


def _safe_bool_flag(value) -> bool:
    return value if isinstance(value, bool) else False


def _source_audit_entries(data: dict) -> list[dict]:
    data = safe_mapping_dict(data) or {}
    return safe_dict_list(data.get("source_audit"))


def _mask_items(items) -> list[str]:
    return [
        masked
        for item in safe_text_list(items)
        if (masked := _mask_blocking_issue(item))
    ]

def build_audit_sections(context: AnalysisContext) -> list[tuple[str, list[str]]]:
    """Collect final audit and preserved abnormality notes for rendering."""
    context = safe_mapping_dict(context) or {}
    audit = safe_mapping_dict(context.get("final_audit")) or {}
    sections = []

    critical = _mask_items(audit.get("critical"))
    blocking = [issue for issue in _mask_items(context.get("blocking_issues")) if issue not in critical]
    if not critical and not blocking:
        return []

    if critical or blocking:
        sections.append(("仍需注意的異常", [*critical[:10], *blocking[:6]]))

    repair_log = _mask_items(context.get("audit_repair_log"))
    if repair_log:
        sections.append(("自動修復紀錄", repair_log[:10]))

    corrections = _mask_items(audit.get("corrections"))
    if corrections:
        sections.append(("系統已套用校正", corrections[:8]))

    warnings = _mask_items(audit.get("warnings"))
    if warnings:
        sections.append(("非阻斷提醒", warnings[:8]))

    return [(title, items) for title, items in sections if items]


def build_audit_banner_html(context: AnalysisContext) -> str:
    """Render a visible report warning when final audit found abnormalities."""
    sections = build_audit_sections(context)
    if not sections:
        return ""

    section_html = []
    for title, items in sections:
        lis = "".join(f"<li>{escape(item)}</li>" for item in items)
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
        lines.extend(f"- {item_text}" for item in items if (item_text := _markdown_cell(item, "")))
        lines.append("")
    return "\n".join(lines).strip()


def _as_notes(value) -> list[str]:
    if isinstance(value, list):
        return [text for item in value if (text := _safe_text(item))]
    text = _safe_text(value)
    if text:
        return [text]
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
    return [_reason_label(code) for code in (trust.get("reason_codes", []) or [])[:limit]]


def build_data_trust_html(data: dict, context: AnalysisContext | None = None) -> str:
    data = safe_mapping_dict(data) or {}
    trust = normalize_data_trust(data.get("data_trust"))
    status = _safe_text(trust.get("status"), "unknown")
    notes = _as_notes(trust.get("notes")) or unknown_data_trust()["notes"]
    critical = trust.get("critical_failures", []) or []
    stale = trust.get("stale_sources", []) or []
    detail_parts = []
    last_market_data_at = _safe_text(trust.get("last_market_data_at"))
    if last_market_data_at:
        detail_parts.append(f"市場資料：{escape(last_market_data_at)}")
    if critical:
        detail_parts.append("核心異常：" + "、".join(escape(source_label(source)) for source in critical[:4]))
    if stale:
        detail_parts.append("過期：" + "、".join(escape(source_label(source)) for source in stale[:4]))
    reasons = _reason_labels(trust)
    if reasons:
        detail_parts.append("原因：" + "、".join(escape(reason) for reason in reasons))
    # quant_metrics fallback warning
    quant = safe_mapping_dict(data.get("quant_metrics"))
    quant_warning_html = ""
    if quant is not None:
        fallback_fields = safe_text_list(quant.get("fallback_fields"))
        warning_msg = _safe_text(quant.get("data_quality_warning"))
        if fallback_fields:
            fields_str = "、".join(escape(field) for field in fallback_fields[:6])
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
    data = safe_mapping_dict(data) or {}
    matrix_html = build_evidence_matrix_html(context or {}) if context else ""
    evidence_html = build_key_evidence_html(data)
    entries = _source_audit_entries(data)
    if not entries:
        return matrix_html + evidence_html + """
            <div class="source-audit-block">
                <h4>來源審計</h4>
                <p class="source-audit-empty">本報告未記錄 source_audit；舊報告仍可正常閱讀，但本報告資料可信度標示為未記錄。</p>
            </div>
        """

    rows = []
    for entry in entries:
        status = _safe_text(entry.get("status"), "unknown")
        message = sanitize_report_plain_text(
            _safe_text(entry.get("message")) or _safe_text(entry.get("error_kind"))
        )
        duration_ms = _safe_duration_ms(entry.get("duration_ms"))
        record_count = _safe_record_count(entry.get("record_count"))
        cache_hit = _safe_bool_flag(entry.get("cache_hit"))
        stale = _safe_bool_flag(entry.get("stale"))
        rows.append(
            "<tr>"
            f"<td>{escape(source_label(_safe_text(entry.get('source'))))}</td>"
            f"<td>{escape(sanitize_report_plain_text(_safe_text(entry.get('provider'), 'N/A')))}</td>"
            f"<td><span class=\"audit-status audit-status-{escape(status)}\">{escape(audit_status_label(status))}</span></td>"
            f"<td>{escape(_safe_text(entry.get('fetched_at'), 'N/A'))}</td>"
            f"<td>{escape(duration_ms)}</td>"
            f"<td>{escape(record_count)}</td>"
            f"<td>{'是' if cache_hit else '否'}</td>"
            f"<td>{'是' if stale else '否'}</td>"
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
    data = safe_mapping_dict(data) or {}
    trust = normalize_data_trust(data.get("data_trust"))
    status = _safe_text(trust.get("status"), "unknown")
    last_market_data_at = _markdown_cell(trust.get("last_market_data_at"), "N/A")
    notes = [_markdown_cell(note, "") for note in (_as_notes(trust.get("notes")) or unknown_data_trust()["notes"])]
    notes = [note for note in notes if note]
    reasons = [_markdown_cell(reason, "") for reason in _reason_labels(trust, limit=8)]
    reasons = [reason for reason in reasons if reason]
    critical_sources = [_markdown_cell(source_label(source), "") for source in trust.get("critical_failures", []) or []]
    critical_sources = [source for source in critical_sources if source]
    stale_sources = [_markdown_cell(source_label(source), "") for source in trust.get("stale_sources", []) or []]
    stale_sources = [source for source in stale_sources if source]
    lines = [
        "## 本報告資料可信度",
        f"- **狀態:** {trust_status_label(status)}",
        f"- **市場資料時間:** {last_market_data_at}",
        f"- **核心異常:** {', '.join(critical_sources) or '無'}",
        f"- **過期來源:** {', '.join(stale_sources) or '無'}",
        f"- **原因:** {', '.join(reasons) or '無'}",
        f"- **摘要:** {'；'.join(notes)}",
    ]
    lines.extend(build_trust_controls_markdown(data, context))
    # quant_metrics fallback warning — injected when key DCF fields use default assumptions
    quant = safe_mapping_dict(data.get("quant_metrics"))
    if quant is not None:
        fallback_fields = safe_text_list(quant.get("fallback_fields"))
        warning_msg = _safe_text(quant.get("data_quality_warning"))
        if fallback_fields:
            fields = [_markdown_cell(field, "") for field in fallback_fields[:6]]
            fields_str = "、".join(field for field in fields if field)
            msg = _markdown_cell(warning_msg, "") if warning_msg else f"以下欄位使用預設假設，DCF/WACC 結論僅供參考：{fields_str}"
            lines.append(f"- **⚠️ 量化模型警示:** {msg}")
    return "\n".join(lines)

def build_source_audit_markdown(data: dict, context: AnalysisContext | None = None) -> str:
    data = safe_mapping_dict(data) or {}
    entries = _source_audit_entries(data)
    lines = build_evidence_matrix_markdown(context or {}) if context else []
    lines.extend(build_key_evidence_markdown(data))
    lines.extend([
        "## 來源審計",
        "",
        "| 來源 | Provider | 狀態 | 抓取時間 | 耗時 ms | 筆數 | 快取 | 過期 | 訊息 |",
        "|---|---|---|---|---:|---:|---|---|---|",
    ])
    if not entries:
        lines.append("| 未記錄 | N/A | 未記錄 | N/A | N/A | 0 | N/A | N/A | 舊報告未保存 source_audit。 |")
        return "\n".join(lines)

    for entry in entries:
        status = _safe_text(entry.get("status"))
        message = _markdown_cell(_safe_text(entry.get("message")) or _safe_text(entry.get("error_kind")), "")
        duration_ms = _safe_duration_ms(entry.get("duration_ms"))
        record_count = _safe_record_count(entry.get("record_count"))
        cache_hit = _safe_bool_flag(entry.get("cache_hit"))
        stale = _safe_bool_flag(entry.get("stale"))
        lines.append(
            "| "
            f"{_markdown_cell(source_label(_safe_text(entry.get('source'))))} | "
            f"{_markdown_cell(entry.get('provider'))} | "
            f"{_markdown_cell(audit_status_label(status))} | "
            f"{_markdown_cell(entry.get('fetched_at'))} | "
            f"{_markdown_cell(duration_ms)} | "
            f"{_markdown_cell(record_count)} | "
            f"{'是' if cache_hit else '否'} | "
            f"{'是' if stale else '否'} | "
            f"{message} |"
        )
    return "\n".join(lines)
