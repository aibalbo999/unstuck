import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "secret_scan.py"


def test_secret_scan_catches_provider_keys(tmp_path):
    sample = tmp_path / "leaked.env"
    sample.write_text("GEMINI_API_KEYS=AIza" + ("A" * 36) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(sample)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "possible_google_api_key" in result.stdout
    assert "leaked.env" in result.stdout


def test_secret_scan_allows_placeholders(tmp_path):
    sample = tmp_path / "example.env"
    sample.write_text(
        "GEMINI_API_KEYS=replace_with_your_key\nOPENAI_API_KEY=sk-your_placeholder_key\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(sample)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "No obvious secrets found" in result.stdout


def test_ci_gate_runs_secret_scan():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "scripts/secret_scan.py" in ci_gate
