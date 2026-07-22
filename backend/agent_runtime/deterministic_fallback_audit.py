"""Audit helpers for deterministic fallback repair events."""

from __future__ import annotations

from datetime import datetime, timezone

from analysis_types import AnalysisContext
from agent_catalog import AGENT_NAMES


def clear_agent_blocking_issues(context: AnalysisContext, agent_num: int) -> None:
    agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
    prefixes = (f"Agent {agent_num} ", f"Agent {agent_num}: ", f"{agent_name}: ")
    context["blocking_issues"] = [
        issue for issue in context.get("blocking_issues", [])
        if not str(issue).startswith(prefixes)
    ]
    if not context["blocking_issues"]:
        context.pop("blocking_issues", None)


def record_deterministic_fallback(
    context: AnalysisContext,
    agent_num: int,
    message: str,
    trigger: str,
    issues: list[str] | None = None,
    raw_failure: str = "",
    metadata: dict | None = None,
) -> None:
    entry = {
        "type": "deterministic_fallback",
        "agent_num": agent_num,
        "agent_name": AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
        "trigger": trigger,
        "message": message,
        "issues": [str(issue) for issue in (issues or [])[:5]],
        "raw_failure": str(raw_failure or "")[:240],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        entry["metadata"] = {
            str(key): value
            for key, value in metadata.items()
            if value is not None
        }
    context.setdefault("deterministic_fallbacks", []).append(entry)
