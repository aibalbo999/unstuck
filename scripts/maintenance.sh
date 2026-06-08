#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"
PYTHONPATH=backend "$PYTHON_BIN" backend/maintenance.py "$@"
