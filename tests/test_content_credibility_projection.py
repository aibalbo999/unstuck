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


def test_projection_merge_drops_resolved_trade_setup_warning():
    from reporting.content_credibility_projection import merge_content_credibility_results

    result = merge_content_credibility_results(
        {
            "status": "warning",
            "warnings": [{"id": "ambiguous_trade_setup_price_inputs"}],
        },
        {
            "status": "passed",
            "warnings": [],
            "checks": [{"id": "trade_setup_alignment", "status": "passed"}],
        },
    )

    assert result["status"] == "passed"
    assert result["warnings"] == []


def test_projection_merge_drops_stale_evidence_alignment_issue_when_current_gate_is_approved():
    from reporting.content_credibility_projection import merge_content_credibility_results

    result = merge_content_credibility_results(
        {
            "status": "warning",
            "warnings": [{"id": "non_approved_evidence_gate", "message": "舊的 evidence warning"}],
            "checks": [{"id": "confidence_evidence_alignment", "status": "warning"}],
        },
        {
            "status": "passed",
            "warnings": [],
            "checks": [{
                "id": "confidence_evidence_alignment",
                "status": "passed",
                "details": {"evidence_verdict": "approved"},
            }],
        },
    )

    assert result["status"] == "passed"
    assert result["warnings"] == []


def test_projection_merge_prefers_current_issue_details_over_stale_recorded_details():
    from reporting.content_credibility_projection import merge_content_credibility_results

    issue = {
        "id": "ambiguous_trade_setup_price_inputs",
        "message": "交易計畫的目標或停損包含多個情境價格，無法用單一數值代表，需人工核對。",
    }
    result = merge_content_credibility_results(
        {
            "status": "warning",
            "warnings": [{**issue, "details": {"stop_loss_candidates": [227.0, 10.0]}}],
        },
        {
            "status": "warning",
            "warnings": [{**issue, "details": {"target_price_candidates": [306.0, 227.0]}}],
            "checks": [{"id": "trade_setup_alignment", "status": "warning"}],
        },
    )

    assert result["warnings"] == [{**issue, "details": {"target_price_candidates": [306.0, 227.0]}}]


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


def test_projection_uses_snapshot_pipeline_when_rerun_context_pipeline_is_missing():
    from reporting.content_credibility_projection import project_content_credibility

    snapshot = _snapshot(stored={})
    snapshot["pipeline"] = "v4"
    snapshot["rerun_context"]["pipeline_id"] = "N/A"
    snapshot["rerun_context"]["parsed"]["recommendation"] = {}
    snapshot["rerun_context"]["parsed"]["trade_setup"] = {
        "trade_direction": "Long",
        "entry_zone": "NT$95-100",
        "target_price": "NT$95",
        "stop_loss": "NT$105",
    }

    result = project_content_credibility(snapshot)

    assert result["status"] == "blocked"
    assert {issue["id"] for issue in result["blocking_issues"]} == {
        "long_target_not_above_current_price",
        "long_stop_not_below_current_price",
    }


def test_evidence_projection_refreshes_legacy_check_without_parsed_context():
    from reporting.content_credibility_projection import project_evidence_confidence_alignment

    snapshot = _snapshot(stored={"status": "passed"})
    snapshot["rerun_context"] = {}
    snapshot["evidence_exit_gate"] = {"verdict": "caution", "failed_count": 0}
    recorded = {
        "status": "passed",
        "checks": [{
            "id": "confidence_evidence_alignment",
            "status": "passed",
            "details": {"evidence_verdict": "approved"},
        }],
    }

    result = project_evidence_confidence_alignment(snapshot, recorded)

    assert result["status"] == "warning"
    assert result["checks"][0]["status"] == "warning"
    assert result["checks"][0]["details"]["evidence_verdict"] == "caution"


def test_legacy_projection_uses_normalized_index_recommendation():
    from reporting.content_credibility_projection import project_content_credibility_with_current_evidence

    snapshot = _snapshot(stored={})
    snapshot["rerun_context"] = {}
    snapshot["evidence_exit_gate"] = {"verdict": "caution", "failed_count": 0}
    recommendation = {
        "recommendation": "持有",
        "current_price": "NT$209.00",
        "target_3m": "NT$174.5 - NT$209.0",
        "target_6m": "NT$209.0 - NT$254.0",
        "target_12m": "NT$254.0 - NT$327.0",
        "confidence": "6/10",
    }

    result = project_content_credibility_with_current_evidence(
        snapshot,
        {},
        evidence_projection=snapshot["evidence_exit_gate"],
        recommendation=recommendation,
    )

    assert result["_projection_scope"] == "recommendation_context"
    assert result["status"] == "warning"
    check = next(item for item in result["checks"] if item["id"] == "confidence_evidence_alignment")
    assert check["details"]["evidence_verdict"] == "caution"


def test_legacy_projection_rebuilds_empty_matrix_from_canonical_source_audit():
    from reporting.content_credibility_projection import project_content_credibility_with_current_evidence

    snapshot = _snapshot(stored={})
    snapshot["rerun_context"] = {}
    snapshot["evidence_matrix"] = []
    snapshot["data"]["source_audit"] = [{
        "source": "market_data",
        "status": "success",
        "provider": "fixture",
        "record_count": 1,
    }]

    result = project_content_credibility_with_current_evidence(
        snapshot,
        {},
        evidence_projection=snapshot["evidence_exit_gate"],
        recommendation={
            "recommendation": "持有",
            "current_price": "NT$100.00",
            "target_12m": "NT$110.00",
            "confidence": "6/10",
        },
    )

    assert result["_projection_scope"] == "recommendation_context"
    assert not any(issue["id"] == "missing_final_recommendation_evidence" for issue in result["warnings"])
    coverage_check = next(check for check in result["checks"] if check["id"] == "evidence_matrix_coverage")
    assert coverage_check["status"] == "passed"
