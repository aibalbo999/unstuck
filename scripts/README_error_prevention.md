# Historical error-prevention replay

This tool preserves a case registry and runs current deterministic gates. It does **not** rerun models, repair reports, publish results, or prove that the complete generation pipeline will succeed.

Export explicitly named canonical sources using read-only SQLite connections and `ReportArtifactLocator`. Put the corpus outside the service's storage directories:

```bash
"$(scripts/project_python.sh)" scripts/replay_error_prevention.py export \
  --audit-dir '/path/to/original-audit' \
  --corpus '/path/to/private-corpus' \
  --checkpoint-db '/Volumes/X10 Pro Mac/stock-agent/backend/cache/stock_agent_cache.sqlite3' \
  --operational-db '/Volumes/X10 Pro Mac/stock-agent/backend/cache/operational.sqlite3' \
  --output-root '/Volumes/X10 Pro Mac/stock-agent/backend/output'
```

The export preserves decoded original inputs, structured outputs, streamed candidates and their hashes. Credential/header/environment metadata is removed; anonymous key slots remain. Original checkpoint binary is **not** exported: its hash and read-only database locator are retained. Corpus permissions are `0700` and JSON files `0600`. Missing checkpoints, versions and candidate text remain explicitly unknown.

Run the regression checks with the repository's mandatory isolated runner. Set an optional corpus path to replay all retained cases with SQLite/Redis/provider network access disabled:

```bash
STOCK_ERROR_PREVENTION_CORPUS='/path/to/private-corpus' \
  "$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_error_prevention_replay.py tests/test_error_prevention_mode_c.py -q
```

A standalone offline CLI is also available for an already exported corpus:

```bash
"$(scripts/project_python.sh)" scripts/replay_error_prevention.py replay \
  '/path/to/private-corpus/manifest.json' --result '/path/to/private-corpus/current-replay.json'
```

Replay verifies every payload hash and rejects paths outside the corpus. Results include a source-code file manifest covering backend Python and prompt JSON files. The small repository registry `tests/fixtures/error_prevention_manifest_20260922.json` identifies the 41 failed jobs and 49 warning reports; full financial inputs stay in the private release corpus.

Interpretation:

- `fixed_in_scoped_replay`: the current deterministic checks passed with sufficient retained evidence. This is not generation or publication success.
- `true_error_still_blocked`: a manually reviewed, input-hash-bound candidate defect remains blocked. A gate result alone never creates this classification.
- `true_error_unexpectedly_passed`: a known, input-bound true error escaped the current checks. The CLI exits 2 and regression validation fails; this is never labeled a fix.
- `still_reproduced`: a current finding remains; further review may distinguish valid rejection from parser error.
- `evidence_missing`: input/output is unavailable, corrupted, or original report input binding is unknown. A saved artifact checksum alone does not prove which input generated its conclusions.

The original stored `parsed` and final audit stay in the payload. Job replay uses the current parser on the retained outputs and reports that projection separately. Report replay keeps recorded final-audit warnings visible. A refreshed report without a provable original input is never counted as fixed.
