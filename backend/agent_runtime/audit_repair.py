"""Final audit orchestration and repair compatibility facade."""

from __future__ import annotations

from analysis_types import AnalysisContext, AuditResult, StockData
from agent_catalog import AGENT_NAMES
from final_audit import run_final_report_audit
from llm_client import KeyRotator
from runtime_events import emit_context_event, emit_context_event_async, emit_log, make_runtime_event
from structured_outputs import parse_structured_data

from . import repair_loop as _repair_loop
from .deterministic_fallbacks import (
    _deterministic_quality_fallback,
    _deterministic_structured_fallback,
)
from .prompt_config import FINAL_AUDIT_REPAIR_PASSES
from .repair_circuit_breaker import clear_repair_429_circuit
from .single_agent import run_single_agent, run_single_agent_async


def _structured_output_missing(context: AnalysisContext, agent_num: int) -> bool:
    return _repair_loop._structured_output_missing(context, agent_num)


def _repair_agent_output(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Compatibility wrapper; the implementation lives in repair_loop."""
    previous = _repair_loop.run_single_agent
    _repair_loop.run_single_agent = run_single_agent
    try:
        return _repair_loop._repair_agent_output(agent_num, data, context, rotator, issues)
    finally:
        _repair_loop.run_single_agent = previous


async def _repair_agent_output_async(agent_num: int, data: StockData, context: AnalysisContext, rotator: KeyRotator, issues: list[str]) -> tuple[bool, str]:
    """Compatibility wrapper; the implementation lives in repair_loop."""
    previous = _repair_loop.run_single_agent_async
    _repair_loop.run_single_agent_async = run_single_agent_async
    try:
        return await _repair_loop._repair_agent_output_async(agent_num, data, context, rotator, issues)
    finally:
        _repair_loop.run_single_agent_async = previous


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
        _record_repair_result(context, progress_callback, agent_num, agent_name, ok, message)


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
        await _record_repair_result_async(context, progress_callback, agent_num, agent_name, ok, message)


def _record_repair_result(context: AnalysisContext, progress_callback, agent_num: int, agent_name: str, ok: bool, message: str) -> None:
    status = "成功" if ok else "失敗"
    log = f"{agent_name} AI 修復{status}：{message}"
    context.setdefault("audit_repair_log", []).append(log)
    emit_log(f"     - {log}")
    emit_context_event(
        context,
        _repair_result_event(context, agent_num, agent_name, ok, log),
        progress_callback,
    )


async def _record_repair_result_async(context: AnalysisContext, progress_callback, agent_num: int, agent_name: str, ok: bool, message: str) -> None:
    status = "成功" if ok else "失敗"
    log = f"{agent_name} AI 修復{status}：{message}"
    context.setdefault("audit_repair_log", []).append(log)
    emit_log(f"     - {log}")
    await emit_context_event_async(
        context,
        _repair_result_event(context, agent_num, agent_name, ok, log),
        progress_callback,
    )


def _repair_result_event(context: AnalysisContext, agent_num: int, agent_name: str, ok: bool, log: str) -> dict:
    return make_runtime_event(
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
            _record_repair_limit(context, last_audit, max_repair_passes)
            break

        _emit_repair_pass(context, progress_callback, repair_pass, max_repair_passes, is_async=False)
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
            _record_repair_limit(context, last_audit, max_repair_passes)
            break

        await _emit_repair_pass_async(context, progress_callback, repair_pass, max_repair_passes)
        await attempt_final_audit_repair_async(context, last_audit, rotator, progress_callback=progress_callback)
        if not last_audit.get("repair_agent_issues"):
            break

    context["parsed"] = parse_structured_data(context)
    context["final_audit"] = run_final_report_audit(context, append_section=True)
    return context["final_audit"]


def _record_repair_limit(context: AnalysisContext, audit: AuditResult, max_repair_passes: int) -> None:
    remaining = _summarize_audit_issues(audit)
    context.setdefault("audit_repair_log", []).append(
        f"最終稽核自動修復已達 {max_repair_passes} 輪上限；報告會保留並標示剩餘異常：{remaining}"
    )


def _repair_pass_event(context: AnalysisContext, repair_pass: int, max_repair_passes: int, *, is_async: bool) -> dict:
    async_label = "非同步" if is_async else ""
    return make_runtime_event(
        "status",
        phase="final_audit_repair_pass",
        level="warning",
        message=f"最終稽核第 {repair_pass + 1}/{max_repair_passes} 輪{async_label}修復，完成後會重新稽核。",
        current=context.get("agent_total"),
        total=context.get("agent_total"),
        name="最終稽核",
        pipeline_id=context.get("pipeline_id"),
        pipeline_label=context.get("pipeline_label"),
        metadata={"repair_pass": repair_pass + 1, "max_repair_passes": max_repair_passes},
    )


def _emit_repair_pass(context: AnalysisContext, progress_callback, repair_pass: int, max_repair_passes: int, *, is_async: bool) -> None:
    event = _repair_pass_event(context, repair_pass, max_repair_passes, is_async=is_async)
    emit_log(f"  🧭 {event['message']}")
    emit_context_event(context, event, progress_callback)


async def _emit_repair_pass_async(context: AnalysisContext, progress_callback, repair_pass: int, max_repair_passes: int) -> None:
    event = _repair_pass_event(context, repair_pass, max_repair_passes, is_async=True)
    emit_log(f"  🧭 {event['message']}")
    await emit_context_event_async(context, event, progress_callback)
