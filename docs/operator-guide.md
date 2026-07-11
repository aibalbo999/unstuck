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

For runtime path and storage navigation checks:

```bash
$(scripts/project_python.sh) scripts/doctor_runtime.py
```

The doctor prints the canonical report index DB, operational DB, legacy decision-tracking DB, output directory, queue settings, and storage existence checks. Use it before manually inspecting SQLite files.

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
BASIC_AUTH_USERNAME=operator
BASIC_AUTH_PASSWORD=replace_with_long_random_password
```

Production startup fails fast if `MUTATION_API_TOKEN` is missing. `ALLOWED_ORIGINS=*` is rejected in production; use an explicit allowlist. Production/server/lan CORS allows only `GET`, `POST`, `DELETE`, `OPTIONS` and the required request headers instead of wildcards. Network-exposed profiles also require either built-in Basic Auth (`BASIC_AUTH_USERNAME` / `BASIC_AUTH_PASSWORD`) or `EXTERNAL_ACCESS_CONTROLLED=true` when an OAuth proxy, Tailscale ACL, or equivalent external boundary is already enforced. Mutation endpoints check `X-Mutation-Token`; the legacy `X-Admin-Token` alias is disabled unless `ALLOW_LEGACY_ADMIN_TOKEN=true` is set for a short migration window. Mutation calls are rate-limited in memory by `MUTATION_RATE_LIMIT_MAX_REQUESTS` per `MUTATION_RATE_LIMIT_WINDOW_SECONDS`; clients that exceed it receive HTTP 429 with `Retry-After`. External data providers that run through `audited_fetch` / `audited_fetch_async` can be locally paced with `PROVIDER_RATE_LIMIT_MIN_INTERVAL_SECONDS` or provider-specific overrides such as `PROVIDER_RATE_LIMIT_YFINANCE_MIN_INTERVAL_SECONDS`; HTTP 429/403/402 responses enter cooldown for `PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS` seconds by default. External httpx helpers can rotate outbound proxies with `PROVIDER_PROXY_URLS` or provider-specific pools such as `PROVIDER_PROXY_FMP_URLS` and `PROVIDER_PROXY_GDELT_URLS`. Report HTML responses include CSP / nosniff / referrer headers, and API error payloads should not include secrets, stack traces, or local filesystem paths.

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

Queue workers consume every name in `TASK_QUEUE_NAMES`. Keep `TASK_QUEUE_NAME` first for compatibility, then add tiered queues such as `analysis.high`, `analysis.normal`, `watchlist`, `maintenance`, and `llm.retry`. API-created manual analysis jobs route to `analysis.high`, report reruns route to `analysis.normal`, and watchlist scheduler jobs route to `watchlist`, so batch work does not block high-value manual analysis.

RQ retry behavior is configured with `RQ_JOB_MAX_RETRIES` and `RQ_JOB_RETRY_INTERVALS`; long-running job timeout is configured with `RQ_JOB_TIMEOUT_SECONDS` (default 4 hours). The queue role runs the RQ scheduler so delayed retries stored in `ScheduledJobRegistry` are promoted back to runnable queues. A job waiting for a delayed retry uses status `waiting_retry` and remains active in duplicate-job checks and dashboards.

Health checks are split by purpose. `/healthz` is a liveness probe for process managers. `/readyz` verifies runtime storage and queue availability and returns HTTP 503 when the API should not accept work. For operator triage, use `/api/observability/dashboard`; it combines job latency percentiles, stuck jobs, node/model telemetry, prompt token budget, RQ depth and registries, provider alerts, and API quota ledger observations.

Analysis workflow execution is durable. Each Worker run uses LangGraph with a SQLite checkpointer at `LANGGRAPH_CHECKPOINT_PATH` (default `backend/cache/langgraph_checkpoints.sqlite3`). A pipeline segment uses `thread_id = job_id:pipeline_id`; if an LLM call exhausts short in-node retries and the outer RQ job retries later, the Worker resumes the same graph thread instead of repeating completed Agent nodes. Do not delete the checkpoint DB while jobs are `queued`, `running`, or `waiting_retry`.

Agent step cache is enabled by default with `AGENT_STEP_CACHE_ENABLED=true` and `AGENT_STEP_CACHE_SECONDS=604800`. Cache hits emit `agent_step_cache_hit` events and restore the agent structured output without calling the LLM provider. If prompt rules, model routing, or source data changes unexpectedly, clear the configured cache backend or lower the TTL before rerunning critical reports.

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
- `data_confidence_score` is the 0-100 report confidence score derived from `data_trust`; below 60, the report should not be treated as having a valid explicit target price.
- `conclusion_guardrails.explicit_target_price` records whether target prices are allowed and which structured fields tried to provide explicit prices under low confidence.
- `reproducibility_packet` records the final snapshot hash, provider list, prompt/model identifiers, pipeline, code commit, generated time, and source data time for audit and rerun comparison.
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
.venv/bin/python -m pip install --require-hashes -r backend/requirements.lock
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
scripts/maintenance.sh sqlite-maintenance --write
scripts/maintenance.sh cleanup-report-index --write
scripts/maintenance.sh cleanup-analysis-history --write
```

