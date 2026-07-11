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

Health checks are split by purpose. `/healthz` is a liveness probe for process managers. `/readyz` verifies runtime storage and queue availability and returns HTTP 503 when the API should not accept work. For operator triage, use `/api/observability/dashboard`; it combines job latency percentiles, stuck jobs, node/model telemetry, prompt token budget, model route budget, RQ depth and registries, provider alerts, API quota ledger observations, and `notification_delivery` sender audit health. The model route budget groups telemetry by `pipeline_id/model`; cache hits are excluded from billable token totals, and `estimated_cost_usd` remains null until a verified price table is configured. `notification_delivery.health` becomes `warning` when failed or retry-exhausted delivery rows exist, and the dashboard status is raised to `warning` so broken external channels are visible before operators assume notifications are still flowing. The ops maintenance panel reads the same dashboard health and shows failed, retry-exhausted, pending, channel-count, low-cardinality failure reason details, and `attention_contexts` under the `通知通道` chip. The maintenance chip reuses the daily queue attention context summary, so affected ticker/report/CTA context is visible in ops before opening raw audit rows. The shared summary includes a human-readable original source label plus the raw source key, queue rank, displayed count, and top-priority flag when present, preserving the upstream daily queue ordering context across operator summary, watchlist, and maintenance surfaces. Operator action and watchlist daily board `來源` labels use the same helper as attention context `原始來源` labels, so source wording does not drift between UI surfaces. The same helper covers the no-action `monitor` fallback as `監控`, avoiding raw fallback keys when a queue is healthy. If a legacy audit row has no context snapshot, the same summary falls back to channel/status/attempt metadata and still avoids rendering raw `last_error`. `attention_contexts` is capped context from failed audit rows; use it to see which source label/key, ticker, report, target panel, CTA, queue rank, displayed count, or top-priority flag was affected before opening raw audit rows. `/metrics` exposes the same delivery health as `stock_agent_notification_delivery_count`, `stock_agent_notification_delivery_channel_count`, `stock_agent_notification_delivery_failure_reason_count`, and `stock_agent_notification_delivery_health` gauges for external alerting; the health gauge always emits both `state="ok"` and `state="warning"` so alert rules do not depend on a disappearing time series. Failure reason metrics use low-cardinality buckets such as `timeout`, `auth`, `rate_limited`, `configuration`, and `network`; inspect the audit row `last_error` only when doing detailed local triage.

Notification delivery summary fetch failures fall back to empty delivery summaries for Prometheus, so notification audit storage or aggregation errors cannot interrupt provider or queue metrics output.

Ops dashboard notification delivery summary fetch failures fall back to empty delivery summaries, so notification audit storage or aggregation errors cannot suppress jobs, queue, provider, or API quota sections.

Ops dashboard API quota payload failures fall back to empty quota services, so local quota ledger or aggregation errors cannot suppress jobs, queue, provider, or notification delivery sections.

Ops dashboard malformed API quota payloads fall back to empty quota services, so quota payload shape errors cannot suppress jobs, queue, provider, or notification delivery sections.

Ops dashboard API quota service lists use list-of-dict safe conversion before payload output, so malformed quota service collections fall back to empty services without suppressing jobs, queue, provider, or notification delivery sections.

Ops dashboard job snapshot failures fall back to empty job sections and mark dashboard status warning, so job telemetry or latency aggregation errors cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard malformed job payloads fall back to empty job sections and mark dashboard status warning, so job payload shape errors cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard nested job sections use dict-safe conversion before payload output, so malformed job telemetry sections fall back to empty maps without suppressing queue, provider, API quota, or notification delivery sections.

Ops dashboard job unavailable status flags use bool-safe conversion, so malformed observability_unavailable truthiness cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard stuck job count status aggregation uses dict- and integer-safe conversion, so malformed stuck job count truthiness cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard malformed provider payloads fall back to an empty last_24h provider state, so provider SLA payload shape errors cannot suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider selected windows use string-safe conversion before payload output, so malformed selected-window values cannot leak non-JSON-safe objects or suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard malformed provider alert lists fall back to empty alerts, so provider alert payload shape errors cannot suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert impact classification uses string-safe source conversion, so malformed alert source truthiness cannot interrupt jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert level comparison uses string-safe conversion before status and count aggregation, so malformed alert-level equality cannot interrupt jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert success-rate fields use finite-float conversion before payload output, so NaN or Infinity alert rates fall back to zero instead of leaking non-standard JSON numbers.

Ops dashboard provider alert text and window fields use string- and dict-safe conversion before payload output, so malformed alert source, provider, message, status, basis, selected window, or windows maps cannot leak non-JSON-safe objects.

Report conformance quality gate inputs use dict-native field reads before decision-tree evaluation, so malformed report lint, final audit, evidence exit gate, or content credibility accessors cannot interrupt report quality classification or erase valid blocking and warning evidence.

Report renderer lint repair result fields use dict-native field reads before structured-key scrubbing, so malformed lint result or issue accessors cannot interrupt automatic repair for structured JSON key leaks.

Report execution summary quality gate fields use dict-native field reads before report rendering, so malformed final audit, evidence gate, report conformance, or report lint accessors cannot interrupt HTML/Markdown execution summary output or erase valid quality status evidence.

Report quality repair queue quality gate fields use dict-native field reads before action prioritization, so malformed report, content credibility, report conformance, evidence gate, data trust, or decision freshness accessors cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue report identity fields use string-safe conversion before provider-impact handoff and action prioritization, so malformed ticker, filename, or pipeline truthiness cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue quality gate text fields use string-safe conversion before action prioritization, so malformed status, summary, or message truthiness cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue reason codes use string-safe conversion before action prioritization, so malformed reason-code text cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue stale source lists use string-safe conversion before action prioritization, so malformed stale-source text cannot interrupt refresh-data prioritization or erase valid stale source evidence.

Report quality repair queue text list tuple sequences are evaluated before action prioritization, so immutable reason-code or stale-source batches do not lose repair evidence.

Shared mapping list conversions use native list and tuple iterators when iterator accessors fail before item traversal, so report repair and strategy evaluation do not erase valid sequence evidence.

Shared mapping text list conversions use native list and tuple iterators when custom iterators fail before yielding, so report repair reason-code or stale-source evidence is not erased by malformed iterator objects.

Shared mapping dict list conversions use native list and tuple iterators when custom iterators fail before yielding, so report repair provider-alert evidence is not erased by malformed iterator objects.

Shared mapping traversal falls back to native dict items when custom items iterators fail before yielding, so malformed mapping iterator objects cannot erase underlying snapshot, repair, or provider evidence.

Report quality repair queue provider alert lists preserve valid entries before iterator failures, so malformed provider alert iteration cannot interrupt provider-impact handoff or erase wait-provider-recovery repair evidence.

Report quality repair queue report collections preserve valid reports before iterator failures, so malformed report iteration cannot interrupt action prioritization or erase valid repair reasons.

