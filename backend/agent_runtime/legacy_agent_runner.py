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
from structured_outputs import parse_structured_data  # noqa: F401
from runtime_events import emit_log
from validators import (  # noqa: F401
    append_quality_warnings,
    sanitize_model_output,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)

from .audit_repair import *  # noqa: F401,F403
from .llm_calls import *  # noqa: F401,F403
from .pipeline_compat import *  # noqa: F401,F403
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
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    try:
        current_issues = list(issues)
        last_result = None
        last_quality_issues = []
        for repair_attempt in range(2):
            reflection = generate_audit_reflection(
                agent_num,
                current_issues,
                last_result or context.get("analyses", {}).get(agent_num, ""),
                data,
                rotator,
            )
            context["_audit_reflection_instruction"] = build_audit_reflection_instruction(reflection)
            context["_audit_retry_instruction"] = build_audit_retry_instruction(agent_num, current_issues)
            model_override = dict(context.get("_model_sequence_override", {}) or {})
            model_override[agent_num] = get_audit_model_sequence()
            context["_model_sequence_override"] = model_override
            context["structured_outputs"].pop(agent_num, None)
            result = run_single_agent(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                emit_log(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return True, "已重寫並通過品質檢查"
        if last_result:
            context["analyses"][agent_num] = last_result
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except Exception as exc:
        return False, str(exc)[:160]
    finally:
        if previous_instruction is None:
            context.pop("_audit_retry_instruction", None)
        else:
            context["_audit_retry_instruction"] = previous_instruction
        if previous_reflection_instruction is None:
            context.pop("_audit_reflection_instruction", None)
        else:
            context["_audit_reflection_instruction"] = previous_reflection_instruction
        if previous_model_override is None:
            context.pop("_model_sequence_override", None)
        else:
            context["_model_sequence_override"] = previous_model_override


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
