"""Agent rewrite loop used by final audit repair."""

from __future__ import annotations

from analysis_types import AnalysisContext, StockData
from agent_catalog import AGENT_NAMES
from llm_client import KeyRotator
from pipeline_modes import get_structured_agent_num
from runtime_events import emit_context_error, emit_context_error_async, emit_log
from validators import (
    append_quality_warnings,
    sanitize_model_output,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)

from .deterministic_fallbacks import _clear_agent_blocking_issues
from .repair_circuit_breaker import is_repair_429_error, record_repair_429_failure, repair_429_circuit_state
from .repair_context import capture_repair_context, install_repair_attempt_context, restore_repair_context
from .repair_quality_fallback import record_quality_fallback
from .repair_attempt_limits import apply_429_fallback, increment_repair_attempt_count, per_job_repair_limit_fallback
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
        get_structured_agent_num("trade_setup", context),
    }
    return agent_num in structured_agents and agent_num not in (context.get("structured_outputs", {}) or {})


def _repair_agent_output(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Synchronously ask the relevant agent to rewrite after final audit failure."""
    previous = capture_repair_context(context)
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    try:
        limit_result = per_job_repair_limit_fallback(agent_num, data, context, original_analysis, list(issues))
        if limit_result is not None:
            return limit_result
        open_state = repair_429_circuit_state(agent_num)
        if open_state.get("open"):
            fallback_ok, fallback_message = apply_429_fallback(
                agent_num,
                data,
                context,
                original_analysis,
                list(issues),
                "repair_429_circuit_open",
                str(open_state.get("last_error") or ""),
                {"circuit": open_state},
            )
            if fallback_ok:
                return True, f"{fallback_message}（模型修復暫不可用：429 熔斷中）"
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
            install_repair_attempt_context(
                context,
                agent_num,
                reflection_instruction=build_audit_reflection_instruction(reflection),
                retry_instruction=build_audit_retry_instruction(agent_num, current_issues),
                model_sequence=get_audit_model_sequence(),
            )
            try:
                result = sanitize_model_output(run_single_agent(agent_num, data, context, rotator, max_retries=1))
            finally:
                increment_repair_attempt_count(context, agent_num)
            if is_agent_execution_failure(result):
                if is_repair_429_error(result):
                    circuit = record_repair_429_failure(agent_num, result)
                    fallback_ok, fallback_message = apply_429_fallback(
                        agent_num,
                        data,
                        context,
                        original_analysis,
                        current_issues,
                        "repair_429_failure",
                        result,
                        {"circuit": circuit},
                    )
                    if fallback_ok:
                        return True, f"{fallback_message}（模型修復暫不可用：429）"
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
        fallback_ok, fallback_message = record_quality_fallback(
            agent_num, data, context, original_analysis, current_issues, last_quality_issues, last_result
        )
        if fallback_ok:
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
        restore_repair_context(context, previous)


async def _repair_agent_output_async(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Asynchronously ask the relevant agent to rewrite after final audit failure."""
    previous = capture_repair_context(context)
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    try:
        limit_result = per_job_repair_limit_fallback(agent_num, data, context, original_analysis, list(issues))
        if limit_result is not None:
            return limit_result
        open_state = repair_429_circuit_state(agent_num)
        if open_state.get("open"):
            fallback_ok, fallback_message = apply_429_fallback(
                agent_num,
                data,
                context,
                original_analysis,
                list(issues),
                "repair_429_circuit_open",
                str(open_state.get("last_error") or ""),
                {"circuit": open_state},
            )
            if fallback_ok:
                return True, f"{fallback_message}（模型修復暫不可用：429 熔斷中）"
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
            install_repair_attempt_context(
                context,
                agent_num,
                reflection_instruction=build_audit_reflection_instruction(reflection),
                retry_instruction=build_audit_retry_instruction(agent_num, current_issues),
                model_sequence=get_audit_model_sequence(),
            )
            try:
                result = sanitize_model_output(await run_single_agent_async(agent_num, data, context, rotator, max_retries=1))
            finally:
                increment_repair_attempt_count(context, agent_num)
            if is_agent_execution_failure(result):
                if is_repair_429_error(result):
                    circuit = record_repair_429_failure(agent_num, result)
                    fallback_ok, fallback_message = apply_429_fallback(
                        agent_num,
                        data,
                        context,
                        original_analysis,
                        current_issues,
                        "repair_429_failure",
                        result,
                        {"circuit": circuit},
                    )
                    if fallback_ok:
                        return True, f"{fallback_message}（模型修復暫不可用：429）"
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
        fallback_ok, fallback_message = record_quality_fallback(
            agent_num, data, context, original_analysis, current_issues, last_quality_issues, last_result
        )
        if fallback_ok:
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
        restore_repair_context(context, previous)