Report quality repair queue decision freshness detail fields use string-safe conversion before action prioritization, so malformed rerun reason truthiness cannot interrupt rerun-analysis prioritization or erase valid freshness repair context.

Report quality repair queue decision freshness flags use bool-safe conversion before action prioritization, so malformed rerun flag truthiness cannot interrupt rerun-analysis prioritization or erase valid freshness repair context.

Report quality repair queue limit uses integer-safe conversion before slicing prioritized actions, so malformed limit truthiness cannot interrupt action prioritization or erase valid repair reasons.

Outcome calibration quality signal fields use dict-native field reads before miss attribution, so malformed backtest, report, data trust, content credibility, report conformance, or decision freshness accessors cannot interrupt quality-signal learning or misclassify low-quality misses as thesis failures.

Outcome calibration report identity fields use string-safe conversion before report matching and miss attribution, so malformed report filename, ticker, pipeline, horizon, or reason truthiness cannot interrupt quality-signal learning or disconnect misses from valid report-time evidence.

Outcome calibration data trust score fields use float-safe fallback before miss attribution, so malformed score truthiness cannot interrupt quality-signal learning or replace a valid zero score with fallback confidence.

Outcome calibration row collections use list-safe normalization before report matching and miss attribution, so malformed backtest or report collection truthiness cannot interrupt quality-signal learning or erase valid rows.

Outcome calibration decision freshness flags use bool-safe conversion before miss attribution, so malformed rerun flag truthiness cannot interrupt quality-signal learning or misclassify stale report-time evidence.

Outcome calibration matched reports use dict-safe fallback before miss attribution, so malformed matched report truthiness cannot interrupt quality-signal learning or disconnect misses from valid report-time evidence.

Outcome calibration numeric fields use conversion-safe fallback before miss attribution, so malformed ROI or data trust score conversion cannot interrupt quality-signal learning or erase valid stale report-time evidence.

Strategy evaluator numeric fields use conversion-safe fallback before alpha model comparison, so malformed ROI, excess return, or drawdown conversion cannot interrupt strategy evaluation or erase valid hit-rate evidence.

Strategy evaluator artifact fields use dict-native field reads before alpha model comparison, so malformed artifact, metrics, or quality funnel accessors cannot interrupt strategy evaluation or erase valid model, trigger, quality, or hit-rate evidence.

Strategy evaluator hit flags use bool-safe fallback before alpha model comparison, so malformed hit flag truthiness cannot interrupt strategy evaluation or erase valid outcome-based hit-rate evidence.

Strategy evaluator artifact iterators preserve valid entries before alpha model comparison, so malformed artifact collection iteration cannot erase already parsed model, trigger, quality, or hit-rate evidence.

Strategy evaluator artifact tuple sequences are evaluated before alpha model comparison, so immutable artifact batches do not appear as empty backtest evidence.

Provider impact report fields use dict-native field reads before provider recovery decisions, so malformed report, data trust, or provider alert accessors cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact report identity fields use string-safe conversion before provider recovery output, so malformed filename or pipeline truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact ticker identity uses string-safe conversion before provider recovery output, so malformed ticker payload objects cannot interrupt JSON serialization or erase wait-provider-recovery blocking evidence.

Provider impact current fetch fields use bool-, integer-, and string-safe conversion before provider recovery decisions, so malformed current fetch truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact alert text fields use string-safe conversion before provider recovery decisions, so malformed source, provider, or alert level truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact reason codes use string-safe conversion before provider recovery decisions, so malformed reason-code text cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact reason code iterators preserve valid entries before failures, so malformed reason-code iteration cannot erase already parsed provider recovery blocking evidence.

Provider impact text list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed reason-code iterator objects cannot erase underlying provider recovery blocking evidence.

Provider impact alert iterators preserve valid entries before failures, so malformed provider alert iteration cannot erase already parsed core-source provider recovery blocking evidence.

Provider impact ledger report iterators preserve valid reports before failures, so malformed report collection iteration cannot erase already parsed provider recovery impact rows or sampled report counts.

Provider impact tuple sequences are evaluated before provider recovery decisions, so immutable reason-code, alert, or ledger report batches do not lose wait-provider-recovery blocking evidence.

Provider impact list conversions use native list and tuple iterators when iterator accessors fail before provider recovery decisions, so underlying reason-code, alert, or ledger report evidence is not erased.

Provider impact dict list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed provider alert iterator objects cannot erase underlying provider recovery evidence.

Provider impact ledger sort keys use string-safe conversion before ordering, so malformed ticker sort-key truthiness cannot interrupt provider recovery impact ledger output.

Daily decision queue action fields use dict-native field reads before priority ordering, so malformed repair, provider impact, notification delivery, backtest, rerun, model route, watchlist, or screener action accessors cannot interrupt daily operating order or erase valid queue context.

Notification plan action fields use dict-native field reads before message and outbox handoff, so malformed decision queue or legacy action accessors cannot interrupt notification planning or erase source, report, CTA, rank, and delivery identity context.

Notification delivery audit context fields use dict-native field reads before persistence and reconciliation, so malformed outbox or audit-record accessors cannot interrupt sender audit writes or erase source, report, CTA, rank, retry, and attention context snapshots.

Provider SLA dashboard alert payload fields use dict-native field reads before impact classification, so malformed provider alert accessors cannot interrupt core/enrichment status projection or erase valid provider, level, message, window, and success-rate evidence.

Notification delivery observability summaries use dict-safe conversion before rendering dashboard and Prometheus maps, so malformed summary or count-map truthiness cannot interrupt external delivery health metrics.

Notification delivery observability fields use dict-native field reads before attention, dashboard, and Prometheus rendering, so malformed summary accessors cannot interrupt notification health visibility or erase failed, retry-exhausted, channel, and reason evidence.

Notification delivery observability counts use integer-safe conversion before rendering dashboard and Prometheus gauges, so malformed count conversion cannot interrupt external delivery health metrics.

Notification delivery Prometheus channel and reason labels use string-safe conversion, so malformed label truthiness cannot interrupt external delivery health metrics.

Prometheus label rendering uses string-safe key and value conversion, so malformed provider, queue, or delivery label truthiness cannot interrupt metrics output.

Prometheus provider summary fetch failures fall back to empty provider series, so provider SLA storage or aggregation errors cannot interrupt queue or notification delivery metrics output.

Prometheus provider summary non-iterable payloads fall back to empty provider series, so malformed provider summary payload shape cannot interrupt queue or notification delivery metrics output.

Prometheus provider summary iterator failures preserve provider rows parsed before the failure, so one broken provider summary iterator cannot suppress earlier valid provider series or interrupt queue and notification delivery metrics output.

Prometheus queue snapshot fetch failures fall back to unknown/zero queue gauges, so queue observer or backend errors cannot interrupt provider or notification delivery metrics output.

