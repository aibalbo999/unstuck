from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]


def _parsed_requirements(path: Path) -> dict[str, Requirement]:
    return {
        canonicalize_name(requirement.name): requirement
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
        for requirement in [Requirement(line)]
    }


def _locked_versions(path: Path) -> dict[str, Version]:
    versions = {}
    for name, requirement in _parsed_requirements(path).items():
        specifiers = list(requirement.specifier)
        if len(specifiers) == 1 and specifiers[0].operator == "==":
            versions[name] = Version(specifiers[0].version)
    return versions


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


def test_ci_gate_runs_supply_chain_audit_before_tests():
    ci_gate = (ROOT / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")
    audit_script = ROOT / "scripts" / "supply_chain_audit.py"

    assert audit_script.exists()
    assert "scripts/supply_chain_audit.py" in ci_gate
    assert ci_gate.index("scripts/supply_chain_audit.py") < ci_gate.index("-m pytest")
