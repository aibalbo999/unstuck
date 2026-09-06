"""Atomic repair rounds shared by synchronous and asynchronous final-audit nodes."""

from __future__ import annotations

import copy
import functools
import inspect

from analysis_dependencies import (
    downstream_agent_numbers, initialize_result_provenance, invalidate_analysis_results, invalidate_analysis_rag,
    output_fingerprint, pipeline_agent_order, record_result_provenance, stale_agent_numbers,
)
from .cancellation import raise_if_cancelled
from .state_report_adapter import record_agent_state_report


def clone_repair_context(context: dict) -> dict:
    # Copy only owned data. Clients, callbacks, locks, rotators and unknown
    # process-local objects retain identity and are never traversed by deepcopy.
    clone = dict(context)
    for key in COPY_FIELDS:
        if key in context:
            clone[key] = copy.deepcopy(context[key])
    return clone


def commit_repair_context(context: dict, candidate: dict) -> None:
    raise_if_cancelled(candidate)
    context.clear()
    context.update(candidate)
    context["_replace_analysis_state"] = True


def repair_requests(audit: dict) -> dict[int, list[str]]:
    result = {}
    for field in ("repair_agent_issues", "coverage_repair_agent_issues"):
        for agent, issues in (audit.get(field) or {}).items():
            result.setdefault(int(agent), []).extend(str(issue) for issue in issues)
    return result


def _finish_audit_transaction(context: dict, candidate: dict, audit: dict) -> dict:
    stale = stale_agent_numbers(candidate)
    if stale or audit.get("critical") or candidate.get("_repair_round_failed"):
        audit = {**audit, "repair_transaction": {
            "accepted": False,
            "audited_output_hashes": {str(agent): output_fingerprint(agent, candidate) for agent in pipeline_agent_order(candidate)},
            "accepted_output_hashes": {str(agent): output_fingerprint(agent, context) for agent in pipeline_agent_order(context)},
        }}
        candidate["final_audit"] = audit
        candidate["status"] = "blocked"
        if stale:
            candidate.setdefault("blocking_issues", []).append("final_audit:stale_dependencies")
        if audit.get("critical"):
            candidate.setdefault("blocking_issues", []).append("final_audit:unresolved_critical")
        # Failure metadata can advance a blocked state; analysis versions cannot.
        for key in ("status", "blocking_issues", "audit_repair_log", "repair_attempt_counts",
                    "repair_iteration_count", "final_audit", "_runtime_events"):
            if key in candidate:
                context[key] = copy.deepcopy(candidate[key])
        context["_replace_analysis_state"] = True
    else:
        resolved = {"final_audit:repair_iteration_limit", "final_audit:dependency_rebuild_failed",
                    "final_audit:stale_dependencies", "final_audit:unresolved_critical"}
        candidate["blocking_issues"] = [issue for issue in candidate.get("blocking_issues", []) if issue not in resolved]
        if candidate.get("status") == "blocked" and not candidate["blocking_issues"]:
            candidate["status"] = "running"
        commit_repair_context(context, candidate)
    return audit


def atomic_final_audit(function):
    """Keep the complete final-audit graph node as the minimum commit unit."""
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def asynchronous(context, *args, **kwargs):
            candidate = clone_repair_context(context)
            candidate.pop("_repair_round_failed", None)
            initialize_result_provenance(candidate)
            result = await function(candidate, *args, **kwargs)
            return _finish_audit_transaction(context, candidate, result)
        return asynchronous

    @functools.wraps(function)
    def synchronous(context, *args, **kwargs):
        candidate = clone_repair_context(context)
        candidate.pop("_repair_round_failed", None)
        initialize_result_provenance(candidate)
        result = function(candidate, *args, **kwargs)
        return _finish_audit_transaction(context, candidate, result)
    return synchronous


RESULT_FIELDS = (
    "analyses", "structured_outputs", "agent_state", "parsed", "context_digests", "_digest_hash_map",
    "rag_context", "rag_index", "market_context_manifests", "analysis_provenance", "invalidated_agents",
    "executive_thesis", "investment_thesis", "smoothed_markdown", "tear_sheet_summary", "report_cover", "next_catalysts",
)


def _restore_result_fields(context, before, fields=RESULT_FIELDS):
    for key in fields:
        if key in before:
            context[key] = before[key]
        else:
            context.pop(key, None)


