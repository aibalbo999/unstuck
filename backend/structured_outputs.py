"""Compatibility facade for structured agent output handling."""

from __future__ import annotations

from openai_structured_outputs import openai_json_schema_response_format
from structured_output_models import (
    BubbleSniperRecommendationFields,
    BubbleSniperStructuredOutput,
    BearAdvocateStructuredOutput,
    DcfScenarioOutput,
    DownsideRisk,
    ManagementHighlight,
    ManagementSentimentStructuredOutput,
    STRUCTURED_AGENT_INSTRUCTIONS,
    STRUCTURED_AGENT_RESPONSE_SCHEMAS,
    MoatScores,
    MoatStructuredOutput,
    PriceTargetStructuredOutput,
    PriceTargets,
    RecommendationFields,
    RecommendationStructuredOutput,
    StructuredModel,
    SwingTradeSetup,
    ValuationSummary,
    _extract_json_payload,
    build_structured_output_instruction,
    get_structured_response_schema,
)
from structured_output_normalizer import (
    _coerce_number,
    _coerce_reasoning_steps,
    _coerce_text,
    _confidence_score,
    _pick_mapping_value,
    _warn_high_confidence_with_low_trust,
    confidence_score,
    normalize_structured_output,
    price_targets_have_unit_error,
    structured_output_to_report_text,
    warn_high_confidence_with_low_trust,
)
from structured_output_parser import (
    parse_moat_scores_from_text,
    parse_price_targets_from_text,
    parse_recommendation_from_text,
    parse_structured_data,
)
from structured_output_runtime import process_agent_response

__all__ = [
    name
    for name in globals()
    if not name.startswith("__") and name not in {"annotations"}
]
