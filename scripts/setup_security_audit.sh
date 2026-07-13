#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BASE_PYTHON="${PYTHON_BIN:-$(scripts/project_python.sh)}"
AUDIT_VENV="${AUDIT_VENV:-$PWD/.audit-venv}"
AUDIT_PYTHON="$AUDIT_VENV/bin/python"

if [[ ! -x "$AUDIT_PYTHON" ]]; then
  "$BASE_PYTHON" -m venv "$AUDIT_VENV"
fi

"$AUDIT_PYTHON" -m pip install -q --require-hashes -r scripts/security_requirements.lock
"$AUDIT_VENV/bin/pip-audit" --version
