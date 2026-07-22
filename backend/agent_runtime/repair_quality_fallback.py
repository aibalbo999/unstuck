"""Quality fallback selection for final audit repair retries."""

from __future__ import annotations

from analysis_types import AnalysisContext, StockData

from .deterministic_fallbacks import (
    _deterministic_quality_fallback,
    _deterministic_structured_fallback,
    _record_deterministic_fallback,
)


def record_quality_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    original_analysis: str,
    current_issues: list[str],
    last_quality_issues: list[str],
    last_result: str | None,
) -> tuple[bool, str]:
    fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, original_analysis)
    if not fallback_ok:
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, last_quality_issues or current_issues)
    if fallback_ok:
        _record_deterministic_fallback(
            context,
            agent_num,
            fallback_message,
            "quality_fallback_after_retries",
            issues=last_quality_issues or current_issues,
            raw_failure=last_result or "",
        )
    return fallback_ok, fallback_message


__all__ = ["record_quality_fallback"]
