"""Helpers for attaching deterministic audit notes to final agent output."""

from __future__ import annotations

from analysis_types import AnalysisContext, AuditResult
from pipeline_modes import get_structured_agent_num


def append_final_audit_section(context: AnalysisContext, audit: AuditResult) -> None:
    """Expose non-blocking final audit notes in the pipeline's final section."""
    if context.get("_final_audit_appended"):
        return
    final_agent = (
        get_structured_agent_num("recommendation", context)
        or get_structured_agent_num("trade_setup", context)
        or 7
    )
    if final_agent not in context.get("analyses", {}):
        return

    critical = audit.get("critical", [])
    warnings = audit.get("warnings", [])
    corrections = audit.get("corrections", [])
    repair_log = context.get("audit_repair_log", [])
    if not critical and not warnings and not corrections and not repair_log:
        return

    lines = ["## 系統最終稽核"]
    if critical:
        lines.append("### 仍需注意的異常")
        lines.extend(f"- {item}" for item in critical[:8])
    if repair_log:
        lines.append("### 自動修復紀錄")
        lines.extend(f"- {item}" for item in repair_log[:8])
    if corrections:
        lines.append("### 已套用校正")
        lines.extend(f"- {item}" for item in corrections[:8])
    if warnings:
        lines.append("### 非阻斷提醒")
        lines.extend(f"- {item}" for item in warnings[:8])
    context["analyses"][final_agent] = f"{context['analyses'][final_agent].rstrip()}\n\n" + "\n".join(lines)
    context["_final_audit_appended"] = True
