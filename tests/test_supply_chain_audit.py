import json
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from requirements_lock import (  # noqa: E402
    locked_requirements,
    locked_versions as parse_locked_versions,
    unhashed_locked_requirements,
)
import supply_chain_audit as audit  # noqa: E402


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
    expected = {"feedparser", "ddgs", "beautifulsoup4", "httpx", "trafilatura"}

    for name in expected:
        assert name in direct, f"{name} must be a direct requirement"
        operators = {specifier.operator for specifier in direct[name].specifier}
        assert operators & {">", ">="}, f"{name} must have a lower bound"
        assert operators & {"<", "<="}, f"{name} must have an upper bound"
        assert name in locked, f"{name} must have an exact locked version"
        assert locked[name] in direct[name].specifier, (
            f"locked {name}=={locked[name]} must satisfy {direct[name].specifier}"
        )
    assert "requests" not in direct, "requests should not be a direct runtime requirement after httpx migration"


def test_supply_chain_lockfile_covers_direct_runtime_requirements():
    requirements = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    lockfile = ROOT / "backend" / "requirements.lock"

    direct_names = [
        line.split("<", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().lower().replace("_", "-")
        for line in requirements.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    locked_names = set(locked_requirements(lockfile))

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


def test_supply_chain_audit_covers_visual_runtime_lockfile():
    audit_script = (ROOT / "scripts" / "supply_chain_audit.py").read_text(encoding="utf-8")
    source = ROOT / "scripts" / "visual_requirements.txt"
    lockfile = ROOT / "scripts" / "visual_requirements.lock"
    direct = _parsed_requirements(source)
    locked = locked_requirements(lockfile)

    assert "visual_requirements.txt" in audit_script
    assert "visual_requirements.lock" in audit_script
    assert set(direct) <= set(locked)
    assert unhashed_locked_requirements(lockfile) == []


def test_backend_lock_excludes_currently_reported_vulnerable_versions():
    direct = _parsed_requirements(ROOT / "backend" / "requirements.txt")
    locked = _locked_versions(ROOT / "backend" / "requirements.lock")
    minimums = {
        "aiohttp": Version("3.14.1"),
        "cryptography": Version("48.0.1"),
        "pytest": Version("9.0.3"),
        "starlette": Version("1.3.1"),
    }

    for name, minimum in minimums.items():
        assert name in direct
        assert minimum in direct[name].specifier
        assert locked[name] >= minimum


def test_pip_audit_toolchain_is_hash_locked_and_bootstrapped():
    source = ROOT / "scripts" / "security_requirements.txt"
    lockfile = ROOT / "scripts" / "security_requirements.lock"
    bootstrap = (ROOT / "scripts" / "bootstrap_venv.sh").read_text(encoding="utf-8")

    assert source.exists()
    assert lockfile.exists()
    assert "scripts/setup_security_audit.sh" in bootstrap
    direct = _parsed_requirements(source)
    locked = locked_requirements(lockfile)
    assert set(direct) <= set(locked)
    assert str(locked["pip-audit"].specifier) == "==2.10.1"
    assert unhashed_locked_requirements(lockfile) == []


def test_supply_chain_audit_fails_closed_without_pip_audit(monkeypatch):
    monkeypatch.delenv("SUPPLY_CHAIN_SKIP_PIP_AUDIT", raising=False)
    monkeypatch.setattr(audit, "resolve_pip_audit", lambda: None)

    assert audit.run_pip_audit_if_available() == 1


def test_security_audit_uses_isolated_hash_locked_environment():
    setup_script = ROOT / "scripts" / "setup_security_audit.sh"
    setup = setup_script.read_text(encoding="utf-8") if setup_script.exists() else ""
    bootstrap = (ROOT / "scripts" / "bootstrap_venv.sh").read_text(encoding="utf-8")
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert setup_script.exists()
    assert ".audit-venv" in setup
    assert "--require-hashes -r scripts/security_requirements.lock" in setup
    assert "scripts/setup_security_audit.sh" in bootstrap
    assert "scripts/setup_security_audit.sh" in ci_gate
    assert ci_gate.index("scripts/setup_security_audit.sh") < ci_gate.index("scripts/supply_chain_audit.py")


def test_langgraph_dependencies_are_direct_and_locked():
    direct = set(_parsed_requirements(ROOT / "backend" / "requirements.txt"))
    locked = set(_locked_versions(ROOT / "backend" / "requirements.lock"))

    assert {"langgraph", "langgraph-checkpoint-sqlite", "langgraph-checkpoint-postgres"} <= direct
    assert {"langgraph", "langgraph-checkpoint-sqlite", "langgraph-checkpoint-postgres", "aiosqlite", "psycopg"} <= locked


def test_ci_gate_runs_supply_chain_audit_before_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")
    audit_script = ROOT / "scripts" / "supply_chain_audit.py"

    assert audit_script.exists()
    assert "scripts/supply_chain_audit.py" in ci_gate
    assert ci_gate.index("scripts/supply_chain_audit.py") < ci_gate.index("-m pytest")


def test_ci_gate_runs_visual_regression_by_default_in_ci():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert 'case "${CI:-}" in' in ci_gate
    assert "1|true|TRUE|yes|YES)" in ci_gate
    assert 'RUN_VISUAL_REGRESSION:-' in ci_gate
    assert "VISUAL_REGRESSION_REQUIRED=1 scripts/visual_regression.sh" in ci_gate


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


def test_ci_gate_generates_visual_runtime_sbom_before_coverage_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "scripts/visual_requirements.lock" in ci_gate
    assert "backend/cache/visual-sbom.cdx.json" in ci_gate
    assert ci_gate.index("visual-sbom.cdx.json") < ci_gate.index("-m coverage run")


def test_ci_gate_runs_mypy_on_core_type_contracts_before_coverage_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "-m mypy" in ci_gate
    assert "backend/analysis_types.py" in ci_gate
    assert "backend/workflow_state.py" in ci_gate
    assert ci_gate.index("-m mypy") < ci_gate.index("-m coverage run")


def test_ci_gate_compileall_excludes_runtime_artifacts():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")

    assert "-m compileall" in ci_gate
    assert "backend/(cache|output)" in ci_gate
