"""Reconcile append-only graph risk history with the latest report versions."""

from agent_state import AgentState


def reconcile_report_risks(state: AgentState) -> AgentState:
    """Reports own agent-attributed flags; keep provider/unattributed flags."""
    managed_agents = set(state.agent_reports)
    report_flags = [flag for report in state.agent_reports.values() for flag in report.risk_flags]
    external_flags = [
        flag for flag in state.risk_flags
        if not (flag.source_agents and set(flag.source_agents) <= managed_agents)
        and flag not in report_flags
    ]
    state.risk_flags = external_flags + report_flags
    return state
