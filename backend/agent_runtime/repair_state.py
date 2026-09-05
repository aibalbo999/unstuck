"""Publish only accepted repair versions to the typed State blackboard."""

from context_dependencies import invalidate_repair_digests

from .state_report_adapter import record_agent_state_report


def adopt_repair_result(agent_num: int, context: dict, result: tuple[bool, str]) -> tuple[bool, str]:
    if result[0]:
        analyses = context.get("analyses") or {}
        structured = context.get("structured_outputs") or {}
        record_agent_state_report(
            context.get("agent_state"), agent_num,
            analyses.get(agent_num, analyses.get(str(agent_num), "")),
            structured.get(agent_num, structured.get(str(agent_num))),
        )
        invalidate_repair_digests(context, agent_num)
    return result
