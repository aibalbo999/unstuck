"""Per-job repair attempt counters and fallback routing."""

from __future__ import annotations

from analysis_types import AnalysisContext, StockData
from config import MAX_PER_JOB_REPAIR_ATTEMPTS
from runtime_events import emit_log

from .deterministic_fallbacks import _apply_deterministic_fallback


def repair_attempt_count(context: AnalysisContext, agent_num: int) -> int:
    repair_counts = context.get("repair_attempt_counts") or {}
    return int(repair_counts.get(int(agent_num), repair_counts.get(str(agent_num), 0)) or 0)


def increment_repair_attempt_count(context: AnalysisContext, agent_num: int) -> None:
    repair_counts = dict(context.get("repair_attempt_counts") or {})
    agent_key = int(agent_num)
    repair_counts[agent_key] = int(repair_counts.get(agent_key, repair_counts.get(str(agent_key), 0)) or 0) + 1
    context["repair_attempt_counts"] = repair_counts


def per_job_repair_limit_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    original_analysis: str,
    issues: list[str],
) -> tuple[bool, str] | None:
    attempts = repair_attempt_count(context, agent_num)
    if attempts < MAX_PER_JOB_REPAIR_ATTEMPTS:
        return None
    emit_log(f"Agent {agent_num} 已達 per-job 修復上限（{MAX_PER_JOB_REPAIR_ATTEMPTS}），改用 deterministic fallback。")
    fallback_ok, fallback_message = _apply_deterministic_fallback(
        agent_num,
        data,
        context,
        original_analysis,
        issues,
        "per_job_repair_limit",
        metadata={"attempts": attempts, "limit": MAX_PER_JOB_REPAIR_ATTEMPTS},
    )
    if fallback_ok:
        return True, f"{fallback_message}（per-job 修復上限 {MAX_PER_JOB_REPAIR_ATTEMPTS}）"
    return False, f"Agent {agent_num} 已達 per-job 修復上限（{MAX_PER_JOB_REPAIR_ATTEMPTS}），且 deterministic fallback 不可用。"


def apply_429_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    original_analysis: str,
    issues: list[str],
    trigger: str,
    raw_failure: str,
    metadata: dict,
) -> tuple[bool, str]:
    return _apply_deterministic_fallback(
        agent_num,
        data,
        context,
        original_analysis,
        issues,
        trigger,
        raw_failure=raw_failure,
        metadata=metadata,
    )
