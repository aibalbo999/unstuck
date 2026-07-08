#!/usr/bin/env python3
"""Small offline secret scanner for tracked project files."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "backend/cache",
    "backend/output",
    "output",
}
PLACEHOLDER_MARKERS = {
    "replace_with",
    "your_key",
    "placeholder",
    "example",
    "dummy",
    "test-only",
}
PATTERNS = [
    ("possible_google_api_key", re.compile(r"(?:AIza[0-9A-Za-z_-]{30,}|AQ\.[0-9A-Za-z_-]{40,})")),
    ("possible_openai_api_key", re.compile(r"sk-[0-9A-Za-z_-]{24,}")),
    ("possible_anthropic_api_key", re.compile(r"sk-ant-[0-9A-Za-z_-]{24,}")),
    (
        "possible_secret_assignment",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*=\s*['\"]?[0-9A-Za-z_./+=:-]{24,}"),
    ),
]


def is_placeholder(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def is_skipped(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(ROOT)
    except ValueError:
        return False
    parts = set(relative.parts)
    if parts & SKIP_DIRS:
        return True
    rel_text = relative.as_posix()
    return any(rel_text == item or rel_text.startswith(f"{item}/") for item in SKIP_DIRS)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def iter_files(paths: list[str]) -> list[Path]:
    if not paths:
        try:
            return tracked_files()
        except (OSError, subprocess.CalledProcessError):
            paths = [str(ROOT)]
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for current_root, dirs, names in os.walk(path):
                dirs[:] = [name for name in dirs if not is_skipped(Path(current_root) / name)]
                files.extend(Path(current_root) / name for name in names)
        else:
            files.append(path)
    return files


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    if is_skipped(path) or not path.exists() or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if is_placeholder(line):
            continue
        for finding_type, pattern in PATTERNS:
            if pattern.search(line):
                findings.append((finding_type, line_number, line.strip()[:160]))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan project files for obvious provider secrets.")
    parser.add_argument("paths", nargs="*", help="Optional files or directories. Defaults to git tracked files.")
    args = parser.parse_args(argv)

    all_findings = []
    for path in iter_files(args.paths):
        for finding in scan_file(path):
            all_findings.append((path, *finding))

    if not all_findings:
        print("No obvious secrets found.")
        return 0

    for path, finding_type, line_number, excerpt in all_findings:
        try:
            display = path.resolve().relative_to(ROOT)
        except ValueError:
            display = path
        print(f"{display}:{line_number}: {finding_type}: {excerpt}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
