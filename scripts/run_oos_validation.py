#!/usr/bin/env python3
"""Run the offline OOS validation suite with no production configuration."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True, help="explicit result JSON path")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "pytest", "tests/test_oos_research.py", "-q", "-p", "no:cacheprovider", "--tb=short"]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    payload = {"schema_version": "oos.validation.v1", "command": command, "returncode": completed.returncode,
               "stdout": completed.stdout, "stderr": completed.stderr}
    output = Path(args.result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
