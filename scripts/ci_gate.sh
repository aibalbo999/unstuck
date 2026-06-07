#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"

"$PYTHON_BIN" scripts/check_runtime.py --strict
"$PYTHON_BIN" -m compileall backend
"$PYTHON_BIN" -m pytest -q -m "not live"

if [[ "${RUN_VISUAL_REGRESSION:-0}" == "1" ]]; then
  VISUAL_REGRESSION_REQUIRED=1 scripts/visual_regression.sh
fi
