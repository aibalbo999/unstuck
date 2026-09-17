"""Read-only report admission based on still-required critical model routes."""

from __future__ import annotations

import copy

from analysis_dependencies import agent_value, is_agent_result_current
from config import CRITICAL_REPORT_AGENT_NUMBERS
from context_dependencies import upstream_agent_numbers
from pipeline_modes import PIPELINE_DEFINITIONS

from .deferred import AgentDeferredError, unavailable_model
from .model_policy import MODEL_CIRCUITS_KEY
from .retry_policy import AgentConfigurationError
from .routing import get_runtime_model_sequence, is_agent_execution_failure


def _needs_generation(agent: int, context: dict, current_agent: int | None) -> bool:
    # A scheduled upstream rewrite will invalidate its dependent result, even
    # before the new output exists and its provenance hash can change.
    if agent == current_agent or current_agent in upstream_agent_numbers(agent, context):
        return True
    text = agent_value(context, "analyses", agent)
    return not (
        isinstance(text, str) and text.strip() and not is_agent_execution_failure(text)
        and is_agent_result_current(agent, context)
    )


def preflight_remaining_critical_agents(context: dict, rotator, *, current_agent: int | None = None) -> None:
    """Defer only when an essential remaining role has no known available route.

    No prompt is built, token capacity guessed, key reserved or circuit opened.
    Unknown availability/configuration is left to normal per-agent admission;
    one unknown route is enough to prevent a false all-routes-blocked claim.
    Accepted checkpoint outputs and their provenance are never changed here.
    """
    definition = PIPELINE_DEFINITIONS.get(str(context.get("pipeline_id") or ""))
    if definition is None:
        return
    probe_context = {MODEL_CIRCUITS_KEY: copy.deepcopy(context.get(MODEL_CIRCUITS_KEY) or {})}
    for agent in definition["agents"]:
        if agent not in CRITICAL_REPORT_AGENT_NUMBERS or not _needs_generation(agent, context, current_agent):
            continue
        try:
            models = get_runtime_model_sequence(agent, context)
        except (KeyError, TypeError, ValueError):
            continue
        if not models:
            continue
        blocked = []
        for model in models:
            try:
                unavailable = unavailable_model(probe_context, rotator, model)
            except (AgentConfigurationError, OSError, TypeError, ValueError):
                break
            if unavailable is None:
                break
            blocked.append(unavailable)
        else:
            raise AgentDeferredError(agent, blocked)
