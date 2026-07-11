#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"
export VISUAL_REGRESSION_REQUIRED="${VISUAL_REGRESSION_REQUIRED:-1}"

"$PYTHON_BIN" scripts/check_visual_regression.py
"$PYTHON_BIN" -m pytest -q \
  tests/test_frontend_visual_optional.py \
  tests/test_report_chart_visual_optional.py
