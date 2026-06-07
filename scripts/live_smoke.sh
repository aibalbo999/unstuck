#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export RUN_LIVE_SMOKE="${RUN_LIVE_SMOKE:-1}"
PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"

"$PYTHON_BIN" scripts/check_runtime.py --strict
"$PYTHON_BIN" -m compileall backend
"$PYTHON_BIN" -m pytest -q -m live tests/live "$@"
