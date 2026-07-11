#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"

"$PYTHON_BIN" -m pip install -q playwright
"$PYTHON_BIN" -m playwright install chromium
"$PYTHON_BIN" scripts/check_visual_regression.py
