"""Source-audit table rendering for report trust sections."""

from __future__ import annotations

from html import escape

from analysis_types import AnalysisContext
from data_trust import audit_status_label, source_label
from mapping_fields import safe_dict_list, safe_int, safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number

from .evidence import build_key_evidence_html, build_key_evidence_markdown
from .evidence_matrix import build_evidence_matrix_html, build_evidence_matrix_markdown
from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def _safe_text(value, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    return default if is_missing_text_token(text) else text

def _markdown_cell(value, default: str = "N/A") -> str:
    text = _safe_text(value, default).replace("|", "/")
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _safe_duration_ms(value) -> str:
    return "N/A" if value is None or isinstance(value, (bool, bytes, bytearray, memoryview)) else str(safe_int(value))


def _safe_record_count(value) -> str:
    return str(safe_int(value))


def _safe_bool_flag(value) -> bool:
    return value if isinstance(value, bool) else False


def _source_audit_entries(data: dict) -> list[dict]:
    data = safe_mapping_dict(data) or {}
    return safe_dict_list(data.get("source_audit"))


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
        message = _markdown_cell(
            sanitize_report_plain_text(_safe_text(entry.get("message")) or _safe_text(entry.get("error_kind"))),
            "",
        )
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
