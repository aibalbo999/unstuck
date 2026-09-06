#!/usr/bin/env python3
"""CLI entrypoint for one disposable PostgreSQL validation run."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from pg_validation.launcher import run_validation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return run_validation(ROOT, args.result_dir)


if __name__ == "__main__":
    raise SystemExit(main())
