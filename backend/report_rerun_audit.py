"""Bounded audit for final-only reruns; prior analyses are never repair targets."""

from __future__ import annotations

from fastapi import HTTPException

from analysis_dependencies import stale_agent_numbers, upstream_input_hash
from agent_runtime import audit_repair
from agent_runtime.cancellation import raise_if_cancelled
from agent_runtime.repair_transaction import repair_requests
from agent_runtime.routing import is_agent_execution_failure


class FinalRerunQualityBlockedError(HTTPException):
    """Keep the HTTP 409 contract while identifying a terminal quality failure."""
    def __init__(self, detail: str):
        self.issues = [detail]
        super().__init__(status_code=409, detail=detail)


def _require_final_output(context: dict, final_agent: int, prior_hash: str) -> None:
    raise_if_cancelled(context)
    if upstream_input_hash(final_agent, context) != prior_hash:
        raise HTTPException(status_code=409, detail="前序分析在局部重跑期間變動；請使用完整重跑產生一致報告。")
    text = (context.get("analyses") or {}).get(final_agent, "")
    if (not isinstance(text, str) or not text.strip() or is_agent_execution_failure(text)
            or context.get("blocking_issues") or context.get("status") == "blocked"):
        raise FinalRerunQualityBlockedError("最終建議生成或品質檢查未完成，未產生新報告；請稍後重試或完整重跑。")


def _require_final_only_repair(context: dict, audit: dict, final_agent: int) -> None:
    upstream = {int(agent) for agent in (audit.get("repair_agent_issues") or {}) if int(agent) != final_agent}
    upstream.update(agent for agent in stale_agent_numbers(context) if agent != final_agent)
    if upstream:
        raise FinalRerunQualityBlockedError(f"稽核需要更正前序 Agent {sorted(upstream)}；只重跑最終建議不能修改上游，請使用完整重跑。")


async def run_final_rerun_audit(context: dict, final_agent: int, rotator, *, run_agent, parse, audit, progress_callback=None) -> dict:
    """Use existing bounded repair policy, restricting every request to final_agent."""
    prior_hash = upstream_input_hash(final_agent, context)
    await run_agent(final_agent, context["data"], context, rotator)
    _require_final_output(context, final_agent, prior_hash)
    max_passes = max(0, audit_repair.MAX_REPAIR_ITERATIONS)
    for repair_pass in range(max_passes + 1):
        context["parsed"] = parse(context)
        current = audit(context, append_section=False)
        _require_final_only_repair(context, current, final_agent)
        requests = repair_requests(current)
        final_requests = requests.get(final_agent)
        if not current.get("critical") and (not final_requests or repair_pass >= max_passes):
            context["final_audit"] = audit(context, append_section=True)
            _require_final_only_repair(context, context["final_audit"], final_agent)
            if context["final_audit"].get("critical"):
                raise FinalRerunQualityBlockedError("最終稽核仍有未解決的可信度異常，未產生新報告。")
            _require_final_output(context, final_agent, prior_hash)
            return context["final_audit"]
        if repair_pass >= max_passes or not final_requests:
            raise FinalRerunQualityBlockedError("最終建議的可信度異常經有界修復仍未解決，未產生新報告；請使用完整重跑。")
        context["repair_iteration_count"] = repair_pass + 1
        scoped = dict(current)
        for field in ("repair_agent_issues", "coverage_repair_agent_issues"):
            scoped[field] = {int(agent): issues for agent, issues in (scoped.get(field) or {}).items() if int(agent) == final_agent}
        await audit_repair.attempt_final_audit_repair_async(context, scoped, rotator, progress_callback=progress_callback)
        _require_final_output(context, final_agent, prior_hash)
