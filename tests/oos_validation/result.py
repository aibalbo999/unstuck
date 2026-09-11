"""Small fail-closed result envelope for the offline OOS runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


RESULT_SCHEMA = "stock-agent.oos-validation.result.v1"
MAX_RESULT_SIZE = 512 * 1024


def validate_result(payload: Any) -> bool:
    if not isinstance(payload, dict) or set(payload) != {
        "schema", "status", "network", "paths", "tests", "exit_code", "cleanup_status",
    }:
        return False
    if payload["schema"] != RESULT_SCHEMA or payload["network"] != "none" or payload["paths"] != "container-layer-only":
        return False
    tests = payload["tests"]
    return (
        isinstance(tests, dict)
        and type(tests.get("passed")) is int and type(tests.get("failed")) is int
        and tests["passed"] >= 0 and tests["failed"] >= 0
        and type(payload["exit_code"]) is int
        and payload["cleanup_status"] in {"removed", "not_attempted"}
        and payload["status"] in {"passed", "failed"}
        and (payload["status"] == "passed") == (payload["exit_code"] == 0 and tests["failed"] == 0)
    )


def write_result(path: Path, payload: dict[str, Any]) -> None:
    if not validate_result(payload):
        raise ValueError("isolated_oos_result_invalid")
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > MAX_RESULT_SIZE:
        raise ValueError("isolated_oos_result_too_large")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short result write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