Ops dashboard queue snapshot fetch failures fall back to an unavailable unknown queue status, so queue observer or backend errors mark the dashboard critical without suppressing jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue availability uses bool-safe conversion before status aggregation and payload output, so malformed queue availability truthiness cannot suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue metadata uses string-, integer-, and dict-safe conversion before payload output, so malformed backend, queue name, depth, or queues maps cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard named queue details use string-key and dict-safe conversion before payload output, so malformed named queue keys or detail rows cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard named queue detail fields use integer-, string-, and registry-map safe conversion before payload output, so malformed named queue depth, registry counts, or supplemental detail fields cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue supplemental fields use integer-, float-, string-, and registry-map safe conversion before payload output, so malformed registries, active task counts, queue age, timeout, or error values cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue age fields use finite-float conversion before payload output, so NaN or Infinity queue age values fall back to zero instead of leaking non-standard JSON numbers.

Ops dashboard free mode provider summaries use dict-, list-, bool-, and string-safe conversion before payload output, so malformed free-mode provider tiers or provider lists cannot suppress jobs, queue, provider, API quota, or notification delivery sections.

Ops dashboard free mode violations use string-safe conversion before payload output, so malformed violation entries cannot leak non-JSON-safe objects or suppress jobs, queue, provider, API quota, or notification delivery sections.

Prometheus queue snapshots use dict-safe conversion before rendering queue gauges, so malformed queue snapshot mapping cannot interrupt metrics output and falls back to unknown/zero queue gauges.

Prometheus queue backend and queue name rendering uses string-safe conversion, so malformed queue label truthiness cannot interrupt queue gauges.

Prometheus queue availability rendering uses bool-safe conversion, so malformed queue availability truthiness cannot interrupt queue gauges.

Prometheus named queue depth maps use dict-safe conversion, so malformed queue map or detail truthiness cannot interrupt queue gauges.

Prometheus integer gauges use integer-safe conversion, so malformed provider or queue count conversion cannot interrupt metrics output.

Prometheus float gauges use float-safe conversion, so malformed provider success-rate conversion cannot interrupt metrics output.

Prometheus provider rows use dict-safe conversion before rendering provider gauges, so malformed provider row mapping cannot interrupt metrics output or create empty-label provider series.

Provider SLA window alert enrichment uses integer-, float-, and string-safe conversion, so malformed provider attempts, success-rate, error count, or status values cannot interrupt dashboard alert recalculation.

Provider SLA alert policy basis selection uses dict-, integer-, float-, and string-safe conversion, so malformed window stats truthiness cannot interrupt upstream provider alert generation.

Data trust provider SLA evidence attempts use truthiness-safe integer and basis text conversion, so malformed provider SLA alert evidence cannot interrupt report trust downgrade decisions.

Data trust provider SLA nested window maps use dict-safe conversion before evidence attempts, so malformed nested window accessors cannot interrupt report trust downgrade decisions or suppress alert-level attempts fallback.

Data trust provider SLA alert matching uses string-safe source, provider, level, and message conversion, so malformed alert text truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit entries use string-, integer-, and bool-safe conversion, so malformed current source audit truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA trust metadata uses list- and string-safe conversion, so malformed existing trust status, reason codes, or notes cannot interrupt report trust downgrade decisions.

Data trust provider SLA alert collections use iterable-safe conversion, so malformed alert collection truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit collections use iterable-safe conversion, so malformed current source audit iterator failures cannot erase valid source audit rows or interrupt report trust downgrade decisions.

Data trust provider SLA rows use dict-safe conversion before matching current source audit entries and provider alerts, so malformed row accessors cannot interrupt data-trust downgrades or erase provider SLA evidence.

Data trust provider SLA source data uses dict-safe conversion before reading current source audit rows, so malformed source data accessors cannot interrupt data-trust downgrades or erase provider SLA evidence.

Data trust provider SLA alert fetch failures fall back to existing trust, so provider SLA storage or helper failures cannot interrupt report trust downgrade decisions.

Data trust provider SLA trust metadata iterators preserve valid entries before failures, so malformed reason-code or note iterators cannot erase already parsed report trust context.

Data trust provider SLA list conversions use native list and tuple iterators when iterator accessors fail before trust downgrade decisions, so source-audit rows, provider alerts, reason codes, and notes are not erased.

Data trust provider SLA dict row conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed source-audit or provider-alert iterator objects cannot erase trust downgrade evidence.

Data trust provider SLA text list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed trust metadata reason-code or note iterator objects cannot erase existing report trust context.

Data trust scoring audit source names use string-safe conversion, so malformed source truthiness cannot interrupt report trust scoring or erase valid source audit decisions.

Data trust audit entry text fields use string-safe conversion, so malformed source, provider, error kind, or message truthiness cannot interrupt source audit evidence creation.

Data trust audit entry status uses string-safe conversion, so malformed but valid status text cannot be misclassified as unavailable.

Data trust audit entry record counts use integer-safe conversion, so malformed numeric truthiness cannot erase valid source evidence counts.

Data trust audit entry boolean fields use bool-safe conversion, so malformed cache-hit or stale truthiness cannot interrupt source audit evidence creation.

Prompt source audit summary fields use string-, integer-, and bool-safe conversion, so malformed audit provider, status, count, cache, stale, or message fields cannot interrupt prompt JSON generation.

Prompt source audit root source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid source audit summary provider, status, count, cache, stale, mismatch, or message evidence.

Prompt source audit entry fields use dict-native field reads before prompt output, so malformed source audit entry accessors cannot interrupt prompt JSON generation or erase valid source audit provider, status, record count, merged count, mismatch, cache, stale, or message evidence.

Prompt data trust list fields use truthiness- and iterator-safe conversion before prompt output, so malformed data trust critical failures, stale sources, notes, or reason codes cannot interrupt prompt JSON generation and valid trust evidence parsed before iterator failure remains visible.

Prompt data trust source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid data trust evidence.

Prompt data trust fields use dict-native field reads before prompt output, so malformed data trust field accessors cannot interrupt prompt JSON generation or erase valid data trust evidence.

Prompt company identity mapping uses truthiness-safe handoff before prompt output, so malformed identity mapping truthiness cannot interrupt prompt JSON generation or erase valid stock identity and alias constraints.

Prompt company identity fields use dict-native field reads before prompt output, so malformed company identity field accessors cannot erase valid stock identity and alias constraints.

Prompt company identity source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid company identity evidence.

Prompt company metadata source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid schema version, sector, industry, country, employee count, fetch date, or deterministic financial sector context evidence.

Agent runtime identity guard uses truthiness-safe company identity handoff before prompt assembly, so malformed identity mapping truthiness cannot interrupt agent prompt construction or erase the hard identity lock.

Agent runtime identity guard mapping length checks tolerate malformed length access before prompt assembly, so valid company identity evidence remains available even when mapping length cannot be computed.

Agent runtime identity guard mapping access uses dict-native field reads before prompt assembly, so malformed mapping accessor methods cannot interrupt agent prompt construction or erase valid company identity evidence.

Agent runtime identity guard ticker fields use string-safe conversion before prompt assembly, so malformed ticker or stock-id string conversion cannot interrupt agent prompt construction and falls back to the best available identity ticker.

Agent runtime identity guard text fields use string-safe conversion before prompt assembly, so malformed official or legal name truthiness cannot interrupt agent prompt construction or erase valid hard identity evidence.

