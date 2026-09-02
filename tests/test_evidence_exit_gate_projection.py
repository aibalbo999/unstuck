import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _snapshot():
    return {
        "pipeline": "v2",
        "data": {"dupont_identity_note": 0.891},
        "evidence_exit_gate": {
            "verdict": "approved",
            "failed_count": 0,
            "sampled_count": 1,
        },
    }


def test_projection_rechecks_current_evidence_without_mutating_snapshot():
    from reporting.evidence_exit_gate_projection import project_evidence_exit_gate

    snapshot = _snapshot()
    original = copy.deepcopy(snapshot)

    result = project_evidence_exit_gate(snapshot, "- 信心: 0.85")

    assert result["verdict"] == "caution"
    assert result["failed_count"] == 0
    assert result["unverifiable_count"] == 1
    assert snapshot == original


def test_projection_requires_both_snapshot_and_markdown():
    from reporting.evidence_exit_gate_projection import project_evidence_exit_gate

    assert project_evidence_exit_gate({}, "- 信心: 0.85") is None
    assert project_evidence_exit_gate(_snapshot(), "") is None


def test_projection_treats_legacy_false_requires_rerun_as_current(monkeypatch):
    import reporting.evidence_exit_gate_projection as projection

    monkeypatch.setattr(
        projection,
        "evaluate_report_evidence",
        lambda *_args: {"verdict": "approved"},
    )
    monkeypatch.setattr(
        projection,
        "build_decision_freshness",
        lambda **_kwargs: {"status": "current", "requires_rerun": "false"},
    )

    result = projection.project_evidence_exit_gate(_snapshot(), "- 信心: 0.85")

    assert "freshness_context" not in result
