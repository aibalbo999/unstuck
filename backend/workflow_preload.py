"""Preload deterministic context for later LangGraph agent groups."""

from __future__ import annotations

import copy
from typing import Callable

from workflow_state import AgentGraphState


def preload_node_name(agent_num: int) -> str:
    return f"agent_{agent_num}_preload"


def preload_agent_context_factory(agent_num: int) -> Callable[[AgentGraphState], AgentGraphState]:
    node_name = preload_node_name(agent_num)

    def preload(state: AgentGraphState) -> AgentGraphState:
        return {
            "tool_results": {
                node_name: {
                    "agent_num": agent_num,
                    "pipeline_id": state.get("pipeline_id", ""),
                    "quant_metrics": copy.deepcopy(state.get("quant_metrics") or {}),
                    "peer_context": copy.deepcopy(state.get("peer_context") or {}),
                    "risk_flags": copy.deepcopy(state.get("risk_flags") or []),
                    "validation_issues": copy.deepcopy(state.get("validation_issues") or []),
                }
            },
            "execution_trace": [{"id": f"preload:{agent_num}", "node": node_name, "agent_num": agent_num}],
        }

    return preload


__all__ = ["preload_agent_context_factory", "preload_node_name"]