Job cleanup keeps active `queued`, `running`, and `waiting_retry` rows. It removes only terminal history older than the configured retention window plus orphan events. SQLite maintenance creates one backup per database per UTC day under `SQLITE_BACKUP_DIR`, then runs WAL checkpoint and `VACUUM`; schedule it during quiet hours and keep report output backups separate from `TASK_DB_PATH` cleanup.

## Safety

Mutation endpoints require `X-Mutation-Token`. The browser UI receives a same-origin runtime token automatically. Direct API clients should call `/api/client-config` first or set `MUTATION_API_TOKEN` and send that value in `X-Mutation-Token`. Avoid `X-Admin-Token`; it is a temporary legacy alias only when explicitly enabled.

## Commercial Investment Workspace

從首頁的「商業版」分頁進入後，依序使用三個共用操作設定的資金頁面：

1. **今日決策**：查看最多五筆工作佇列，並以「全部、需重跑、報酬轉弱」篩選。按唯一主動作「檢查最高優先股票」進入最需要處理的股票；每一列也可直接開啟單股研究。
2. **單股研究**：可從清單選擇股票（來源包含追蹤股票、既有報告與常用代號），也可手動輸入股票代號，再按「更新股票快照」。先看結論與部位試算，再用「操作計畫、估值、基本面、事件、技術」分頁查證。修改進場價或停損價只會更新試算，不會送出交易或修改研究結論。
3. **組合健檢**：持股可從追蹤股票、既有報告與常用股票清單選擇，輸入新台幣金額後按「加入／更新持股」，也可從目前持股清單移除。系統會自動換算權重，並把剩餘操作資金列為 Cash。另可選擇 .csv 檔案，或直接貼上與編輯含 `ticker`，以及 `weight` 或 `market_value` 的內容，再按「分析目前組合」。先看每檔實際金額與前三項調整，再到資金配置、曝險、論點與調整清單查看原因。

### 可調整操作設定

- 展開「調整操作資金與風險設定」，可修改操作資金、現金保留、單一持股上限與單筆最大風險。
- 按「套用設定」後會保存在目前瀏覽器並由三頁共用；按「恢復預設」回到 500 萬、20%、15%、1%。
- 預設現金保留 20%（NT$1,000,000）、單一持股上限 15%（NT$750,000）、單筆最大風險 1%（NT$50,000），但這些數值不再寫死於試算。
- `weight` CSV 依目前操作資金換算；`market_value` CSV 使用檔案實際總額，並顯示與操作資金的差異。
- 快速建立器以 market_value 保存輸入金額；既有 weight CSV 會先依目前操作資金轉換。股票投入總額超過操作資金時不會修改組合，也不會產生負數 Cash。
- 單股部位與組合調整金額是操作規則試算，不是後端投資建議、報酬承諾或下單指令。
- 海外股票需要匯率才能換算新台幣部位；缺少匯率時只顯示研究資料，不計算股數。

青色按鈕是每頁唯一的資料更新或主要導覽動作。若資料來源失敗，頁面會保留輸入與上一次成功內容，並顯示可讀錯誤，不會顯示或改用範例資料、假結果。修正代號、CSV 或服務狀態後，再按同一個主動作重試。
