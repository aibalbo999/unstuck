import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_conformance_data_trust_step_prefers_snapshot_and_passes_fresh_status():
    from reporting.conformance_data_trust_step import build_data_trust_conformance_step

    result = build_data_trust_conformance_step(
        context={"data": {"data_trust": {"status": "stale"}}},
        snapshot={"data_trust": {"status": "fresh"}},
    )

    assert result["decision_tree"] == [{"id": "data_trust", "status": "passed", "message": "資料可信度為 fresh。"}]
    assert result["blocking_issues"] == []
    assert result["warnings"] == []


def test_conformance_data_trust_step_warns_for_context_fallback_status():
    from reporting.conformance_data_trust_step import build_data_trust_conformance_step

    result = build_data_trust_conformance_step(
        context=MappingProxyType({"data": {"data_trust": {"status": "partial", "critical_failures": ["market_data"]}}}),
        snapshot=MappingProxyType({}),
    )

    step = result["decision_tree"][0]
    assert step["id"] == "data_trust"
    assert step["status"] == "warning"
    assert "資料可信度為" in step["message"]
    assert "partial" in step["message"]
    assert result["blocking_issues"] == []
    assert [warning["id"] for warning in result["warnings"]] == ["data_trust"]
