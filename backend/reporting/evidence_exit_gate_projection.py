"""Read-only current-rule projections for persisted evidence gates."""

from __future__ import annotations

from typing import Any

from decision_tracking import build_decision_freshness
from evidence_exit_gate import evaluate_report_evidence
from mapping_fields import safe_mapping_dict, safe_text


def project_evidence_exit_gate(snapshot: Any, markdown: Any) -> dict[str, Any] | None:
    """Re-evaluate a saved report without mutating its snapshot or artifact."""
    snapshot_map = safe_mapping_dict(snapshot) or {}
    markdown_text = safe_text(markdown)
    if not snapshot_map or not markdown_text.strip():
        return None
    try:
        projected = evaluate_report_evidence(markdown_text, snapshot_map)
        freshness = build_decision_freshness(snapshot=snapshot_map)
        if freshness.get("requires_rerun"):
            projected["freshness_context"] = {
                key: freshness[key]
                for key in ("status", "requires_rerun", "conclusion_generated_at", "snapshot_refreshed_at", "requires_rerun_reason")
                if key in freshness
            }
        return projected
    except Exception:
        # Historical rows are read-only; malformed legacy content stays available.
        return None


def evidence_exit_gate_projection_metadata(projected: Any, recorded: Any) -> dict[str, str]:
    projected_map = safe_mapping_dict(projected) or {}
    recorded_map = safe_mapping_dict(recorded) or {}
    return {
        "status": "projected" if projected_map else "unavailable",
        "source": "markdown+snapshot.current_rules",
        "persisted_verdict": safe_text(recorded_map.get("verdict")).strip().lower(),
    }


__all__ = ["evidence_exit_gate_projection_metadata", "project_evidence_exit_gate"]
