import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import reporting.conformance_data_trust_step as data_trust_step  # noqa: E402
from reporting.conformance_steps import build_conformance_gate_steps  # noqa: E402


def test_conformance_steps_build_gate_decision_tree_and_issue_buckets():
    result = build_conformance_gate_steps(
        context={
            "data": {"data_trust": {"status": "fresh"}},
            "final_audit": {"status": "warning", "critical": [], "warnings": [{"id": "audit_warning"}]},
        },
        snapshot={"data_trust": {"status": "fresh"}},
        report_lint={"status": "warning", "blocking_issues": [], "warnings": [{"id": "lint_warning"}]},
        evidence_exit_gate={"verdict": "rejected", "failed_count": 1},
        content_credibility={"status": "blocked", "blocking_issues": [{"id": "credibility_blocker"}], "warnings": []},
    )

    assert [step["id"] for step in result["decision_tree"]] == [
        "report_lint",
        "final_audit",
        "evidence_exit_gate",
        "content_credibility",
        "data_trust",
    ]
    assert [step["status"] for step in result["decision_tree"]] == [
        "warning",
        "warning",
        "blocked",
        "blocked",
        "passed",
    ]
    assert {issue["id"] for issue in result["blocking_issues"]} == {
        "evidence_exit_gate",
        "content_credibility",
    }
    assert {issue["id"] for issue in result["warnings"]} == {
        "report_lint",
        "final_audit",
    }


def test_conformance_steps_accept_mapping_safe_payloads_and_tuple_issues():
    result = build_conformance_gate_steps(
        context=MappingProxyType({
            "data": {"data_trust": {"status": "stale"}},
            "final_audit": {"status": "passed", "critical": [], "warnings": []},
        }),
        snapshot=MappingProxyType({}),
        report_lint=MappingProxyType({"status": "passed", "blocking_issues": [], "warnings": []}),
        evidence_exit_gate=MappingProxyType({"verdict": "approved"}),
        content_credibility=MappingProxyType({
            "status": "passed",
            "blocking_issues": ({"id": "tuple_blocker"},),
            "warnings": (),
        }),
    )

    assert any(issue["id"] == "content_credibility" for issue in result["blocking_issues"])
    assert any(issue["id"] == "data_trust" for issue in result["warnings"])
    assert result["decision_tree"][-1]["status"] == "warning"


def test_conformance_steps_drop_string_empty_gate_status_tokens():
    result = build_conformance_gate_steps(
        context={
            "data": {"data_trust": {"status": "fresh"}},
            "final_audit": {"status": "Infinity", "critical": [], "warnings": []},
        },
        snapshot={"data_trust": {"status": "fresh"}},
        report_lint={"status": "NaN", "blocking_issues": [], "warnings": []},
        evidence_exit_gate={"verdict": "NaN", "failed_count": 0},
        content_credibility={"status": "-Infinity", "blocking_issues": [], "warnings": []},
    )

    statuses = {step["id"]: step["status"] for step in result["decision_tree"]}
    assert statuses["report_lint"] == "passed"
    assert statuses["final_audit"] == "passed"
    assert statuses["evidence_exit_gate"] == "warning"
    assert statuses["content_credibility"] == "passed"

    evidence_step = next(step for step in result["decision_tree"] if step["id"] == "evidence_exit_gate")
    assert evidence_step["details"]["verdict"] == "not_recorded"
    rendered = str(result).lower()
    assert "nan" not in rendered
    assert "infinity" not in rendered


def test_data_trust_conformance_step_drops_string_empty_status_tokens(monkeypatch):
    monkeypatch.setattr(
        data_trust_step,
        "normalize_data_trust",
        lambda value: {"status": "Infinity", "score": 80, "notes": ["有效限制說明"]},
    )

    result = data_trust_step.build_data_trust_conformance_step(
        context={"data": {"data_trust": {"status": "fresh"}}},
        snapshot={},
    )

    data_step = result["decision_tree"][0]
    assert data_step["status"] == "warning"
    assert data_step["details"]["status"] == "unknown"
    assert "未記錄（unknown）" in data_step["message"]
    rendered = str(result).lower()
    assert "有效限制說明" in rendered
    assert "infinity" not in rendered
