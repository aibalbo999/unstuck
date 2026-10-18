# Remaining public optimization delivery — 2026-10-18

The dated TWSE daily fallback was present, but its public screener adapter still used the older feed path. This change connects the date-verified adapter and propagates source warnings. Missing dates remain unknown. It also publishes source boundary checks, the updated social-query fixture, and public source and maintenance documentation.

## Review and verification

- Reviewed 197 remaining test modules individually, including their fixture and helper dependencies. The accompanying JSON records each decision.
- Isolated selected-scope suite: **1791 passed in 115.36s (0:01:55)**, across 104 test targets. Candidate file hashes were unchanged during the run.
- Existing identity, period, amount, completeness, timeout and rejection assertions remain in the public test cases. The MOPS route isolation and independent candidate-scoring boundary are explicitly recorded in the JSON.
- The legacy flatten implementation remains an independent comparison. Tests restore module, circuit and shared executor state where required by their original fixtures.
- Myson and Medtecs HTML fixtures are redacted. TEWC viewer metadata is synthetic. Their private originals are retained locally; successful replay is not native HTTP or production coverage proof.
- README search-provider defaults match `backend/settings/providers.py`. Two remaining source-file differences are whitespace-only noise and remain local. The public TEWC test received trailing-whitespace normalization after the run; its Python AST is unchanged.

Reproduce from the repository root:

```bash
"$(scripts/project_python.sh)" - <<'PY'
import json
import subprocess
import sys
from pathlib import Path
manifest = json.loads(Path("docs/remaining-public-optimizations-2026-10-18.json").read_text())
subprocess.run([sys.executable, "tests/run_prompt_boundary_tests.py", *manifest["test_targets"], "-q", "--tb=short"], check=True)
PY
```

## Kept local

Full original test files and operational notes remain local wherever they also contain private replay cases, report captures, credentials or execution evidence. Independent candidate, performance and backtest work, archive-path relocation, and concurrent report-reader changes are outside this delivery. Public documentation omits individual runtime jobs, private receipts and deployment traces.

The source catalog is an implementation index. This delivery establishes selected-scope offline validation; it does not claim a passing whole-repository suite, deployment, new report acceptance, or acquisition above 80% in every source category.
