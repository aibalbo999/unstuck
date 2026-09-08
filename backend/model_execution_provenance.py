"""Reconstruct secret-safe model provenance from persisted runtime events."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


SELECTED_PHASES = {"llm_model_response", "agent_step_cache_hit"}
SKIPPED_PHASES = {"model_circuit_open", "model_config_error", "model_input_capacity"}
FAILED_PHASES = {"llm_model_error", "model_failed"}


def model_executions_from_events(events: Sequence[Mapping[str, Any]], pipeline_id: str) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    for row in events:
        payload = row.get("payload")
        if not isinstance(payload, Mapping) or payload.get("pipeline_id") != pipeline_id:
            continue
        phase = str(payload.get("phase") or "")
        metadata = payload.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        model_id = str(metadata.get("model_id") or "").strip()
        agent_num = _positive_int(payload.get("agent_num"))
        if not model_id or agent_num is None:
            continue
        record = records.setdefault(agent_num, _new_record(agent_num))
        _append_unique(record["route_considered"], model_id)
        if phase == "llm_provider_request":
            _append_unique(record["provider_call_models"], model_id)
        if phase in SKIPPED_PHASES:
            _append_unique(record["route_skipped"], model_id)
        if phase in FAILED_PHASES:
            _append_unique(record["failed_models"], model_id)
        if phase in SELECTED_PHASES:
            record["model_id"] = model_id
            record["cache_hit"] = phase == "agent_step_cache_hit"
            record["route_index"] = record["route_considered"].index(model_id)
        if phase == "model_fallback":
            record["fallback_used"] = True
    return {agent: record for agent, record in records.items() if record["model_id"]}


def normalized_model_executions(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = context.get("model_executions")
    if not isinstance(raw, Mapping):
        return []
    rows = []
    for key, value in raw.items():
        if not isinstance(value, Mapping):
            continue
        agent_num = _positive_int(value.get("agent_num", key))
        model_id = str(value.get("model_id") or "").strip()
        if agent_num is None or not model_id:
            continue
        row = _new_record(agent_num)
        row.update({field: value.get(field, row[field]) for field in row})
        row["agent_num"], row["model_id"] = agent_num, model_id
        rows.append(row)
    return sorted(rows, key=lambda item: item["agent_num"])


def report_model_id(
    context: Mapping[str, Any],
    data: Mapping[str, Any],
    text_fn: Callable[[Any], str] = str,
) -> str:
    executions = normalized_model_executions(context)
    if executions:
        sequence = context.get("agent_sequence")
        final_agent = _positive_int(sequence[-1]) if isinstance(sequence, (tuple, list)) and sequence else None
        selected = next((item for item in executions if item["agent_num"] == final_agent), executions[-1])
        return selected["model_id"]
    for key in ("model_id", "final_model_id", "decision_model_id"):
        for source in (context, data):
            raw = dict.get(source, key) if isinstance(source, dict) else source.get(key)
            value = text_fn(raw).strip()
            if value:
                return value
    metadata = context.get("metadata")
    if isinstance(metadata, Mapping):
        raw = dict.get(metadata, "model_id") if isinstance(metadata, dict) else metadata.get("model_id")
        return text_fn(raw).strip() or "unknown"
    return "unknown"


def _new_record(agent_num: int) -> dict[str, Any]:
    return {"agent_num": agent_num, "model_id": "", "route_index": None, "route_considered": [],
            "provider_call_models": [], "route_skipped": [], "failed_models": [],
            "fallback_used": False, "cache_hit": False}


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
