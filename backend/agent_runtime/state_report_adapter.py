"""Convert completed runtime outputs into typed AgentState reports."""

from __future__ import annotations

from agent_catalog import AGENT_NAMES
from agent_state import AgentReport
from state_memory import merge_agent_report


def record_agent_state_report(state, agent_num: int, markdown: str, structured_output=None) -> None:
    if state is None:
        return
    if agent_num == 20 and isinstance(structured_output, dict):
        from .sentiment_analysis_agent import SentimentAnalysisAgent
        report = SentimentAnalysisAgent.build_report(structured_output)
        report.markdown = markdown
    elif agent_num == 21 and isinstance(structured_output, dict):
        from .bear_advocate_agent import BearAdvocateAgent
        report = BearAdvocateAgent.build_report(structured_output)
        report.markdown = markdown
    else:
        report = AgentReport(
            agent_id=str(agent_num),
            role=AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
            markdown=markdown,
            structured_output=structured_output,
        )
    merge_agent_report(state, report)
