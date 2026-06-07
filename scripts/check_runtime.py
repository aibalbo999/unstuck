#!/usr/bin/env python3
"""Check the Python runtime recommended for this project."""

from __future__ import annotations

import argparse
import platform
import sys


MIN_RECOMMENDED = (3, 13)
STRICT_MIN = (3, 13)


def version_text(version: tuple[int, int]) -> str:
    return ".".join(str(part) for part in version)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check stock-agent Python runtime")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when Python is below the deployment minimum")
    args = parser.parse_args()

    current = sys.version_info[:2]
    current_text = platform.python_version()
    minimum = STRICT_MIN if args.strict else MIN_RECOMMENDED
    if current < minimum:
        message = (
            f"Python {current_text} detected; recommended runtime is "
            f"Python {version_text(MIN_RECOMMENDED)}+ to avoid Google auth / urllib3 "
            "warnings from older macOS runtimes and to match the project .venv."
        )
        print(("ERROR: " if args.strict else "WARNING: ") + message)
        return 1 if args.strict else 0

    print(f"Python runtime OK: {current_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
