# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from __future__ import annotations

from analysis_types import AnalysisContext, AuditResult, StockData
from agent_catalog import AGENT_NAMES
from final_audit import run_final_report_audit
from llm_client import KeyRotator
from pipeline_modes import get_structured_agent_num
from runtime_events import emit_context_error, emit_context_error_async, emit_context_event, emit_context_event_async, emit_log, make_runtime_event
from structured_outputs import parse_structured_data
from validators import (
    append_quality_warnings,
    sanitize_model_output,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)

from .deterministic_fallbacks import (
    _apply_deterministic_fallback,
    _clear_agent_blocking_issues,
    _deterministic_quality_fallback,
    _deterministic_structured_fallback,
    _record_deterministic_fallback,
)
from .prompt_config import FINAL_AUDIT_REPAIR_PASSES
from .repair_circuit_breaker import (
    clear_repair_429_circuit,
    is_repair_429_error,
    record_repair_429_failure,
    repair_429_circuit_state,
)
from .repair_reflection import (
    build_audit_reflection_instruction,
    build_audit_retry_instruction,
    generate_audit_reflection,
    generate_audit_reflection_async,
)
from .routing import get_audit_model_sequence, is_agent_execution_failure
from .single_agent import run_single_agent, run_single_agent_async


def _structured_output_missing(context: AnalysisContext, agent_num: int) -> bool:
    structured_agents = {
        get_structured_agent_num("moat", context),
        get_structured_agent_num("valuation", context),
        get_structured_agent_num("recommendation", context),
    }
    return agent_num in structured_agents and agent_num not in (context.get("structured_outputs", {}) or {})


def _repair_agent_output(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Synchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    try:
        open_state = repair_429_circuit_state(agent_num)
        if open_state.get("open"):
            fallback_ok, fallback_message = _apply_deterministic_fallback(
                agent_num,
                data,
                context,
                original_analysis,
                list(issues),
                "repair_429_circuit_open",
                raw_failure=str(open_state.get("last_error") or ""),
                metadata={"circuit": open_state},
            )
            if fallback_ok:
                return True, f"{fallback_message}（AI 修復不可用：429 熔斷中）"
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
            context.setdefault("structured_outputs", {}).pop(agent_num, None)
            result = run_single_agent(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                if is_repair_429_error(result):
                    circuit = record_repair_429_failure(agent_num, result)
                    fallback_ok, fallback_message = _apply_deterministic_fallback(
                        agent_num,
                        data,
                        context,
                        original_analysis,
                        current_issues,
                        "repair_429_failure",
                        raw_failure=result,
                        metadata={"circuit": circuit},
                    )
                    if fallback_ok:
                        return True, f"{fallback_message}（AI 修復不可用：429）"
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if not quality_issues and _structured_output_missing(context, agent_num):
                quality_issues = [f"Agent {agent_num} 未提供可解析 JSON 結構化輸出。"]
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
        fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, original_analysis)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, last_quality_issues or current_issues)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except Exception as exc:
        emit_context_error(
            context,
            "final_audit_repair_failed",
            exc,
            message=f"Agent {agent_num} 稽核修復失敗。",
            level="error",
            error_category="repair_failed",
            name=AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
            agent_num=agent_num,
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
        )
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


