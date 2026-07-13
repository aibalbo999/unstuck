#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"

"$PYTHON_BIN" scripts/check_runtime.py --strict
"$PYTHON_BIN" scripts/secret_scan.py
scripts/setup_security_audit.sh
"$PYTHON_BIN" scripts/supply_chain_audit.py
"$PYTHON_BIN" scripts/generate_sbom.py
"$PYTHON_BIN" scripts/generate_sbom.py \
  --requirements scripts/visual_requirements.lock \
  --output backend/cache/visual-sbom.cdx.json
"$PYTHON_BIN" scripts/generate_pipeline_mode_fallback.py --check
"$PYTHON_BIN" -m compileall -q -x '(^|/)backend/(cache|output)(/|$)' backend
"$PYTHON_BIN" -m mypy --strict --follow-imports=skip backend/analysis_types.py backend/workflow_state.py
"$PYTHON_BIN" -m coverage erase
"$PYTHON_BIN" -m coverage run --source=backend -m pytest -q -m "not live"
"$PYTHON_BIN" -m coverage report --fail-under=75

CI_MODE=false
case "${CI:-}" in
  1|true|TRUE|yes|YES) CI_MODE=true ;;
esac

if [[ "${RUN_VISUAL_REGRESSION:-}" == "1" || ( -z "${RUN_VISUAL_REGRESSION:-}" && "$CI_MODE" == "true" ) ]]; then
  "$PYTHON_BIN" scripts/check_visual_regression.py
  VISUAL_REGRESSION_REQUIRED=1 scripts/visual_regression.sh
fi
