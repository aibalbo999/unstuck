"""Pure analysis-version and pipeline-dependency boundaries."""

from __future__ import annotations

import hashlib
import json

from context_dependencies import upstream_agent_numbers
from pipeline_modes import get_pipeline_definition
from validators import strip_generated_audit_sections


def pipeline_agent_order(context: dict) -> tuple[int, ...]:
    return tuple(agent for group in get_pipeline_definition(context.get("pipeline_id"))["groups"] for agent in group)


def agent_value(context: dict, section: str, agent: int, default=None):
    values = context.get(section) or {}
    return values.get(agent, values.get(str(agent), default))


def _hash(value) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def output_fingerprint(agent: int, context: dict) -> str:
    """Audit appendices and runtime telemetry are not analysis revisions."""
    return _hash({"body": strip_generated_audit_sections(str(agent_value(context, "analyses", agent, ""))).strip(),
                  "structured": agent_value(context, "structured_outputs", agent)})


def upstream_input_hash(agent_num: int, context: dict) -> str:
    return _hash({str(agent): output_fingerprint(agent, context)
                  for agent in upstream_agent_numbers(agent_num, context)})


def downstream_agent_numbers(agent: int, context: dict) -> tuple[int, ...]:
    return tuple(target for target in pipeline_agent_order(context)
                 if agent in upstream_agent_numbers(target, context))


def record_result_provenance(agent: int, context: dict) -> None:
    values = context.setdefault("analysis_provenance", {})
    values.pop(str(agent), None)
    values[agent] = {"input_hash": upstream_input_hash(agent, context),
                     "output_hash": output_fingerprint(agent, context)}
    context["invalidated_agents"] = [item for item in context.get("invalidated_agents", []) if int(item) != agent]


def is_agent_result_current(agent: int, context: dict) -> bool:
    if agent in {int(item) for item in context.get("invalidated_agents", [])}:
        return False
    version = agent_value(context, "analysis_provenance", agent)
    if version is None:
        return True  # Legacy results remain readable until the first repair boundary.
    return (version.get("input_hash") == upstream_input_hash(agent, context)
            and version.get("output_hash") == output_fingerprint(agent, context))


def stale_agent_numbers(context: dict) -> tuple[int, ...]:
    return tuple(agent for agent in pipeline_agent_order(context) if not is_agent_result_current(agent, context))


def initialize_result_provenance(context: dict) -> None:
    """Bind a consistent legacy node input once; never refresh existing stale versions."""
    for agent in pipeline_agent_order(context):
        if (agent not in {int(item) for item in context.get("invalidated_agents", [])}
                and agent_value(context, "analyses", agent) is not None
                and agent_value(context, "analysis_provenance", agent) is None):
            record_result_provenance(agent, context)


def invalidate_analysis_results(context: dict, agents) -> None:
    """Invalidate owned projections while preserving raw evidence and external risks."""
    invalid = {int(agent) for agent in agents}
    if not invalid:
        return
    context["_replace_analysis_state"] = True
    context["invalidated_agents"] = sorted(invalid | {int(item) for item in context.get("invalidated_agents", [])})
    for section in ("analyses", "structured_outputs", "context_digests", "rag_context", "market_context_manifests"):
        values = context.get(section) or {}
        for agent in invalid:
            values.pop(agent, None)
            values.pop(str(agent), None)
    from context_dependencies import invalidate_repair_digests
    for agent in invalid:
        invalidate_repair_digests(context, agent)
    context["parsed"] = {}
    for key in ("executive_thesis", "smoothed_markdown", "tear_sheet_summary"):
        context[key] = ""
    context["investment_thesis"], context["report_cover"], context["next_catalysts"] = {}, {}, []
    state = context.get("agent_state")
    if state is not None:
        ids = {str(agent) for agent in invalid}
        removed_flags = [flag for agent, report in state.agent_reports.items() if str(agent) in ids
                         for flag in report.risk_flags]
        for agent in ids:
            state.agent_reports.pop(agent, None)
        state.risk_flags = [flag for flag in state.risk_flags
                            if not (set(flag.source_agents) & ids) and flag not in removed_flags]
        state.executive_thesis, state.smoothed_markdown, state.next_catalysts = "", "", []
    invalidate_analysis_rag(context, invalid)


def invalidate_analysis_rag(context: dict, agents) -> None:
    invalid = {int(agent) for agent in agents}
    index = context.get("rag_index")
    if index is not None:
        # Raw provider chunks have no analysis ownership and survive this operation.
        context["rag_index"] = type(index)([
            chunk for chunk in index.chunks if not _analysis_chunk_owned_by(chunk, invalid)
        ], metadata=index.metadata.copy())


def _analysis_chunk_owned_by(chunk, agents: set[int]) -> bool:
    metadata = getattr(chunk, "metadata", {}) or {}
    source = str(getattr(chunk, "source", ""))
    if not (source.startswith(("analysis:", "agent:", "agent_"))
            or metadata.get("source_type") in {"analysis", "agent_analysis"}):
        return False
    owner = metadata.get("agent_num", metadata.get("agent_id", source.rsplit(":", 1)[-1].removeprefix("agent_")))
    return str(owner) in {str(agent) for agent in agents}
