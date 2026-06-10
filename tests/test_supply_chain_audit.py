from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
