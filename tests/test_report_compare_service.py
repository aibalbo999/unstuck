import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_compare_compatibility_treats_legacy_false_requires_rerun_as_current():
    from report_compare_service import _compatibility

    left = {
        "filename": "left.html",
        "ticker": "2330.TW",
        "pipeline_id": "v2",
        "generated_at": "2026-09-01T01:00:00+00:00",
        "decision_freshness": {"requires_rerun": "false"},
    }
    right = {
        **left,
        "filename": "right.html",
        "generated_at": "2026-09-02T01:00:00+00:00",
    }

    result = _compatibility(left, right)

    assert result["warnings"] == []
