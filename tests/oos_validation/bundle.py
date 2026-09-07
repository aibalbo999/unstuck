"""Explicit OOS build-context allowlist; no secrets or production stores."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil


REJECTION_REASON = "isolated_oos_bundle_rejected"
_EXACT = {
    "tests/test_oos_research.py",
    "tests/oos_validation/Dockerfile",
}
_BACKEND = {
    "decision_backtest.py", "trade_path_backtest.py", "trade_execution_contract.py", "trade_price_inputs.py",
    "recommendation_labels.py", "data_trust_values.py", "mapping_fields.py", "mapping_sequence_items.py",
}


def allowed_path(name: str) -> bool:
    if not isinstance(name, str):
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or any(part.startswith(".env") for part in path.parts):
        return False
    if name in _EXACT or name.startswith("tests/oos_validation/") and path.suffix in {".py", ""}:
        return True
    if name.startswith("backend/oos_research/") and path.suffix == ".py":
        return True
    return path.parts[:1] == ("backend",) and len(path.parts) == 2 and path.name in _BACKEND


def build_context(repo: Path, destination: Path) -> list[str]:
    root = Path(repo).resolve(strict=True)
    target = Path(destination)
    if target.exists() or target.is_symlink() or target.resolve(strict=False).is_relative_to(root):
        raise ValueError(REJECTION_REASON)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(mode=0o700)
    copied: list[str] = []
    for source in sorted(root.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        if not allowed_path(relative):
            continue
        if source.is_symlink():
            raise ValueError(REJECTION_REASON)
        destination_file = target / relative
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination_file)
        os.chmod(destination_file, 0o600)
        copied.append(relative)
    if not copied:
        raise ValueError(REJECTION_REASON)
    return copied
