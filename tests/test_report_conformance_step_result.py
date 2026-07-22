import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_conformance_step_result_builds_warning_and_blocking_buckets():
    from reporting.conformance_step_result import merge_step_result, step, step_result

    warning = step_result(step("report_lint", "warning", "報告 lint 有警示。", [{"id": "lint"}]), issue_kind="warning")
    blocking = step_result(step("final_audit", "blocked", "最終稽核存在 critical 問題。"), issue_kind="blocking")
    result = {"decision_tree": [], "blocking_issues": [], "warnings": []}
    merge_step_result(result, warning)
    merge_step_result(result, blocking)

    assert [item["id"] for item in result["decision_tree"]] == ["report_lint", "final_audit"]
    assert result["warnings"] == [
        {"id": "report_lint", "message": "報告 lint 有警示。", "details": [{"id": "lint"}]}
    ]
    assert result["blocking_issues"] == [
        {"id": "final_audit", "message": "最終稽核存在 critical 問題。", "details": None}
    ]
