"""Capture process-stable Git provenance for report reproducibility."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@lru_cache(maxsize=None)
def runtime_code_identity(repo_root: str | None = None) -> dict[str, str | bool | None]:
    """Return commit and dirty state captured once for a repository path."""
    root = Path(repo_root).resolve() if repo_root else PROJECT_ROOT
    commit = str(os.getenv("GIT_COMMIT") or "").strip()
    dirty = _optional_bool(os.getenv("GIT_DIRTY"))

    if not commit:
        commit_ok, commit_output = _git_output(root, "rev-parse", "HEAD")
        if commit_ok:
            commit = commit_output
    if dirty is None:
        status_ok, status_output = _git_output(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        )
        if status_ok:
            dirty = bool(status_output)

    return {"commit": commit, "dirty": dirty}


def _optional_bool(value: str | None) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def _git_output(root: Path, *args: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    if result.returncode != 0:
        return False, ""
    return True, result.stdout.strip()
