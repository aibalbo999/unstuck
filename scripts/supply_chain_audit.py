#!/usr/bin/env python3
"""Offline supply-chain guard for runtime and visual Python dependencies."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from requirements_lock import locked_requirements, unhashed_locked_requirements


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
LOCKFILE = ROOT / "backend" / "requirements.lock"
VISUAL_REQUIREMENTS = ROOT / "scripts" / "visual_requirements.txt"
VISUAL_LOCKFILE = ROOT / "scripts" / "visual_requirements.lock"
SECURITY_REQUIREMENTS = ROOT / "scripts" / "security_requirements.txt"
SECURITY_LOCKFILE = ROOT / "scripts" / "security_requirements.lock"
AUDIT_VENV = ROOT / ".audit-venv"


def package_name(line: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", line)
    return match.group(1).lower().replace("_", "-") if match else ""


def requirements_from(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.add(package_name(stripped))
    return {name for name in names if name}


def direct_requirements() -> set[str]:
    return requirements_from(REQUIREMENTS)


def locked_packages(path: Path) -> set[str]:
    return set(locked_requirements(path))


def validate_lock(source: Path, lockfile: Path, label: str) -> bool:
    missing = sorted(requirements_from(source) - locked_packages(lockfile))
    if missing:
        print(f"{label} lockfile missing packages: " + ", ".join(missing))
        return False
    unhashed = unhashed_locked_requirements(lockfile)
    if unhashed:
        print(f"{label} lockfile requirements missing hashes: " + ", ".join(unhashed))
        return False
    return True


def resolve_pip_audit() -> str | None:
    configured = os.getenv("PIP_AUDIT_BIN")
    if configured:
        return configured if Path(configured).is_file() else None
    isolated = AUDIT_VENV / "bin" / "pip-audit"
    if isolated.is_file():
        return str(isolated)
    return shutil.which("pip-audit")


def run_pip_audit_if_available() -> int:
    if os.getenv("SUPPLY_CHAIN_SKIP_PIP_AUDIT") == "1":
        print("pip-audit skipped by SUPPLY_CHAIN_SKIP_PIP_AUDIT=1")
        return 0
    pip_audit = resolve_pip_audit()
    if pip_audit is None:
        print("pip-audit unavailable; run scripts/bootstrap_venv.sh or set SUPPLY_CHAIN_SKIP_PIP_AUDIT=1 explicitly.")
        return 1
    for lockfile in (LOCKFILE, VISUAL_LOCKFILE, SECURITY_LOCKFILE):
        result = subprocess.run([pip_audit, "-r", str(lockfile)], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


def main() -> int:
    for path, label in (
        (REQUIREMENTS, "Runtime requirements"),
        (VISUAL_REQUIREMENTS, "Visual requirements"),
        (SECURITY_REQUIREMENTS, "Security requirements"),
    ):
        if not path.exists():
            print(f"Missing {label.lower()} file: {path.relative_to(ROOT)}")
            return 1
    for path, label in (
        (LOCKFILE, "Runtime"),
        (VISUAL_LOCKFILE, "Visual"),
        (SECURITY_LOCKFILE, "Security"),
    ):
        if not path.exists():
            print(f"Missing {label.lower()} lockfile: {path.relative_to(ROOT)}")
            return 1

    if not validate_lock(REQUIREMENTS, LOCKFILE, "Runtime"):
        return 1
    if not validate_lock(VISUAL_REQUIREMENTS, VISUAL_LOCKFILE, "Visual"):
        return 1
    if not validate_lock(SECURITY_REQUIREMENTS, SECURITY_LOCKFILE, "Security"):
        return 1

    return run_pip_audit_if_available()


if __name__ == "__main__":
    raise SystemExit(main())