Agent runtime identity guard alias lists use iterator-safe string conversion before prompt assembly, so malformed English-name or forbidden-alias iterators cannot interrupt agent prompt construction and valid aliases parsed before iterator failure remain visible.

Agent runtime identity guard alias native lists preserve limits before prompt assembly, so malformed list iterator accessors cannot turn bounded English-name aliases into noisy repr strings or leak aliases beyond the configured cap.

Agent runtime identity guard templates use string-safe formatting before prompt assembly, so malformed runtime identity rule templates cannot interrupt hard identity lock construction and valid company identity guidance remains visible.

Agent runtime identity guard runtime rules use dict-native field reads before prompt assembly, so malformed identity guard rule config accessors cannot erase valid company identity constraints.

Agent runtime identity guard values use dict-native field reads before prompt assembly, so malformed identity guard value accessors cannot erase valid legal name, English-name, or forbidden-alias constraints.

Agent runtime identity guard source data uses dict-native field reads before prompt assembly, so malformed source data accessors cannot interrupt hard identity lock construction or erase valid company identity evidence.

Agent runtime RAG context mapping uses truthiness-safe handoff before prompt assembly, so malformed RAG context mapping truthiness cannot interrupt agent prompt construction or erase valid retrieved context for the target agent.

Agent runtime RAG context text uses string-safe conversion before compact prompt truncation, so malformed retrieved-context length or slice behavior cannot interrupt agent prompt construction and valid retrieved context remains visible.

Agent runtime temporal memory reflection prompt uses string-safe conversion before prompt assembly, so malformed reflection prompt truthiness cannot interrupt agent prompt construction and valid reflection evidence remains visible.

Agent runtime temporal memory backtests use iterator- and JSON-safe conversion before prompt assembly, so malformed backtest slices cannot interrupt agent prompt construction and valid backtests parsed before iterator failure remain visible.

Agent runtime prompt safety helpers are split from prompt assembly, so string, bool, iterator, and JSON coercion guards stay reusable without pushing agent prompt construction past backend module size limits.

Agent runtime top-level rule sections use dict-native field reads before prompt assembly, so malformed runtime rules mapping accessors cannot erase valid section configs.

Agent runtime prompt JSON dict items use dict-native field reads before prompt assembly, so malformed mapping item accessors cannot erase valid JSON-safe prompt evidence.

Agent runtime prompt JSON sequence items use native iterators before prompt assembly, so malformed list or tuple iterator accessors cannot erase valid JSON-safe prompt evidence.

Agent runtime prompt JSON collection items use native iterators before prompt assembly, so malformed set or frozenset iterator accessors cannot erase valid JSON-safe prompt evidence.

Agent runtime structured instructions mappings use dict-native traversal before prompt assembly, so malformed structured-agent rule mapping truthiness or item accessors cannot erase valid structured output constraints.

Agent runtime rule section mappings use dict-native lookup before prompt assembly, so malformed runtime rule section truthiness or lookup accessors cannot erase valid agent-specific guidance.

Agent runtime rule block configs use dict-native field reads before prompt assembly, so malformed rule block config truthiness or field accessors cannot erase valid title, intro, schema, or rule guidance.

Agent runtime rule list mappings use dict-native field reads before prompt assembly, so malformed nested rule-list mapping accessors cannot erase valid runtime rule guidance.

Agent runtime state view uses JSON-safe conversion before prompt assembly, so non-serializable AgentState view leaves cannot interrupt agent prompt construction and valid state evidence remains visible.

Agent runtime forensic warning uses string-safe conversion before prompt assembly, so malformed V2 forensic-warning truthiness cannot interrupt agent prompt construction and valid warning evidence remains visible.

Agent runtime retry and audit instruction fields use string-safe conversion before prompt part filtering, so malformed retry or audit instruction truthiness cannot interrupt agent prompt construction and valid runtime guidance remains visible.

Agent runtime final audit mappings use dict-native field reads before preflight rule assembly, so malformed final-audit config, per-agent, or per-pipeline mapping accessors cannot erase valid audit guidance.

Agent runtime final audit pipeline id uses string-safe conversion before preflight rule selection, so malformed pipeline-id truthiness cannot interrupt agent prompt construction and valid mode-specific audit rules remain visible.

Agent runtime final audit rule lists use string-safe conversion before preflight rule assembly, so malformed rule text cannot interrupt agent prompt construction and valid final-audit rules parsed before or after the bad entry remain visible.

Agent runtime prompt rule blocks use string-safe conversion before prompt assembly, so malformed runtime rule titles, intros, schema lines, or rule items cannot interrupt agent prompt construction and valid runtime guidance remains visible.

Agent runtime output cleanliness mappings use dict-native field reads before prompt assembly, so malformed formal-output config accessors cannot erase valid report output contracts.

Agent runtime output cleanliness rules use string-safe conversion before prompt assembly, so malformed formal-output rule text cannot interrupt agent prompt construction and valid report output contracts remain visible.

Agent runtime assistant task prompt mappings use dict-native field reads before background task prompt assembly, so malformed task prompt group or task config accessors cannot erase valid tear sheet, context digest, or repair reflection guidance.

Agent runtime assistant task prompts use string-safe conversion before background task prompt assembly, so malformed task system instructions or instruction lines cannot interrupt tear sheet, context digest, or repair reflection task construction and valid task guidance remains visible.

Agent runtime primary probe flag uses bool-safe conversion before prompt assembly, so malformed compact prompt flag truthiness cannot interrupt agent prompt construction and falls back to the full prompt context.

Prompt freshness mappings use truthiness-safe handoff before prompt output, so malformed data_freshness or source_freshness mapping truthiness cannot interrupt prompt JSON generation or erase valid source recency evidence.

Prompt freshness source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid data_freshness or source_freshness recency evidence.

Prompt market data source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid current price, market cap, and 52-week range evidence.

Prompt valuation metrics source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid valuation multiples, share count, EPS, dividend yield, dividend per share, payout ratio, or deterministic DDM evidence.

Prompt TTM financials source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid trailing revenue, net income, EBITDA, margin, or forward EPS implied revenue evidence.

Prompt cash flow source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid free cash flow, operating cash flow, or deterministic DCF base FCF evidence.

Prompt balance sheet source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid debt, cash, net debt, liquidity, leverage, WACC, or deterministic DCF net debt evidence.

Prompt growth source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid annual, TTM, Yahoo, or 5-year CAGR growth evidence.

Prompt financial history source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid history rows, deterministic revenue CAGR, latest annual revenue growth, or FCF conversion evidence.

Prompt institutional trading mapping uses truthiness-safe handoff before prompt output, so malformed institutional trading mapping truthiness cannot interrupt prompt JSON generation or erase valid chip-flow evidence.

Prompt institutional trading source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid institutional trading chip-flow evidence.

Prompt full market catalyst items use truthiness- and iterator-safe conversion before prompt output, so malformed catalyst lists cannot interrupt default prompt JSON generation and valid news items parsed before iterator failure remain visible.

