#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"

"$PYTHON_BIN" scripts/check_runtime.py --strict
"$PYTHON_BIN" scripts/secret_scan.py
"$PYTHON_BIN" scripts/supply_chain_audit.py
"$PYTHON_BIN" scripts/generate_sbom.py
"$PYTHON_BIN" -m compileall -q -x '(^|/)backend/(cache|output)(/|$)' backend
"$PYTHON_BIN" -m mypy --strict --follow-imports=skip backend/analysis_types.py backend/workflow_state.py
"$PYTHON_BIN" -m coverage erase
"$PYTHON_BIN" -m coverage run --source=backend -m pytest -q -m "not live"
"$PYTHON_BIN" -m coverage report --fail-under=75

if [[ "${RUN_VISUAL_REGRESSION:-0}" == "1" ]]; then
  VISUAL_REGRESSION_REQUIRED=1 scripts/visual_regression.sh
fi
