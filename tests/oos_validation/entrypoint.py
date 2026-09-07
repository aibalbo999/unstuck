"""Container entrypoint: run only the synthetic OOS tests and emit a safe result."""

from __future__ import annotations

import os
import re
import subprocess
import json
from pathlib import Path

from .result import RESULT_SCHEMA, write_result


def run(result_path: str | os.PathLike[str]) -> int:
    path = Path(result_path)
    command = ["python", "tests/oos_validation/selfcheck.py"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, shell=False,
                               cwd="/work",
                               env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": "/work/backend",
                                    "PYTHONDONTWRITEBYTECODE": "1"})
    passed_match = re.search(r"(\d+) passed", completed.stdout)
    passed = int(passed_match.group(1)) if passed_match else 0
    failed_match = re.search(r"(\d+) failed", completed.stdout)
    failed = int(failed_match.group(1)) if failed_match else (0 if completed.returncode == 0 else 1)
    payload = {"schema": RESULT_SCHEMA, "status": "passed" if completed.returncode == 0 else "failed",
               "network": "none", "paths": "container-layer-only", "tests": {"passed": int(passed), "failed": failed},
               "exit_code": completed.returncode, "cleanup_status": "not_attempted"}
    write_result(path, payload)
    print(json.dumps(payload, sort_keys=True), flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(run(os.environ.get("OOS_RESULT_PATH", "/results/result.json")))