Prompt market catalyst source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid recent catalyst and news evidence.

Prompt peer context source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid dynamic peer metrics and peer discovery evidence.

Prompt full dynamic peer metrics use truthiness- and iterator-safe conversion before prompt output, so malformed peer metric lists cannot interrupt default prompt JSON generation and valid peer rows parsed before iterator failure remain visible.

Prompt full peer discovery results use truthiness- and iterator-safe conversion before prompt output, so malformed peer discovery lists cannot interrupt default prompt JSON generation and valid discovered peer rows parsed before iterator failure remain visible.

Prompt supplemental source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid data quality notes and monthly revenue evidence.

Prompt full recent monthly revenue text uses truthiness- and iterator-safe conversion before prompt output, so malformed monthly revenue lists cannot interrupt default prompt JSON generation and valid monthly revenue rows parsed before iterator failure remain visible.

Prompt full data quality notes use truthiness- and iterator-safe conversion before prompt output, so malformed data source note lists cannot interrupt default prompt JSON generation and valid notes parsed before iterator failure remain visible.

Prompt PE river chart source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid full or compact PE river chart evidence.

Prompt full PE river chart mapping uses truthiness-safe handoff before prompt output, so malformed valuation chart mapping truthiness cannot interrupt default prompt JSON generation or erase valid local valuation context.

Prompt compact list fields use truthiness- and iterator-safe conversion before compact prompt output, so malformed compact source lists cannot interrupt prompt JSON generation and valid items parsed before iterator failure remain visible.

Prompt compact PE river chart mapping uses truthiness-safe handoff before compact prompt output, so malformed valuation chart mapping truthiness cannot interrupt prompt JSON generation or erase valid local valuation context.

Prompt compact PE river chart fields use dict-native field reads before compact prompt output, so malformed valuation chart field accessors cannot interrupt prompt JSON generation or erase valid PE river chart source, years, multiples, or band labels.

Prompt compact PE river years use truthiness- and iterator-safe tail conversion before compact prompt output, so malformed valuation year lists cannot interrupt prompt JSON generation and valid trailing years parsed before iterator failure remain visible.

Prompt cross-check source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid DuPont identity fallback and WACC capital structure notes.

Prompt history rows use truthiness- and iterator-safe year conversion before prompt output, so malformed history year lists cannot interrupt prompt JSON generation and valid year rows parsed before iterator failure remain visible.

Prompt history value fields use truthiness- and iterator-safe sequence conversion before prompt output, so malformed revenue, net income, and FCF history lists cannot interrupt prompt JSON generation or deterministic financial tool context, and valid values parsed before iterator failure remain visible.

Prompt history source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt prompt JSON generation or erase valid financial history rows.

Prompt agent context fields use truthiness-safe presence checks before prompt output, so malformed routed context truthiness cannot interrupt prompt JSON generation or erase valid agent context sections.

Prompt agent context source data uses dict-native field reads before prompt output, so malformed source data accessors cannot interrupt agent context routing or erase valid routed macro, chip, alternative, sentiment, filing, open-data, or earnings-call sections.

Data trust string list conversion uses string-safe conversion, so malformed text truthiness cannot interrupt reason-code or score-reason normalization.

Data trust score normalization uses float-safe conversion, so malformed existing trust score conversion cannot interrupt snapshot generation and falls back to status-derived scoring.

Data trust normalization uses dict-native trust field reads, so malformed existing trust mapping accessors cannot interrupt score, freshness, reason, note, or provider SLA metadata normalization.

Data trust snapshot existing trust selection uses dict-safe conversion, so malformed `data_trust` truthiness cannot interrupt snapshot generation or erase valid trust metadata.

Data trust snapshot refresh flags use bool-safe conversion, so malformed refresh metadata truthiness cannot interrupt snapshot generation.

Data trust snapshot rerun context text uses string-safe conversion, so malformed analysis text truthiness cannot interrupt snapshot generation or rerun context preservation.

Data trust snapshot sanitizer uses string-safe key and value conversion, so malformed snapshot object string conversion cannot interrupt snapshot generation or leak empty keys.

Data trust snapshot sanitizer uses native list and tuple iterators when iterator accessors fail, so malformed snapshot sequence subclasses cannot interrupt snapshot generation or erase underlying list or tuple evidence.

Data trust snapshot sanitizer falls back to native list and tuple iterators when custom sequence iterators fail before yielding, so malformed snapshot iterator objects cannot erase underlying list or tuple evidence.

Data trust snapshot sanitizer uses native dict items when items accessors fail, so malformed snapshot mapping subclasses cannot interrupt snapshot generation or erase underlying mapping evidence.

Data trust snapshot sanitizer falls back to native dict items when custom items iterables fail, so malformed snapshot mapping item views cannot erase underlying mapping evidence.

Data trust snapshot integrity hash lookup uses string-safe conversion, so malformed hash metadata truthiness cannot interrupt snapshot verification.

Data trust snapshot integrity and schema validators use dict-native snapshot field reads, so malformed snapshot accessors cannot interrupt hash or schema verification.

Data trust snapshot rerun context agent keys use string-safe conversion, so malformed analysis key conversion cannot interrupt snapshot generation or leak malformed rerun context keys.

Data trust snapshot content hash keys use string-safe conversion, so malformed snapshot object keys cannot interrupt integrity verification or leak non-JSON-safe hash inputs.

Data trust snapshot content hashing uses iterator-safe mapping traversal, so malformed snapshot items accessors cannot interrupt integrity generation or verification.

Data trust snapshot size governance uses snapshot sanitizer input, so malformed snapshot object keys cannot interrupt size governance or leak non-JSON-safe snapshot inputs.

Data trust snapshot size byte calculation uses snapshot sanitizer input, so malformed snapshot object keys cannot interrupt size measurement or leak non-JSON-safe snapshot inputs.

Data trust snapshot builds use dict-native context and data field reads, so malformed mapping accessors cannot interrupt snapshot generation or erase identity, freshness, quality, or rerun metadata.

Data trust snapshot identity fields use string-safe context/data selection, so malformed ticker, company name, or pipeline truthiness cannot interrupt snapshot generation or reproducibility packet identity.

Data trust reproducibility source audit metadata uses string-safe provider and timestamp extraction, so malformed source audit provider or fetched-at truthiness cannot interrupt snapshot generation or erase valid traceability fields.

Data trust reproducibility packets use dict-native context, data, source audit, and metadata field reads, so malformed mapping accessors cannot interrupt provenance generation or erase traceability fields.

Data trust reproducibility packets preserve validated full prompt fingerprints, so report audit can distinguish exact prompt content without exposing arbitrary prompt-like values.

Prompt fingerprints cover agent templates, state-view policy, system prompts, and runtime prompt rules, so report identity follows the effective prompt bundle rather than only `agents.json`.

Prompt identity and prompt injection share one process-stable runtime-rule snapshot, so a report fingerprint cannot drift from the rules injected into the same workflow.

