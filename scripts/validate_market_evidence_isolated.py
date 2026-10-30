#!/usr/bin/env python3
"""Run the scoped evidence-repair regression suite through the mandatory boundary."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    tests = json.loads((root / "docs/market-evidence-validation-tests.json").read_text())
    for name in tests:
        path = Path(name)
        if (path.is_absolute() or ".." in path.parts or path.parts[0] != "tests"
                or path.suffix != ".py" or not (root / path).is_file()):
            raise ValueError("Invalid scoped test module: " + str(name))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    print(f"Running {len(tests)} modules with isolated databases and network disabled", flush=True)
    return subprocess.call([sys.executable, "tests/run_prompt_boundary_tests.py", *tests, "-q"],
                           cwd=root, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