async def _repair_agent_output_async(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Asynchronously ask the relevant agent to rewrite after final audit failure."""
    previous_instruction = context.get("_audit_retry_instruction")
    previous_reflection_instruction = context.get("_audit_reflection_instruction")
    previous_model_override = context.get("_model_sequence_override")
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    try:
        open_state = repair_429_circuit_state(agent_num)
        if open_state.get("open"):
            fallback_ok, fallback_message = _apply_deterministic_fallback(
                agent_num,
                data,
                context,
                original_analysis,
                list(issues),
                "repair_429_circuit_open",
                raw_failure=str(open_state.get("last_error") or ""),
                metadata={"circuit": open_state},
            )
            if fallback_ok:
                return True, f"{fallback_message}（AI 修復不可用：429 熔斷中）"
        current_issues = list(issues)
        last_result = None
        last_quality_issues = []
        for repair_attempt in range(2):
            reflection = await generate_audit_reflection_async(
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
            context.setdefault("structured_outputs", {}).pop(agent_num, None)
            result = await run_single_agent_async(agent_num, data, context, rotator, max_retries=1)
            result = sanitize_model_output(result)
            if is_agent_execution_failure(result):
                if is_repair_429_error(result):
                    circuit = record_repair_429_failure(agent_num, result)
                    fallback_ok, fallback_message = _apply_deterministic_fallback(
                        agent_num,
                        data,
                        context,
                        original_analysis,
                        current_issues,
                        "repair_429_failure",
                        raw_failure=result,
                        metadata={"circuit": circuit},
                    )
                    if fallback_ok:
                        return True, f"{fallback_message}（AI 修復不可用：429）"
                return False, result
            prompt_issues = validate_prompt_leakage(result)
            identity_issues = validate_company_identity(result, data)
            if prompt_issues or identity_issues:
                return False, "；".join(prompt_issues + identity_issues)
            quality_issues = validate_analysis_output(agent_num, result, data)
            if not quality_issues and _structured_output_missing(context, agent_num):
                quality_issues = [f"Agent {agent_num} 未提供可解析 JSON 結構化輸出。"]
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
        fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, original_analysis)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, last_quality_issues or current_issues)
        if fallback_ok:
            _record_deterministic_fallback(
                context,
                agent_num,
                fallback_message,
                "quality_fallback_after_retries",
                issues=last_quality_issues or current_issues,
                raw_failure=last_result or "",
            )
            return True, fallback_message
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except Exception as exc:
        await emit_context_error_async(
            context,
            "final_audit_repair_failed",
            exc,
            message=f"Agent {agent_num} 稽核修復失敗。",
            level="error",
            error_category="repair_failed",
            name=AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
            agent_num=agent_num,
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
        )
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


def attempt_final_audit_repair(context: AnalysisContext, audit: AuditResult, rotator: KeyRotator, progress_callback=None):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    message = "最終稽核發現異常，嘗試請相關 Agent 自動重寫修復..."
    emit_log(f"  🛠️  {message}")
    emit_context_event(
        context,
        make_runtime_event(
            "status",
            phase="final_audit_repair",
            level="warning",
            message=message,
            current=context.get("agent_total"),
            total=context.get("agent_total"),
            name="最終稽核",
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
            metadata={"repair_agents": sorted(repair_requests)},
        ),
        progress_callback,
    )
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = _repair_agent_output(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        emit_log(f"     - {log}")
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_result",
                level="info" if ok else "error",
                message=log,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name=agent_name,
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"ok": ok},
            ),
            progress_callback,
        )


async def attempt_final_audit_repair_async(context: AnalysisContext, audit: AuditResult, rotator: KeyRotator, progress_callback=None):
    repair_requests = audit.get("repair_agent_issues", {}) or {}
    if not repair_requests:
        context.setdefault("audit_repair_log", []).append("最終稽核發現問題，但沒有可定位到單一 Agent 的自動重寫項目；報告會保留並標示異常。")
        return

    message = "最終稽核發現異常，嘗試請相關 Agent 非同步重寫修復..."
    emit_log(f"  🛠️  {message}")
    await emit_context_event_async(
        context,
        make_runtime_event(
            "status",
            phase="final_audit_repair",
            level="warning",
            message=message,
            current=context.get("agent_total"),
            total=context.get("agent_total"),
            name="最終稽核",
            pipeline_id=context.get("pipeline_id"),
            pipeline_label=context.get("pipeline_label"),
            metadata={"repair_agents": sorted(repair_requests)},
        ),
        progress_callback,
    )
    data = context.get("data", {})
    for agent_num in sorted(repair_requests):
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        ok, message = await _repair_agent_output_async(agent_num, data, context, rotator, repair_requests[agent_num])
        status = "成功" if ok else "失敗"
        log = f"{agent_name} AI 修復{status}：{message}"
        context.setdefault("audit_repair_log", []).append(log)
        emit_log(f"     - {log}")
        await emit_context_event_async(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_result",
                level="info" if ok else "error",
                message=log,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name=agent_name,
                agent_num=agent_num,
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"ok": ok},
            ),
            progress_callback,
        )


def _summarize_audit_issues(audit: AuditResult, limit: int = 3) -> str:
    issues = [str(item) for item in (audit.get("critical", []) or [])[:limit]]
    return "；".join(issues) if issues else "無可列示異常"


def finalize_final_audit(
    context: AnalysisContext,
    rotator: KeyRotator,
    max_repair_passes: int = FINAL_AUDIT_REPAIR_PASSES,
    progress_callback=None,
) -> AuditResult:
    """Run final audit, repair repairable failures, re-audit, then preserve report state."""
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

        message = f"最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪修復，完成後會重新稽核。"
        emit_log(f"  🧭 {message}")
        emit_context_event(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_pass",
                level="warning",
                message=message,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name="最終稽核",
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"repair_pass": repair_pass + 1, "max_repair_passes": max_repair_passes},
            ),
            progress_callback,
        )
        attempt_final_audit_repair(context, last_audit, rotator, progress_callback=progress_callback)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]


async def finalize_final_audit_async(
    context: AnalysisContext,
    rotator: KeyRotator,
    max_repair_passes: int = FINAL_AUDIT_REPAIR_PASSES,
    progress_callback=None,
) -> AuditResult:
    """Async final audit flow with repair and mandatory re-audit before rendering."""
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

        message = f"最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪非同步修復，完成後會重新稽核。"
        emit_log(f"  🧭 {message}")
        await emit_context_event_async(
            context,
            make_runtime_event(
                "status",
                phase="final_audit_repair_pass",
                level="warning",
                message=message,
                current=context.get("agent_total"),
                total=context.get("agent_total"),
                name="最終稽核",
                pipeline_id=context.get("pipeline_id"),
                pipeline_label=context.get("pipeline_label"),
                metadata={"repair_pass": repair_pass + 1, "max_repair_passes": max_repair_passes},
            ),
            progress_callback,
        )
        await attempt_final_audit_repair_async(context, last_audit, rotator, progress_callback=progress_callback)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]
