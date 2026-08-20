import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_projection_updates_persisted_passed_gate_to_current_warning():
    from reporting.report_conformance_projection import project_report_conformance

    result = project_report_conformance(
        {
            "schema_version": 1,
            "status": "passed",
            "summary": "報告符合輸出契約。",
            "decision_tree": [
                {"id": "evidence_exit_gate", "status": "passed", "message": "證據抽查通過。"},
                {"id": "content_credibility", "status": "passed", "message": "內容可信度檢查通過。"},
            ],
            "blocking_issues": [],
            "warnings": [],
        },
        {"verdict": "caution", "unverifiable_count": 2},
        {"status": "warning", "warnings": [{"id": "non_approved_evidence_gate"}]},
    )

    assert result["status"] == "warning"
    assert [step["status"] for step in result["decision_tree"]] == ["warning", "warning"]
    assert {item["id"] for item in result["warnings"]} == {"evidence_exit_gate", "content_credibility"}


def test_projection_can_surface_current_quality_when_persisted_conformance_is_missing():
    from reporting.report_conformance_projection import project_report_conformance

    result = project_report_conformance({}, {"verdict": "rejected"}, {"status": "warning"})

    assert result["status"] == "blocked"
    assert [step["id"] for step in result["decision_tree"]] == ["evidence_exit_gate", "content_credibility"]
