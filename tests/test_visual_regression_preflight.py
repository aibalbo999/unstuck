import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "check_visual_regression.py"
VISUAL_LOCK = ROOT / "scripts" / "visual_requirements.lock"
BROWSER_MANIFEST = ROOT / "scripts" / "visual_browser_runtime.json"

sys.path.insert(0, str(ROOT / "scripts"))

from requirements_lock import locked_requirements, unhashed_locked_requirements  # noqa: E402


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
    assert payload["browser_revision"] == "1223"
    assert payload["browser_version"] == "148.0.7778.96"


def test_ci_gate_runs_visual_preflight_before_required_visual_regression():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "scripts/check_visual_regression.py" in ci_gate
    assert ci_gate.index("scripts/check_visual_regression.py") < ci_gate.index("VISUAL_REGRESSION_REQUIRED=1 scripts/visual_regression.sh")


def test_direct_visual_regression_script_runs_the_same_preflight_before_pytest():
    visual_script = (ROOT / "scripts" / "visual_regression.sh").read_text(encoding="utf-8")

    assert "scripts/check_visual_regression.py" in visual_script
    assert visual_script.index("scripts/check_visual_regression.py") < visual_script.index("-m pytest")


def test_visual_setup_pins_playwright_python_dependency():
    setup_script = (ROOT / "scripts" / "setup_visual_regression.sh").read_text(encoding="utf-8")
    lockfile = VISUAL_LOCK.read_text(encoding="utf-8")

    assert "--require-hashes -r scripts/visual_requirements.lock" in setup_script
    assert "playwright==1.60.0" in lockfile


def test_visual_regression_preflight_is_directly_executable():
    assert PREFLIGHT.stat().st_mode & stat.S_IXUSR


def test_visual_setup_uses_hash_locked_dependency_file():
    setup_script = (ROOT / "scripts" / "setup_visual_regression.sh").read_text(encoding="utf-8")

    assert '--require-hashes -r scripts/visual_requirements.lock' in setup_script
    assert "pip install -q playwright" not in setup_script


def test_visual_dependency_lock_covers_playwright_runtime_dependencies():
    assert VISUAL_LOCK.exists()
    locked = locked_requirements(VISUAL_LOCK)

    assert str(locked["playwright"].specifier) == "==1.60.0"
    assert {"greenlet", "pyee", "typing-extensions"} <= set(locked)
    assert unhashed_locked_requirements(VISUAL_LOCK) == []


def test_visual_browser_manifest_pins_playwright_chromium_identity():
    manifest = json.loads(BROWSER_MANIFEST.read_text(encoding="utf-8"))

    assert manifest == {
        "browser": "chromium",
        "browser_version": "148.0.7778.96",
        "playwright": "1.60.0",
        "revision": "1223",
    }
