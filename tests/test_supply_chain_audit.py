import json
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from requirements_lock import locked_versions as parse_locked_versions  # noqa: E402


def _parsed_requirements(path: Path) -> dict[str, Requirement]:
    return {
        canonicalize_name(requirement.name): requirement
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
        for requirement in [Requirement(line)]
    }


def _locked_versions(path: Path) -> dict[str, Version]:
    return parse_locked_versions(path)


def test_free_external_data_dependencies_are_locked():
    direct = _parsed_requirements(ROOT / "backend" / "requirements.txt")
    locked = _locked_versions(ROOT / "backend" / "requirements.lock")
    expected = {"feedparser", "ddgs", "beautifulsoup4", "requests", "trafilatura"}

    for name in expected:
        assert name in direct, f"{name} must be a direct requirement"
        operators = {specifier.operator for specifier in direct[name].specifier}
        assert operators & {">", ">="}, f"{name} must have a lower bound"
        assert operators & {"<", "<="}, f"{name} must have an upper bound"
        assert name in locked, f"{name} must have an exact locked version"
        assert locked[name] in direct[name].specifier, (
            f"locked {name}=={locked[name]} must satisfy {direct[name].specifier}"
        )


def test_supply_chain_lockfile_covers_direct_runtime_requirements():
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    lockfile = ROOT / "backend" / "requirements.lock"
    locked = lockfile.read_text(encoding="utf-8")

    direct_names = [
        line.split("<", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().lower().replace("_", "-")
        for line in requirements.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    locked_names = {
        line.split("==", 1)[0].strip().lower().replace("_", "-")
        for line in locked.splitlines()
        if "==" in line
    }

    assert direct_names
    assert set(direct_names) <= locked_names


def test_lockfile_uses_hash_pinned_requirements():
    lockfile = ROOT / "backend" / "requirements.lock"
    text = lockfile.read_text(encoding="utf-8")
    requirement_lines = [
        line
        for line in text.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and not line.startswith(" ")
        and "==" in line
    ]

    assert requirement_lines
    assert "--hash=sha256:" in text
    for line in requirement_lines:
        assert line.rstrip().endswith("\\") or "--hash=sha256:" in line


def test_langgraph_dependencies_are_direct_and_locked():
    direct = set(_parsed_requirements(ROOT / "backend" / "requirements.txt"))
    locked = set(_locked_versions(ROOT / "backend" / "requirements.lock"))

    assert {"langgraph", "langgraph-checkpoint-sqlite"} <= direct
    assert {"langgraph", "langgraph-checkpoint-sqlite", "aiosqlite"} <= locked


def test_ci_gate_runs_supply_chain_audit_before_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")
    audit_script = ROOT / "scripts" / "supply_chain_audit.py"

    assert audit_script.exists()
    assert "scripts/supply_chain_audit.py" in ci_gate
    assert ci_gate.index("scripts/supply_chain_audit.py") < ci_gate.index("-m pytest")


def test_bootstrap_installs_hash_locked_requirements():
    bootstrap = (ROOT / "scripts" / "bootstrap_venv.sh").read_text(encoding="utf-8")

    assert "backend/requirements.lock" in bootstrap
    assert "--require-hashes" in bootstrap
    assert "backend/requirements.txt" not in bootstrap


def test_sbom_generator_outputs_cyclonedx_from_lockfile(tmp_path):
    requirements = tmp_path / "requirements.lock"
    output = tmp_path / "sbom.cdx.json"
    requirements.write_text("requests==2.34.2\ncoverage==7.14.3\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_sbom.py"),
            "--requirements",
            str(requirements),
            "--output",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    sbom = json.loads(output.read_text(encoding="utf-8"))

    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert {component["purl"] for component in sbom["components"]} == {
        "pkg:pypi/requests@2.34.2",
        "pkg:pypi/coverage@7.14.3",
    }


def test_sbom_generator_parses_hash_pinned_lockfile(tmp_path):
    requirements = tmp_path / "requirements.lock"
    output = tmp_path / "sbom.cdx.json"
    requirements.write_text(
        """requests==2.34.2 \\
    --hash=sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \\
    --hash=sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
coverage==7.14.3 \\
    --hash=sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
""",
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_sbom.py"),
            "--requirements",
            str(requirements),
            "--output",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    sbom = json.loads(output.read_text(encoding="utf-8"))

    assert {component["purl"] for component in sbom["components"]} == {
        "pkg:pypi/requests@2.34.2",
        "pkg:pypi/coverage@7.14.3",
    }


def test_ci_gate_generates_sbom_before_coverage_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")
    sbom_script = ROOT / "scripts" / "generate_sbom.py"

    assert sbom_script.exists()
    assert "scripts/generate_sbom.py" in ci_gate
    assert ci_gate.index("scripts/generate_sbom.py") < ci_gate.index("-m coverage run")


def test_ci_gate_runs_mypy_on_core_type_contracts_before_coverage_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "-m mypy" in ci_gate
    assert "backend/analysis_types.py" in ci_gate
    assert "backend/workflow_state.py" in ci_gate
    assert ci_gate.index("-m mypy") < ci_gate.index("-m coverage run")
