"""Split report rendering helper."""

from __future__ import annotations

from html import escape

from analysis_types import AnalysisContext
from mapping_fields import safe_mapping_dict
from .audit_banner import build_audit_banner_html, build_audit_markdown, build_audit_sections
from .data_trust_summary import build_data_trust_summary
from .quant_warning import build_quant_warning_html, build_quant_warning_markdown
from .source_audit import build_source_audit_html, build_source_audit_markdown
from .trust_controls import build_trust_controls_html, build_trust_controls_markdown


def build_data_trust_html(data: dict, context: AnalysisContext | None = None) -> str:
    data = safe_mapping_dict(data) or {}
    summary = build_data_trust_summary(data)
    status = summary["status"]
    detail_html = "".join(f"<span>{escape(part)}</span>" for part in summary["detail_parts"])
    notes_html = " ".join(escape(note) for note in summary["notes"][:2])
    trust_controls_html = build_trust_controls_html(data, context)
    return f"""
        <div class="data-trust-card data-trust-{escape(status)}">
            <div class="data-trust-head">
                <span class="data-trust-badge">{escape(summary["status_label"])}</span>
                <strong>本報告資料可信度</strong>
            </div>
            <div class="data-trust-notes">{notes_html}</div>
            <div class="data-trust-meta">{detail_html}</div>
            {trust_controls_html}
            {build_quant_warning_html(data)}
        </div>
    """

def build_data_trust_markdown(data: dict, context: AnalysisContext | None = None) -> str:
    data = safe_mapping_dict(data) or {}
    summary = build_data_trust_summary(data)
    reasons = [reason for reason in summary["markdown_reason_labels"] if reason]
    notes = [note for note in summary["markdown_notes"] if note]
    critical_sources = [source for source in summary["markdown_critical_sources"] if source]
    stale_sources = [source for source in summary["markdown_stale_sources"] if source]
    lines = [
        "## 本報告資料可信度",
        f"- **狀態:** {summary['status_label']}",
        f"- **市場資料時間:** {summary['markdown_last_market_data_at']}",
        f"- **核心異常:** {', '.join(critical_sources) or '無'}",
        f"- **過期來源:** {', '.join(stale_sources) or '無'}",
        f"- **原因:** {', '.join(reasons) or '無'}",
        f"- **摘要:** {'；'.join(notes)}",
    ]
    lines.extend(build_trust_controls_markdown(data, context))
    quant_warning = build_quant_warning_markdown(data)
    if quant_warning:
        lines.append(quant_warning)
    return "\n".join(lines)
