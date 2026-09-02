"""Deterministic content-credibility checks for rendered reports."""

from __future__ import annotations

from typing import Any

from data_trust_scoring import normalize_data_trust
from mapping_fields import safe_mapping_dict, safe_text
from recommendation_labels import normalize_recommendation_label
from .content_credibility_alignment import evaluate_recommendation_target_alignment
from .content_credibility_confidence_calibration import evaluate_confidence_data_trust_calibration
from .content_credibility_data_confidence import evaluate_data_confidence_target_guardrail
from .content_credibility_evidence_confidence import evaluate_confidence_evidence_alignment
from .content_credibility_evidence_matrix import evaluate_evidence_matrix_coverage
from .content_credibility_final_audit import evaluate_final_audit_alignment, final_audit_from_conformance
from .content_credibility_horizons import evaluate_horizon_target_sequence
from .content_credibility_scenarios import evaluate_scenario_target_order
from .content_credibility_scenario_range import evaluate_recommendation_target_scenario_range
from .content_credibility_trade_setup import evaluate_trade_setup_alignment
from .content_credibility_inputs import (
    confidence_score as recommendation_confidence_score,
    first_price,
    first_value_by_key_fragment,
    main_target_price,
)
from .text_tokens import first_non_missing_text


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
    trade_setup = _as_dict(parsed.get("trade_setup"))
    pipeline_id = first_non_missing_text(context.get("pipeline_id"), snapshot.get("pipeline")).lower()
    data_trust = normalize_data_trust(snapshot.get("data_trust") or data.get("data_trust"))
    current_price = first_price(data.get("current_price"))
    recommendation_label = normalize_recommendation_label(first_value_by_key_fragment(recommendation, "建議"))
    main_target = main_target_price(parsed)
    evidence_gate = _evidence_exit_gate(context, snapshot)
    evidence_verdict = safe_text(evidence_gate.get("verdict")).strip() or "not_recorded"
    confidence_score = recommendation_confidence_score(recommendation)
    final_audit = _as_dict(context.get("final_audit")) or _as_dict(snapshot.get("final_audit")) or final_audit_from_conformance(snapshot.get("report_conformance"))

    if pipeline_id == "v4":
        alignment = evaluate_trade_setup_alignment(trade_setup=trade_setup, current_price=current_price)
    else:
        alignment = evaluate_recommendation_target_alignment(
            recommendation_present=bool(recommendation),
            recommendation_label=recommendation_label,
            current_price=current_price,
            main_target=main_target,
        )
    results = [
        alignment,
        evaluate_scenario_target_order(parsed),
        evaluate_recommendation_target_scenario_range(parsed),
        evaluate_horizon_target_sequence(parsed),
        evaluate_final_audit_alignment(final_audit),
        evaluate_data_confidence_target_guardrail(context, data_trust),
        evaluate_confidence_data_trust_calibration(
            context=context, recommendation=recommendation, data_trust=data_trust
        ),
        evaluate_confidence_evidence_alignment(evidence_verdict, confidence_score, evidence_gate),
        evaluate_evidence_matrix_coverage(
            context=context, snapshot=snapshot, recommendation_present=bool(recommendation)
        ),
    ]
    blocking = [issue for result in results for issue in result["blocking_issues"]]
    warnings = [issue for result in results for issue in result["warnings"]]
    checks = [check for result in results for check in result["checks"]]

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
