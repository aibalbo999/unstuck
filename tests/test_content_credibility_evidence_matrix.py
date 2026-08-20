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


def test_evidence_matrix_coverage_warns_when_final_claim_evidence_is_failed():
    result = evaluate_evidence_matrix_coverage(
        context={},
        snapshot={
            "evidence_matrix": (
                {"claim": "最終投資建議", "basis": "建議: 持有", "status": "failed"},
            ),
        },
        recommendation_present=True,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "unusable_final_recommendation_evidence"
    assert result["warnings"][0]["details"] == {
        "required_claim": "最終投資建議",
        "status": "failed",
        "basis_present": True,
    }
    assert result["checks"][0]["status"] == "warning"


def test_evidence_matrix_coverage_warns_when_final_claim_basis_is_missing():
    result = evaluate_evidence_matrix_coverage(
        context={},
        snapshot={
            "evidence_matrix": (
                {"claim": "最終投資建議", "basis": "", "status": "success"},
            ),
        },
        recommendation_present=True,
    )

    assert result["warnings"][0]["id"] == "unusable_final_recommendation_evidence"
    assert result["warnings"][0]["details"]["basis_present"] is False
    assert result["warnings"][0]["details"]["status"] == "success"


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


def test_evidence_matrix_coverage_warns_when_valuation_claim_lacks_evidence():
    result = evaluate_evidence_matrix_coverage(
        context={"parsed": {"price_targets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 140}}},
        snapshot={
            "evidence_matrix": (
                {"claim": "最終投資建議", "basis": "建議: 持有", "status": "success"},
            ),
        },
        recommendation_present=True,
    )

    assert result["warnings"][-1]["id"] == "missing_valuation_evidence"
    assert result["warnings"][-1]["details"] == {"required_claim": "估值結論"}


def test_evidence_matrix_coverage_warns_when_moat_claim_evidence_is_unusable():
    result = evaluate_evidence_matrix_coverage(
        context={"parsed": {"moat_scores": {"整體護城河": "6/10"}}},
        snapshot={
            "evidence_matrix": (
                {"claim": "最終投資建議", "basis": "建議: 持有", "status": "success"},
                {"claim": "護城河評分", "basis": "整體護城河: 6/10", "status": "failed"},
            ),
        },
        recommendation_present=True,
    )

    issue = next(issue for issue in result["warnings"] if issue["id"] == "unusable_moat_evidence")
    assert issue["details"] == {
        "required_claim": "護城河評分",
        "status": "failed",
        "basis_present": True,
    }
