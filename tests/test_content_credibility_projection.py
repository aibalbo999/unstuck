import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _snapshot(*, stored=None, target_12m="NT$90"):
    return {
        "pipeline": "v1",
        "data": {
            "current_price": 100.0,
            "data_trust": {
                "status": "fresh",
                "score": 90,
                "critical_failures": [],
                "stale_sources": [],
                "notes": [],
            },
        },
        "data_trust": {
            "status": "fresh",
            "score": 90,
            "critical_failures": [],
            "stale_sources": [],
            "notes": [],
        },
        "evidence_exit_gate": {"verdict": "approved", "failed_count": 0},
        "evidence_matrix": [
            {"claim": "估值結論", "basis": "熊市 80；基本 120；牛市 140", "status": "success"},
            {"claim": "最終投資建議", "basis": "建議 買入；12 個月 90", "status": "success"},
        ],
        "rerun_context": {
            "pipeline_id": "v1",
            "parsed": {
                "recommendation": {
                    "建議": "買入",
                    "12個月": target_12m,
                    "信心": "7/10",
                },
                "price_targets": {"熊市情境": 80, "基本情境": 120, "牛市情境": 140},
            },
        },
        "content_credibility": stored if stored is not None else {},
    }


def test_projection_rechecks_saved_context_without_mutating_snapshot():
    from reporting.content_credibility_projection import project_content_credibility

    snapshot = _snapshot(stored={"status": "passed"})
    original = copy.deepcopy(snapshot)

    result = project_content_credibility(snapshot)

    assert result["status"] == "blocked"
    assert any(issue["id"] == "buy_target_below_current_price" for issue in result["blocking_issues"])
    assert snapshot == original


def test_projection_merge_keeps_recorded_warning_when_current_projection_passes():
    from reporting.content_credibility_projection import merge_content_credibility_results

    result = merge_content_credibility_results(
        {"status": "warning", "warnings": [{"id": "recorded_warning"}]},
        {"status": "passed", "warnings": [], "checks": [{"id": "current_check"}]},
    )

    assert result["status"] == "warning"
    assert result["warnings"][0]["id"] == "recorded_warning"
    assert result["checks"][0]["id"] == "current_check"


def test_projection_merge_prefers_current_check_for_same_id():
    from reporting.content_credibility_projection import merge_content_credibility_results

    result = merge_content_credibility_results(
        {
            "status": "passed",
            "checks": [{
                "id": "confidence_data_trust_calibration",
                "status": "passed",
                "message": "舊的校準通過訊息",
            }],
        },
        {
            "status": "passed",
            "checks": [{
                "id": "confidence_data_trust_calibration",
                "status": "unavailable",
                "message": "目前無法完成校準",
            }],
        },
    )

    checks = [check for check in result["checks"] if check["id"] == "confidence_data_trust_calibration"]
    assert checks == [{
        "id": "confidence_data_trust_calibration",
        "status": "unavailable",
        "message": "目前無法完成校準",
    }]


def test_projection_requires_parsed_context():
    from reporting.content_credibility_projection import project_content_credibility

    snapshot = _snapshot(stored={"status": "passed"})
    snapshot["rerun_context"] = {}

    assert project_content_credibility(snapshot) is None
