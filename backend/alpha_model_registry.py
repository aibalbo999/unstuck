"""Versioned alpha-model registry built on top of research playbooks."""

from __future__ import annotations

from typing import Any

from pipeline_modes import PIPELINE_DEFINITIONS, normalize_pipeline_id


SCHEMA_VERSION = "alpha_model.v1"

_PIPELINE_MODEL_IDS = {
    "v1": "mode-a-deep-research",
    "v2": "mode-b-practical-trading",
    "v3": "mode-c-contrarian-risk",
    "v4": "mode-d-event-swing",
}

_MODEL_CATEGORIES = {
    "v1": "deep_research",
    "v2": "practical_trading",
    "v3": "contrarian_risk",
    "v4": "event_driven_swing",
}


def list_alpha_models() -> list[dict[str, Any]]:
    return [model_for_pipeline(pipeline_id) for pipeline_id in PIPELINE_DEFINITIONS]


def get_alpha_model(model_id: str) -> dict[str, Any]:
    normalized = str(model_id or "").strip().lower()
    for model in list_alpha_models():
        if model["id"] == normalized:
            return model
    raise KeyError(f"unknown alpha model: {model_id}")


def model_for_pipeline(pipeline_id: str) -> dict[str, Any]:
    pipeline_id = normalize_pipeline_id(pipeline_id)
    definition = PIPELINE_DEFINITIONS[pipeline_id]
    horizon = "1-2w" if pipeline_id == "v4" else "3-12m"
    return {
        "id": _PIPELINE_MODEL_IDS[pipeline_id],
        "version": SCHEMA_VERSION,
        "pipeline_id": pipeline_id,
        "label": definition["label"],
        "category": _MODEL_CATEGORIES[pipeline_id],
        "agent_sequence": list(definition["agents"]),
        "minimum_data_confidence": 60,
        "horizon": horizon,
        "free_mode_policy": {
            "max_debate_rounds": 1,
            "allow_optional_paid_enrichment": False,
            "skip_explicit_target_below_confidence": 60,
        },
        "required_outputs": [
            "recommendation",
            "thesis",
            "invalidation_trigger",
            "time_horizon",
            "data_confidence",
            "next_review_date",
        ],
    }


__all__ = ["SCHEMA_VERSION", "get_alpha_model", "list_alpha_models", "model_for_pipeline"]
