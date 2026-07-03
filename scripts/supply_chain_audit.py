#!/usr/bin/env python3
"""Offline supply-chain guard for backend Python dependencies."""

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


def package_name(line: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", line)
    return match.group(1).lower().replace("_", "-") if match else ""


def direct_requirements() -> set[str]:
    names = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.add(package_name(stripped))
    return {name for name in names if name}


def locked_packages() -> set[str]:
    return set(locked_requirements(LOCKFILE))


def run_pip_audit_if_available() -> int:
    if os.getenv("SUPPLY_CHAIN_SKIP_PIP_AUDIT") == "1":
        print("pip-audit skipped by SUPPLY_CHAIN_SKIP_PIP_AUDIT=1")
        return 0
    if shutil.which("pip-audit") is None:
        print("pip-audit not installed; lock coverage check passed, vulnerability audit skipped.")
        return 0
    return subprocess.run(["pip-audit", "-r", str(LOCKFILE)], cwd=ROOT, check=False).returncode


def main() -> int:
    if not REQUIREMENTS.exists():
        print(f"Missing requirements file: {REQUIREMENTS.relative_to(ROOT)}")
        return 1
    if not LOCKFILE.exists():
        print(f"Missing lockfile: {LOCKFILE.relative_to(ROOT)}")
        return 1

    missing = sorted(direct_requirements() - locked_packages())
    if missing:
        print("Direct requirements missing from lockfile: " + ", ".join(missing))
        return 1
    unhashed = unhashed_locked_requirements(LOCKFILE)
    if unhashed:
        print("Locked requirements missing hashes: " + ", ".join(unhashed))
        return 1

    return run_pip_audit_if_available()


if __name__ == "__main__":
    raise SystemExit(main())
