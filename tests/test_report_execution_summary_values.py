from decimal import Decimal
import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_execution_summary_values_build_deterministic_runtime_payload():
    from reporting.execution_summary_values import build_execution_summary_values

    values = build_execution_summary_values(
        {
            "pipeline_id": "v4",
            "agent_sequence": (22, "23", "bad-agent", True, 24),
            "data": {"data_trust": {"status": "fresh"}},
            "final_audit": {"status": "passed"},
            "evidence_exit_gate": {"verdict": "approved", "summary": "抽樣通過。"},
            "report_conformance": {"status": "passed", "summary": "符合輸出契約。"},
            "report_lint": {"status": "clean"},
            "prompt_version": "runtime v4",
            "model_id": "gemini-test",
        },
        model_routes="primary route",
    )

    assert values["pipeline"] == "V4"
    assert values["agent_sequence"] == [22, 23, 24]
    assert values["agent_count"] == 3
    assert values["structured_agent_count"] == 1
    assert values["model_routes"] == "primary route"
    assert values["data_trust"] == "資料新鮮"
    assert values["final_audit"] == "passed"
    assert values["evidence_gate"] == "approved"
    assert values["evidence_summary"] == "抽樣通過。"
    assert values["report_conformance"] == "passed"
    assert values["conformance_summary"] == "符合輸出契約。"
    assert values["report_lint"] == "clean"
    assert values["prompt_version"] == "runtime v4"
    assert values["model_id"] == "gemini-test"


def test_execution_summary_values_accept_mapping_safe_quality_gate_child_maps():
    from reporting.execution_summary_values import build_execution_summary_values

    values = build_execution_summary_values(
        MappingProxyType({
            "pipeline_id": "v1",
            "data": MappingProxyType({"data_trust": MappingProxyType({"status": "partial"})}),
            "final_audit": MappingProxyType({"status": "warning"}),
            "evidence_exit_gate": MappingProxyType({"verdict": "caution"}),
            "report_conformance": MappingProxyType({"status": "warning"}),
            "report_lint": MappingProxyType({"status": "warning"}),
        }),
        model_routes="primary",
    )

    assert values["data_trust"] == "部分異常"
    assert values["data_trust_raw"] == "partial"
    assert values["final_audit"] == "warning"
    assert values["evidence_gate"] == "caution"
    assert values["report_conformance"] == "warning"
    assert values["report_lint"] == "warning"


def test_execution_summary_values_use_safe_text_and_collapse_newlines():
    from reporting.execution_summary_values import build_execution_summary_values

    class MalformedText:
        def __str__(self):
            raise RuntimeError("execution summary value unavailable")

    values = build_execution_summary_values(
        {
            "pipeline_id": "v1",
            "agent_sequence": b"bad-agent-sequence",
            "data": {"data_trust": {"status": "unknown"}},
            "final_audit": {"status": b"bad-final-status"},
            "evidence_exit_gate": {"verdict": "caution\nmanual check", "summary": MalformedText()},
            "report_conformance": {"status": "warning\nminor", "summary": "符合性\n仍需注意"},
            "report_lint": {"status": bytearray(b"bad-lint-status")},
            "prompt_version": "runtime\nv2",
            "model_id": memoryview(b"bad-model-id"),
        },
        model_routes="primary\nbackup",
    )

    assert values["agent_sequence"]
    assert values["model_routes"] == "primary backup"
    assert values["final_audit"] == "not_recorded"
    assert values["evidence_gate"] == "caution manual check"
    assert values["evidence_summary"] == ""
    assert values["report_conformance"] == "warning minor"
    assert values["conformance_summary"] == "符合性 仍需注意"
    assert values["report_lint"] == "not_recorded"
    assert values["prompt_version"] == "runtime v2"
    assert values["model_id"] == "N/A"


def test_execution_summary_values_drop_non_finite_status_text_fields():
    from reporting.execution_summary_values import build_execution_summary_values

    values = build_execution_summary_values(
        {
            "pipeline_id": "v1",
            "data": {"data_trust": {"status": Decimal("NaN")}},
            "final_audit": {"status": Decimal("Infinity")},
            "evidence_exit_gate": {"verdict": float("nan"), "summary": Decimal("NaN")},
            "report_conformance": {"status": Decimal("-Infinity"), "summary": float("inf")},
            "report_lint": {"status": float("-inf")},
            "prompt_version": Decimal("Infinity"),
            "model_id": Decimal("-Infinity"),
        },
        model_routes=Decimal("NaN"),
    )

    rendered = " ".join(str(value) for value in values.values())

    assert values["model_routes"] == "N/A"
    assert values["data_trust"] == "未記錄"
    assert values["data_trust_raw"] == "unknown"
    assert values["final_audit"] == "not_recorded"
    assert values["evidence_gate"] == "not_recorded"
    assert values["evidence_summary"] == ""
    assert values["report_conformance"] == "not_recorded"
    assert values["conformance_summary"] == ""
    assert values["report_lint"] == "not_recorded"
    assert values["prompt_version"] == "N/A"
    assert values["model_id"] == "N/A"
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()


def test_execution_summary_values_drop_non_finite_string_status_text_fields():
    from reporting.execution_summary_values import build_execution_summary_values

    values = build_execution_summary_values(
        {
            "pipeline_id": "v1",
            "data": {"data_trust": {"status": "NaN"}},
            "final_audit": {"status": "Infinity"},
            "evidence_exit_gate": {"verdict": "NaN", "summary": "N/A"},
            "report_conformance": {"status": "-Infinity", "summary": "Infinity"},
            "report_lint": {"status": "N/A"},
            "prompt_version": "NaN",
            "model_id": "Infinity",
        },
        model_routes="-Infinity",
    )

    rendered = " ".join(str(value) for value in values.values())

    assert values["model_routes"] == "N/A"
    assert values["data_trust"] == "未記錄"
    assert values["data_trust_raw"] == "unknown"
    assert values["final_audit"] == "not_recorded"
    assert values["evidence_gate"] == "not_recorded"
    assert values["evidence_summary"] == ""
    assert values["report_conformance"] == "not_recorded"
    assert values["conformance_summary"] == ""
    assert values["report_lint"] == "not_recorded"
    assert values["prompt_version"] == "N/A"
    assert values["model_id"] == "N/A"
    assert "nan" not in rendered.lower()
    assert "infinity" not in rendered.lower()
