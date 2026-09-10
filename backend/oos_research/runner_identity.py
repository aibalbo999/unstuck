"""Source identity for deterministic OOS replay executions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .canonical import content_hash


_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_RUNNER_DEPENDENCIES = (
    "decision_backtest.py",
    "recommendation_labels.py",
    "trade_execution_contract.py",
    "trade_path_backtest.py",
    "trade_price_inputs.py",
)


def runner_identity() -> dict[str, Any]:
    source_paths = sorted(Path(__file__).resolve().parent.glob("*.py"))
    source_paths.extend(_BACKEND_ROOT / name for name in _RUNNER_DEPENDENCIES)
    files = {
        str(path.relative_to(_BACKEND_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    return {
        "schema_version": "oos.runner-identity.v1",
        "source_sha256": content_hash({"files": files}),
        "files": files,
    }
