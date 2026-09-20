"""Schema-backed confidence scales survive formatting and evidence classification."""

import pytest

from evidence_exit_gate import evaluate_report_evidence
from structured_output_report_text import structured_output_to_report_text
from structured_output_risk_models import BearAdvocateStructuredOutput, ManagementSentimentStructuredOutput


FINANCIAL = "股價:100元\nP/E:20x\n營收:20000000"
SNAPSHOT = {"data": {"current_price": 100, "pe_ratio": 20, "revenue": 20000000}}


def _validated_output(agent, value, body=FINANCIAL):
    if agent == 20:
        return ManagementSentimentStructuredOutput.model_validate({
            "guidance_tone": "中立", "confidence": value,
            "highlights": [{"keyword": "需求", "quote": "需求尚待驗證"}] * 3,
            "analysis_markdown": body,
        }).model_dump()
    return BearAdvocateStructuredOutput.model_validate({
        "thesis_summary": "需求波動風險", "analysis_markdown": body,
        "downside_risks": [{"title": "需求波動", "evidence": "需求尚待驗證",
                            "severity": "high", "confidence": value,
                            "falsifier": "確認需求持續改善後重估"}],
    }).model_dump()


@pytest.mark.parametrize("agent", [20, 21])
@pytest.mark.parametrize("value", [0.0, 0.85, 1.0])
def test_schema_confidence_keeps_value_with_explicit_unit_interval_in_report_and_gate(agent, value):
    payload = _validated_output(agent, value)
    text = structured_output_to_report_text(agent, payload)
    label = "信心分數" if agent == 20 else "信心"
    assert f"{label}（0–1）：{value:g}" in text
    result = evaluate_report_evidence(text, SNAPSHOT, sample_ratio=1)
    assert result["metadata_checked_count"] == 1
    assert result["metadata_unverifiable_count"] == result["metadata_invalid_count"] == 0
    score = result["metadata_claims"][0]
    assert score["reported_value"] == value
    assert (score["scale_min"], score["scale_max"]) == (0, 1)
    assert score["financial_evidence"] is False
    assert result["verified_count"] == 3
    assert result["verdict"] == "approved"


@pytest.mark.parametrize("agent", [20, 21])
def test_free_text_confidence_without_source_scale_remains_unverifiable(agent):
    body = FINANCIAL + "\n信心:0.85"
    text = structured_output_to_report_text(agent, _validated_output(agent, 0.6, body))
    assert "信心:0.85" in text
    result = evaluate_report_evidence(text, SNAPSHOT, sample_ratio=1)
    assert result["metadata_checked_count"] == 2
    assert result["metadata_unverifiable_count"] == 1
    assert [item["status"] for item in result["metadata_claims"]].count("valid") == 1
    assert result["verdict"] == "caution"
