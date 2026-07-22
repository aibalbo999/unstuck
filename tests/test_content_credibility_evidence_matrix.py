import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.content_credibility_evidence_matrix import evaluate_evidence_matrix_coverage  # noqa: E402


def test_evidence_matrix_coverage_warns_when_recommendation_lacks_final_claim():
    result = evaluate_evidence_matrix_coverage(
        context={},
        snapshot={"evidence_matrix": []},
        recommendation_present=True,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "missing_final_recommendation_evidence"
    assert result["warnings"][0]["details"] == {"required_claim": "最終投資建議"}
    assert result["checks"][0]["id"] == "evidence_matrix_coverage"
    assert result["checks"][0]["status"] == "warning"


def test_evidence_matrix_coverage_accepts_tuple_and_mapping_safe_rows():
    result = evaluate_evidence_matrix_coverage(
        context={},
        snapshot={
            "evidence_matrix": (
                MappingProxyType({"claim": "最終投資建議", "basis": "建議: 持有", "status": "success"}),
            ),
        },
        recommendation_present=True,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"


def test_evidence_matrix_coverage_passes_without_recommendation():
    result = evaluate_evidence_matrix_coverage(
        context={},
        snapshot={"evidence_matrix": []},
        recommendation_present=False,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["id"] == "evidence_matrix_coverage"
    assert result["checks"][0]["status"] == "passed"
