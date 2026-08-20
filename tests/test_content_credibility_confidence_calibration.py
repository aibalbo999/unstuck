import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _context(*, trust_status="partial", confidence="9/10"):
    return {
        "data": {
            "data_trust": {
                "status": trust_status,
                "score": 72,
                "critical_failures": [],
                "stale_sources": [],
                "notes": [],
            },
        },
        "parsed": {"recommendation": {"信心": confidence}},
    }


def test_confidence_calibration_warns_when_score_exceeds_partial_trust_cap():
    from data_trust_scoring import normalize_data_trust
    from reporting.content_credibility_confidence_calibration import evaluate_confidence_data_trust_calibration

    context = _context()
    result = evaluate_confidence_data_trust_calibration(
        context,
        context["parsed"]["recommendation"],
        normalize_data_trust(context["data"]["data_trust"]),
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "confidence_exceeds_data_trust_cap"
    assert result["warnings"][0]["details"]["max_recommended_confidence"] == 7


def test_confidence_calibration_does_not_warn_when_score_is_at_cap():
    from data_trust_scoring import normalize_data_trust
    from reporting.content_credibility_confidence_calibration import evaluate_confidence_data_trust_calibration

    context = _context(confidence="7/10")
    result = evaluate_confidence_data_trust_calibration(
        context,
        context["parsed"]["recommendation"],
        normalize_data_trust(context["data"]["data_trust"]),
    )

    assert result["warnings"] == []
    assert result["checks"][0]["status"] == "passed"


def test_confidence_calibration_skips_unparseable_confidence():
    from data_trust_scoring import normalize_data_trust
    from reporting.content_credibility_confidence_calibration import evaluate_confidence_data_trust_calibration

    context = _context(confidence="尚未提供")
    result = evaluate_confidence_data_trust_calibration(
        context,
        context["parsed"]["recommendation"],
        normalize_data_trust(context["data"]["data_trust"]),
    )

    assert result["warnings"] == []
    assert "略過" in result["checks"][0]["message"]
