"""Compatibility facade for model-output validation helpers."""

from __future__ import annotations

from company_identity_validator import (
    _count_unqualified_alias,
    append_identity_warnings,
    build_identity_retry_instruction,
    count_unqualified_alias,
    validate_company_identity,
)
from financial_output_validator import (
    CYCLICAL_INDUSTRY_KEYWORDS,
    _append_deep_numeric_consistency_issues,
    _extract_first_money_billion,
    _extract_first_percent,
    _extract_revenue_mentions,
    _has_data_quality_caveat,
    _is_cyclical_low_pe_setup,
    _money_text_to_billion,
    _relative_gap,
    _safe_float,
    append_deep_numeric_consistency_issues,
    append_quality_warnings,
    extract_first_money_billion,
    extract_first_percent,
    extract_revenue_mentions,
    has_data_quality_caveat,
    is_cyclical_low_pe_setup,
    money_text_to_billion,
    relative_gap,
    safe_float,
    validate_analysis_output,
)
from output_sanitizer import (
    PROMPT_LEAK_RESIDUE_RE,
    REPORT_CONTENT_START_RE,
    normalize_bad_number_commas,
    sanitize_model_output,
    strip_generated_audit_sections,
    strip_prompt_preamble,
    validate_prompt_leakage,
)
from price_parser import (
    _extract_price_numbers,
    _parse_price_number,
    extract_price_numbers,
    parse_price_number,
)

__all__ = [
    name
    for name in globals()
    if not name.startswith("__") and name not in {"annotations"}
]
