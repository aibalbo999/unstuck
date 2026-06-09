#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-$(scripts/project_python.sh)}"

"$PYTHON_BIN" - <<'PY'
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))

import report_history_service

output_dir = ROOT / "backend" / "output"
result = report_history_service.list_reports(
    page=1,
    limit=5,
    q="",
    pipeline="all",
    recommendation="all",
    data_trust="all",
    output_dir=str(output_dir),
    report_cache={},
)

print(json.dumps({
    "output_dir": str(output_dir),
    "reports": result.get("reports", [])[:5],
    "pagination": result.get("pagination", {}),
}, ensure_ascii=False, indent=2))
PY