def _accept_single_result(agent, context, before, result):
    if not result[0]:
        _restore_result_fields(context, before)
    else:
        record_result_provenance(agent, context)
        if output_fingerprint(agent, context) != output_fingerprint(agent, before):
            invalidate_analysis_rag(context, [agent])
            invalidate_analysis_results(context, downstream_agent_numbers(agent, context))
        else:
            _restore_result_fields(context, before, ("context_digests", "_digest_hash_map", "rag_context", "rag_index"))
    return result


def preserve_failed_repair(function):
    """Keep rejected drafts separate from the last accepted per-agent views."""
    if inspect.iscoroutinefunction(function):
        @functools.wraps(function)
        async def asynchronous(agent, data, context, *args, **kwargs):
            before = clone_repair_context(context)
            try:
                result = await function(agent, data, context, *args, **kwargs)
            except BaseException:
                _restore_result_fields(context, before)
                raise
            return _accept_single_result(agent, context, before, result)
        return asynchronous

    @functools.wraps(function)
    def synchronous(agent, data, context, *args, **kwargs):
        before = clone_repair_context(context)
        try:
            result = function(agent, data, context, *args, **kwargs)
        except BaseException:
            _restore_result_fields(context, before)
            raise
        return _accept_single_result(agent, context, before, result)
    return synchronous


COPY_FIELDS = set(RESULT_FIELDS) | {
    "data", "blocking_issues", "audit_repair_log", "repair_attempt_counts", "repair_iteration_count",
    "final_audit", "llm_token_usage", "_llm_model_circuits", "_runtime_events", "rag_status",
    "agent_quality_retry_counts", "agent_step_cache", "deterministic_fallbacks", "_model_sequence_override",
    "_market_context_attempt_manifests", "_audit_retry_instruction", "_audit_reflection_instruction",
    "_identity_retry_instruction", "_quality_retry_instruction", "source_audit", "execution_trace",
}


class RepairRound:
    """A topological sweep expands its pending set only after accepted changes."""

    def __init__(self, context: dict, audit: dict):
        self.original = context
        self.context = clone_repair_context(context)
        self.context.pop("_repair_round_failed", None)
        initialize_result_provenance(self.context)
        self.requests = repair_requests(audit)
        self.pending = set(self.requests) | set(stale_agent_numbers(self.context))
        self.required = {int(agent) for agent in audit.get("repair_agent_issues", {})}
        self.before = {agent: output_fingerprint(agent, self.context) for agent in pipeline_agent_order(self.context)}
        self.failed = []

    def steps(self):
        for agent in pipeline_agent_order(self.context):
            if agent not in self.pending:
                continue
            raise_if_cancelled(self.context)
            issues = list(self.requests.get(agent, []))
            if agent in {int(item) for item in self.context.get("invalidated_agents", [])}:
                issues.append("上游分析已更正，請依目前上游資料重新產生完整分析與結構化輸出。")
            yield agent, issues, clone_repair_context(self.context)
            if self.failed:
                break

    def accept(self, agent: int, candidate: dict, ok: bool, message: str):
        if not ok:
            for key in ("repair_attempt_counts", "agent_quality_retry_counts", "_llm_model_circuits", "llm_token_usage"):
                if key in candidate:
                    self.context[key] = candidate[key]
            if agent in self.required or agent in self.context.get("invalidated_agents", []):
                self.failed.append(f"Agent {agent}: {message}")
            return
        raise_if_cancelled(candidate)
        self.context = candidate
        from analysis_dependencies import agent_value
        record_agent_state_report(candidate.get("agent_state"), agent,
                                  agent_value(candidate, "analyses", agent, ""),
                                  agent_value(candidate, "structured_outputs", agent))
        record_result_provenance(agent, candidate)
        if output_fingerprint(agent, candidate) != self.before.get(agent):
            invalidate_analysis_rag(candidate, [agent])
            descendants = downstream_agent_numbers(agent, candidate)
            self.pending.update(descendants)
            invalidate_analysis_results(candidate, descendants)

    def finish(self) -> bool:
        stale = stale_agent_numbers(self.context)
        if self.failed or stale:
            self.original["status"] = "blocked"
            issues = self.original.setdefault("blocking_issues", [])
            if "final_audit:dependency_rebuild_failed" not in issues:
                issues.append("final_audit:dependency_rebuild_failed")
            self.original["audit_repair_log"] = list(self.context.get("audit_repair_log", []))
            self.original["audit_repair_log"].extend(self.failed or [f"尚未完成依賴重建：{stale}"])
            for key in ("repair_attempt_counts", "agent_quality_retry_counts", "_llm_model_circuits", "llm_token_usage"):
                if key in self.context:
                    self.original[key] = self.context[key]
            self.original["_repair_round_failed"] = True
            return False
        commit_repair_context(self.original, self.context)
        return True