Runtime code provenance records commit and dirty state once per workflow, so uncommitted code cannot be mistaken for a report reproducible from the commit alone. `code_dirty = true` means local changes were present, `false` means the worktree was clean at initialization, and `null` means the state was unknown.

Data trust explicit target price detection uses dict-native root field reads, so malformed parsed or structured output context accessors cannot interrupt target-price guardrail generation or erase underlying evidence.

Data trust explicit target price detection uses string-safe key and value conversion, so malformed parsed or structured output target fields cannot interrupt snapshot guardrail generation or erase valid detected target fields.

Data trust explicit target price detection preserves valid list items before iterator failures, so malformed parsed or structured output collections cannot erase already detected target fields.

Data trust explicit target price detection uses native list iterators when iterator accessors fail, so malformed parsed or structured output list subclasses cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native list iterators when custom iterators fail before yielding, so malformed parsed or structured output list iterator objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection preserves valid mapping items before iterator failures, so malformed parsed or structured output objects cannot erase already detected target fields.

Data trust explicit target price detection uses native dict items when items accessors fail, so malformed parsed or structured output mapping subclasses cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native dict items when custom items iterables fail to create iterators, so malformed parsed or structured output mapping items iterable objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native dict items when custom items iterators fail before yielding, so malformed parsed or structured output mapping iterator objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection ignores non-finite numeric targets, so NaN or Infinity parsed outputs cannot create false explicit target-price evidence.

Data trust source record counting uses string-safe source keys, so malformed source truthiness cannot interrupt merged evidence counts for audit summaries.

Provider SLA window selection uses string-safe conversion, so malformed selected-window truthiness or string conversion cannot interrupt provider SLA payload generation.

Provider SLA window maps use dict-safe conversion, so malformed provider `windows` or selected-window stats map truthiness cannot interrupt dashboard alert recalculation.

Provider SLA nested window numeric fields use integer- and finite-float-safe conversion, so malformed `windows.*` attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA numeric field shaping uses dict-safe row conversion before provider and window output, so malformed direct-helper row mappings cannot interrupt numeric shaping or leak unnormalized attempts, counts, success rate, duration, and total-record evidence.

Provider SLA nested window maps keep only canonical `last_1h`, `last_24h`, and `last_7d` buckets before payload output, so experimental or malformed window keys cannot leak into API/UI contracts.

Provider SLA selected-window helper output normalizes nested `windows` maps before returning provider rows, so direct helper callers cannot bypass nested window numeric shaping.

Provider SLA selected-window numeric fields use integer- and finite-float-safe conversion, so malformed attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA provider rows use dict-safe conversion before window selection, so malformed provider row mapping conversion cannot interrupt dashboard alert recalculation.

Provider SLA alert projection uses dict-safe row conversion and string-safe alert-level conversion, so malformed alert row mapping or alert level hashing cannot interrupt dashboard alert lists.

Provider SLA alert projection output fields use string-, finite-float-, and dict-safe conversion, so malformed alert source, provider, message, status, basis, selected window, success rate, or windows maps cannot leak non-JSON-safe values.

Provider SLA all-window cumulative alerts reuse the same safe alert projection, so malformed cumulative alert rows cannot bypass the dashboard alert-list guard.

Provider SLA all-window provider summaries use dict-safe row conversion before returning dashboard payloads, so malformed cumulative provider rows cannot bypass the provider-list guard.

Provider SLA all-window provider numeric fields use integer- and finite-float-safe conversion, so malformed cumulative attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA payload summary fetch failures fall back to empty provider lists, so provider SLA storage or aggregation errors cannot interrupt selected-window dashboard payloads.

Provider SLA payload alert fetch failures fall back to empty alert lists, so cumulative alert storage or aggregation errors cannot suppress otherwise available provider summary rows.

Prometheus provider alert level rendering uses string-safe conversion, so malformed alert level truthiness cannot interrupt alert gauges.

Notification delivery failure reason bucketing uses string-safe error conversion, so malformed `last_error` truthiness cannot interrupt low-cardinality delivery health summaries.

Notification delivery summary channel counts use string-safe channel conversion, so malformed `channel_id` truthiness cannot interrupt delivery health channel distribution.

Notification delivery summary status counts use string-safe status conversion, so malformed `delivery_status` equality cannot interrupt delivery health status distribution.

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
- `reproducibility_packet` records the final snapshot hash, provider list, prompt version, full prompt fingerprint, model identifier, pipeline, code commit, code dirty state, generated time, and source data time for audit and rerun comparison.
- `decision_freshness.status = current` means the investment conclusion was generated from the current snapshot.
- `decision_freshness.status = needs_rerun` means the snapshot was refreshed after the HTML/Markdown conclusion was written. Treat the old conclusion as historical until rerun finishes.
- Watchlist items use the same signal. Items marked `需重跑` are sorted first so the operator can rerun the stale conclusion before reviewing lower-priority names.

## Decision Tracking And Backtests

The decision tracking scheduler runs after the daily tracking refresh. It scans reports whose generated date has reached the 3, 6, or 12 month horizon, fetches historical market closes, and writes one idempotent result per `(report_filename, horizon_months)`.

Backtest results are visible in `報告與維運` under `決策回測`. The panel shows hit rate, average strategy ROI, horizon breakdown, and the latest evaluated reports. A `買入/買進` call earns market ROI, `避免/強烈放空` earns inverse market ROI, and `持有` is treated as a range call. A duplicate run on the same day is skipped by the unique result key.

The daily dashboard also builds an outcome calibration ledger from recent backtest details and report metadata. Use it to distinguish a miss caused by weak data quality or insufficient report evidence from a miss where the thesis itself was likely wrong. Missing report metadata stays `unknown` rather than being over-attributed.

When provider health is degraded, the daily dashboard includes a provider impact ledger. Core-source critical impact can block blind reruns and recommend waiting for provider recovery; optional-source critical impact is only a monitor notice. This distinction prevents rerunning reports repeatedly while the same core source is still unavailable.

