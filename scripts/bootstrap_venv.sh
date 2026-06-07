#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BASE_PYTHON="${PYTHON_BIN:-}"
if [ -z "$BASE_PYTHON" ]; then
    if [ -x "/opt/homebrew/bin/python3.13" ]; then
        BASE_PYTHON="/opt/homebrew/bin/python3.13"
    elif command -v python3.13 >/dev/null 2>&1; then
        BASE_PYTHON="$(command -v python3.13)"
    else
        BASE_PYTHON="$(command -v python3)"
    fi
fi

"$BASE_PYTHON" scripts/check_runtime.py --strict
"$BASE_PYTHON" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt

echo "Created .venv with $(.venv/bin/python --version)"
