"""Deterministic content-credibility checks for rendered reports."""

from __future__ import annotations

from typing import Any

from data_trust_scoring import normalize_data_trust
from mapping_fields import safe_mapping_dict, safe_text
from recommendation_labels import normalize_recommendation_label
from .content_credibility_alignment import evaluate_recommendation_target_alignment
from .content_credibility_data_confidence import evaluate_data_confidence_target_guardrail
from .content_credibility_evidence_confidence import evaluate_confidence_evidence_alignment
from .content_credibility_evidence_matrix import evaluate_evidence_matrix_coverage
from .content_credibility_inputs import (
    confidence_score as recommendation_confidence_score,
    first_price,
    first_value_by_key_fragment,
    main_target_price,
)


def _as_dict(value: Any) -> dict:
    return safe_mapping_dict(value) or {}


def _evidence_exit_gate(context: dict, snapshot: dict) -> dict:
    return _as_dict(snapshot.get("evidence_exit_gate")) or _as_dict(context.get("evidence_exit_gate"))


def evaluate_content_credibility(context: dict, snapshot: dict | None = None, markdown: str | None = None) -> dict:
    """Evaluate whether report conclusions are directionally credible against deterministic data."""
    context = _as_dict(context)
    snapshot = _as_dict(snapshot)
    data = _as_dict(snapshot.get("data")) or _as_dict(context.get("data"))
    parsed = _as_dict(context.get("parsed"))
    recommendation = _as_dict(parsed.get("recommendation"))
    data_trust = normalize_data_trust(snapshot.get("data_trust") or data.get("data_trust"))
    current_price = first_price(data.get("current_price"))
    recommendation_label = normalize_recommendation_label(first_value_by_key_fragment(recommendation, "建議"))
    main_target = main_target_price(parsed)
    evidence_gate = _evidence_exit_gate(context, snapshot)
    evidence_verdict = safe_text(evidence_gate.get("verdict")).strip() or "not_recorded"
    confidence_score = recommendation_confidence_score(recommendation)

    blocking: list[dict] = []
    warnings: list[dict] = []
    checks: list[dict] = []

    alignment = evaluate_recommendation_target_alignment(
        recommendation_present=bool(recommendation),
        recommendation_label=recommendation_label,
        current_price=current_price,
        main_target=main_target,
    )
    blocking.extend(alignment["blocking_issues"])
    warnings.extend(alignment["warnings"])
    checks.extend(alignment["checks"])

    data_confidence = evaluate_data_confidence_target_guardrail(context, data_trust)
    blocking.extend(data_confidence["blocking_issues"])
    warnings.extend(data_confidence["warnings"])
    checks.extend(data_confidence["checks"])

    evidence_confidence = evaluate_confidence_evidence_alignment(evidence_verdict, confidence_score)
    blocking.extend(evidence_confidence["blocking_issues"])
    warnings.extend(evidence_confidence["warnings"])
    checks.extend(evidence_confidence["checks"])

    matrix_coverage = evaluate_evidence_matrix_coverage(
        context=context,
        snapshot=snapshot,
        recommendation_present=bool(recommendation),
    )
    blocking.extend(matrix_coverage["blocking_issues"])
    warnings.extend(matrix_coverage["warnings"])
    checks.extend(matrix_coverage["checks"])

    if blocking:
        status = "blocked"
        summary = "報告關鍵結論與資料或證據存在阻斷矛盾。"
    elif warnings:
        status = "warning"
        summary = "報告關鍵結論未見阻斷矛盾，但仍有可信度警示。"
    else:
        status = "passed"
        summary = "報告關鍵結論通過內容可信度檢查。"

    return {
        "schema_version": 1,
        "status": status,
        "summary": summary,
        "blocking_issues": blocking,
        "warnings": warnings,
        "checks": checks,
    }
