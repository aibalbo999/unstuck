"""Per-mode input and model receipts for persisted report artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from analysis_input_provenance import freeze_analysis_inputs
from model_execution_provenance import model_executions_from_events


def freeze_and_record_analysis_inputs(
    job_id: str,
    pipeline_id: str,
    mode_data: dict[str, Any],
    append_event: Callable[[str, dict[str, Any]], None],
) -> None:
    receipt = freeze_analysis_inputs(mode_data)
    append_event(job_id, {"type": "provenance", "phase": "analysis_input_frozen",
                          "pipeline_id": pipeline_id, **receipt})


def attach_model_executions(
    context: dict[str, Any],
    events: Sequence[Mapping[str, Any]],
    pipeline_id: str,
) -> None:
    context["model_executions"] = model_executions_from_events(events, pipeline_id)
