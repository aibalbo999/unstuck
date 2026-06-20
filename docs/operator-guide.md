# Operator Guide

## Start The App

Use the macOS launcher for normal local operation:

```bash
./start_mac.command
```

For terminal-only checks:

```bash
scripts/check_runtime.py --strict
scripts/demo_report.sh
```

## Daily Workflow

1. Open the analysis tab.
2. Enter a ticker such as `2308.TW`.
3. Pick mode A, mode B, or continuous A+B.
4. Read the preview first, then open the full report when needed.
5. Use report compare or rerun only when the conclusion or data freshness says the report is stale.

## Freshness Rules

- `data_trust` tells you whether the data snapshot itself is fresh, partial, stale, or errored.
- `decision_freshness.status = current` means the investment conclusion was generated from the current snapshot.
- `decision_freshness.status = needs_rerun` means the snapshot was refreshed after the HTML/Markdown conclusion was written. Treat the old conclusion as historical until rerun finishes.
- Watchlist items use the same signal. Items marked `需重跑` are sorted first so the operator can rerun the stale conclusion before reviewing lower-priority names.

## Free External Data Waterfall

Install the free-source dependencies with the backend requirements:

```bash
.venv/bin/python -m pip install -r backend/requirements.txt
```

The optional free waterfall uses this order:

1. Google News RSS for recent catalysts.
2. DuckDuckGo News when Google RSS returns no usable records.
3. PTT Stock only when an explicit Taiwan ticker is present.
4. MOPS balance-sheet lookup when `total_debt_raw` is missing, negative, or NaN for a Taiwan ticker.

Warnings and `source_audit` are expected when a layer returns no records. Treat them as provenance: `unavailable` means the system tried that free source and moved to the next layer; `error` means a controlled provider failure occurred; `success` means records were merged. The final report should only resume from an opened financial circuit breaker when MOPS agrees with at least one API provider within tolerance and unit, period, and statement scope match.

Live smoke tests are opt-in because they call public external sites:

```bash
RUN_LIVE_FREE_DATA_TESTS=1 .venv/bin/python -m pytest tests/live/test_free_external_data_smoke.py -q
```

Respect provider access policies. These fetchers use public pages/APIs, timeouts, conservative parsing, and controlled `None`/empty results rather than scraping aggressively or retrying indefinitely.

## Agent-Scoped External Context

Set the FRED key only in `backend/.env` or the process environment:

```bash
FRED_API_KEY=replace_with_your_key
```

FRED observations are cached in memory for 15 minutes. TDCC shareholder distribution and TWSE margin/short balances use public endpoints and require no key. The 104 job-opening detector runs only when the stock payload includes `alternative_data_keywords` or `job_opening_keywords`; at most the first three keywords are queried for one analysis.

External context is routed by least privilege to control token use:

- `macro_indicators` goes only to Agent 11.
- `chip_data` goes only to Agents 15 and 18.
- `sentiment_context` goes only to Agent 17.
- `alternative_data` goes only to Agents 13 and 14.

Provider failures remain controlled audit entries. A missing FRED key is `not_configured`; unavailable TDCC, TWSE, or 104 responses do not inject guessed values into prompts.

## Maintenance

Maintenance actions live under the `報告與維運` tab. HTTP cleanup endpoints are dry-run by default; UI buttons send `write=true` only after the operator intentionally clicks the action.

Use CLI maintenance for inspectable local cleanup:

```bash
scripts/maintenance.sh storage-summary
scripts/maintenance.sh cleanup-report-index --write
scripts/maintenance.sh cleanup-analysis-history --write
```

## Safety

Mutation endpoints require `X-Mutation-Token`. The browser UI receives a same-origin runtime token automatically. Direct API clients should call `/api/client-config` first or set `MUTATION_API_TOKEN` and send that value in `X-Mutation-Token`.
