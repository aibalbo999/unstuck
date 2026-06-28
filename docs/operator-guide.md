# Operator Guide

## Start The App

Use the macOS launcher for normal local operation:

```bash
./start_mac.command
```

The launcher now starts the full local runtime stack: it installs backend requirements, ensures `TASK_QUEUE_BACKEND=rq`, starts or reuses local Redis, starts `worker_main.py --role all`, then starts FastAPI. Use `LAN_ACCESS=1 ./start_mac.command` or `./start_mac_lan.command` for trusted Wi-Fi access from a phone/tablet.

For terminal-only checks:

```bash
scripts/check_runtime.py --strict
scripts/demo_report.sh
```

## Local And Production Profiles

Local mode is the default:

```bash
UNSTUCK_ENV=local
```

Local mode keeps the workstation-friendly runtime token behavior: if `MUTATION_API_TOKEN` is absent, FastAPI generates a same-origin runtime token and exposes it through `/api/client-config` for the bundled UI. Keep the server bound to `127.0.0.1` unless you intentionally use trusted LAN mode, and do not expose local mode directly to a public network.

Production mode can be selected with either `UNSTUCK_ENV=production` or the existing `DEPLOYMENT_MODE=server` / `DEPLOYMENT_MODE=lan` profiles:

```bash
UNSTUCK_ENV=production
MUTATION_API_TOKEN=replace_with_long_random_secret
ALLOWED_ORIGINS=https://your-ui.example.com
```

Production startup fails fast if `MUTATION_API_TOKEN` is missing. `ALLOWED_ORIGINS=*` is rejected in production; use an explicit allowlist. Mutation endpoints check `X-Mutation-Token`, report HTML responses include CSP / nosniff / referrer headers, and API error payloads should not include secrets, stack traces, or local filesystem paths.

## Split API / Worker Startup

FastAPI is now a lightweight HTTP/RQ producer. The macOS launcher handles Redis and Worker startup automatically for local use. For manual or process-manager operation, run Redis and the Worker separately before starting the API:

```bash
redis-server
python backend/worker_main.py --role all
uvicorn api:app --app-dir backend
```

For production-style process managers, split `--role all` into dedicated `queue / schedulers / maintenance` roles:

```bash
python backend/worker_main.py --role queue
python backend/worker_main.py --role schedulers
python backend/worker_main.py --role maintenance
```

`TASK_QUEUE_BACKEND=local` is intentionally rejected by Web/API mode with `API task queue requires Redis and RQ`; use `TASK_QUEUE_BACKEND=rq` with a shared `REDIS_URL`. Check Redis with `redis-cli -u "$REDIS_URL" ping`, then inspect RQ with `rq info --url "$REDIS_URL"`.

RQ retry behavior is configured with `RQ_JOB_MAX_RETRIES` and `RQ_JOB_RETRY_INTERVALS`; long-running job timeout is configured with `RQ_JOB_TIMEOUT_SECONDS` (default 4 hours). A job waiting for a delayed retry uses status `waiting_retry` and remains active in duplicate-job checks and dashboards.

Analysis workflow execution is durable. Each Worker run uses LangGraph with a SQLite checkpointer at `LANGGRAPH_CHECKPOINT_PATH` (default `backend/cache/langgraph_checkpoints.sqlite3`). A pipeline segment uses `thread_id = job_id:pipeline_id`; if an LLM call exhausts short in-node retries and the outer RQ job retries later, the Worker resumes the same graph thread instead of repeating completed Agent nodes. Do not delete the checkpoint DB while jobs are `queued`, `running`, or `waiting_retry`.

Checkpoint cleanup policy is intentionally conservative for local-first operation: back up or delete old checkpoint files only after related jobs have reached `done`, `error`, or `cancelled`, and after preserving any reports you need. The checkpoint stores JSON-compatible graph state only; callbacks, API clients, Redis handles, and SQLite connections are process-local and are rebuilt on resume.

Analysis job state lives in `TASK_DB_PATH`. The same SQLite DB now contains jobs, SSE events, and per-node telemetry. API and worker processes must point at the same `TASK_DB_PATH`; otherwise the API can enqueue work but the UI will not see progress. Suggested retention is the default `ANALYSIS_JOB_HISTORY_RETENTION_DAYS=30`; use cleanup dry-runs before deleting old event/telemetry history.

`SIGTERM` / `SIGINT` sent to `worker_main.py --role all` is forwarded to child roles. Queue workers can be smoke-tested without staying resident:

```bash
python backend/worker_main.py --role queue --burst --max-jobs 1
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

## Decision Tracking And Backtests

The decision tracking scheduler runs after the daily tracking refresh. It scans reports whose generated date has reached the 3, 6, or 12 month horizon, fetches historical market closes, and writes one idempotent result per `(report_filename, horizon_months)`.

Backtest results are visible in `報告與維運` under `決策回測`. The panel shows hit rate, average strategy ROI, horizon breakdown, and the latest evaluated reports. A `買入/買進` call earns market ROI, `避免/強烈放空` earns inverse market ROI, and `持有` is treated as a range call. A duplicate run on the same day is skipped by the unique result key.

New reports also load the most recent prior report for the same ticker. When a previous call has a miss, final decision agents receive an `Agent 歷史反思` context and must explicitly explain which assumption changed before writing the new conclusion. The preview panel displays that memory when it exists.

## Event-Driven Watchlist Radar

Watchlist items can include event triggers:

- `price_below_sma`: price below the configured moving average; matched events dispatch mode C / pipeline `v3`.
- `foreign_sell_streak`: foreign investors sell more than the configured threshold for N consecutive days; matched events dispatch `v3`.
- `vix_above`: VIX above the configured threshold; matched events dispatch `v3`.
- `revenue_record_high`: latest monthly revenue reaches a local high; matched events dispatch mode B / pipeline `v2`.

The background scheduler checks normal due watchlist jobs and then runs the event radar after the post-market time. Each trigger evaluation is stored once per ticker, pipeline, trigger key, and date. If the same event is already recorded, the scheduler skips dispatch rather than queueing duplicate reports. Active jobs for the selected pipeline are also skipped.

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

Job cleanup keeps active `queued`, `running`, and `waiting_retry` rows. It removes only terminal history older than the configured retention window plus orphan events. For production, schedule cleanup during quiet hours and keep report output backups separate from `TASK_DB_PATH` cleanup.

## Safety

Mutation endpoints require `X-Mutation-Token`. The browser UI receives a same-origin runtime token automatically. Direct API clients should call `/api/client-config` first or set `MUTATION_API_TOKEN` and send that value in `X-Mutation-Token`.
