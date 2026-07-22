"""Deprecated compatibility module for legacy agent runtime imports."""

from agent_catalog import AGENT_NAMES  # noqa: F401
from assistant_tasks import (  # noqa: F401
    CONTEXT_DIGEST_TARGET_AGENTS,
    _format_previous,
    ensure_context_digest,
    ensure_context_digest_async,
    ensure_tear_sheet_summary,
    ensure_tear_sheet_summary_async,
)
from config import AGENT_MODELS  # noqa: F401
from final_audit import run_final_report_audit  # noqa: F401
from structured_output_parser import parse_structured_data  # noqa: F401
from runtime_events import emit_log
from validators import (  # noqa: F401
    append_quality_warnings,
    sanitize_model_output,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)

from . import audit_repair as _audit_repair
from .audit_repair import *  # noqa: F401,F403
from .llm_calls import *  # noqa: F401,F403
from .prompt_config import *  # noqa: F401,F403
from .prompting import *  # noqa: F401,F403
from .routing import *  # noqa: F401,F403
from .single_agent import *  # noqa: F401,F403


def _clear_agent_blocking_issues(context, agent_num):
    agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
    prefixes = (f"Agent {agent_num} ", f"Agent {agent_num}: ", f"{agent_name}: ")
    context["blocking_issues"] = [
        issue for issue in context.get("blocking_issues", [])
        if not str(issue).startswith(prefixes)
    ]
    if not context["blocking_issues"]:
        context.pop("blocking_issues", None)


def _repair_agent_output(agent_num, data, context, rotator, issues):
    previous = _audit_repair.run_single_agent
    _audit_repair.run_single_agent = run_single_agent
    try:
        return _audit_repair._repair_agent_output(agent_num, data, context, rotator, issues)
    finally:
        _audit_repair.run_single_agent = previous


def attempt_final_audit_repair(context, audit, rotator):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    emit_log("  🛠️  最終稽核發現異常，嘗試請相關 Agent 自動重寫修復...")
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = _repair_agent_output(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        emit_log(f"     - {log}")


def _summarize_audit_issues(audit, limit: int = 3) -> str:
    issues = [str(item) for item in (audit.get("critical", []) or [])[:limit]]
    return "；".join(issues) if issues else "無可列示異常"


def finalize_final_audit(context, rotator, max_repair_passes=FINAL_AUDIT_REPAIR_PASSES):
    last_audit = None
    for repair_pass in range(max_repair_passes + 1):
        context["parsed"] = parse_structured_data(context)
        last_audit = run_final_report_audit(context, append_section=False)
        if not last_audit.get("critical"):
            context["final_audit"] = run_final_report_audit(context, append_section=True)
            return context["final_audit"]

        if repair_pass >= max_repair_passes:
            remaining = _summarize_audit_issues(last_audit)
            context.setdefault("audit_repair_log", []).append(
                f"最終稽核自動修復已達 {max_repair_passes} 輪上限；報告會保留並標示剩餘異常：{remaining}"
            )
            break

        emit_log(f"  🧭 最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪修復，完成後會重新稽核。")
        attempt_final_audit_repair(context, last_audit, rotator)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]