Use `decision_queue.items` as the daily operating order. It ranks free-mode blockers, blocked report repairs, provider recovery waits, notification delivery repair, due backtests, reruns, model route budget warnings, watchlist runs, and screener candidates in one top-five queue. A due backtest can outrank a routine rerun, while blocked report quality, core provider impact, or failed notification delivery can still win over watchlist triggers. The operator summary panel and the watchlist `今日工作台` both show the top queue, priority/source context, and how many secondary items remain so the UI does not hide work just because only the top few tasks are shown. `decision_queue.summary` exposes `source_labels` and `source_texts` beside raw `sources`, so consumers can render readable source distribution without rebuilding the source label map. `fix_notification_delivery` appears there as source `通知通道` with a `查看通知通道` CTA that opens the ops maintenance area, making delivery failure visible without relying on the failed external channel. The item preserves `failure_reason_counts` and `attention_contexts`, and adds a reason summary to `detail`, so operators can distinguish timeout, auth, rate limit, configuration, or network failures and see affected source/report context before opening raw audit rows. The operator summary panel and watchlist `今日工作台` render the same attention context summary in action detail, so affected ticker/report/CTA context stays visible before the maintenance panel opens. When no real work exists, the queue may still include a `monitor` fallback item for UI compatibility, but `summary.total_actionable` remains `0` and should not be rendered as pending work, counted as a quick action, or sent as a notification. Notification messages use `decision_queue.items` as the primary source when available, preserve source, priority score, ticker, filename, and pipeline context for real queue actions, and expose `queue_context` so external channels can see total actionable work, displayed count, secondary count, top priority, source distribution, `source_labels` for human-readable rendering while preserving raw source keys, and `source_texts` for label-plus-raw-key display while preserving raw source keys. `fix_notification_delivery` is a UI/ops repair action with `suppress_notification = true`; it remains visible in the queue but does not create `notification_plan.messages` or `delivery_outbox`, avoiding attempts to notify about a broken external notification channel through that same channel. Notification messages also preserve action-specific metadata such as model `route` / `warning_id`, due `horizon_months`, `recommended_action`, `blocks_auto_rerun`, `severity`, and `action_label` when those fields exist. They include `target_panel` and `target_tab` so downstream channels can open the same provider SLA, decision backtest, model route health, market screener, or watchlist panel used by operator summary quick actions, plus `operator_action` and `operator_action_label` so the channel can render the same CTA semantics as the in-app action list. Each message includes `queue_rank`, `queue_displayed_count`, and `is_top_priority`, computed after excluding `monitor`, so external channels can preserve the same displayed order without re-sorting. Each message also includes `dedupe_key` and `message_id` based on stable identifiers such as source, type, report, route, horizon, and pipeline; title, detail, and priority are intentionally excluded so text or rank changes do not duplicate the same underlying action. `delivery_outbox` then creates one pending audit entry for each enabled channel and message pair, carrying `channel_id`, `message_id`, `dedupe_key`, `delivery_key`, `delivery_status`, and `attempt_count`; disabled channels stay out of the outbox and remain visible through `channels[].missing_env`. External senders should call `reconcile_outbox_with_audit()` before sending so entries already marked sent return `already_sent = true` and `should_send = false`; failed entries observe the retry backoff before the next send attempt and return `skip_reason = retry_wait`, `retry_wait_seconds`, `next_retry_at`, and `should_send = false` while waiting. Reconciled entries also expose `audit_context`, copied from the persisted audit context snapshot, so sender logs or repair screens can recover prior source, report, CTA, and queue-rank context even when the current outbox entry is minimal. After the backoff window, failed entries remain retryable until the default retry budget is exhausted, then return `retry_exhausted = true`, `skip_reason = retry_exhausted`, and `should_send = false`. Sender attempts should then be recorded through `notification_delivery_audit`, which stores one row per `delivery_key` in `operational.sqlite3` and updates status, attempt count, last error, response id, success timestamp, and a context snapshot copied from the outbox entry without touching report index state. The context snapshot lets local triage recover source, ticker, report filename, target panel/tab, CTA, and queue rank from audit history even when the original daily dashboard payload is gone. The audit summary includes `retry_exhausted_count` so operators can spot channels that need configuration or provider repair instead of silent infinite retries.

For a `review_candidate` queue item, the operator summary keeps the ticker, company name, score, and real screener reason visible, then offers three direct actions: `查看股票快照`, `加入追蹤`, and `選擇分析模式`. Snapshot and watchlist reuse the existing stock snapshot panel methods. Analysis only opens the analysis tab, fills the ticker, selects the current mode, and focuses the controls; it never submits a new analysis automatically.

`notification_plan.queue_context` preserves upstream `decision_queue.summary.source_labels` and `source_texts` when those fields are present, so sender channels keep the same display contract as the daily queue instead of recomputing labels from raw source counts. `notification_plan.queue_context` fills missing `source_labels` and `source_texts` from raw `sources` while preserving upstream overrides, so partial summary maps still cover every active source key. `notification_plan.queue_context` ignores blank upstream source display overrides so fallback labels stay readable. `notification_plan.queue_context` drops upstream source display overrides for keys absent from raw `sources`, keeping display maps scoped to the active source distribution. `notification_plan.queue_context` trims raw source distribution keys before exposing `sources`, `source_labels`, and `source_texts`, so sender channels do not receive mismatched raw and display-map keys. Notification message and `delivery_outbox` entries carry `source_label` and `source_text` so sender templates can render the same readable source wording without rebuilding the source label map. Notification messages and `delivery_outbox` entries preserve action-provided `source_label` and `source_text` before fallback labels, so persisted or external source wording is not overwritten by the default backend map. Notification messages and `delivery_outbox` entries ignore blank action-provided `source_label` and `source_text` before fallback labels, so empty action metadata cannot suppress readable sender wording. Notification messages and `delivery_outbox` entries trim raw action `source` keys before exposing source display context, so sender payloads keep the same canonical source key as their readable source text. Notification source display override values are trimmed before `queue_context`, `messages`, and `delivery_outbox` expose them, so persisted wording keeps its content without leaking formatting whitespace. Notification messages and `delivery_outbox` entries drop blank action `source` keys before exposing source display context, so sender payloads do not carry whitespace-only source keys. The audit context snapshot also derives `source_label` and `source_text` from raw `source` when a legacy outbox entry omits them. Audit context snapshots ignore blank `source_label` and `source_text` before deriving fallback labels, so persisted audit history does not keep empty source wording. Frontend attention context summaries prefer persisted `source_text` or `source_label` before local source maps, so audit history can keep its original source wording even when the browser label map changes later. Frontend attention context summaries ignore blank persisted `source_text` and `source_label` before local source maps, so legacy or external blank values cannot hide the readable source fallback. Frontend `sourceLabels` is contract-tested against backend `SOURCE_LABELS`; keep both label maps in sync when adding a daily queue source. Frontend source label helpers trim raw source keys before lookup, matching the backend source display contract. Backend `SOURCE_LABELS` is immutable and must cover every daily queue `SOURCE_ORDER` key, so new queue sources cannot silently fall back to raw technical keys. Backend source label helpers trim raw source keys before lookup, so accidental whitespace around a source key cannot bypass the canonical readable label. Backend source label helpers drop blank raw source keys before outputting display maps, so empty source distribution entries cannot leak into sender or API payloads as empty labels. Backend source display map helpers ignore non-mapping raw source distributions, so `source_labels` and `source_texts` cannot be generated from malformed list or tuple payloads. Backend source key helpers ignore non-string raw source keys before display maps, so numeric, boolean, or bytes payload keys cannot become synthetic source labels. Backend source count normalization ignores non-mapping raw source distributions, so malformed summary payloads do not interrupt source display generation. Backend source count normalization drops non-positive raw source counts before outputting source distribution maps, so zero, negative, or unparseable counts do not appear as active source rows. Backend source count normalization treats boolean and non-finite raw source counts as inactive, so `true`, `NaN`, or infinity cannot become source distribution rows. Backend source count normalization treats fractional raw source counts as inactive, so decimal counts are not silently truncated into active source rows. Backend source count normalization requires non-string numeric raw source counts to equal their integer value, so Decimal or Fraction payload values cannot be truncated into active source rows. Backend source display override helpers normalize active raw source keys before matching upstream overrides, so fallback and override maps use the same canonical source key set. Backend source display override helpers ignore non-mapping active source distributions, so malformed active source inputs cannot generate override maps. Backend source display helpers ignore mapping accessor failures, so broken `keys()` or `items()` accessors cannot interrupt source display generation. Backend source display helpers ignore malformed mapping items, so non-pair mapping entries cannot interrupt source count or override processing. Backend source display helpers ignore mapping item unpack failures, so one broken item entry cannot suppress later valid source rows. Backend source display helpers ignore malformed mapping keys, so string or bytes `keys()` payloads cannot be split into synthetic source labels. Backend source display override helpers ignore non-string override values before fallback labels, so numeric or boolean display overrides cannot replace canonical wording.

