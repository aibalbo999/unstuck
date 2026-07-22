import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.content_credibility_evidence_confidence import evaluate_confidence_evidence_alignment  # noqa: E402


def test_evidence_confidence_blocks_rejected_gate_with_high_confidence():
    result = evaluate_confidence_evidence_alignment("rejected", 9.0)

    assert result["blocking_issues"][0]["id"] == "high_confidence_rejected_evidence"
    assert result["warnings"] == []
    assert result["checks"][0]["id"] == "confidence_evidence_alignment"
    assert result["checks"][0]["status"] == "blocked"
    assert result["blocking_issues"][0]["details"] == {
        "evidence_verdict": "rejected",
        "confidence_score": 9.0,
    }


def test_evidence_confidence_warns_for_non_approved_gate():
    result = evaluate_confidence_evidence_alignment("needs_review", 6.0)

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "non_approved_evidence_gate"
    assert result["checks"][0]["status"] == "warning"


def test_evidence_confidence_treats_string_empty_tokens_as_not_recorded():
    result = evaluate_confidence_evidence_alignment("NaN", 9.0)

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"
    assert result["checks"][0]["details"] == {"evidence_verdict": "not_recorded"}


def test_evidence_confidence_passes_approved_and_not_recorded_gates():
    approved = evaluate_confidence_evidence_alignment("approved", 9.0)
    not_recorded = evaluate_confidence_evidence_alignment("not_recorded", None)

    assert approved["blocking_issues"] == []
    assert approved["warnings"] == []
    assert approved["checks"][0]["status"] == "passed"
    assert not_recorded["checks"][0]["details"] == {"evidence_verdict": "not_recorded"}
