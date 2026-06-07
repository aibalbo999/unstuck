#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -n "${PYTHON_BIN:-}" ]; then
    printf '%s\n' "$PYTHON_BIN"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    printf '%s\n' "$ROOT_DIR/.venv/bin/python"
elif [ -x "/opt/homebrew/bin/python3.13" ]; then
    printf '%s\n' "/opt/homebrew/bin/python3.13"
elif command -v python3.13 >/dev/null 2>&1; then
    command -v python3.13
elif command -v python3 >/dev/null 2>&1; then
    command -v python3
else
    echo "No Python runtime found" >&2
    exit 1
fi
