"""Normalize structured-agent JSON and convert it to report text."""

from __future__ import annotations

from structured_output_normalizer_basic import (
    _coerce_bool,
    _coerce_number,
    _display_line,
    _display_price_target,
    _display_text,
    _has_string_key,
    _legacy_body_text,
    _normalized_analysis_markdown,
    _number_text,
    _pick_mapping_value,
    _raw_structured_payload_is_complete_enough,
    _report_body_text,
    _string_field_line,
    _string_field_text,
)
from structured_output_normalizer_core import (
    _coerce_confidence_basis,
    _coerce_dcf_scenarios,
    _coerce_downside_risks,
    _coerce_moat_payload,
    _coerce_next_catalysts,
    _coerce_price_target_payload,
    _coerce_reasoning_steps,
    _coerce_required_text_list,
    _coerce_scenario_triggers,
    _coerce_string_text_list,
    _derive_next_catalysts_from_scenario_triggers,
)
from structured_output_normalizer_payloads import (
    _coerce_bear_advocate_payload,
    _coerce_downside_risk_rows,
    _coerce_management_highlights,
    _coerce_management_sentiment_payload,
    _coerce_recommendation_payload,
    _coerce_trade_setup_payload,
)
from structured_output_normalizer_text import (
    _coerce_text,
    _dcf_scenarios_text,
    _downside_risk_line,
    _management_highlight_line,
    _moat_reasoning_steps_text,
    _moat_score_line,
    _next_catalyst_field,
    _next_catalyst_text,
    _percent_text,
    _plain_jsonish,
    _reasoning_steps_text,
    _trade_plan_field,
    _valuation_reasoning_text,
    _valuation_summary_line,
)
from structured_output_normalize_dispatch import _normalize_recommendation_payload_aliases, normalize_structured_output
from structured_output_report_text import structured_output_to_report_text
from structured_output_warnings import (
    _confidence_score,
    _warn_high_confidence_with_low_trust,
    confidence_score,
    price_targets_have_unit_error,
    warn_high_confidence_with_low_trust,
)


__all__ = [
    "confidence_score",
    "normalize_structured_output",
    "price_targets_have_unit_error",
    "structured_output_to_report_text",
    "warn_high_confidence_with_low_trust",
]
