"""Select the highest-priority action from report-quality gates."""

from __future__ import annotations

from typing import Any

from report_quality_repair_items import (
    content_credibility_repair_item,
    evidence_exit_gate_repair_item,
    report_conformance_repair_item,
)


def quality_gate_repair_item(report: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        content_credibility_repair_item(report),
        report_conformance_repair_item(report),
        evidence_exit_gate_repair_item(report),
    ]
    return max((item for item in candidates if item is not None), key=lambda item: int(item["priority_score"]), default=None)
