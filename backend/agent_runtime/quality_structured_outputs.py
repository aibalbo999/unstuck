"""Structured-output parsing helpers for agent quality gates."""

from __future__ import annotations

from analysis_types import AnalysisContext
from pipeline_modes import get_pipeline_definition
from structured_output_runtime import process_agent_response


def is_structured_agent(agent_num: int, context: AnalysisContext) -> bool:
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    return int(agent_num) in set(pipeline_def["structured_agents"].values())


def try_parse_structured_output(agent_num: int, result: str, context: AnalysisContext) -> tuple[bool, str]:
    """Parse structured output immediately when a structured agent did not persist one."""
    if not is_structured_agent(agent_num, context):
        return True, result
    structured_outputs = context.setdefault("structured_outputs", {})
    existing = structured_outputs.get(agent_num, structured_outputs.get(str(agent_num)))
    if existing:
        return True, result

    parsed_result = process_agent_response(agent_num, result, context)
    parsed = structured_outputs.get(agent_num, structured_outputs.get(str(agent_num)))
    if parsed:
        return True, parsed_result
    return False, parsed_result