Backend source count normalization treats raw source count conversion failures as inactive, so malformed count objects cannot interrupt source distribution output or suppress later valid source rows.

Backend source count normalization treats arithmetic raw source count conversion failures as inactive, so divide-by-zero or arithmetic conversion failures cannot interrupt source distribution output.

`notification_plan.queue_context` treats numeric conversion failures as zero before exposing count and priority fields, so malformed summary counts or priority scores cannot interrupt notification planning.

Notification messages treat malformed dedupe identity values as fallback identity parts before exposing `dedupe_key` and `message_id`, so one broken title/report/route identifier cannot interrupt delivery identity generation.

Notification delivery reconcile preflight uses string-safe delivery key lookup, so malformed outbox delivery key truthiness cannot interrupt audit reuse or already-sent suppression when the key is stringable.

Notification delivery reconcile attempt counts use string-safe integer conversion, so malformed audit attempt metadata cannot interrupt retry budget or next-attempt calculation.

Notification delivery reconcile retry timestamps use string-safe float conversion, so malformed audit last-attempt metadata cannot interrupt retry wait calculation.

Notification delivery reconcile statuses use string-safe text conversion, so malformed audit status truthiness cannot interrupt already-sent, retry-exhausted, or retry-wait decisions.

Notification delivery reconcile text metadata uses string-safe conversion, so malformed audit `last_error` or `last_response_id` truthiness cannot interrupt sender preflight result assembly.

Notification delivery reconcile audit context uses dict-safe conversion, so malformed persisted audit context truthiness cannot interrupt sender preflight context recovery.

Notification identity branch selection sanitizes report, ticker, pipeline, route, and warning identifiers before choosing fallback identity parts, so malformed truthiness cannot interrupt derived delivery identity generation.

Notification messages normalize `filename` and `report_filename` aliases with string-safe selection before exposing message and `delivery_outbox` report context, so malformed filename truthiness cannot interrupt notification planning.

Notification message and `delivery_outbox` context presence checks tolerate malformed equality comparisons before carrying optional metadata, so one broken action metadata value cannot interrupt notification planning.

Notification suppression flag checks treat malformed `suppress_notification` truthiness as unsuppressed while preserving type-based suppression, so one broken flag cannot interrupt notification planning or hide real actions.

Notification messages ignore malformed action-provided `dedupe_key` and `message_id` overrides before falling back to derived delivery identity, so external queue metadata cannot break sender idempotency handoff.

Notification operator CTA metadata selection uses string-safe action/label fallbacks, so malformed custom CTA truthiness cannot interrupt notification planning and stringable custom CTAs remain available to sender payloads.

Notification target metadata selection uses string-safe panel/tab fallbacks, so malformed custom target truthiness cannot interrupt notification planning and stringable custom targets remain available to sender payloads.

Notification message envelope selection uses string-safe type/title/detail fallbacks, so malformed message envelope truthiness cannot interrupt notification planning and stringable notification fields remain available to sender payloads.

Audit context source display presence checks use string-safe text conversion before deriving fallback labels, so malformed `source_label` or `source_text` truthiness cannot interrupt sender audit persistence.

Audit context source key normalization uses string-safe text conversion before deriving fallback labels, so malformed raw `source` truthiness cannot interrupt sender audit persistence and stringable source keys are trimmed before persistence.

Audit context snapshot presence checks tolerate malformed equality comparisons before preserving optional outbox metadata, so one broken context value cannot interrupt sender audit persistence.

Notification delivery attempt result fields use string-safe status, error, and response id conversion, so malformed sender result truthiness cannot interrupt audit persistence.

Notification delivery outbox identity fields use string-safe required text extraction, so malformed `delivery_key`, `channel_id`, `message_id`, or `dedupe_key` truthiness cannot interrupt audit persistence when the identity value is stringable.

Notification delivery audit listing uses string-safe integer limit conversion, so malformed list limit truthiness cannot interrupt audit record listing or delivery summary generation.

Notification attention context record serialization uses string-safe text, integer, and dict conversion, so malformed failed audit row truthiness cannot interrupt notification delivery summary output.

Notification messages and `delivery_outbox` entries ignore non-string action-provided `source_label` and `source_text` before fallback labels, so numeric or boolean action metadata cannot replace canonical source wording.

`notification_plan.queue_context` maps non-string legacy action source keys to `unknown` before exposing source distribution maps, so numeric or boolean legacy sources cannot create synthetic source rows.

`notification_plan.queue_context` uses a string-safe legacy action type filter before excluding `monitor` fallback actions, so malformed legacy action type truthiness cannot interrupt notification planning or inflate legacy actionable counts.

Backend source display helpers preserve valid mapping items before iterator failures, so an iterator error after a valid entry does not erase already parsed source rows or overrides.

Backend source display helpers preserve valid mapping keys before iterator failures, so an iterator error after a valid key does not erase already parsed source labels, source texts, or active override matches.

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

Job cleanup keeps active `queued`, `running`, and `waiting_retry` rows. It removes only terminal history older than the configured retention window plus orphan events. SQLite maintenance creates a backup under `SQLITE_BACKUP_DIR` only when the database's UTC backup interval is due, then runs one WAL checkpoint and `VACUUM`; schedule it during quiet hours and keep report output backups separate from `TASK_DB_PATH` cleanup. With the default `SQLITE_BACKUP_INTERVAL_DAYS=30`, a recent backup is reported as `skipped_interval` and no backup, checkpoint, or vacuum runs (including same-day reruns).

SQLite backup rotation uses `SQLITE_BACKUP_RETENTION_DAYS` (default `1`), so each current runtime DB label keeps its latest managed backup even when the backup predates the current UTC day. Older backups for the same active label, plus managed backups for labels no longer present in the current runtime DB set, are pruning candidates. The command is a dry-run by default: `backup_pruning.candidates` reports candidates without removing them. Add `--write` to unlink those candidates. Rotation manages only `cache_db-YYYYMMDD.sqlite3`, `task_db-YYYYMMDD.sqlite3`, and `checkpoint_db-YYYYMMDD.sqlite3`; unknown names such as `manual-archive.sqlite3`, directories, symlinks, WAL/SHM files, and all other files remain untouched. Non-positive interval or retention settings fail closed before any database or backup action.

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
