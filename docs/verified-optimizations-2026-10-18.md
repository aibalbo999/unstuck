# Verified optimization delivery — 2026-10-18

This change improves free-source acquisition and recovery, report evidence lineage and quality checks, model output completion, and bounded runtime reads. It retains evidence and publication requirements.

## Verification

- The isolated selected-scope suite covered 307 test targets: **6779 passed, 145 warnings, 75 subtests passed in 466.24s (0:07:46)**.
- Python syntax: 763 files. JavaScript syntax: 5 files.
- The publication scan covered 1085 source, test and public fixture files, including compressed and encoded payloads, with no credential findings.
- Replay clocks and fixture boundaries are explicit. Tests restore imported settings modules and the shared executor to prevent suite-order failures and cancellation hangs.

The accompanying JSON records exact source hashes and test targets. From the repository root, reproduce the selected suite using the project interpreter:

```bash
"$(scripts/project_python.sh)" - <<'PY'
import json
import subprocess
import sys
from pathlib import Path
manifest = json.loads(Path("docs/verified-optimizations-2026-10-18.json").read_text())
subprocess.run([sys.executable, "tests/run_prompt_boundary_tests.py", *manifest["test_targets"], "-q", "--tb=short"], check=True)
PY
```

## Scope and limits

Private runtime records, databases, credentials, saved-report bundles and credential-bearing webpage captures are excluded. Independent candidate and backtest research remains outside this delivery.

Two unrelated frontend checks also failed on the unchanged base: `test_decision_tracking_dense_layout_uses_workspace_efficiently` expects an older asset cache tag, and `test_frontend_static_modules_are_sized` has an API quota module line-limit mismatch. This delivery does not claim a passing whole-repository suite.

These are isolated verification results. They do not establish production deployment, live report quality, or acquisition rates above 80% in every source category.
