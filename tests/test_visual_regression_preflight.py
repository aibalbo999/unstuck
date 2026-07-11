import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "check_visual_regression.py"


def test_visual_regression_preflight_launches_chromium_in_current_runtime():
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["browser"] == "chromium"


def test_ci_gate_runs_visual_preflight_before_required_visual_regression():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "scripts/check_visual_regression.py" in ci_gate
    assert ci_gate.index("scripts/check_visual_regression.py") < ci_gate.index("VISUAL_REGRESSION_REQUIRED=1 scripts/visual_regression.sh")
