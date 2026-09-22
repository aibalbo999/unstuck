"""Agent rewrite loop used by final audit repair."""

from __future__ import annotations

from analysis_types import AnalysisContext, StockData
from agent_catalog import AGENT_NAMES
from config import MAX_PER_JOB_REPAIR_ATTEMPTS
from llm_client import KeyRotator
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
from .repair_candidates import repair_candidate_call, observe_candidate, reject_candidate, validate_repair_candidate
from .repair_state import adopt_repair_result, repair_contract_issues
from .repair_transaction import preserve_failed_repair
from .cancellation import raise_if_cancelled
from .repair_attempt_limits import apply_429_fallback, increment_repair_attempt_count, per_job_repair_limit_fallback, repair_attempt_count
from .repair_reflection import (
    build_audit_reflection_instruction, build_audit_retry_instruction,
    generate_audit_reflection, generate_audit_reflection_async,
)
from .routing import get_audit_rewrite_model_sequence, is_agent_execution_failure
from .deferred import AgentDeferredError
from .single_agent import run_single_agent, run_single_agent_async
from .structured_repair_contracts import structured_output_missing as _structured_output_missing
from .trade_audit_source_contract import mark_audit_source_attempt


@preserve_failed_repair
def _repair_agent_output(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Synchronously ask the relevant agent to rewrite after final audit failure."""
    previous = capture_repair_context(context)
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    reject_candidate(context, agent_num, data, original_analysis, issues)
    try:
        raise_if_cancelled(context)
        limit_result = per_job_repair_limit_fallback(agent_num, data, context, original_analysis, list(issues))
        if limit_result is not None:
            return adopt_repair_result(agent_num, context, limit_result)
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
                return adopt_repair_result(agent_num, context, (True, f"{fallback_message}（模型修復暫不可用：429 熔斷中）"))
        current_issues = list(issues)
        last_result = None
        last_quality_issues = []
        remaining = max(0, MAX_PER_JOB_REPAIR_ATTEMPTS - repair_attempt_count(context, agent_num))
        for repair_attempt in range(min(2, remaining)):
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
                retry_instruction=build_audit_retry_instruction(agent_num, current_issues,
                    previous_text=last_result or context.get("analyses", {}).get(agent_num, ""), data=data),
                model_sequence=get_audit_rewrite_model_sequence(agent_num),
            )
            try:
                with repair_candidate_call(context, agent_num, data):
                    result = sanitize_model_output(run_single_agent(agent_num, data, context, rotator, max_retries=1))
                observe_candidate(context, agent_num, data, result)
                mark_audit_source_attempt(agent_num, context, current_issues)
                raise_if_cancelled(context)
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
                        return adopt_repair_result(agent_num, context, (True, f"{fallback_message}（模型修復暫不可用：429）"))
                return False, result
            fatal, quality_issues = validate_repair_candidate(agent_num, result, data, context,
                validators=(validate_prompt_leakage, validate_company_identity, validate_analysis_output),
                contract=repair_contract_issues)
            if fatal:
                return False, "；".join(fatal)
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                emit_log(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return adopt_repair_result(agent_num, context, (True, "已重寫並通過品質檢查"))
        if last_result:
            context["analyses"][agent_num] = last_result
        fallback_ok, fallback_message = record_quality_fallback(
            agent_num, data, context, original_analysis, current_issues, last_quality_issues, last_result
        )
        if fallback_ok:
            return adopt_repair_result(agent_num, context, (True, fallback_message))
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except AgentDeferredError:
        raise
    except Exception as exc:
        raise_if_cancelled(context)
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


@preserve_failed_repair
async def _repair_agent_output_async(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Asynchronously ask the relevant agent to rewrite after final audit failure."""
    previous = capture_repair_context(context)
    original_analysis = str(context.get("analyses", {}).get(agent_num, ""))
    reject_candidate(context, agent_num, data, original_analysis, issues)
    try:
        raise_if_cancelled(context)
        limit_result = per_job_repair_limit_fallback(agent_num, data, context, original_analysis, list(issues))
        if limit_result is not None:
            return adopt_repair_result(agent_num, context, limit_result)
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
                return adopt_repair_result(agent_num, context, (True, f"{fallback_message}（模型修復暫不可用：429 熔斷中）"))
        current_issues = list(issues)
        last_result = None
        last_quality_issues = []
        remaining = max(0, MAX_PER_JOB_REPAIR_ATTEMPTS - repair_attempt_count(context, agent_num))
        for repair_attempt in range(min(2, remaining)):
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
                retry_instruction=build_audit_retry_instruction(agent_num, current_issues,
                    previous_text=last_result or context.get("analyses", {}).get(agent_num, ""), data=data),
                model_sequence=get_audit_rewrite_model_sequence(agent_num),
            )
            try:
                with repair_candidate_call(context, agent_num, data):
                    result = sanitize_model_output(await run_single_agent_async(agent_num, data, context, rotator, max_retries=1))
                observe_candidate(context, agent_num, data, result)
                mark_audit_source_attempt(agent_num, context, current_issues)
                raise_if_cancelled(context)
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
                        return adopt_repair_result(agent_num, context, (True, f"{fallback_message}（模型修復暫不可用：429）"))
                return False, result
            fatal, quality_issues = validate_repair_candidate(agent_num, result, data, context,
                validators=(validate_prompt_leakage, validate_company_identity, validate_analysis_output),
                contract=repair_contract_issues)
            if fatal:
                return False, "；".join(fatal)
            if quality_issues:
                last_result = append_quality_warnings(agent_num, result, data)
                last_quality_issues = quality_issues
                current_issues = quality_issues
                emit_log(f"       ↳ 第 {repair_attempt + 1} 次重寫仍觸發品質紅線，改用紅線重新要求修復。")
                continue
            context["analyses"][agent_num] = strip_generated_audit_sections(result)
            _clear_agent_blocking_issues(context, agent_num)
            return adopt_repair_result(agent_num, context, (True, "已重寫並通過品質檢查"))
        if last_result:
            context["analyses"][agent_num] = last_result
        fallback_ok, fallback_message = record_quality_fallback(
            agent_num, data, context, original_analysis, current_issues, last_quality_issues, last_result
        )
        if fallback_ok:
            return adopt_repair_result(agent_num, context, (True, fallback_message))
        return False, "重寫後仍觸發品質紅線：" + "；".join(last_quality_issues[:3])
    except AgentDeferredError:
        raise
    except Exception as exc:
        raise_if_cancelled(context)
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
