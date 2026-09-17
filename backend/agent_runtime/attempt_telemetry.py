"""Ephemeral response receipts; never restore model or usage from graph state."""

from __future__ import annotations

from llm_usage import extract_usage
from workflow_telemetry_attribution import (
    SCHEMA_VERSION,
    current_node_invocation,
    optional_count,
    result_fingerprint,
    safe_model_label,
)


_KEY = "_node_attempt_telemetry"


def _deterministic_count(context: dict, agent_num: int) -> int:
    fallbacks = context.get("deterministic_fallbacks") or []
    events = context.get("_runtime_events") or []
    entries = [entry for entry in fallbacks if isinstance(entry, dict)] if isinstance(fallbacks, list) else []
    if isinstance(events, list):
        entries.extend(entry for entry in events if isinstance(entry, dict)
                       and entry.get("phase") == "agent_deterministic_result")
    return sum(str(entry.get("agent_num")) == str(agent_num) for entry in entries)


def reset_node_attempt_telemetry(context: dict, agent_num: int) -> None:
    """Start one node invocation before any draft, cache, or LLM execution."""
    context[_KEY] = {"agent_num": agent_num, "invocation": current_node_invocation(),
                     "calls": {}, "response": None}
    usage = context.get("llm_token_usage")
    if isinstance(usage, dict):
        usage.pop(agent_num, None)
        usage.pop(str(agent_num), None)


def _current(context: dict, agent_num: int) -> dict | None:
    record = context.get(_KEY)
    if (not isinstance(record, dict) or record.get("agent_num") != agent_num
            or record.get("invocation") != current_node_invocation()):
        return None
    return record


def record_node_model_call(context: dict, agent_num: int, model_id: str) -> None:
    record = _current(context, agent_num)
    if record is not None:
        record["response"] = None
        record["calls"][model_id] = record["calls"].get(model_id, 0) + 1


def record_node_model_response(context: dict, agent_num: int, model_id: str, response) -> None:
    record = _current(context, agent_num)
    if record is None:
        return
    diagnostics = response.get("diagnostics") if isinstance(response, dict) else getattr(response, "diagnostics", None)
    cache_hit = isinstance(diagnostics, dict) and diagnostics.get("cache_hit") is True
    model = safe_model_label(diagnostics.get("model_id")) if cache_hit else safe_model_label(model_id)
    usage = extract_usage(response, include_missing=False) or {}
    record["response"] = {
        "model": model,
        "cache_hit": cache_hit,
        "input_tokens": optional_count(usage.get("input_tokens")),
        "output_tokens": optional_count(usage.get("output_tokens")),
        "retry_count": max(0, record["calls"].get(model_id, 0) - 1),
        "deterministic_count": _deterministic_count(context, agent_num),
    }


def record_node_cache_response(context: dict, agent_num: int, cached: dict) -> None:
    record = _current(context, agent_num)
    if record is None:
        return
    # Cache-key construction binds the stored model; never substitute the route
    # or reuse a previous attempt's usage when a legacy cache lacks provenance.
    model = safe_model_label(cached.get("model_id"))
    record["response"] = {"model": model, "cache_hit": True, "input_tokens": None,
                           "output_tokens": None, "retry_count": 0,
                           "deterministic_count": _deterministic_count(context, agent_num)}


def build_agent_node_receipt(context: dict, agent_num: int, result: dict, *, quality_gate_pass=None) -> dict:
    """Seal current provenance to a returned delta, after all transformations.

    A quality verdict must come from explicit validation of this exact result.
    Returning normally, producing a response, or lacking new blocking issues is
    not a quality verdict. Leave the default None when no such verdict exists.
    """
    record = _current(context, agent_num)
    invocation = current_node_invocation()
    if record is None or invocation is None:
        return {}
    response = record.get("response") or {}
    from .routing import is_agent_execution_failure
    analyses = result.get("analyses") or {}
    text = analyses.get(str(agent_num), analyses.get(agent_num)) if isinstance(analyses, dict) else None
    if (not isinstance(text, str) or is_agent_execution_failure(text) or
            _deterministic_count(context, agent_num) != response.get("deterministic_count", 0)):
        response = {}  # A policy-produced replacement is not the model's result.
    return {
        "schema_version": SCHEMA_VERSION,
        **invocation,
        "result_fingerprint": result_fingerprint(result, agent_num),
        "model": response.get("model"),
        "cache_hit": response.get("cache_hit") is True,
        "input_tokens": response.get("input_tokens"),
        "output_tokens": response.get("output_tokens"),
        "retry_count": response.get("retry_count", 0),
        "quality_gate_pass": quality_gate_pass if type(quality_gate_pass) is bool else None,
    }
