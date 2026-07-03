"""Helpers for parsing pip-style hashed requirements lockfiles."""

from __future__ import annotations

import re
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


HASH_RE = re.compile(r"--hash=sha256:[A-Fa-f0-9]{64}")


def requirement_blocks(path: Path) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")):
            if current:
                current.append(raw_line.strip())
            continue
        if current:
            blocks.append(current)
        current = [raw_line.strip()]
    if current:
        blocks.append(current)
    return blocks


def parse_requirement_line(line: str) -> Requirement:
    requirement_text = line.strip().removesuffix("\\").strip()
    requirement_text = requirement_text.split(" --hash=", 1)[0].strip()
    return Requirement(requirement_text)


def locked_requirements(path: Path) -> dict[str, Requirement]:
    requirements = {}
    for block in requirement_blocks(path):
        requirement = parse_requirement_line(block[0])
        requirements[canonicalize_name(requirement.name)] = requirement
    return requirements


def locked_versions(path: Path) -> dict[str, Version]:
    versions = {}
    for name, requirement in locked_requirements(path).items():
        specifiers = list(requirement.specifier)
        if len(specifiers) == 1 and specifiers[0].operator == "==":
            versions[name] = Version(specifiers[0].version)
    return versions


def unhashed_locked_requirements(path: Path) -> list[str]:
    missing = []
    for block in requirement_blocks(path):
        if any(HASH_RE.search(line) for line in block):
            continue
        requirement = parse_requirement_line(block[0])
        missing.append(canonicalize_name(requirement.name))
    return missing
