from decimal import Decimal
import sys
from pathlib import Path
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from reporting.reading_notice_values import build_report_reading_notice_values  # noqa: E402


def _context(**overrides):
    context = {"data": {"data_trust": {"status": "fresh"}}}
    context.update(overrides)
    return context


def test_reading_notice_values_block_invalid_snapshot_integrity_with_specific_detail():
    values = build_report_reading_notice_values(
        _context(
            evidence_exit_gate={"verdict": "approved"},
            content_credibility={"status": "passed"},
            report_conformance={"status": "passed"},
            snapshot_integrity={
                "status": "invalid",
                "valid": False,
                "errors": ["provider audit source digest mismatch"],
            },
        )
    )

    assert values["state"] == "blocked"
    assert values["state_label"] == "品質 gate 未通過"
    assert "provider audit source digest mismatch" in values["state_note"]
    assert ("資料快照完整性", "未通過") in values["checks"]


def test_reading_notice_values_treat_mapping_quality_gates_as_recorded():
    values = build_report_reading_notice_values(
        _context(
            evidence_exit_gate=MappingProxyType({"verdict": "approved"}),
            content_credibility=MappingProxyType({"status": "passed"}),
            report_conformance=MappingProxyType({"status": "passed"}),
        )
    )

    assert values["state"] == "passed"
    assert values["state_label"] == "已通過已知檢查"
    assert values["state_note"].startswith("綠燈只代表已知自動檢查通過")
    assert ("證據抽查", "已通過") in values["checks"]
    assert ("內容一致性", "已通過") in values["checks"]
    assert ("輸出契約", "已通過") in values["checks"]


def test_reading_notice_values_warn_for_partial_gate_records():
    values = build_report_reading_notice_values(
        _context(content_credibility={"status": "passed"})
    )

    assert values["state"] == "warning"
    assert values["state_label"] == "品質 gate 有警示"
    assert ("內容一致性", "已通過") in values["checks"]
    assert ("證據抽查", "未記錄") in values["checks"]


def test_reading_notice_values_drop_non_finite_gate_status_text():
    values = build_report_reading_notice_values(
        _context(
            data={"data_trust": {"status": Decimal("NaN")}},
            evidence_exit_gate={"verdict": Decimal("Infinity")},
            content_credibility={"status": float("nan")},
            report_conformance={"status": Decimal("-Infinity")},
        )
    )

    rendered_checks = " ".join(f"{label} {value}" for label, value in values["checks"])

    assert values["state"] == "warning"
    assert ("資料可信度", "未記錄") in values["checks"]
    assert ("證據抽查", "未記錄") in values["checks"]
    assert ("內容一致性", "未記錄") in values["checks"]
    assert ("輸出契約", "未記錄") in values["checks"]
    assert "nan" not in rendered_checks.lower()
    assert "infinity" not in rendered_checks.lower()


def test_reading_notice_values_drop_non_finite_string_gate_status_text():
    values = build_report_reading_notice_values(
        _context(
            data={"data_trust": {"status": "NaN"}},
            evidence_exit_gate={"verdict": "Infinity"},
            content_credibility={"status": "-Infinity"},
            report_conformance={"status": "N/A"},
        )
    )

    rendered_checks = " ".join(f"{label} {value}" for label, value in values["checks"])

    assert values["state"] == "warning"
    assert ("資料可信度", "未記錄") in values["checks"]
    assert ("證據抽查", "未記錄") in values["checks"]
    assert ("內容一致性", "未記錄") in values["checks"]
    assert ("輸出契約", "未記錄") in values["checks"]
    assert "nan" not in rendered_checks.lower()
    assert "infinity" not in rendered_checks.lower()
