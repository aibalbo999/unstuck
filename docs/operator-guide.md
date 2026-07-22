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

Ops dashboard API quota numeric and observation fields use strict string/count conversion before payload output, so boolean, binary, or memory-view quota limits and provider observations cannot become synthetic quota evidence.

Ops dashboard job snapshot failures fall back to empty job sections and mark dashboard status warning, so job telemetry or latency aggregation errors cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard malformed job payloads fall back to empty job sections and mark dashboard status warning, so job payload shape errors cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard nested job sections use dict-safe conversion before payload output, so malformed job telemetry sections fall back to empty maps without suppressing queue, provider, API quota, or notification delivery sections.

Ops dashboard job unavailable status flags use bool-safe conversion, so malformed observability_unavailable truthiness cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard stuck job count status aggregation uses dict- and integer-safe conversion, so malformed stuck job count truthiness cannot suppress queue, provider, API quota, or notification delivery sections.

Ops dashboard stuck job count fields use strict count conversion before status and payload output, so boolean, binary, or memory-view counts cannot be decoded into synthetic stuck-job warnings or non-JSON-safe payload values.

Ops dashboard malformed provider payloads fall back to an empty last_24h provider state, so provider SLA payload shape errors cannot suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider selected windows use string-safe conversion before payload output, so malformed selected-window values cannot leak non-JSON-safe objects or suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard malformed provider alert lists fall back to empty alerts, so provider alert payload shape errors cannot suppress jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert impact classification uses string-safe source conversion, so malformed alert source truthiness cannot interrupt jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert level comparison uses string-safe conversion before status and count aggregation, so malformed alert-level equality cannot interrupt jobs, queue, API quota, or notification delivery sections.

Ops dashboard provider alert success-rate fields use finite-float conversion before payload output, so NaN or Infinity alert rates fall back to zero instead of leaking non-standard JSON numbers.

Ops dashboard provider alert text and window fields use string- and dict-safe conversion before payload output, so malformed alert source, provider, message, status, basis, selected window, or windows maps cannot leak non-JSON-safe objects.

Report conformance quality gate inputs use dict-native field reads before decision-tree evaluation, so malformed report lint, final audit, evidence exit gate, or content credibility accessors cannot interrupt report quality classification or erase valid blocking and warning evidence.

Report conformance quality gate inputs accept mapping-safe wrappers before decision-tree evaluation, so read-only report lint, final audit, evidence, content credibility, context, or snapshot payloads cannot hide blocker or warning evidence.

Report conformance quality gate issue lists use sequence-safe conversion before decision-tree evaluation, so tuple blocking or warning rows from lint, final audit, or content credibility gates cannot be ignored.

Report conformance visible artifact and gate status text fields use safe text fallback before decision-tree evaluation, so malformed HTML, Markdown, template heading, lint, audit, evidence, content, or data-trust status values cannot interrupt report quality classification.

Report content credibility evidence matrix rows use sequence-safe conversion before coverage checks, so tuple snapshot evidence rows do not trigger false missing-evidence warnings.

Report content credibility evidence matrix row maps use mapping-safe conversion before coverage checks, so read-only evidence rows do not trigger false missing-evidence warnings.

Report content credibility quality gate inputs use mapping-safe conversion before contradiction checks, so read-only context or snapshot wrappers cannot hide recommendation, price, target, evidence, or data-trust blockers.

Report content credibility recommendation and gate text fields use safe text fallback before contradiction checks, so malformed recommendation keys, target values, confidence values, evidence verdicts, or data-trust statuses cannot interrupt content-credibility classification.

Report renderer lint repair result fields use dict-native field reads before structured-key scrubbing, so malformed lint result or issue accessors cannot interrupt automatic repair for structured JSON key leaks.

Report execution summary quality gate fields use dict-native field reads before report rendering, so malformed final audit, evidence gate, report conformance, or report lint accessors cannot interrupt HTML/Markdown execution summary output or erase valid quality status evidence.

Report execution summary quality gate child maps use mapping-safe conversion before report rendering, so read-only data trust, final audit, evidence gate, report conformance, or report lint wrappers cannot be downgraded to unknown or not_recorded.

Report execution summary text fields use shared text conversion before HTML and Markdown output, so malformed final audit, evidence gate, report conformance, report lint, prompt, or model values cannot leak boolean, binary, or memory-view text into runtime trace copy.

Report execution summary Markdown text fields collapse embedded newlines before Markdown output, so model routes, quality gate statuses, prompt versions, model ids, and gate summaries cannot split runtime trace bullet rows.

Report mode template display fields use shared text conversion before HTML and Markdown output, so malformed template id, template name, audience, core question, headings, visual-focus chips, or reading-path items cannot leak boolean, binary, or memory-view text into report template cards.

Report mode template visual focus and reading path fields use shared text-list conversion before HTML and Markdown output, so tuple profile overrides preserve chips and reading paths without leaking malformed binary items.

Report mode template Markdown display fields collapse embedded newlines before Markdown output, so template names, audiences, core questions, headings, visual-focus chips, and reading-path items cannot split reading-path headings or bullet rows.

Report summary and decision discipline display fields use shared text conversion before HTML and Markdown output, so malformed ticker, company name, recommendation, trade setup, metric, or thesis discipline values cannot leak boolean, binary, or memory-view text into report summaries, decision lists, or investment-thesis discipline sections.

Report tear-sheet recent catalyst rows use dict-list safe conversion before HTML and investment-thesis output, so malformed recent_catalysts truthiness cannot interrupt summary or decision-discipline rendering when valid catalyst rows exist.

Report investment-thesis final-audit warning rows use text-list safe conversion before HTML and Markdown output, so malformed warning-list truthiness cannot interrupt decision-discipline data-gap rendering when valid warnings exist.

Report investment-thesis final-audit critical rows use text-list safe conversion before HTML and Markdown output, so malformed critical-list truthiness cannot interrupt decision-discipline downside-risk rendering when valid critical issues exist.

Report investment-thesis agent analysis text uses truthiness-safe fallback before payload and Markdown output, so malformed analysis text truthiness cannot interrupt Mode C thesis mirror rendering when valid agent evidence exists.

Report investment-thesis current price display uses truthiness-safe fallback before payload and Markdown output, so malformed formatted-price truthiness cannot interrupt mirror lines or valuation anchors when valid price text exists.

Report investment-thesis moat score display uses shared text conversion before payload and Markdown output, so malformed moat-score string conversion cannot interrupt mirror lines when valid or fallback moat evidence exists.

Report investment-thesis prebuilt payloads use mapping-safe conversion before HTML and Markdown output, so malformed payload truthiness cannot interrupt report rendering when valid decision-discipline rows already exist.

Report Markdown renderer prebuilt investment-thesis payloads use mapping-safe handoff before Markdown output, so malformed thesis truthiness cannot interrupt Markdown report rendering when valid decision-discipline rows already exist.

Report investment-thesis source audit rows use dict-list safe conversion before HTML and Markdown output, so malformed source_audit truthiness cannot interrupt information-richness grading or erase valid audit row counts.

Report investment-thesis history series use sequence-safe conversion before HTML and Markdown output, so malformed history-series truthiness cannot interrupt information-richness grading or erase valid history evidence.

Report investment-thesis Markdown list fields use text- and dict-list safe conversion before Markdown output, so malformed mirror-test, assumption, red-line, or data-gap list truthiness cannot interrupt decision-discipline Markdown rendering or erase valid thesis evidence.

Report investment-thesis Markdown display fields collapse embedded newlines before Markdown output, so prebuilt thesis headings, score labels, mirror lines, assumptions, red lines, data gaps, and next-review text cannot split decision-discipline headings or bullet rows.

Report investment-thesis recommendation and trade setup mappings use mapping-item safe conversion before payload and Markdown output, so malformed mapping truthiness cannot interrupt recommendation, target-price, confidence, or trade-plan extraction when valid fields exist.

Report investment-thesis structured scenario triggers use dict-list safe conversion before payload and Markdown output, so malformed trigger-list truthiness cannot interrupt Mode C crash-trigger or stop-condition extraction when valid scenario triggers exist.

Report investment-thesis data trust status uses text-safe comparison before payload and Markdown output, so malformed status hash or equality adapters cannot interrupt data-gap or red-line rendering when valid status text exists.

Report HTML sanitizer uses truthiness-safe string conversion before allowlist cleaning, so malformed model or report fragment truthiness cannot interrupt HTML sanitization when the fragment is still stringable.

Report plain-text sanitizer uses truthiness-safe string conversion before HTML output, so malformed report field truthiness cannot interrupt catalyst, summary, discipline, or overlay rendering when the value is still stringable.

Report next catalyst list fields use dict-list safe conversion before HTML output, so malformed catalyst iterators cannot interrupt event trigger rendering when valid rows exist.

Report structured-output child maps use mapping-safe conversion before next-catalyst extraction, so read-only agent payload wrappers cannot hide valid catalyst watchlist triggers.

Report structured-output schema-derived next catalysts accept mapping-safe root payloads before model validation, so read-only structured agent payloads can still derive catalyst watchlists from valid scenario triggers.

Report structured-output schema-derived next catalysts treat null catalyst lists as derivable before model validation, so valid scenario triggers can still produce catalyst watchlists when the model leaves `next_catalysts` empty by null.

Report structured-output schema-derived next catalysts treat non-list catalyst payloads as derivable before model validation, so malformed scalar `next_catalysts` values cannot block catalyst watchlist generation from valid scenario triggers.

Report structured-output schema-derived next catalysts treat non-mapping catalyst rows as derivable before model validation, so malformed catalyst-list contents cannot block catalyst watchlist generation from valid scenario triggers.

Report structured-output schema-derived next catalysts keep valid mapping catalyst rows before model validation, so malformed rows in a mixed `next_catalysts` list cannot discard otherwise valid catalyst watchlist items.

Report structured-output schema-derived next catalysts filter schema-invalid mapping catalyst rows before model validation, so one malformed catalyst mapping cannot discard later valid catalyst watchlist items.

Report structured-output catalyst text fields use safe text fallback before direct model validation, so malformed catalyst event, timeframe, impact, or trigger fields cannot drop otherwise valid catalyst rows.

Report recommendation legacy text uses event metadata fallback for single-character next catalysts, so plain-text catalyst rows show `待確認催化事件 / 待後續資料確認` instead of non-actionable one-character event names or timeframes.

Report structured-output scenario-trigger text fields use safe text fallback before direct model validation, so malformed trigger condition, action, or direction fields cannot drop otherwise valid scenario trigger rows.

Report structured-output normalizer payloads use mapping-safe conversion before schema validation and legacy report text rendering, so read-only structured agent payloads and nested recommendation maps cannot be dropped before final recommendation, confidence, catalyst, or trigger output.

Report structured-output normalizer scalar root payloads use schema fallback before final projection, so malformed scalar strict-schema payloads can keep conservative fallback structured sections instead of being rejected before validation.

Report structured-output runtime parsing rejects non-JSON structured responses before schema fallback, so quality gates retry malformed model output instead of accepting conservative `資料不足` report sections as successful structured output.

Report structured-output normalizer rejects incomplete supplied core sections before final projection, so partial moat, valuation, or recommendation JSON cannot be padded into report-contract output when companion core sections were omitted.

Report structured-output normalizer reasoning steps use safe text conversion before schema validation, so malformed reasoning-step values cannot drop otherwise valid recommendation payloads before final report rendering.

Report structured-output normalizer reasoning steps use minimum fallback before schema validation, so malformed reasoning-step values cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer reasoning-step empty lists use minimum fallback before schema validation, so empty reasoning-step collections cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer reasoning-step null values use minimum fallback before schema validation, so null reasoning-step collections cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer reasoning-step scalar objects use minimum fallback before schema validation, so malformed scalar reasoning-step collections cannot drop otherwise valid structured payloads below the required reasoning-step count.

Report structured-output normalizer scenario trigger rows use dict-list and safe text conversion before schema validation, so malformed trigger rows cannot interrupt next-catalyst derivation or drop otherwise valid recommendation payloads before final report rendering.

Report structured-output normalizer scenario trigger non-mapping rows use sequence-safe fallback before schema validation, so malformed trigger rows cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger mapping fields use minimum fallback before schema validation, so malformed trigger condition or action fields cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger mapping fields enforce schema minimum lengths before validation, so too-short trigger condition or action fragments cannot drop otherwise valid trigger rows or recommendation payloads.

Report structured-output normalizer scenario trigger fallback rows use schema-safe placeholder text, so minimum-count repair cannot reinsert too-short trigger condition or action fragments.

Report structured-output normalizer scenario trigger empty lists use minimum fallback before schema validation, so empty trigger collections cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger null values use minimum fallback before schema validation, so null trigger collections cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger scalar collections use minimum fallback before schema validation, so non-list trigger collections cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output normalizer scenario trigger lists use schema-limit truncation before validation, so overlong but otherwise valid recommendation payloads keep the first five trigger rows instead of being dropped.

Report structured-output normalizer scenario trigger fallback rows are deferred until minimum-count repair, so placeholder trigger rows cannot displace valid trigger rows when schema-limit truncation applies.

Report structured-output schema-derived next catalysts use safe scenario-trigger text before model validation, so malformed trigger rows cannot interrupt automatic catalyst extraction when enough valid triggers exist.

Report structured-output schema-derived next catalysts enforce scenario-trigger minimum lengths before model validation, so too-short trigger rows cannot interrupt automatic catalyst extraction when enough valid triggers exist.

Report structured-output schema-derived scenario triggers use minimum fallback before model validation, so malformed trigger rows cannot drop otherwise valid recommendation payloads below the required trigger count.

Report structured-output schema-derived scenario trigger collections use list-safe fallback before model validation, so malformed scalar trigger collections cannot drop otherwise valid recommendation payloads or catalyst derivation.

Report structured-output scenario-trigger collections use missing-field fallback before model validation, so omitted trigger collections cannot drop otherwise valid recommendation payloads while existing catalyst watchlists remain intact.

Report structured-output missing scenario-trigger fallback drives schema-derived next catalysts before model validation, so payloads that omit both trigger and catalyst collections still keep a neutral catalyst watchlist.

Report structured-output schema-derived next catalysts truncate overlong scenario-trigger lists before model validation, so valid first-five trigger rows can still drive catalyst watchlists when the model emits extra trigger rows.

Report structured-output executive-thesis root payloads use mapping-safe fallback before model validation, so malformed scalar executive synthesis payloads cannot drop the report opening thesis section.

Report structured-output executive-thesis text fields use safe text fallback before model validation, so malformed executive thesis, bull/bear summary, or smoothed markdown fields cannot drop the report opening thesis section.

Report structured-output executive-thesis resolved-contradiction list items use safe text fallback before model validation, so malformed contradiction rows cannot drop otherwise valid executive synthesis payloads.

Report structured-output confidence-basis lists use safe text conversion before model validation, so malformed evidence, risk, or data-gap items cannot drop otherwise valid recommendation payloads when enough valid confidence rows remain.

Report structured-output confidence-basis required lists use minimum fallback before model validation, so malformed evidence or risk items cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output confidence-basis required list collections use list-safe fallback before model validation, so malformed scalar evidence or risk collections cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output confidence-basis root payloads use mapping-safe fallback before direct model validation, so malformed scalar confidence-basis payloads cannot drop the confidence-basis fallback.

Report structured-output confidence-basis objects use missing-field fallback before model validation, so omitted confidence-basis objects cannot drop otherwise valid recommendation payloads.

Report structured-output reasoning steps use safe text conversion before model validation, so malformed reasoning-step items cannot drop otherwise valid recommendation payloads when enough valid reasoning rows remain.

Report structured-output reasoning steps use minimum fallback before model validation, so malformed reasoning-step items cannot drop otherwise valid recommendation payloads below the required reasoning-step count.

Report structured-output reasoning step collections use list-safe fallback before model validation, so malformed scalar reasoning-step collections cannot drop otherwise valid recommendation payloads.

Report structured-output recommendation labels use canonical alias normalization before model validation, so strong-buy or strong-short phrasing cannot drop otherwise valid recommendation payloads while final labels remain in the canonical set.

Report structured-output recommendation labels use missing-field fallback before model validation, so omitted recommendation labels cannot drop otherwise valid investment recommendation payloads.

Report structured-output recommendation text fields use safe text fallback before model validation, so malformed target, potential, or confidence fields cannot drop otherwise valid investment recommendation payloads.

Report structured-output recommendation text fields use missing-field fallback before model validation, so omitted target, potential, or confidence fields cannot drop otherwise valid investment recommendation payloads.

Report structured-output analysis markdown uses safe text fallback before model validation, so malformed report body text cannot drop otherwise valid structured recommendation payloads.

Report structured-output analysis markdown fields use missing-field fallback before model validation, so omitted analysis markdown fields cannot drop otherwise valid structured report payloads.

Report structured-output recommendation root payloads use mapping-safe fallback before model validation, so malformed scalar investment recommendation payloads cannot drop the recommendation section.

Report structured-output recommendation objects use missing-field fallback before model validation, so omitted recommendation objects cannot drop otherwise valid investment recommendation payloads.

Report structured-output recommendation field root payloads use mapping-safe fallback before direct model validation, so malformed scalar recommendation field payloads cannot drop the recommendation field fallback.

Report structured-output bubble-sniper root payloads use mapping-safe fallback before model validation, so malformed scalar bubble-sniper payloads cannot drop the short-bias recommendation section.

Report structured-output bubble-sniper recommendation field root payloads use mapping-safe fallback before direct model validation, so malformed scalar bubble-sniper recommendation fields fall back to avoid instead of dropping the short-bias recommendation fields.

Report structured-output moat analysis markdown uses safe text fallback before model validation, so malformed moat report body text cannot drop otherwise valid moat score payloads.

Report structured-output moat root payloads use mapping-safe fallback before model validation, so malformed scalar moat payloads cannot drop the moat-score section.

Report structured-output moat reasoning steps use minimum fallback before model validation, so malformed moat reasoning-step items cannot drop otherwise valid moat score payloads below the required reasoning-step count.

Report structured-output moat reasoning-step collections use list-safe fallback before model validation, so malformed scalar moat reasoning-step collections cannot drop otherwise valid moat score payloads.

Report structured-output moat-score containers use mapping-safe fallback before model validation, so malformed scalar moat-score containers cannot drop otherwise valid moat reasoning or report body payloads.

Report structured-output moat-score containers use missing-field fallback before model validation, so omitted moat-score containers cannot drop otherwise valid moat reasoning or report body payloads.

Report structured-output moat-score values use safe number fallback before model validation, so malformed moat score values cannot drop otherwise valid moat payloads.

Report structured-output price-target analysis markdown uses safe text fallback before model validation, so malformed valuation report body text cannot drop otherwise valid price-target payloads.

Report structured-output price-target root payloads use mapping-safe fallback before model validation, so malformed scalar price-target payloads cannot drop the valuation section.

Report structured-output price-target containers use mapping-safe fallback before model validation, so malformed scalar price-target containers cannot drop otherwise valid valuation summary or report body payloads.

Report structured-output price-target containers use missing-field fallback before model validation, so omitted price-target objects cannot drop otherwise valid valuation summary or report body payloads.

Report structured-output price-target direct target containers use mapping-safe fallback before direct model validation, so malformed scalar target containers cannot drop the valuation target fallback.

Report structured-output price-target text fields use safe text fallback before model validation, so malformed valuation reasoning, primary method, or double-counting check fields cannot drop otherwise valid price-target payloads.

Report structured-output price-target valuation-summary containers use mapping-safe fallback before model validation, so malformed scalar valuation summaries cannot drop otherwise valid price-target payloads.

Report structured-output price-target valuation-summary containers use missing-field fallback before model validation, so omitted valuation-summary objects cannot drop otherwise valid target-price payloads.

Report structured-output price-target direct valuation-summary containers use mapping-safe fallback before direct model validation, so malformed scalar valuation-summary containers cannot drop the valuation-summary fallback.

Report structured-output price-target valuation-summary boolean fields use bool-safe fallback before model validation, so malformed WACC or normalized-FCF flags cannot drop otherwise valid price-target payloads.

Report structured-output price-target values use safe number fallback before model validation, so malformed bear, base, or bull target values cannot drop otherwise valid price-target payloads.

Report structured-output price-target DCF scenario values use safe number fallback before model validation, so malformed scenario growth, margin, WACC, or intrinsic-value fields cannot drop otherwise valid price-target payloads.

Report structured-output price-target DCF scenario rows use row-safe filtering before model validation, so malformed DCF scenario rows cannot drop otherwise valid price-target payloads or valid DCF scenario rows.

Report structured-output price-target DCF scenario names use enum-safe filtering before model validation, so invalid DCF scenario names cannot drop otherwise valid price-target payloads or valid DCF scenario rows.

Report structured-output price-target direct DCF scenario names use enum-safe fallback before direct model validation, so invalid scalar DCF scenario names cannot drop the direct DCF scenario fallback.

Report structured-output price-target DCF scenario collections use list-safe fallback before model validation, so malformed scalar DCF scenario collections cannot drop otherwise valid price-target payloads.

Report structured-output price-target direct DCF scenario root payloads use mapping-safe fallback before direct model validation, so malformed scalar DCF scenario payloads cannot drop the direct DCF scenario fallback.

Report structured-output management-sentiment analysis markdown uses safe text fallback before model validation, so malformed management report body text cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment root payloads use mapping-safe fallback before model validation, so malformed scalar management sentiment payloads cannot drop the management sentiment section.

Report structured-output management-sentiment text fields use safe text fallback before model validation, so malformed guidance tone, highlight keyword, or highlight quote fields cannot drop otherwise valid management sentiment payloads.

Report structured-output management-highlight root payloads use mapping-safe fallback before direct model validation, so malformed scalar management highlight rows cannot drop otherwise valid highlight content.

Report structured-output management-sentiment highlight rows use row-safe fallback before model validation, so malformed highlight rows cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment highlight collections use list-safe fallback before model validation, so malformed scalar highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment highlight collections use missing-field fallback before model validation, so omitted highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output management-sentiment short highlight collections use minimum-count fallback before model validation, so undersized highlight lists preserve valid rows and pad missing rows instead of dropping otherwise valid management sentiment payloads.

Report structured-output management-sentiment confidence uses safe number fallback before model validation, so malformed confidence values cannot drop otherwise valid management sentiment payloads.

Report structured-output downside-risk analysis markdown uses safe text fallback before model validation, so malformed downside-risk report body text cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk root payloads use mapping-safe fallback before model validation, so malformed scalar downside-risk payloads cannot drop the downside-risk section.

Report structured-output downside-risk root rows use mapping-safe fallback before direct model validation, so malformed scalar downside-risk rows cannot drop otherwise valid downside-risk content.

Report structured-output downside-risk text fields use safe text fallback before model validation, so malformed thesis summary, risk title, evidence, impact, or severity fields cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk rows use row-safe fallback before model validation, so malformed risk rows cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk collections use list-safe fallback before model validation, so malformed scalar downside-risk collections cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk collections use missing-field fallback before model validation, so omitted downside-risk collections cannot drop otherwise valid downside-risk payloads.

Report structured-output downside-risk short collections use minimum-count fallback before model validation, so undersized downside-risk lists preserve valid rows and pad missing rows instead of dropping otherwise valid downside-risk payloads.

Report structured-output downside-risk confidence uses safe number fallback before model validation, so malformed risk confidence values cannot drop otherwise valid downside-risk payloads.

Report structured-output trade-plan text fields use safe text fallback before model validation, so malformed trade direction, entry, target, stop-loss, catalyst, or risk-level fields cannot drop otherwise valid 1-2 week trade setup payloads.

Report structured-output trade-plan root payloads use mapping-safe fallback before model validation, so malformed scalar trade-plan payloads cannot drop the 1-2 week trade setup section.

Report structured-output trade-plan direct schema preserves enum and required-field strictness, so invalid string trade directions or missing trade-plan fields still fail direct model validation while malformed non-string values can use safe fallbacks.

Report structured-output normalizer confidence-basis lists use safe text conversion before schema validation, so malformed evidence, risk, or data-gap items cannot drop otherwise valid recommendation payloads before final report rendering.

Report structured-output normalizer confidence-basis required lists use minimum fallback before schema validation, so malformed evidence or risk items cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output normalizer confidence-basis required list collections use list-safe fallback before schema validation, so missing, null, or scalar evidence or risk collections cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output normalizer confidence-basis empty required lists use minimum fallback before schema validation, so empty evidence or risk collections cannot drop otherwise valid recommendation payloads below required confidence-basis counts.

Report structured-output normalizer recommendation text fields use safe text conversion before schema validation, so malformed target, potential, or confidence fields cannot drop otherwise valid investment recommendation payloads.

Report structured-output normalizer bubble-sniper recommendation labels use avoid fallback before schema validation, so malformed Agent 19 labels keep the short-bias `避免` default instead of being normalized to generic hold.

Report structured-output normalizer next-catalyst text fields use safe text conversion before schema validation, so malformed catalyst event, timeframe, impact, or trigger fields cannot drop otherwise valid recommendation payloads.

Report structured-output normalizer next-catalyst trigger fields enforce schema minimum length before validation, so too-short trigger fragments cannot drop otherwise valid catalyst rows or recommendation payloads.

Report structured-output normalizer next-catalyst fallback rows use schema-safe trigger text, so minimum-count repair cannot reinsert too-short catalyst trigger fragments.

Report structured-output normalizer next-catalyst rows use sequence-safe fallback before schema validation, so malformed catalyst rows cannot drop otherwise valid recommendation payloads below the required catalyst count.

Report structured-output normalizer next-catalyst empty lists derive from scenario triggers before schema validation, so empty catalyst watchlists cannot drop otherwise valid recommendation payloads below the required catalyst count.

Report structured-output normalizer empty next-catalyst lists derive from missing scenario-trigger fallback before schema validation, so payloads with omitted trigger collections and empty catalyst watchlists still keep neutral catalyst rows.

Report structured-output normalizer next-catalyst fallback rows are deferred until minimum-count repair, so placeholder catalyst rows cannot appear before valid catalysts.

Report structured-output normalizer price-target numbers exclude boolean values after schema validation, so malformed target flags cannot become `NT$1` or `NT$0` valuation rows in legacy report text.

Report structured-output normalizer price-target values use safe number fallback before schema validation, so malformed target values cannot drop otherwise valid bear/base/bull valuation payloads before final target filtering.

Report structured-output normalizer price-target missing objects use validated fallback targets after schema validation, so payloads with valuation context but no valid raw bear/base/bull targets keep a `0.0` fallback valuation section instead of dropping the whole price-target output.

Report structured-output normalizer moat-score numbers exclude boolean values after schema validation, so malformed moat flags cannot become `1.0` or `0.0` score rows in legacy moat reports.

Report structured-output normalizer moat-score fields use safe number fallback before schema validation, so malformed moat score values cannot drop otherwise valid moat payloads before final score filtering.

Report structured-output normalizer moat-score missing objects use validated fallback scores after schema validation, so payloads with moat reasoning but no valid raw moat scores keep a conservative `1.0` fallback moat-score section instead of dropping the whole moat output.

Report structured-output normalizer moat analysis markdown uses safe text conversion before schema validation, so malformed moat body text cannot drop otherwise valid moat score payloads.

Report moat legacy text surfaces reasoning steps from structured outputs, so Agent 3 and Agent 12 plain-text report sections keep the moat scoring rationale before the analysis body.

Report legacy reasoning-step text skips single-character fragments, so moat and recommendation plain-text sections do not present non-actionable one-character model scraps as reasoning bullets.

Report structured-output normalizer management-confidence numbers exclude boolean values after schema validation, so malformed confidence flags cannot become `1.0` max-confidence management sentiment payloads.

Report structured-output normalizer management-confidence numbers use safe fallback before schema validation, so malformed confidence values cannot drop otherwise valid management sentiment payloads.

Report management-sentiment legacy text surfaces confidence from structured outputs, so Agent 20 plain-text report sections keep the certainty score beside management guidance tone.

Report management-sentiment legacy text uses quote fallback for empty highlights, so Agent 20 plain-text highlight rows show `資料不足` instead of leaving a blank quote after malformed highlight text.

Report management-sentiment legacy text uses highlight fallback for single-character fragments, so Agent 20 plain-text highlight rows show `亮點 / 資料不足` instead of presenting non-actionable one-character keyword or quote scraps.

Report management-sentiment legacy text uses fallback row for empty highlights, so Agent 20 plain-text report sections show `亮點 / 資料不足` instead of leaving management guidance without any highlight row when no highlights are displayable.

Report management-sentiment legacy text uses guidance-tone fallback for invalid metadata, so Agent 20 plain-text sections show schema-aligned `資料不足` instead of arbitrary guidance-tone labels outside `樂觀`, `中立`, or `保守`.

Report management-sentiment legacy text uses analysis body fallback for single-character fragments, so Agent 20 plain-text sections end with `資料不足` instead of non-actionable one-character analysis body scraps.

Report structured-output normalizer management-sentiment text fields use safe text conversion before schema validation, so malformed guidance tone, highlight keyword, or highlight quote fields cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment highlight rows use sequence-safe fallback before schema validation, so malformed highlight rows cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment highlight collections use missing-field fallback before schema validation, so omitted highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment empty highlight lists use minimum fallback before schema validation, so empty highlight collections cannot drop otherwise valid management sentiment payloads.

Report structured-output normalizer management-sentiment highlight fallback rows are deferred until fixed-count repair, so placeholder highlight rows cannot displace valid management highlights.

Report structured-output normalizer downside-risk confidence numbers exclude boolean values after schema validation, so malformed risk-confidence flags cannot become `1.0` max-confidence downside risk payloads.

Report structured-output normalizer downside-risk confidence preserves explicit zero values after schema validation, so valid low-confidence risk signals cannot be silently promoted to the default confidence.

Report structured-output normalizer downside-risk confidence numbers use safe fallback before schema validation, so malformed risk-confidence values cannot drop otherwise valid downside risk payloads.

Report structured-output normalizer downside-risk text fields use safe text conversion before schema validation, so malformed risk title, evidence, impact, or severity fields cannot drop otherwise valid downside risk payloads.

Report structured-output normalizer downside-risk rows use sequence-safe fallback before schema validation, so malformed risk rows cannot drop otherwise valid downside risk payloads below the required row count.

Report structured-output normalizer downside-risk collections use missing-field fallback before schema validation, so omitted downside-risk collections cannot drop otherwise valid downside-risk payloads.

Report structured-output normalizer downside-risk empty lists use minimum fallback before schema validation, so empty downside-risk collections cannot drop otherwise valid downside-risk payloads below the required row count.

Report structured-output normalizer downside-risk fallback rows are deferred until minimum-count repair, so placeholder risk rows cannot displace valid downside risks or misalign confidence values.

Report structured-output legacy price-target rendering uses exception-safe number conversion, so malformed target number objects render as `N/A` while other valid valuation scenarios remain visible.

Report structured-output legacy price-target rendering excludes non-finite numbers, so NaN or Infinity target values render as `N/A` instead of `NT$nan` or `NT$inf` in legacy valuation text.

Report structured-output legacy price-target rendering preserves single scientific-notation numeric strings, so `1e3` renders as `NT$1,000` instead of being stripped into a synthetic `NT$13` target.

Report valuation legacy text uses fallback row for empty price targets, so Agent 4/14 plain-text valuation sections show `目標價: N/A` instead of leaving an empty target-price block when no target scenarios are displayable.

Report structured-output normalizer price-target scenario keys use safe text conversion, so malformed extra target keys cannot interrupt valuation normalization or erase valid bear/base/bull targets.

Report structured-output normalizer price-target reasoning fields use safe text conversion before schema validation, so malformed DCF, peer, or scenario reasoning fields cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer valuation-summary text fields use safe text conversion before schema validation, so malformed valuation method or double-counting check text cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer valuation-summary boolean fields use bool-safe conversion before schema validation, so malformed WACC or normalized-FCF flags cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer DCF scenario rows use safe finite-number conversion before schema validation, so malformed DCF scenario rows cannot drop otherwise valid bear/base/bull valuation payloads.

Report structured-output normalizer DCF scenario numeric fields use safe number fallback before schema validation, so DCF rows with valid scenario names keep conservative numeric defaults instead of losing the row.

Report structured-output normalizer trade-plan text fields use safe text conversion before schema validation, so malformed entry, target, stop-loss, or catalyst fields cannot drop otherwise valid 1-2 week trade setup payloads.

Report structured-output normalizer trade-plan enum fields use literal fallback before schema validation, so invalid trade direction or risk level values cannot drop otherwise valid 1-2 week trade setup payloads.

Report structured-output normalizer trade-plan analysis markdown uses safe text projection after schema validation, so Agent 24 normalized payloads keep trade setup body context for legacy report text rendering when callers provide it.

Report Agent 19 required structured sections use dict-list safe scenario triggers before legacy report text rendering, so read-only trigger rows still populate crash-catalyst and stop-loss sections instead of placeholder warnings.

Report Agent 19 required structured trigger rows collapse embedded newlines before legacy report text rendering, so crash-catalyst and stop-loss condition/action text cannot split required-section bullets.

Report Agent 19 required structured trigger rows use action fallback before legacy report text rendering, so crash-catalyst and stop-loss bullets keep an actionable response when malformed or missing action text would otherwise leave only a trigger condition.

Report Agent 19 required structured trigger rows guard single-character fragments before legacy report text rendering, so crash-catalyst and stop-loss bullets skip non-actionable one-character trigger conditions and use actionable fallback text for one-character actions.

Report recommendation block skips mapping-safe nested confidence-basis maps before legacy report text rendering, so read-only confidence-basis payloads do not leak Python mapping representations into final investment recommendation blocks.

Report recommendation block display keys use shared text conversion before legacy report text rendering, so malformed recommendation field names are skipped instead of leaking Python literal text into final investment recommendation blocks.

Report recommendation block skips single-character display keys before legacy report text rendering, so Agent 7/16 plain-text recommendation rows do not present non-actionable one-character field names while preserving compact valid values.

Report recommendation block uses fallback row for empty standard recommendations, so Agent 7/16 plain-text recommendation sections show `建議: N/A` instead of leaving an empty `[投資建議]` block when no recommendation rows are displayable.

Report Agent 19 recommendation ordered values use shared text conversion before legacy report text rendering, so malformed binary or memory-view target fields fall back to `N/A` instead of leaking Python literal text into final investment recommendation blocks.

Report Agent 19 recommendation ordered values guard single-character fragments before legacy report text rendering, so ordered target and recommendation rows fall back to `N/A` for non-numeric one-character scraps while preserving compact numeric confidence values.

Report recommendation block Markdown display rows collapse embedded newlines before legacy report text rendering, so recommendation labels and values cannot split investment recommendation rows.

Report recommendation tail basis and trigger fields use shared text conversion before legacy report text rendering, so malformed confidence-basis items or trigger actions are skipped or blanked instead of leaking Python literal text into final recommendation tail sections.

Report recommendation tail confidence-basis bullets skip single-character fragments in legacy reports, so Agent 7/16/19 confidence-basis sections do not present non-actionable one-character evidence, risk, or data-gap scraps.

Report recommendation legacy analysis bodies use fallback for single-character fragments, so Agent 7/16/19 plain-text recommendation report bodies show `資料不足` instead of non-actionable one-character analysis scraps.

Report recommendation tail trigger actions use fallback text in legacy reports, so Agent 7/16/19 scenario trigger rows keep an actionable `重新檢查投資結論` recommendation when safe conversion drops malformed action values.

Report recommendation tail trigger conditions skip single-character fragments in legacy reports, so Agent 7/16/19 scenario trigger rows do not present non-actionable one-character model scraps while still preserving short readable Chinese trigger conditions.

Report recommendation tail trigger actions use fallback for single-character fragments in legacy reports, so Agent 7/16/19 scenario trigger rows keep `重新檢查投資結論` instead of presenting non-actionable one-character action scraps.

Report recommendation tail omits empty basis and trigger sections in legacy text, so Agent 7/16/19 plain-text reports do not leave orphan `信心依據` or `情境觸發器` headings when safe conversion drops malformed rows.

Report recommendation tail Markdown fields collapse embedded newlines before legacy report text rendering, so confidence-basis items and scenario trigger condition/action text cannot split final recommendation tail bullets.

Report legacy score and valuation fields use shared display conversion before legacy report text rendering, so malformed moat scores, price targets, or valuation summaries fall back to `N/A` instead of interrupting or leaking Python literal text into structured report bodies.

Report moat score legacy text uses semantic key fallback, so Agent 3/12 score rows show `護城河指標` instead of `N/A` when malformed moat-score keys cannot be displayed safely.

Report moat score legacy text uses key fallback for single-character fragments, so Agent 3/12 score rows show `護城河指標` instead of non-actionable one-character moat-score labels while preserving compact numeric score values.

Report moat score legacy text uses value fallback for single-character fragments, so Agent 3/12 score rows show `N/A` instead of non-actionable one-character moat-score values while preserving compact numeric score values.

Report moat score legacy text uses fallback row for empty scores, so Agent 3/12 plain-text score sections show `護城河指標: N/A` instead of leaving an empty moat-score block when no score rows are displayable.

Report valuation summary legacy text uses semantic key fallback, so Agent 4/14 structured valuation checks show `估值檢查項目` instead of `N/A` when malformed summary keys cannot be displayed safely.

Report valuation summary legacy text uses fallback for single-character fragments, so Agent 4/14 structured valuation checks show `估值檢查項目 / N/A` instead of non-actionable one-character summary labels or values.

Report legacy score and valuation Markdown key-value fields collapse embedded newlines before legacy report text rendering, so moat-score and valuation-summary labels or values cannot split score rows or valuation bullets.

Report legacy analysis markdown body uses shared text conversion before escaped-newline normalization, so malformed analysis bodies fall back to safe fallback text instead of leaking Python literal text into structured report bodies.

Report structured-output normalization analysis bodies use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into normalized structured report payloads.

Report structured-output schema analysis bodies use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into structured report analysis bodies.

Report structured-output schema executive thesis fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into executive thesis summaries, resolved contradictions, or smoothed markdown.

Report structured-output normalization display fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into downside thesis summaries, recommendation target rows, or short-term trade-plan fields.

Report structured-output schema display fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into management highlights, downside-risk rows, downside thesis summaries, or short-term trade-plan fields.

Report structured-output schema valuation and recommendation text fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into valuation reasoning, double-counting checks, target rows, or confidence text fields.

Report structured-output schema DCF scenario names use string-only enum fallback before legacy report text rendering, so direct model validation cannot route non-string objects with custom `__str__` methods into bear, base, or bull DCF scenario rows.

Report structured-output schema boolean fields use string-only coercion before legacy report text rendering, so direct model validation cannot let non-string objects with custom `__str__` methods choose valuation boolean flags.

Report structured-output normalization boolean fields use string-only coercion before legacy report text rendering, so normalized payloads cannot let numeric literals choose valuation boolean flags.

Report structured-output schema numeric fields use primitive-only coercion before legacy report text rendering, so direct model validation cannot let non-string objects with custom `__float__` or `__str__` methods choose valuation target or DCF scenario numbers.

Report structured-output normalization numeric fields use primitive-only coercion before legacy report text rendering, so normalized payloads cannot let non-string objects with custom `__float__` methods choose valuation target, DCF scenario, confidence, or score numbers.

Report structured-output schema recommendation keys and labels use string-only routing before legacy report text rendering, so direct model validation cannot let non-string objects with custom `__str__` methods choose recommendation labels or target-row aliases.

Report structured-output normalization recommendation keys and labels use string-only routing before legacy report text rendering, so normalized Agent 7/16/19 payloads cannot let non-string objects with custom `__str__` methods choose recommendation labels or target-row aliases.

Report structured-output schema alias lookups use string-only mapping keys before legacy report text rendering, so direct model validation cannot let non-string keys with custom equality choose valuation reasoning, target aliases, or moat-score aliases.

Report structured-output schema field lookups use string-only mapping keys before legacy report text rendering, so direct model validation cannot let non-string keys with custom equality choose valuation summary methods, boolean flags, double-counting checks, DCF scenario names, DCF scenario numbers, or recommendation trigger/catalyst fields.

Report structured-output normalization alias lookups use string-only mapping keys before legacy report text rendering, so normalized payloads cannot let non-string keys with custom equality choose valuation target aliases.

Report recommendation block legacy text uses primitive-only display fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into standard recommendation rows or Agent 19 ordered recommendation fields.

Report recommendation tail legacy next-catalyst text uses primitive-only display fallback before legacy report text rendering, so direct legacy rendering cannot persist Python-derived literals into next-catalyst event names, timeframes, directions, or trigger conditions.

Report recommendation legacy reasoning steps use primitive-only display fallback before legacy report text rendering, so direct legacy rendering cannot persist Python-derived literals into investment reasoning-step bullets.

Report recommendation legacy confidence basis uses primitive-only display fallback before legacy report text rendering, so direct legacy rendering cannot persist Python-derived literals into evidence, risk, or data-gap bullets.

Report Agent 19 required-section trigger directions use primitive-only enum checks before legacy report text rendering, so non-string objects with custom `__str__` methods cannot route crash or stop-loss trigger rows into required sections.

Report structured-output normalization nested display rows use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into management highlight rows or downside-risk rows.

Report structured-output normalization valuation display fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into valuation reasoning or structured valuation-check rows.

Report structured-output normalization recommendation tail fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into scenario trigger rows or next-catalyst rows.

Report structured-output schema recommendation tail fields use string-only fallback before legacy report text rendering, so direct model validation cannot persist Python-derived literals into scenario trigger rows or next-catalyst rows.

Report structured-output normalization reasoning steps use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into moat or recommendation reasoning chains.

Report structured-output normalization confidence basis fields use string-only fallback before legacy report text rendering, so non-string objects with custom `__str__` methods cannot persist Python-derived literals into evidence, risk, or data-gap lists.

Report legacy score and valuation analysis bodies use fallback for single-character fragments, so Agent 3/12/4/14 plain-text report bodies show `資料不足` instead of non-actionable one-character analysis scraps.

Report legacy structured display fields use shared text conversion before legacy report text rendering, so malformed management tone, highlight, downside-risk, or short-term trade-plan values fall back to defaults instead of leaking Python literal text into final report bodies.

Report short-term trade-plan legacy text preserves analysis body fallback, so Agent 24 plain-text sections keep the trade setup context after the 1-2 week plan when callers provide fallback or analysis body text.

Report short-term trade-plan legacy text uses enum fallback for invalid metadata, so Agent 24 plain-text sections show schema-aligned `Neutral` / `High` instead of arbitrary trade-direction or risk-level labels outside the structured trade-plan enums.

Report short-term trade-plan legacy text uses field fallback for single-character fragments, so Agent 24 plain-text sections show `N/A` instead of non-actionable one-character entry, target, stop-loss, or catalyst scraps.

Report short-term trade-plan legacy text uses analysis body fallback for single-character fragments, so Agent 24 plain-text sections end with `資料不足` instead of non-actionable one-character trade setup body scraps.

Report legacy structured Markdown display fields collapse embedded newlines before legacy report text rendering, so management tone, highlights, downside risks, and short-term trade-plan values cannot split headings or bullet rows.

Report analysis overlay display fields use shared text conversion before HTML output, so malformed management guidance tone, highlight, downside-risk, peer name, or peer ticker values cannot leak boolean, binary, or memory-view text into management sentiment, downside risk, or peer-comparison sections.

Report analysis overlay display fields collapse embedded newlines before HTML output, so management guidance tone, highlights, downside risks, and peer comparison labels remain single-line overlay fields.

Report analysis overlay list fields use dict-list safe conversion before HTML output, so malformed highlight or downside-risk iterators cannot interrupt management sentiment or downside-risk sections when valid rows exist.

Report analysis overlay structured-output maps use mapping-safe conversion before HTML output, so malformed structured-output accessors cannot interrupt management sentiment or downside-risk sections when valid agent payloads exist.

Report analysis overlay data child maps use mapping-safe conversion before HTML output, so malformed DCF scenario or dynamic peer metric accessors cannot interrupt scenario and peer-comparison overlays when valid data exists.

Report analysis overlay financial history sequences use sequence-safe conversion before peer-comparison target rows, so tuple asset-history payloads preserve target-company asset turnover evidence.

Report key evidence source audit child maps use mapping-safe conversion before HTML and Markdown output, so malformed source audit row accessors cannot interrupt key data evidence tables when valid provider evidence exists.

Report source audit table child maps use mapping-safe conversion before HTML and Markdown output, so malformed source audit row accessors cannot interrupt the source audit table when valid audit rows exist.

Report TWSE official availability banner source audit rows use dict-list safe conversion before HTML output, so tuple or read-only official-source audit rows cannot trigger false TWSE/MOPS unavailable warnings.

Report data trust quant metrics child maps use mapping-safe conversion before HTML and Markdown output, so malformed quant metric accessors cannot interrupt data trust cards when valid fallback warning fields exist.

Report data trust Markdown summary bullets collapse embedded newlines before report output, so market data time, reason labels, notes, and quant warning text cannot split data-confidence bullets.

Report bundle data trust property accepts mapping-safe snapshot maps before persistence or follow-up processing, so immutable data snapshots cannot hide valid report confidence metadata.

Report trust controls data and context maps use mapping-safe conversion before HTML and Markdown output, so malformed data_trust or context data accessors cannot interrupt confidence guardrails or erase valid reproducibility metadata.

Report trust controls generated-at fields use safe text conversion before reproducibility metadata output, so malformed generated time truthiness cannot interrupt confidence guardrails or hide valid provider and model traceability.

Report trust controls Markdown reproducibility fields collapse embedded newlines before report output, so model ids, prompt versions, code status, providers, and source data times cannot split the reproducibility bullet.

Report price target card and chart payload values use JSON-safe numeric conversion before HTML output, so malformed boolean, binary, memory-view, or non-finite target values cannot interrupt report rendering, leak Python literal text, or render boolean values as NT$1 targets.

Report chart payload series fields use JSON-safe text and finite-number conversion before HTML output, so malformed year labels, money series, margin series, price history, moat scores, or P/E river bands cannot interrupt report rendering or leak Python literal text into chart scripts.

Report moat score normalization excludes boolean values before HTML and Markdown output, so malformed flags cannot render as `True`, `False`, or synthetic 1/0 moat scores in visible report sections or chart payloads.

Report price history chart payload accepts mapping-safe chart wrappers before HTML chart JSON output, so immutable price history payloads preserve dates and prices instead of rendering an empty price chart.

Report price history chart series fields use sequence-safe truthiness fallback before HTML chart JSON output, so malformed date or price series truthiness cannot interrupt chart rendering when valid price history rows exist.

Report price history chart date fields use safe text conversion before future-date filtering, so one unstringable date cannot interrupt chart rendering or hide later valid price history rows.

Report price history chart mapping keys use future-date filtering before HTML chart JSON output, so legacy date-to-price payloads cannot leak future close prices into chart scripts.

Report PE river chart payload uses truthiness-safe mapping handoff before HTML chart JSON output, so malformed pe_river_chart truthiness cannot interrupt chart rendering when valid PE river rows exist.

Report PE river chart payload accepts mapping-safe chart wrappers before HTML chart JSON output, so immutable PE river payloads preserve years, bands, and EPS rows instead of rendering an empty river chart.

Report current price chart literals use finite-number conversion before HTML output, so malformed boolean, binary, memory-view, or non-finite current prices cannot render invalid JavaScript literals or distort target-price upside percentages.

Report recommendation banner target and confidence fields use shared text conversion before HTML output, so malformed boolean, binary, or memory-view recommendation values cannot leak Python literal text into verdict banners or final verdict blocks.

Report executive synthesis text fields use shared text conversion before HTML output, so malformed boolean, binary, or memory-view executive thesis or editor-synthesis values cannot leak Python literal text into high-visibility report opening sections.

Report cover metadata uses mapping-safe conversion before HTML output, so malformed report-cover payloads cannot interrupt report rendering or leak Python literal text into cover image styles.

Report cover image URL sanitizer uses truthiness-safe string conversion before HTML output, so malformed report-cover image truthiness cannot interrupt cover metadata handling while URL protocol allowlisting still blocks unsafe image sources.

Report parsed payload and child maps use mapping-safe conversion before HTML output, so malformed parsed, recommendation, price-target, moat-score, or trade-setup payloads cannot interrupt report rendering or leak Python literal text into summary, chart, or verdict sections.

Report data payload and child maps use mapping-safe conversion before HTML output, so malformed data, institutional-trading, or P/E river payloads cannot interrupt report rendering or leak Python literal text into summary, metrics, or chart sections.

Report Markdown renderer data and parsed payload maps use mapping-safe conversion before Markdown output, so malformed data, parsed, recommendation, price-target, or trade-setup payloads cannot interrupt Markdown report rendering or leak Python literal text into summary, metrics, or verdict sections.

Report Markdown renderer reference source table cells escape table separators before Markdown output, so dynamic model-route summary values containing `|` or newlines cannot corrupt the reference source table structure.

Report Markdown renderer single-line fields collapse embedded newlines before Markdown output, so ticker, company, fetch date, metric, target-price, tear-sheet, and investment-thesis display values cannot split headings, summary sentences, or bullet rows.

Report agent output maps use mapping-safe conversion before HTML and Markdown section rendering, so malformed analyses or structured-output payloads cannot interrupt report body rendering or leak Python literal text into agent sections.

Report agent output child maps use mapping-safe conversion before structured tail rendering, so read-only structured recommendation payloads cannot be skipped in HTML or Markdown final sections.

Report agent output maps preserve string-key agent ids before HTML and Markdown section rendering, so JSON-loaded analyses and structured-output maps do not silently fall back to `分析進行中` when valid agent reports exist.

Report agent sequence ids normalize string values before HTML and Markdown section rendering, so JSON-loaded agent sequences keep localized section titles, model labels, and structured tail placement.

Report agent sequence payloads fall back to pipeline defaults when malformed scalar values are loaded, so HTML/Markdown sections and execution traces do not render byte-derived fake agents such as `Agent 98`.

Report tear-sheet target price display avoids duplicate currency prefixes before HTML and Markdown output, so formatted values like `NT$120` are not rendered as `NT$NT$120` in the one-page summary.

Report audit banner final-audit child maps use mapping-safe conversion before HTML and Markdown output, so malformed final audit accessors cannot interrupt top-of-report abnormality notices when valid abnormality evidence exists.

Report audit banner abnormality list fields use list-safe conversion before HTML and Markdown output, so malformed scalar final audit, blocking issue, repair log, correction, or warning values cannot render byte-derived fake abnormality notices.

Report audit banner abnormality list fields use truthiness-safe conversion before HTML and Markdown output, so malformed final audit, blocking issue, repair log, correction, or warning list wrappers cannot interrupt top-of-report abnormality notices when valid issue text exists.

Report audit banner abnormality text fields use shared text conversion before HTML and Markdown output, so malformed final audit, blocking issue, repair log, correction, or warning values cannot leak boolean, binary, or memory-view text into top-of-report abnormality notices.

Report audit banner Markdown abnormality bullets collapse embedded newlines before Markdown output, so final audit, blocking issue, repair log, correction, and warning text cannot split top-of-report abnormality bullets.

Report reading notice quality gate text fields use shared text conversion before HTML and Markdown output, so malformed data trust, evidence gate, content credibility, or conformance values cannot leak boolean, binary, or memory-view text into usage-limit copy.

Report reading notice Markdown gate text collapses embedded newlines before Markdown output, so quality gate values and snapshot integrity details cannot split usage-limit checklist rows or warning blockquotes.

Report reading notice quality gate record detection accepts mapping-safe gate payloads before HTML and Markdown output, so immutable evidence, content credibility, or conformance wrappers cannot downgrade fully recorded passed gates to pending.

Report reading notice snapshot integrity checks treat `valid=false` as blocked before HTML and Markdown output, so contradictory snapshot metadata cannot mark a hash mismatch as ready to quote.

Report reading notice snapshot integrity checks let invalid `data.snapshot_integrity` override a conflicting verified top-level record before HTML and Markdown output, so nested snapshot blockers cannot be hidden by optimistic metadata.

Report reading notice snapshot integrity checks preserve the most specific invalid snapshot integrity detail across top-level and `data.snapshot_integrity` before HTML and Markdown output, so generic top-level blockers cannot hide nested provider or hash mismatch evidence.

Report reading notice snapshot integrity checks accept mapping-safe snapshot integrity payloads before HTML and Markdown output, so immutable integrity wrappers cannot hide invalid snapshot blockers.

Report reading notice snapshot integrity checks downgrade recorded non-verified snapshots to warning before HTML and Markdown output, so unverified legacy or hashless snapshots do not render as passed.

Report reading notice snapshot integrity details deduplicate repeated error entries before HTML and Markdown output, so live/generated report usage notices show each provider or hash detail once while preserving first-seen order.

Report reading notice snapshot integrity details derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so live/generated report usage notices keep hash evidence visible.

Report reading notice snapshot integrity details prefer hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report reading notice snapshot integrity details remove default generic blocker text when the same error list contains specific provider or hash details, so live/generated report usage notices stay focused on the actionable failure reason.

Report view and HTML download paths re-check the current `.data.json` snapshot integrity before returning stored report HTML, so a stale static passed notice is replaced with a blocked notice when the snapshot hash no longer matches.

Report Markdown download paths re-check the current `.data.json` snapshot integrity before returning stored Markdown, so a stale static passed notice is replaced with a blocked Markdown notice when the snapshot hash no longer matches.

Report artifact view and download paths treat malformed or non-object `.data.json` snapshots as blocked before returning stored HTML or Markdown, so corrupted snapshot files cannot leave stale passed notices in reusable report artifacts.

Report artifact view and download paths treat missing `.data.json` snapshots as warning before returning stored HTML or Markdown, so legacy reports without a snapshot cannot leave stale passed notices in reusable artifacts.

Report artifact view and download paths honor invalid `snapshot_integrity` recorded inside `.data.json` before returning stored HTML or Markdown, so hashless snapshots that already failed verification cannot leave stale passed notices in reusable artifacts.

Report artifact view and download paths also honor invalid `data.snapshot_integrity` recorded inside `.data.json`, so nested snapshot integrity metadata follows the same blocked-notice contract as top-level metadata.

Report artifact view and download paths let any recorded invalid snapshot integrity override a conflicting verified record before returning stored HTML or Markdown, so nested blockers cannot be hidden by a top-level green state.

Report artifact view and download paths preserve the most specific invalid snapshot integrity detail before returning stored HTML or Markdown, so a generic top-level blocker cannot hide a nested hash or provider-audit mismatch.

Report artifact view and download paths treat default generic snapshot integrity blocker text as less specific than nested hash or provider-audit mismatch details, so operators see the actionable failure reason first.

Report artifact view and download paths derive a `snapshot_hash mismatch` detail from recorded invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so hash evidence is still visible in stored HTML or Markdown.

Report artifact view and download paths prefer recorded hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report artifact view and download paths remove default generic snapshot integrity errors when the same recorded error list also contains specific details, so stored HTML and Markdown surface the actionable blocker without boilerplate noise.

Report artifact view and download paths deduplicate recorded snapshot integrity error details before repairing stored HTML or Markdown reading notices, so repeated provider or hash details are shown once while preserving first-seen order.

Report quality repair queue quality gate fields use dict-native field reads before action prioritization, so malformed report, content credibility, report conformance, evidence gate, data trust, or decision freshness accessors cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue report identity fields use string-safe conversion before provider-impact handoff and action prioritization, so malformed ticker, filename, or pipeline truthiness cannot interrupt manual-review prioritization or erase valid repair reasons.

Data trust reproducibility packet identity fields use shared text conversion before snapshot provenance projection, so malformed ticker, prompt version, pipeline id, code commit, generated time, model id, provider, or source time fields cannot leak boolean, binary, or memory-view text into report reproducibility metadata.

Report quality repair queue quality gate text fields use string-safe conversion before action prioritization, so malformed status, summary, or message truthiness cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue quality gate text fields treat lookup string conversion failures as blank before action prioritization, so `KeyError` or `IndexError` from malformed summary or message text cannot interrupt manual-review prioritization while later valid fallback text can still describe the repair reason.

Report quality repair queue reason codes use string-safe conversion before action prioritization, so malformed reason-code text cannot interrupt manual-review prioritization or erase valid repair reasons.

Report quality repair queue stale source lists use string-safe conversion before action prioritization, so malformed stale-source text cannot interrupt refresh-data prioritization or erase valid stale source evidence.

Report quality repair queue text list tuple sequences are evaluated before action prioritization, so immutable reason-code or stale-source batches do not lose repair evidence.

Report quality repair queue reports envelopes use mapping-safe conversion before action prioritization, so immutable report-list wrappers cannot hide stale, blocked, or invalid repair actions.

Report quality repair queue snapshot integrity maps use mapping-safe conversion before action prioritization, so immutable integrity payloads still block automatic reuse when a snapshot hash is invalid.

Report quality repair queue quality gate child maps use mapping-safe conversion before action prioritization, so immutable content credibility, conformance, evidence, data trust, or freshness payloads cannot hide manual-review repair actions.

Report quality repair queue quality gate child maps use Mapping traversal when `.items()` lookup fails before action prioritization, so malformed content credibility or conformance wrappers cannot hide manual-review repair actions if standard key traversal remains readable.

Report quality repair queue quality gate child maps skip lookup item failures during Mapping traversal before action prioritization, so one broken content credibility key cannot hide later valid blocked status or summary fields.

Report quality repair queue snapshot integrity verifier results treat `valid=false` as invalid before action prioritization, so raw verifier payloads still block automatic reuse when a snapshot hash is invalid.

Report quality repair queue snapshot integrity verifier results let `valid=false` override non-invalid status text before action prioritization, so contradictory metadata cannot hide a hash mismatch.

Report quality repair queue snapshot integrity error details use string-safe conversion before action prioritization, so scalar mismatch details still reach manual-review actions instead of falling back to generic repair text.

Report quality repair queue derives a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so manual-review actions keep hash evidence visible.

Report quality repair queue prefers hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.

Report quality repair queue removes default generic snapshot integrity error details when specific provider or hash details exist before action prioritization, so manual-review actions focus on the actionable blocker without boilerplate noise.

Report quality repair queue deduplicates repeated snapshot integrity error details before action prioritization, so manual-review actions show each provider or hash detail once while preserving first-seen order.

Shared mapping list conversions use native list and tuple iterators when iterator accessors fail before item traversal, so report repair and strategy evaluation do not erase valid sequence evidence.

Shared mapping text list conversions use native list and tuple iterators when custom iterators fail before yielding, so report repair reason-code or stale-source evidence is not erased by malformed iterator objects.

Shared mapping text list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed report repair reason-code or stale-source iterators cannot erase underlying list evidence.

Shared mapping dict list conversions use native list and tuple iterators when custom iterators fail before yielding, so report repair provider-alert evidence is not erased by malformed iterator objects.

Shared mapping dict list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed report repair provider-alert iterators cannot erase underlying alert evidence.

Shared mapping traversal falls back to native dict items when custom items iterators fail before yielding, so malformed mapping iterator objects cannot erase underlying snapshot, repair, or provider evidence.

Report quality repair queue provider alert lists preserve valid entries before iterator failures, so malformed provider alert iteration cannot interrupt provider-impact handoff or erase wait-provider-recovery repair evidence.

Report quality repair queue report collections preserve valid reports before iterator failures, so malformed report iteration cannot interrupt action prioritization or erase valid repair reasons.

Report quality repair queue decision freshness detail fields use string-safe conversion before action prioritization, so malformed rerun reason truthiness cannot interrupt rerun-analysis prioritization or erase valid freshness repair context.

Report quality repair queue decision freshness flags use bool-safe conversion before action prioritization, so malformed rerun flag truthiness cannot interrupt rerun-analysis prioritization or erase valid freshness repair context.

Report quality repair queue decision freshness flags treat lookup truthiness failures as false before action prioritization, so `KeyError` or `IndexError` from malformed rerun flags cannot interrupt rerun-analysis prioritization while later valid stale-report flags can still trigger repair.

Report quality repair queue limit uses integer-safe conversion before slicing prioritized actions, so malformed limit truthiness cannot interrupt action prioritization or erase valid repair reasons.

Report quality repair queue limit uses the default cap on lookup integer conversion failures before slicing prioritized actions, so `KeyError` or `IndexError` from malformed limit adapters cannot interrupt action prioritization or hide valid repair items.

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

Provider impact report, data trust, and alert maps use mapping-safe conversion before provider recovery decisions, so immutable report confidence wrappers cannot hide core-source wait-provider-recovery blocking evidence.

Provider impact report, data trust, and alert maps use Mapping traversal when `.items()` lookup fails before provider recovery decisions, so malformed report confidence wrappers cannot hide core-source wait-provider-recovery evidence if standard key traversal remains readable.

Provider impact report, data trust, and alert maps skip lookup item failures during Mapping traversal before provider recovery decisions, so one broken report, trust, or alert key cannot hide later valid provider recovery evidence.

Provider impact report identity fields use string-safe conversion before provider recovery output, so malformed filename or pipeline truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact ticker identity uses string-safe conversion before provider recovery output, so malformed ticker payload objects cannot interrupt JSON serialization or erase wait-provider-recovery blocking evidence.

Provider impact current fetch fields use bool-, integer-, and string-safe conversion before provider recovery decisions, so malformed current fetch truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact current fetch fields treat lookup integer and bool conversion failures as empty current-fetch evidence, so `KeyError` or `IndexError` from malformed record-count, stale, or healthy-entry adapters cannot interrupt provider recovery impact classification.

Provider impact alert text fields use string-safe conversion before provider recovery decisions, so malformed source, provider, or alert level truthiness cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact reason codes use string-safe conversion before provider recovery decisions, so malformed reason-code text cannot interrupt core-source impact classification or erase wait-provider-recovery blocking evidence.

Provider impact reason code iterators preserve valid entries before failures, so malformed reason-code iteration cannot erase already parsed provider recovery blocking evidence.

Provider impact text list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed reason-code iterator objects cannot erase underlying provider recovery blocking evidence.

Provider impact text list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code iterators cannot erase underlying provider recovery blocking evidence.

Provider impact text list conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code `__iter__` access cannot erase underlying provider recovery blocking evidence before iteration starts.

Provider impact alert iterators preserve valid entries before failures, so malformed provider alert iteration cannot erase already parsed core-source provider recovery blocking evidence.

Provider impact ledger report iterators preserve valid reports before failures, so malformed report collection iteration cannot erase already parsed provider recovery impact rows or sampled report counts.

Provider impact ledger reports envelopes use mapping-safe conversion before provider recovery decisions, so immutable report-list wrappers cannot hide wait-provider-recovery blocking evidence or sampled report counts.

Provider impact tuple sequences are evaluated before provider recovery decisions, so immutable reason-code, alert, or ledger report batches do not lose wait-provider-recovery blocking evidence.

Provider impact list conversions use native list and tuple iterators when iterator accessors fail before provider recovery decisions, so underlying reason-code, alert, or ledger report evidence is not erased.

Provider impact dict list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed provider alert iterator objects cannot erase underlying provider recovery evidence.

Provider impact dict list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed provider alert iterators cannot erase underlying provider recovery evidence.

Provider impact dict list conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed provider alert `__iter__` access cannot erase underlying provider recovery evidence before iteration starts.

Provider impact ledger sort keys use string-safe conversion before ordering, so malformed ticker sort-key truthiness cannot interrupt provider recovery impact ledger output.

Daily decision queue action fields use dict-native field reads before priority ordering, so malformed repair, provider impact, notification delivery, backtest, rerun, model route, watchlist, or screener action accessors cannot interrupt daily operating order or erase valid queue context.

Notification plan action fields use dict-native field reads before message and outbox handoff, so malformed decision queue or legacy action accessors cannot interrupt notification planning or erase source, report, CTA, rank, and delivery identity context.

Notification delivery audit context fields use dict-native field reads before persistence and reconciliation, so malformed outbox or audit-record accessors cannot interrupt sender audit writes or erase source, report, CTA, rank, retry, and attention context snapshots.

Provider SLA dashboard alert payload fields use dict-native field reads before impact classification, so malformed provider alert accessors cannot interrupt core/enrichment status projection or erase valid provider, level, message, window, and success-rate evidence.

Notification delivery observability summaries use dict-safe conversion before rendering dashboard and Prometheus maps, so malformed summary or count-map truthiness cannot interrupt external delivery health metrics.

Notification delivery observability fields use dict-native field reads before attention, dashboard, and Prometheus rendering, so malformed summary accessors cannot interrupt notification health visibility or erase failed, retry-exhausted, channel, and reason evidence.

Notification delivery observability counts use integer-safe conversion before rendering dashboard and Prometheus gauges, so malformed count conversion cannot interrupt external delivery health metrics.

Notification delivery observability counts use strict count conversion before rendering dashboard and Prometheus gauges, so boolean, binary, or memory-view audit counts render as zero instead of decoded delivery-failure evidence.

Notification delivery dashboard count maps use shared text keys and integer-safe values before payload output, so boolean, binary, or memory-view channel/reason keys cannot leak non-JSON-safe map entries into ops dashboard responses.

Notification delivery Prometheus channel and reason labels use shared text conversion with unknown fallback, so malformed, boolean, binary, or memory-view labels cannot leak into external delivery health metrics.

Prometheus label rendering uses shared text conversion with unknown fallback, so malformed, boolean, binary, or memory-view provider, queue, or delivery label values cannot leak into metrics output.

Prometheus provider summary fetch failures fall back to empty provider series, so provider SLA storage or aggregation errors cannot interrupt queue or notification delivery metrics output.

Prometheus provider summary non-iterable payloads fall back to empty provider series, so malformed provider summary payload shape cannot interrupt queue or notification delivery metrics output.

Prometheus provider summary iterator failures preserve provider rows parsed before the failure, so one broken provider summary iterator cannot suppress earlier valid provider series or interrupt queue and notification delivery metrics output.

Prometheus queue snapshot fetch failures fall back to unknown/zero queue gauges, so queue observer or backend errors cannot interrupt provider or notification delivery metrics output.

Ops dashboard queue snapshot fetch failures fall back to an unavailable unknown queue status, so queue observer or backend errors mark the dashboard critical without suppressing jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue availability uses bool-safe conversion before status aggregation and payload output, so malformed queue availability truthiness cannot suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue metadata uses string-, integer-, and dict-safe conversion before payload output, so malformed backend, queue name, depth, or queues maps cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard named queue details use string-key and dict-safe conversion before payload output, so malformed named queue keys or detail rows cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard named queue detail fields use integer-, string-, and registry-map safe conversion before payload output, so malformed named queue depth, registry counts, or supplemental detail fields cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue integer fields use strict count conversion before payload output, so boolean, binary, or memory-view queue depth, registry, active-task, and timeout payloads render as zero instead of decoded backlog values.

Ops dashboard queue supplemental fields use integer-, float-, string-, and registry-map safe conversion before payload output, so malformed registries, active task counts, queue age, timeout, or error values cannot leak non-JSON-safe objects or suppress jobs, provider, API quota, or notification delivery sections.

Ops dashboard queue text metadata uses shared text conversion before payload output, so boolean, binary, or memory-view queue labels and error details cannot leak as operator-facing strings.

Ops dashboard queue age fields use finite-float conversion before payload output, so NaN or Infinity queue age values fall back to zero instead of leaking non-standard JSON numbers.

Ops dashboard queue age fields use strict finite-float conversion before payload output, so boolean, binary, or memory-view queue age payloads render as zero instead of decoded wait-time values.

Observability dashboard and Prometheus payload shaping uses payload-safe mapping conversion instead of persistence JSON pruning, so empty job lists, named queue keys, provider SLA numeric fields, notification delivery label maps, and non-finite numeric fields remain present and are normalized to safe output values.

Ops dashboard free mode provider summaries use dict-, list-, bool-, and string-safe conversion before payload output, so malformed free-mode provider tiers or provider lists cannot suppress jobs, queue, provider, API quota, or notification delivery sections.

Ops dashboard free mode violations use string-safe conversion before payload output, so malformed violation entries cannot leak non-JSON-safe objects or suppress jobs, queue, provider, API quota, or notification delivery sections.

Ops dashboard free mode provider tiers and violations use shared text conversion instead of persistence JSON pruning, so boolean, binary, or memory-view values cannot be decoded into trusted cost-tier counts or visible violation text.

Prometheus queue snapshots use dict-safe conversion before rendering queue gauges, so malformed queue snapshot mapping cannot interrupt metrics output and falls back to unknown/zero queue gauges.

Prometheus queue backend and queue name rendering uses string-safe conversion, so malformed queue label truthiness cannot interrupt queue gauges.

Prometheus queue availability rendering uses bool-safe conversion, so malformed queue availability truthiness cannot interrupt queue gauges.

Prometheus named queue depth maps use payload-safe conversion, so malformed queue map or detail truthiness cannot interrupt queue gauges, and named queues with malformed detail rows still emit zero-depth series instead of disappearing.

Prometheus queue depth gauges use strict count conversion, so boolean, binary, or memory-view default and named queue depths render as zero instead of decoded backlog values.

Prometheus integer gauges use integer-safe conversion, so malformed provider or queue count conversion cannot interrupt metrics output.

Prometheus float gauges use float-safe conversion, so malformed provider success-rate conversion cannot interrupt metrics output.

Prometheus provider numeric gauges use strict numeric conversion, so boolean, binary, or memory-view provider success-rate, attempts, and error-count payloads render as zero instead of decoded metric values.

Prometheus provider rows use dict-safe conversion before rendering provider gauges, so malformed provider row mapping cannot interrupt metrics output or create empty-label provider series.

Provider SLA window alert enrichment uses integer-, float-, and string-safe conversion, so malformed provider attempts, success-rate, error count, or status values cannot interrupt dashboard alert recalculation.

Provider SLA alert policy basis selection uses dict-, integer-, float-, and string-safe conversion, so malformed window stats truthiness cannot interrupt upstream provider alert generation.

Data trust provider SLA evidence attempts use truthiness-safe integer and basis text conversion, so malformed provider SLA alert evidence cannot interrupt report trust downgrade decisions.

Data trust provider SLA evidence attempts treat lookup integer conversion failures as zero evidence, so `KeyError` or `IndexError` from malformed attempt adapters cannot interrupt report trust downgrade decisions or create unsupported provider SLA downgrades.

Data trust provider SLA nested window maps use dict-safe conversion before evidence attempts, so malformed nested window accessors cannot interrupt report trust downgrade decisions or suppress alert-level attempts fallback.

Data trust provider SLA row maps fall back to native dict items when copy lookups fail, so `KeyError` or `IndexError` from malformed source-audit or alert row mapping adapters cannot erase provider downgrade evidence.

Data trust provider SLA alert matching uses string-safe source, provider, level, and message conversion, so malformed alert text truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit entries use string-, integer-, and bool-safe conversion, so malformed current source audit truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit entries treat lookup integer and bool conversion failures as empty current-fetch evidence, so `KeyError` or `IndexError` from malformed record-count or stale adapters cannot interrupt report trust downgrade decisions.

Data trust provider SLA trust metadata uses list- and string-safe conversion, so malformed existing trust status, reason codes, or notes cannot interrupt report trust downgrade decisions.

Data trust provider SLA trust metadata uses shared text conversion before merging existing status, reason codes, and notes, so malformed boolean, binary, or memory-view values cannot leak into report trust metadata.

Data trust provider SLA alert collections use iterable-safe conversion, so malformed alert collection truthiness cannot interrupt report trust downgrade decisions.

Data trust provider SLA source audit collections use iterable-safe conversion, so malformed current source audit iterator failures cannot erase valid source audit rows or interrupt report trust downgrade decisions.

Data trust provider SLA rows use dict-safe conversion before matching current source audit entries and provider alerts, so malformed row accessors cannot interrupt data-trust downgrades or erase provider SLA evidence.

Data trust provider SLA source data uses dict-safe conversion before reading current source audit rows, so malformed source data accessors cannot interrupt data-trust downgrades or erase provider SLA evidence.

Data trust provider SLA alert fetch failures fall back to existing trust, so provider SLA storage or helper failures cannot interrupt report trust downgrade decisions.

Data trust provider SLA policy failures fall back to base trust before final score calculation, so provider SLA policy exceptions cannot interrupt report confidence finalization or erase already computed source audit trust evidence.

Data trust provider SLA policy lookup failures fall back to base trust before final score calculation, so `KeyError` or `IndexError` from provider SLA policy adapters cannot interrupt report confidence finalization or erase already computed source audit trust evidence.

Data trust provider SLA policy failure fallback uses an unmutated base trust snapshot before final score calculation, so partial in-place provider SLA policy mutations cannot pollute report confidence finalization after the policy raises.

Data trust post-SLA status fields use canonical status normalization before final score calculation, so malformed provider SLA status values cannot leak non-canonical report confidence states or drift away from score semantics.

Data trust post-SLA list metadata fields are written back after string-list normalization before final score calculation, so malformed provider SLA critical failures, stale sources, notes, or reason codes cannot leak non-list report confidence metadata while score semantics use normalized evidence.

Data trust post-SLA market timestamp fields use shared text normalization before final score output, so malformed provider SLA last-market timestamps cannot leak non-string report confidence metadata.

Data trust post-SLA provider SLA alert metadata uses dict-list normalization before final score output, so malformed provider SLA alert collections cannot leak non-list report confidence metadata.

Data trust provider SLA trust metadata iterators preserve valid entries before failures, so malformed reason-code or note iterators cannot erase already parsed report trust context.

Data trust provider SLA list conversions use native list and tuple iterators when iterator accessors fail before trust downgrade decisions, so source-audit rows, provider alerts, reason codes, and notes are not erased.

Data trust provider SLA dict row conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed source-audit or provider-alert iterator objects cannot erase trust downgrade evidence.

Data trust provider SLA dict row conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed source-audit or provider-alert iterators cannot erase trust downgrade evidence.

Data trust provider SLA dict row conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed source-audit or provider-alert `__iter__` access cannot erase trust downgrade evidence before iteration starts.

Data trust provider SLA text list conversions use native list and tuple iterators when custom iterators fail before yielding, so malformed trust metadata reason-code or note iterator objects cannot erase existing report trust context.

Data trust provider SLA text list conversions treat lookup iterator failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code or note iterators cannot erase existing report trust context.

Data trust provider SLA text list conversions treat lookup iterator creation failures as native-list fallbacks, so `KeyError` or `IndexError` from malformed reason-code or note `__iter__` access cannot erase existing report trust context before iteration starts.

Data trust normalization note fields use string-list conversion before report trust metadata output, so tuple notes preserve valid report limitation context and malformed binary values are dropped.

Data trust normalization provider SLA alert lists use dict-list safe conversion before report trust metadata output, so tuple or native-backed alert collections preserve valid provider health metadata without interrupting report confidence normalization.

Data trust scoring audit source names use string-safe conversion, so malformed source truthiness cannot interrupt report trust scoring or erase valid source audit decisions.

Data trust audit entry text fields use string-safe conversion, so malformed source, provider, error kind, or message truthiness cannot interrupt source audit evidence creation.

Data trust audit entry text fields use shared text conversion before source audit evidence output, so malformed source, provider, error kind, or message values cannot leak boolean, binary, or memory-view text into source audit rows.

Data trust source audit append preserves tuple audit batches before adding new entries, so immutable upstream source-audit payloads do not lose existing provider evidence during audit enrichment.

Report key evidence source fields use shared text conversion before HTML and Markdown report output, so malformed provider, status, source, or fetched-at values cannot leak boolean, binary, or memory-view text into report evidence tables.

Report key evidence aggregated stale flags use bool-safe conversion before HTML and Markdown report output, so `KeyError` or `IndexError` from malformed source-audit stale adapters cannot interrupt key evidence rendering or mark malformed stale values as true.

Report key evidence data field presence checks ignore malformed scalar values before HTML and Markdown report output, so boolean, binary, or memory-view data fields cannot synthesize source-evidence rows.

Report key evidence data field presence checks use strip-safe shared text conversion before HTML and Markdown report output, so malformed data string `strip()` cannot interrupt key evidence rendering or erase valid source evidence.

Report key evidence Markdown cells escape table separators before Markdown output, so provider or timestamp values containing `|` or newlines cannot corrupt the key evidence table structure.

Report source audit table fields use shared text conversion before HTML and Markdown report output, so malformed source, provider, status, fetched-at, or message values cannot leak boolean, binary, or memory-view text into source audit sections.

Report source audit Markdown cells escape table separators before Markdown output, so provider, fetched-at, or message values containing `|` or newlines cannot corrupt the source audit table structure.

Report source evidence numeric and boolean fields use safe conversion before HTML and Markdown report output, so malformed duration, record count, cache-hit, or stale values cannot leak boolean, binary, or memory-view text into key evidence or source audit tables.

Report data trust summary fields use shared text conversion before HTML and Markdown report output, so malformed trust notes, market timestamps, quant fallback fields, or warning messages cannot leak boolean, binary, or memory-view text into data-trust sections.

Report data trust quant fallback fields use truthiness-safe list conversion before HTML and Markdown report output, so malformed fallback field list wrappers cannot interrupt quant warning rendering and valid fallback field names remain visible.

Report evidence matrix payload source fields use shared text conversion before tooltip JSON output, so malformed provider, status, source, fetched-at, or message values cannot leak boolean, binary, or memory-view text into report evidence data.

Report evidence matrix payload message fallback uses truthiness-safe field selection before tooltip JSON output, so `KeyError` or `IndexError` from malformed source-audit message truthiness cannot interrupt payload generation or overwrite a present message with fallback text.

Report evidence matrix payload message fallback skips text-empty malformed values before tooltip JSON output, so binary or memory-view `message` fields cannot hide a valid `error_kind` fallback in source evidence tooltips.

Report evidence matrix payload message presence checks use length-safe fallback before tooltip JSON output, so malformed source-audit message container length cannot interrupt payload generation or hide a valid `error_kind` fallback.

Report evidence matrix payload message presence checks use strip-safe shared text conversion before tooltip JSON output, so malformed source-audit message string `strip()` cannot interrupt payload generation or overwrite a present message.

Report evidence matrix source audit child maps use mapping-safe conversion before tooltip JSON output, so malformed source audit row accessors cannot interrupt report evidence payload generation when valid provider evidence exists.

Report evidence matrix source row labels use shared text conversion before conclusion matching, so malformed label hash behavior cannot interrupt conclusion evidence rendering when the label text is still valid.

Report evidence matrix Markdown cells use shared text conversion before table output, so malformed cell truthiness cannot interrupt Markdown export and pipe separators are still escaped.

Report evidence matrix HTML cells use shared text conversion before table output, so malformed cell stringification cannot interrupt HTML rendering or leak exception text into visible report evidence.

Report evidence matrix row fetched-at fields use truthiness-safe text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row timestamp truthiness cannot interrupt conclusion evidence rendering.

Report evidence matrix row status fields use truthiness-safe text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row status truthiness cannot interrupt conclusion evidence rendering.

Report evidence matrix row provider fields use truthiness-safe text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row provider truthiness cannot interrupt conclusion evidence rendering.

Report evidence matrix stale-source flags use bool-safe conversion before HTML, Markdown, snapshot, and tooltip output, so malformed evidence row stale truthiness cannot interrupt limitation rendering or synthesize stale-source notes.

Report evidence matrix price-target basis excludes boolean values before HTML, Markdown, snapshot, and tooltip output, so malformed target flags cannot render as `NT$1` or `NT$0` valuation evidence.

Report evidence matrix price-target basis excludes non-finite numeric values before HTML, Markdown, snapshot, and tooltip output, so malformed target numbers cannot render as `NT$nan` or `NT$inf` valuation evidence.

Report evidence matrix price-target scenario keys skip malformed text before HTML, Markdown, snapshot, and tooltip output, so binary or memory-view valuation scenario names cannot render as `N/A: NT$120` evidence.

Report evidence matrix recommendation-basis keys use shared text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed recommendation key stringification cannot interrupt conclusion evidence rendering.

Report evidence matrix recommendation-basis values use equality-safe text checks before HTML, Markdown, snapshot, and tooltip output, so malformed recommendation value comparison cannot interrupt conclusion evidence rendering.

Report evidence matrix recommendation-basis string values use strip-safe shared text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed recommendation value `strip()` cannot interrupt conclusion evidence rendering.

Report evidence matrix moat-score basis skips malformed metric keys before HTML, Markdown, snapshot, and tooltip output, so binary or memory-view moat metric names cannot render as `N/A: 8/10` evidence.

Report evidence matrix limitation notes use shared text conversion before HTML, Markdown, snapshot, and tooltip output, so malformed data-source note values cannot leak boolean, binary, or memory-view text into report limitation copy.

Report evidence matrix limitation notes use text-list safe conversion before HTML, Markdown, snapshot, and tooltip output, so tuple data-source notes preserve valid note text without leaking Python tuple or binary representations.

Data trust audit entry status uses string-safe conversion, so malformed but valid status text cannot be misclassified as unavailable.

Data trust audit entry duration fields ignore boolean millisecond overrides before epoch delta fallback, so true or false duration fields cannot replace valid source fetch timing evidence.

Data trust audit entry duration fields ignore non-finite millisecond overrides before epoch delta fallback, so NaN or Infinity duration fields cannot interrupt source audit creation or replace valid fetch timing evidence.

Data trust audit entry duration fields ignore overflowing millisecond overrides before epoch delta fallback, so oversized duration fields cannot interrupt source audit creation or replace valid fetch timing evidence.

Data trust audit entry duration fields ignore non-finite epoch timestamps before delta calculation, so NaN or Infinity started/finished fields cannot interrupt source audit creation or create synthetic fetch timing evidence.

Data trust audit entry duration fields ignore overflowing epoch timestamps before delta calculation, so oversized started/finished fields cannot interrupt source audit creation or create synthetic fetch timing evidence.

Data trust audit entry duration fields reject out-of-range epoch timestamps before delta calculation, so platform-range-invalid started/finished fields cannot create synthetic fetch timing evidence.

Data trust audit entry fetched-at fields use shared text conversion before epoch fallback, so malformed boolean, binary, or memory-view fetched-at values cannot leak into source audit rows or suppress valid epoch timestamps.

Data trust audit entry fetched-at epoch fallback validates explicit epoch values before finished-at fallback, so malformed boolean or non-finite fetched-at epoch values cannot suppress valid finished timestamps.

Data trust audit entry fetched-at epoch fallback treats out-of-range epoch values as malformed before finished-at fallback, so platform timestamp range errors cannot interrupt source audit creation or suppress valid finished timestamps.

Data trust audit entry finished-at current-time fallback validates epoch values before source audit output, so malformed boolean, non-positive, or non-finite finished timestamps cannot erase source audit fetched-at evidence.

Data trust audit entry record counts use integer-safe conversion, so malformed numeric truthiness cannot erase valid source evidence counts.

Data trust audit entry record counts treat boolean values as malformed counts, so true or false source audit fields cannot inflate source evidence counts.

Data trust audit entry record counts treat fractional numeric values as malformed counts, so non-integer source audit fields cannot be truncated into valid source evidence counts.

Data trust audit entry boolean fields use bool-safe conversion, so malformed cache-hit or stale truthiness cannot interrupt source audit evidence creation.

Data trust audit entry boolean fields treat lookup truthiness failures as false, so `KeyError` or `IndexError` from malformed cache-hit or stale adapters cannot interrupt source audit evidence creation.

Data trust audit entry boolean text fields parse explicit false strings before truthiness fallback, so "false", "0", "no", or "off" cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean binary fields are treated as malformed before truthiness fallback, so byte, bytearray, or memory-view cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean non-finite numeric fields are treated as malformed before truthiness fallback, so NaN or Infinity cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean numeric fields only accept explicit zero or one values before truthiness fallback, so fractional or out-of-range cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean real-number fields apply the same explicit zero or one contract to rational numeric values before truthiness fallback, so Fraction-style cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean overflowing real-number fields are treated as malformed before truthiness fallback, so oversized integer or rational cache-hit and stale values cannot interrupt source audit evidence creation.

Data trust audit entry boolean numeric text fields apply the same finite zero or one contract before truthiness fallback, so numeric-string cache-hit and stale values like "2", "0.5", "NaN", or "Infinity" cannot be misreported as true source audit evidence.

Data trust audit entry boolean free-form text fields are treated as malformed after explicit true, false, and numeric parsing, so unsupported cache-hit and stale labels like "cached", "stale", or "unknown" cannot be misreported as true source audit evidence.

Data trust audit entry boolean complex fields are treated as malformed before truthiness fallback, so complex cache-hit and stale values cannot be misreported as true source audit evidence.

Data trust audit entry boolean container fields are treated as malformed before truthiness fallback, so list, tuple, set, or mapping cache-hit and stale values cannot be misreported as true source audit evidence.

Prompt source audit summary fields use string-, integer-, and bool-safe conversion, so malformed audit provider, status, count, cache, stale, or message fields cannot interrupt prompt JSON generation.

Prompt source audit summary text fields use shared text conversion before prompt output, so malformed source, provider, status, or message fields cannot leak boolean, binary, or memory-view text into prompt JSON.

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

Prompt data trust payload accepts mapping-safe trust maps before prompt output, so immutable or read-only `data_trust` wrappers cannot be mistaken for missing report confidence metadata in model instructions.

Data trust string list conversion uses string-safe conversion, so malformed text truthiness cannot interrupt reason-code or score-reason normalization.

Data trust string list conversion uses native list and tuple iterator fallback, so malformed custom iterators cannot erase valid trust notes, reason codes, stale sources, critical failures, or score reasons.

Data trust string list conversion drops non-finite numeric items, so NaN or Infinity values cannot leak into trust notes, reason codes, stale sources, critical failures, or score reasons.

Data trust score normalization uses float-safe conversion, so malformed existing trust score conversion cannot interrupt snapshot generation and falls back to status-derived scoring.

Data trust score normalization treats lookup conversion failures as malformed scores, so `KeyError` or `IndexError` from existing trust score adapters cannot interrupt snapshot generation and falls back to status-derived scoring.

Data trust score normalization treats boolean score values as malformed, so true or false cannot become synthetic 1 or 0 trust scores in report confidence metadata.

Data trust normalization accepts mapping-safe trust payloads before field normalization, so immutable or read-only mapping wrappers cannot be mistaken for missing report confidence metadata.

Data trust normalization uses dict-native trust field reads, so malformed existing trust mapping accessors cannot interrupt score, freshness, reason, note, or provider SLA metadata normalization.

Data trust normalization market timestamp fields use shared text conversion, so malformed boolean, binary, or memory-view last-market-data values cannot leak into report confidence metadata.

Data trust build source payloads accept mapping-safe inputs before scoring, so immutable or read-only source data wrappers cannot be mistaken for missing report confidence evidence.

Data trust build source data uses mapping- and dict-list-safe conversion before scoring, so malformed root payload accessors or tuple/native-backed source audit collections cannot interrupt report confidence scoring or erase valid source audit evidence.

Data trust build source freshness child maps use mapping-safe conversion before scoring, so malformed nested freshness accessors cannot interrupt stale-source scoring or erase valid market-data freshness timestamps.

Data trust build source freshness stale flags use bool-safe conversion before scoring, so malformed stale truthiness cannot interrupt report confidence scoring or misclassify valid source audit evidence.

Data trust build data source notes use string-list conversion before scoring, so malformed note truthiness cannot interrupt report confidence scoring or create synthetic data-source limitation metadata.

Data trust latest audit rows use mapping-safe conversion before scoring, so malformed source audit row accessors cannot interrupt latest-source selection or erase valid source audit status evidence.

Data trust optional source status selection uses mapping-safe row conversion before scoring, so malformed optional audit row accessors cannot interrupt optional-source reason code projection or promote core sources into optional status buckets.

Data trust usable critical data checks use mapping-safe audit conversion before scoring, so malformed critical audit accessors cannot interrupt error-vs-partial trust status selection or erase valid core source availability evidence.

Data trust source audit status comparisons use string-safe conversion before scoring, so malformed but valid status text cannot be misclassified as fresh and hide core source failures from report confidence metadata.

Data trust last-market timestamp fallback uses string-safe conversion before scoring, so malformed timestamp truthiness cannot interrupt report confidence metadata or suppress valid market freshness time evidence.

Data trust post-SLA trust metadata uses mapping-safe conversion before final score calculation, so malformed provider-SLA return accessors cannot interrupt report confidence finalization or erase valid trust status and reason evidence.

Data trust snapshot existing trust selection uses dict-safe conversion, so malformed `data_trust` truthiness cannot interrupt snapshot generation or erase valid trust metadata.

Data trust snapshot existing trust selection accepts mapping-safe payloads, so immutable or read-only `data_trust` wrappers cannot be mistaken for missing report confidence metadata.

Data trust snapshot root context accepts mapping-safe payloads before metadata selection, so immutable or read-only context wrappers cannot interrupt snapshot generation or erase report confidence evidence.

Data trust snapshot source data accepts mapping-safe payloads before trust scoring, so immutable or read-only `data` wrappers cannot erase valid source audit evidence during snapshot generation.

Data trust snapshot refresh flags use bool-safe conversion, so malformed refresh metadata truthiness cannot interrupt snapshot generation.

Data trust snapshot refresh flags treat lookup truthiness failures as false, so `KeyError` or `IndexError` from malformed refresh metadata cannot interrupt snapshot generation.

Data trust snapshot rerun context text uses string-safe conversion, so malformed analysis text truthiness cannot interrupt snapshot generation or rerun context preservation.

Data trust snapshot sanitizer uses string-safe key and value conversion, so malformed snapshot object string conversion cannot interrupt snapshot generation or leak empty keys.

Data trust snapshot sanitizer uses native list and tuple iterators when iterator accessors fail, so malformed snapshot sequence subclasses cannot interrupt snapshot generation or erase underlying list or tuple evidence.

Data trust snapshot sanitizer falls back to native list and tuple iterators when custom sequence iterators fail before yielding, so malformed snapshot iterator objects cannot erase underlying list or tuple evidence.

Data trust snapshot sanitizer uses native dict items when items accessors fail, so malformed snapshot mapping subclasses cannot interrupt snapshot generation or erase underlying mapping evidence.

Data trust snapshot sanitizer falls back to native dict items when custom items iterables fail, so malformed snapshot mapping item views cannot erase underlying mapping evidence.

Data trust snapshot integrity hash lookup uses string-safe conversion, so malformed hash metadata truthiness cannot interrupt snapshot verification.

Snapshot maintenance verify-snapshots uses verifier-derived hash presence, so falsey hash metadata is repaired or reported as mismatch instead of being backfilled as missing.

Data trust snapshot integrity and schema validators use dict-native snapshot field reads, so malformed snapshot accessors cannot interrupt hash or schema verification.

Data trust snapshot integrity and schema validators fall back to item lookup when mapping field accessors fail, so read-only snapshot wrappers with malformed `.get()` or containment accessors still preserve valid hash and required-field evidence.

Data trust snapshot rerun context agent keys use string-safe conversion, so malformed analysis key conversion cannot interrupt snapshot generation or leak malformed rerun context keys.

Data trust snapshot content hash keys use string-safe conversion, so malformed snapshot object keys cannot interrupt integrity verification or leak non-JSON-safe hash inputs.

Data trust snapshot content hashing uses iterator-safe mapping traversal, so malformed snapshot items accessors cannot interrupt integrity generation or verification.

Data trust snapshot content hash accepts mapping snapshot wrappers before integrity verification, so immutable snapshot containers do not lose valid hash evidence.

Data trust snapshot size governance uses snapshot sanitizer input, so malformed snapshot object keys cannot interrupt size governance or leak non-JSON-safe snapshot inputs.

Data trust snapshot size byte calculation uses snapshot sanitizer input, so malformed snapshot object keys cannot interrupt size measurement or leak non-JSON-safe snapshot inputs.

Data trust snapshot builds use dict-native context and data field reads, so malformed mapping accessors cannot interrupt snapshot generation or erase identity, freshness, quality, or rerun metadata.

Data trust snapshot identity fields use string-safe context/data selection, so malformed ticker, company name, or pipeline truthiness cannot interrupt snapshot generation or reproducibility packet identity.

Data trust snapshot identity fields use shared text conversion before artifact output, so malformed ticker, company name, or pipeline values cannot leak boolean, binary, or memory-view text into `.data.json` snapshots and valid data fallback identity remains available.

Data trust reproducibility source audit metadata uses string-safe provider and timestamp extraction, so malformed source audit provider or fetched-at truthiness cannot interrupt snapshot generation or erase valid traceability fields.

Data trust reproducibility source audit metadata uses dict-list safe conversion before provider and timestamp extraction, so malformed source audit iterator lookup failures cannot interrupt snapshot generation or erase valid traceability rows.

Data trust reproducibility source audit helpers accept mapping-safe data wrappers before provider and timestamp extraction, so read-only data payloads cannot erase valid provider or source-time traceability rows.

Data trust reproducibility packets use dict-native context, data, source audit, and metadata field reads, so malformed mapping accessors cannot interrupt provenance generation or erase traceability fields.

Data trust reproducibility packets accept mapping-safe context, data, source audit, and metadata wrappers, so read-only provenance payloads cannot erase ticker, pipeline, model, code, provider, or source-time traceability fields.

Data trust reproducibility packets preserve validated full prompt fingerprints, so report audit can distinguish exact prompt content without exposing arbitrary prompt-like values.

Prompt fingerprints cover agent templates, state-view policy, system prompts, and runtime prompt rules, so report identity follows the effective prompt bundle rather than only `agents.json`.

Prompt identity and prompt injection share one process-stable runtime-rule snapshot, so a report fingerprint cannot drift from the rules injected into the same workflow.

Runtime code provenance records commit and dirty state once per workflow, so uncommitted code cannot be mistaken for a report reproducible from the commit alone. `code_dirty = true` means local changes were present, `false` means the worktree was clean at initialization, and `null` means the state was unknown.

Data trust explicit target price detection uses dict-native root field reads, so malformed parsed or structured output context accessors cannot interrupt target-price guardrail generation or erase underlying evidence.

Data trust explicit target price detection accepts mapping-safe root and nested maps, so read-only parsed or structured output wrappers cannot hide explicit target-price guardrail evidence.

Data trust explicit target price detection uses string-safe key and value conversion, so malformed parsed or structured output target fields cannot interrupt snapshot guardrail generation or erase valid detected target fields.

Data trust explicit target price detection preserves valid list items before iterator failures, so malformed parsed or structured output collections cannot erase already detected target fields.

Data trust explicit target price detection accepts tuple sequences before guardrail output, so immutable parsed or structured output row collections cannot hide target-price evidence.

Data trust explicit target price detection uses native list iterators when iterator accessors fail, so malformed parsed or structured output list subclasses cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native list iterators when custom iterators fail before yielding, so malformed parsed or structured output list iterator objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection treats lookup list iterator failures as native list fallbacks, so `KeyError` or `IndexError` from malformed parsed or structured output list wrappers cannot erase target-price guardrail evidence.

Data trust explicit target price detection preserves valid mapping items before iterator failures, so malformed parsed or structured output objects cannot erase already detected target fields.

Data trust explicit target price detection uses native dict items when items accessors fail, so malformed parsed or structured output mapping subclasses cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native dict items when custom items iterables fail to create iterators, so malformed parsed or structured output mapping items iterable objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection uses native dict items when custom items iterators fail before yielding, so malformed parsed or structured output mapping iterator objects cannot erase underlying target-price guardrail evidence.

Data trust explicit target price detection treats lookup mapping item failures as native dict item fallbacks, so `KeyError` or `IndexError` from malformed parsed or structured output mapping accessors or iterators cannot erase target-price guardrail evidence.

Data trust explicit target price detection ignores non-finite numeric targets, so NaN or Infinity parsed outputs cannot create false explicit target-price evidence.

Data trust source record counting uses string-safe source keys, so malformed source truthiness cannot interrupt merged evidence counts for audit summaries.

Data trust source record counting normalizes root data maps before field reads, so malformed data snapshot accessors cannot interrupt merged evidence counts when valid source values exist.

Data trust source record counting normalizes institutional trading maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid trading rows exist.

Data trust source record counting ignores empty institutional trading daily-only payloads before fallback counting, so blank chip-flow shells cannot inflate merged evidence counts.

Data trust source record counting normalizes global market context maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid market-context rows exist.

Data trust source record counting normalizes international news context maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid news-topic rows exist.

Data trust source record counting normalizes P/E river chart maps before field reads, so malformed nested accessors cannot interrupt merged evidence counts when valid valuation rows exist.

Data trust source record counting normalizes P/E river chart band maps before counting valuation rows, so immutable band payloads keep accurate merged evidence counts.

Data trust source record counting falls back from empty P/E river chart band series to year or EPS rows, so sparse valuation payloads do not lose remaining source evidence.

Data trust source record counting normalizes default source mapping values before counting keys, so malformed mapping length accessors cannot interrupt merged evidence counts for custom source payloads.

Data trust source record counting counts only default source mapping keys with present child values, so custom mapping payloads made only of missing values cannot inflate merged evidence counts.

Data trust source record counting uses sequence-safe tuple value presence checks, so empty tuple history or enrichment payloads cannot be counted as valid source evidence.

Data trust source record counting uses item-aware sequence value presence checks, so non-empty history or enrichment sequences made only of missing values cannot inflate merged evidence counts.

Data trust source record counting uses mapping-safe value presence checks, so empty immutable mapping history or enrichment payloads cannot be counted as valid source evidence.

Data trust source record counting uses child-aware mapping value presence checks, so mapping history or enrichment payloads made only of missing child values cannot inflate merged evidence counts.

Data trust source record counting uses set-aware value presence checks, so empty set or frozenset history payloads cannot inflate merged evidence counts.

Data trust source record counting treats boolean scalar values as missing evidence, so malformed numeric or source fields such as true or false cannot inflate merged evidence counts.

Data trust source record counting treats non-finite numeric scalar values as missing evidence, so NaN or Infinity market fields cannot inflate merged evidence counts.

Data trust source record counting treats overflowing numeric scalar values as missing evidence, so oversized integer or rational market fields cannot interrupt merged evidence counts or inflate source evidence.

Data trust source record counting treats non-finite numeric string values as missing evidence while preserving finite numeric strings, so string NaN or Infinity market fields cannot inflate merged evidence counts.

Data trust source record counting treats placeholder string values as missing evidence while preserving finite numeric strings, so string None, null, or -- market fields cannot inflate merged evidence counts.

Data trust source record counting treats non-finite Decimal scalar values as missing evidence while preserving finite Decimal values, so decimal NaN or Infinity market fields cannot inflate merged evidence counts.

Data trust source record counting treats binary scalar values as missing evidence, so bytes, bytearray, or memory-view market fields cannot inflate merged evidence counts.

Data trust source record counting treats complex scalar values as missing evidence, so complex-number market fields cannot inflate merged evidence counts.

Data trust source record counting uses native list and tuple iterator fallback, so malformed history or enrichment row iterators cannot interrupt merged evidence counts or erase valid source-audit record counts.

Data trust source record counting treats tuple source values as row batches, so immutable custom enrichment rows keep accurate merged evidence counts instead of collapsing to one present scalar.

Data trust source record counting treats set and frozenset source values as row batches, so unordered custom enrichment rows keep accurate merged evidence counts instead of collapsing to one present scalar.

Data trust source record counting uses native set and frozenset iterator fallback, so malformed set row iterators cannot interrupt merged evidence counts or erase valid custom source rows.

Data trust source record counting treats lookup set iterator failures as native set and frozenset fallbacks, so `KeyError` or `IndexError` from malformed custom enrichment set wrappers cannot erase valid source evidence.

Data trust source record counting uses truthiness-safe value presence checks, so malformed list or mapping truthiness cannot interrupt merged evidence counts or hide valid market, financial, or enrichment evidence.

Provider SLA window selection uses string-safe conversion, so malformed selected-window truthiness or string conversion cannot interrupt provider SLA payload generation.

Provider SLA window maps use dict-safe conversion, so malformed provider `windows` or selected-window stats map truthiness cannot interrupt dashboard alert recalculation.

Provider SLA nested window numeric fields use integer- and finite-float-safe conversion, so malformed `windows.*` attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA numeric field shaping uses dict-safe row conversion before provider and window output, so malformed direct-helper row mappings cannot interrupt numeric shaping or leak unnormalized attempts, counts, success rate, duration, and total-record evidence.

Provider SLA numeric field shaping uses strict numeric conversion before provider and window output, so boolean, binary, or memory-view attempts, counts, success rate, duration, and total-record payloads render as zero instead of decoded SLA evidence.

Provider SLA nested window maps keep only canonical `last_1h`, `last_24h`, and `last_7d` buckets before payload output, so experimental or malformed window keys cannot leak into API/UI contracts.

Provider SLA nested window keys use shared text conversion before canonical bucket matching, so binary or memory-view keys cannot be decoded into accepted `last_1h`, `last_24h`, or `last_7d` windows.

Provider SLA selected-window helper output normalizes nested `windows` maps before returning provider rows, so direct helper callers cannot bypass nested window numeric shaping.

Provider SLA selected-window numeric fields use integer- and finite-float-safe conversion, so malformed attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA provider rows use dict-safe conversion before window selection, so malformed provider row mapping conversion cannot interrupt dashboard alert recalculation.

Provider SLA alert projection uses dict-safe row conversion and string-safe alert-level conversion, so malformed alert row mapping or alert level hashing cannot interrupt dashboard alert lists.

Provider SLA alert projection output fields use string-, finite-float-, and dict-safe conversion, so malformed alert source, provider, message, status, basis, selected window, success rate, or windows maps cannot leak non-JSON-safe values.

Provider SLA alert projection text fields use shared text conversion before dashboard alert output, so boolean, binary, or memory-view source, provider, message, status, basis, or selected-window values cannot leak into provider alert payloads.

Provider SLA all-window cumulative alerts reuse the same safe alert projection, so malformed cumulative alert rows cannot bypass the dashboard alert-list guard.

Provider SLA all-window provider summaries use dict-safe row conversion before returning dashboard payloads, so malformed cumulative provider rows cannot bypass the provider-list guard.

Provider SLA all-window provider numeric fields use integer- and finite-float-safe conversion, so malformed cumulative attempts, counts, success rate, duration, or total record values cannot leak non-JSON-safe values.

Provider SLA payload summary fetch failures fall back to empty provider lists, so provider SLA storage or aggregation errors cannot interrupt selected-window dashboard payloads.

Provider SLA payload alert fetch failures fall back to empty alert lists, so cumulative alert storage or aggregation errors cannot suppress otherwise available provider summary rows.

Prometheus provider alert level rendering uses string-safe conversion, so malformed alert level truthiness cannot interrupt alert gauges.

Notification delivery failure reason bucketing uses shared text conversion, so malformed `last_error` truthiness cannot interrupt low-cardinality delivery health summaries and binary or memory-view errors fall back to `unknown`.

Notification delivery summary channel counts use string-safe channel conversion, so malformed `channel_id` truthiness cannot interrupt delivery health channel distribution.

Notification delivery summary status counts use string-safe status conversion, so malformed `delivery_status` equality cannot interrupt delivery health status distribution.

Analysis workflow execution is durable. Each Worker run uses LangGraph with a SQLite checkpointer at `LANGGRAPH_CHECKPOINT_PATH` (default `backend/cache/langgraph_checkpoints.sqlite3`). A pipeline segment uses `thread_id = job_id:pipeline_id`; if an LLM call exhausts short in-node retries and the outer RQ job retries later, the Worker resumes the same graph thread instead of repeating completed Agent nodes. Do not delete the checkpoint DB while jobs are `queued`, `running`, or `waiting_retry`.

Agent step cache is enabled by default with `AGENT_STEP_CACHE_ENABLED=true` and `AGENT_STEP_CACHE_SECONDS=604800`. Cache hits emit `agent_step_cache_hit` events and restore the agent structured output without calling the LLM provider. If prompt rules, model routing, or source data changes unexpectedly, clear the configured cache backend or lower the TTL before rerunning critical reports.

Checkpoint cleanup policy is intentionally conservative for local-first operation: back up or delete old checkpoint files only after related jobs have reached `done`, `error`, or `cancelled`, and after preserving any reports you need. The checkpoint stores JSON-compatible graph state only; callbacks, API clients, Redis handles, and SQLite connections are process-local and are rebuilt on resume.

Analysis job state lives in `TASK_DB_PATH`. The same SQLite DB now contains jobs, SSE events, and per-node telemetry. API and worker processes must point at the same `TASK_DB_PATH`; otherwise the API can enqueue work but the UI will not see progress. Suggested retention is the default `ANALYSIS_JOB_HISTORY_RETENTION_DAYS=30`; use cleanup dry-runs before deleting old event/telemetry history.

Analysis job status rows use mapping-safe fallback before serialization, so missing or malformed non-mapping job-store rows return not found instead of interrupting the API response.

Analysis job status serializer fields use JSON-safe fallback before response shaping, so malformed status adapter field values do not interrupt public status responses or leak non-JSON payloads.

Analysis job by-id cancellation rows use mapping-safe fallback before cancellation requests, so missing or malformed non-mapping job-store rows return not found instead of reaching the cancel service.

Analysis job by-id cancellation fallback results use bool-safe fallback before response shaping, so malformed fallback cancellation adapter results return not found instead of interrupting cancellation requests.

Analysis job by-id cancellation service results use mapping-safe fallback before response shaping, so malformed service-level cancellation payloads return not found instead of leaking malformed responses.

Analysis job by-id cancellation service fields use JSON-safe fallback before response shaping, so malformed service-level cancellation field values do not interrupt public cancel responses or leak non-JSON payloads.

Analysis job cancellation service rows use mapping-safe fallback before queue cancellation, so malformed service-level job-store rows return not found without cancelling queue tasks or requesting job cancellation.

Analysis job cancellation service request ids use safe text fallback before store lookup and queue cancellation, so malformed requested job ids cannot reach cancellation stores, queue adapters, or public responses as non-JSON payloads.

Analysis job cancellation service status checks use safe text fallback before queue cancellation, so malformed queued status equality cannot interrupt cancellation requests.

Analysis job cancellation queue cancel accessors use safe getattr before queue-side cancellation, so malformed queue adapters cannot block job cancellation requests.

Analysis job serialization rows use mapping-safe fallback before response shaping, so malformed job-store rows produce safe empty payloads without empty job-id event or status URLs.

Analysis job serialization status fields use safe text fallback before response shaping, so malformed status truthiness or string conversion cannot interrupt public job payloads.

Analysis job serialization status fields trim whitespace before public status mapping, so padded internal statuses still map to stable public status values.

Analysis job serialization status fields normalize known status casing before public status mapping, so uppercase or mixed-case internal statuses still map to stable public status values while unknown statuses remain visible.

Analysis job serialization identity fields use safe text fallback before response shaping, so malformed job id truthiness or string conversion cannot interrupt public job payloads or create empty job-id URLs.

Analysis job serialization identity URL helper fields use path-segment fallback before response shaping, so path-like, encoded, or control-character job ids remain visible as text but do not create ambiguous event or status URLs.

Analysis job serialization public URL helper segments reject whitespace before response shaping, so job ids or report filenames with visible or invisible spacing do not create malformed public URLs.

Analysis job serialization public URL helper segments reject encoded percent tokens before response shaping, so double-encoded delimiter or control payloads cannot create ambiguous public URLs.

Analysis job serialization report filename fields use safe text fallback before response shaping, so malformed filename truthiness or string conversion cannot interrupt public job payloads or create invalid report URLs.

Analysis job serialization report filename fields use path-segment fallback before response shaping, so path-like filenames cannot create traversal or absolute public report URLs.

Analysis job serialization report filename fields use URL-delimiter fallback before response shaping, so query, fragment, or encoded separator filenames cannot create ambiguous public report URLs.

Analysis job serialization report filename fields use control-character fallback before response shaping, so invisible filename delimiters cannot create malformed public report URLs.

Analysis job serialization report filename fields use percent-encoded delimiter fallback before response shaping, so encoded query, fragment, separator, or control payloads cannot create ambiguous public report URLs.

Analysis job serialization pipeline fields use safe text fallback before response shaping, so malformed pipeline id truthiness or string conversion cannot interrupt public job payloads and falls back to `v1`.

Analysis job serialization ticker fields use safe text fallback before response shaping, so malformed ticker truthiness or string conversion cannot interrupt public job payloads or leak non-JSON job values.

Analysis job serialization timestamp fields use finite-float fallback before response shaping, so malformed or out-of-range job timestamps become null instead of interrupting public job payloads.

Analysis job serialization timestamp empty checks use type-safe string guards before response shaping, so malformed timestamp equality cannot interrupt public job payloads.

Analysis job serialization error fields use safe sanitizer fallback before response shaping, so malformed error string conversion cannot interrupt public job payloads or leak non-JSON job values.

Analysis job lifecycle result rows use mapping-safe fallback before queue decisions, so malformed create-or-attach rows return safe empty payloads without enqueueing unknown jobs.

Analysis job create handler results use mapping-safe fallback before response shaping, so malformed route-level create adapter payloads return safe empty job payloads instead of leaking malformed responses.

Analysis job create handler fields use serializer-backed JSON-safe fallback before response shaping, so malformed route-level field values do not interrupt public create responses or leak non-JSON payloads.

Analysis job create route normalized pipeline ids use safe text fallback before handler dispatch, so malformed route-level pipeline normalization payloads fall back to `v1` instead of interrupting create responses.

Analysis job id builder input fields use safe text fallback before slug construction, so malformed ticker or pipeline ids fall back to safe slug placeholders instead of interrupting job creation or leaking Python object representations into job ids.

Analysis job id builder force flags use bool-safe fallback before suffix selection, so malformed force truthiness falls back to deterministic non-force job id construction instead of interrupting job creation.

Analysis job lifecycle identity fields use safe text fallback before queue decisions, so malformed create-or-attach job ids return safe payloads without enqueueing unknown jobs.

Analysis job lifecycle status fields use safe text fallback before queue recovery decisions, so malformed create-or-attach statuses return safe payloads without requeueing unknown lifecycle states.

Analysis job input pipeline fields use safe text fallback before lifecycle creation, so malformed input pipeline ids fall back to `v1` without interrupting job creation.

Analysis job input ticker fields use safe text fallback before lifecycle creation, so malformed or empty input tickers return safe payloads without creating or enqueueing unknown jobs.

Analysis job input force flags use bool-safe fallback before lifecycle creation, so malformed force truthiness falls back to non-force job creation without interrupting create responses.

Analysis job input arbitrary object force flags use conservative bool fallback before lifecycle creation, so custom object truthiness cannot trigger forced refresh or append force-refresh queue arguments.

Analysis job input binary or container force flags use conservative bool fallback before lifecycle creation, so malformed binary or collection payloads do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input string force flags use bool-text fallback before lifecycle creation, so string `false`, `0`, `no`, or blank values do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input non-finite numeric force flags use finite-number fallback before lifecycle creation, so `NaN` or infinite values do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input numeric force flags accept only explicit zero or one before lifecycle creation, so fractional or out-of-range numbers do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input Fraction force flags use the same explicit zero-or-one fallback before lifecycle creation, so fractional exact numeric values do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input Decimal force flags use the same explicit zero-or-one fallback before lifecycle creation, so fractional exact numeric values do not trigger forced refresh or append force-refresh queue arguments through float precision loss.

Analysis job input complex force flags use conservative bool fallback before lifecycle creation, so complex numbers do not trigger forced refresh or append force-refresh queue arguments.

Analysis job input resume flags use bool-safe fallback before lifecycle creation, so malformed resume truthiness falls back to active-job attachment without interrupting create responses.

Analysis job lifecycle created flags use explicit boolean selection before queue decisions, so malformed created flag truthiness cannot interrupt create responses or requeue unknown lifecycle states.

Analysis job queue task identity fields use safe text fallback before RQ task id construction, so malformed job ids cannot leak Python object representations into queue task keys.

Analysis job queue task identity fields use path-segment fallback before RQ task id construction, so path-like, encoded, or whitespace job ids cannot create ambiguous queue task keys.

Analysis job queue task lookup ids use safe text fallback before queue adapter lookup, so malformed task ids cannot leak Python object representations into RQ `fetch_job` calls.

Analysis job queue task status fields use safe text fallback before RQ active-state classification, so malformed RQ status values cannot interrupt queue recovery or duplicate-job checks and fall back to inactive.

Analysis job queue task status fetch failures return unknown inspection results before queue recovery or duplicate-job checks, so transient RQ status lookup errors do not interrupt create responses or get misclassified as confirmed missing tasks.

Analysis job queue task status accessors return unknown inspection results before queue recovery or duplicate-job checks, so malformed RQ job status adapters cannot interrupt task lookup.

Analysis job queue task status properties return unknown inspection results before queue recovery or duplicate-job checks, so malformed fallback RQ status fields cannot interrupt task lookup.

Analysis job queue metadata fetch failures return unknown inspection results before queue recovery or duplicate-job checks, so malformed queue adapters cannot interrupt create responses before task lookup starts.

Analysis job child queue fetch-job metadata failures return unknown inspection results before queue recovery or duplicate-job checks, so malformed nested queue adapters cannot interrupt multi-queue task lookup.

Analysis job queue deduplication uses identity-only comparison before multi-queue task lookup, so malformed child queue equality hooks cannot interrupt primary queue inspection.

Analysis job queue enqueue failure messages use safe text fallback before job-store error updates, so malformed queue exception strings cannot interrupt create responses or block error events.

Analysis job legacy create fallback identity fields use safe text fallback before queue enqueue, so malformed fallback job ids return empty job payloads instead of interrupting create responses or enqueueing unknown tasks.

Analysis job legacy create fallback queue enqueue failure messages use safe text fallback before job-store error updates, so malformed fallback queue exception strings cannot interrupt create responses or block terminal error events.

Analysis job legacy create fallback serializer fields use JSON-safe fallback before response shaping, so malformed fallback serializer field values do not interrupt legacy create responses or leak non-JSON payloads.

Analysis SSE setup job rows use mapping-safe fallback before stream creation, so missing or malformed non-mapping job-store rows return not found instead of interrupting the API response.

Analysis SSE intro identity fields use safe text fallback before output, so malformed setup ticker or pipeline values cannot interrupt the initial job event.

Legacy analysis job rows use mapping-safe fallback before stream setup or cancellation, so malformed requested-job or cancel-job rows fall back to the active job or return not found instead of interrupting compatibility endpoints.

Legacy analysis requested-job identity validation uses safe text fallback before stream setup, so malformed requested job ids fall back to the active job instead of interrupting compatibility streams.

Legacy analysis requested-job ticker validation uses safe text fallback before stream setup, so malformed requested ticker values fall back to the active job instead of interrupting compatibility streams.

Legacy analysis requested-job pipeline validation uses safe text fallback before stream setup, so malformed requested pipeline values fall back to the active job instead of interrupting compatibility streams.

Legacy analysis active-job identity validation uses safe text fallback before stream setup, so malformed active job ids fall through to job creation instead of interrupting compatibility streams.

Legacy analysis create handler results use mapping-safe fallback before stream setup, so malformed create adapter payloads fall through to legacy job creation and enqueue instead of interrupting compatibility streams.

Legacy analysis fallback queue enqueue failure messages use safe text fallback before stream setup, so malformed queue exception strings cannot interrupt compatibility streams or block terminal error events.

Legacy analysis API key readiness checks use strict bool fallback before stream setup, so malformed truthy readiness payloads fall back to the missing-key error stream instead of creating analysis jobs.

Legacy analysis missing API key messages use safe text fallback before SSE output, so malformed setup-message payloads cannot interrupt compatibility error streams.

Legacy analysis normalized pipeline ids use safe text fallback before stream setup, so malformed pipeline normalization payloads fall back to `v1` instead of interrupting compatibility streams.

Legacy analysis intro pipeline sequence values use sequence- and text-safe fallback before stream output, so malformed pipeline metadata cannot interrupt compatibility streams.

Legacy analysis intro pipeline label values use safe text fallback before stream output, so malformed pipeline label metadata cannot interrupt compatibility streams.

Legacy analysis intro agent total values use integer-safe fallback before stream output, so malformed binary or boolean agent-count metadata cannot interrupt compatibility streams or become synthetic counts.

Legacy analysis resume id parsing treats negative `Last-Event-ID` values as malformed before stream replay, so negative reconnect cursors fall back instead of reaching job-store event queries.

Legacy analysis cancel normalized pipeline ids use safe text fallback before cancellation requests, so malformed pipeline normalization payloads fall back to `v1` instead of hiding cancellable compatibility jobs.

Legacy analysis cancel ticker validation uses safe text fallback before cancellation requests, so malformed cancel job ticker values return not found instead of interrupting compatibility cancellation.

Legacy analysis cancel pipeline validation uses safe text fallback before cancellation requests, so malformed cancel job pipeline values return not found instead of interrupting compatibility cancellation.

Legacy analysis cancel result handling uses bool-safe fallback before response shaping, so malformed cancellation adapter results return not found instead of interrupting compatibility cancellation.

Analysis SSE resume id parsing ignores malformed `since_id` values and falls back to `Last-Event-ID` or `last_event_id`, so reconnect setup is not interrupted by malformed resume query values.

Analysis SSE resume id parsing treats negative `since_id`, `Last-Event-ID`, and `last_event_id` values as malformed, so negative cursors fall back instead of reaching job-store event queries.

Analysis SSE resume id parsing treats boolean `since_id`, `Last-Event-ID`, and `last_event_id` values as malformed, so boolean cursors fall back instead of being coerced to event id 0 or 1.

Analysis SSE stream replay payloads use mapping-safe fallback before output, so malformed non-mapping job-store events become warning status events and do not interrupt later terminal events.

Analysis SSE stream replay event rows use mapping-safe fallback before output, so malformed non-mapping job-store rows become warning status events and do not interrupt later terminal events.

Analysis SSE stream replay event id fields use integer-safe fallback before output, so malformed boolean or binary job-store event ids become warning status events and cannot advance analysis stream cursors.

Analysis SSE stream replay payload type fields use safe text fallback before output, so malformed non-string event types become warning status events and cannot interrupt replay output.

Analysis SSE stream replay message fields use safe text fallback before output, so malformed boolean, binary, or container messages cannot interrupt replay output.

Analysis SSE stream replay control fields use safe text fallback before output, so malformed phase or level payloads cannot interrupt replay output.

Analysis SSE stream replay done identity fields use safe text fallback before output, so malformed filename or pipeline identity payloads cannot interrupt replay output.

Analysis SSE stream replay report artifact filename fields use safe text fallback before output, so malformed Markdown or data snapshot filename payloads cannot interrupt report_done replay output.

Analysis SSE stream replay progress text fields use safe text fallback before output, so malformed name, detail, or pipeline label payloads cannot interrupt replay output.

Analysis SSE stream replay telemetry text fields use safe text fallback before output, so malformed node name, model, status, or error payloads cannot interrupt replay output.

Analysis SSE stream replay telemetry metric fields use finite-float, integer-, and bool-safe fallback before output, so malformed latency, retry count, or quality-gate payloads cannot interrupt replay output.

Analysis job telemetry setup rows use mapping-safe fallback before diagnostics response shaping, so missing or malformed job-store rows return not found instead of exposing telemetry for invalid jobs.

Analysis job telemetry serializer results use mapping-safe fallback before diagnostics response shaping, so malformed telemetry adapter payloads return an empty telemetry list instead of leaking malformed responses.

Analysis job telemetry serializer fields use JSON-safe fallback before diagnostics response shaping, so malformed telemetry adapter field values do not interrupt diagnostics responses or leak non-JSON payloads.

Analysis job telemetry request ids use safe text fallback before diagnostics store lookup and response shaping, so malformed telemetry request ids cannot interrupt diagnostics responses or leak non-JSON payloads.

Analysis node telemetry row collections use iterable-safe fallback before response shaping, so missing or malformed telemetry store result collections become empty telemetry lists instead of interrupting diagnostics.

Analysis node telemetry row collection iterators preserve valid rows before iteration failures, so partial telemetry store result failures do not erase already available diagnostics evidence.

Analysis node telemetry rows use mapping-safe fallback before response shaping, so malformed telemetry store rows become safe empty telemetry rows instead of interrupting diagnostics.

Analysis node telemetry text fields use safe text fallback before diagnostics response shaping, so malformed telemetry job id, ticker, pipeline, node name, model, or status values cannot interrupt diagnostics payloads or leak non-JSON values.

Analysis node telemetry timestamp fields use conservative object fallback before diagnostics response shaping, so arbitrary numeric-like objects cannot synthesize started or finished diagnostics timestamps through conversion methods.

Analysis node telemetry metric fields use integer- and bool-safe fallback before diagnostics response shaping, so malformed telemetry id, latency, retry count, token count, cache hit, or quality gate values cannot interrupt diagnostics payloads or leak non-JSON values.

Analysis node telemetry optional metric fields reject fractional numeric values before diagnostics response shaping, so id, latency, and token count diagnostics cannot be silently truncated from non-integral payloads.

Analysis node telemetry optional metric fields reject fractional exact numeric values before diagnostics response shaping, so Decimal or Fraction id, latency, and token count diagnostics cannot be rounded into synthetic integers through float precision loss.

Analysis node telemetry optional metric fields use conservative object fallback before diagnostics response shaping, so arbitrary numeric-like objects cannot synthesize id, latency, or token count diagnostics through conversion methods.

Analysis node telemetry optional metric fields reject negative values before diagnostics response shaping, so id, latency, and token count diagnostics cannot leak impossible negative counters.

Analysis node telemetry retry count fields reject fractional numeric values before diagnostics response shaping, so retry diagnostics cannot be silently truncated from non-integral payloads.

Analysis node telemetry retry count fields reject negative values before diagnostics response shaping, so retry diagnostics cannot leak impossible negative counters.

Analysis node telemetry bool fields use strict bool fallback before diagnostics response shaping, so binary or container cache-hit and quality-gate values stay false unless they are explicit booleans, accepted truthy strings, or explicit numeric zero or one values.

Analysis node telemetry bool numeric fields accept only explicit zero or one before diagnostics response shaping, so out-of-range cache-hit or quality-gate numbers cannot be misreported as true diagnostics.

Analysis node telemetry bool exact numeric fields use the same explicit zero-or-one contract before diagnostics response shaping, so Decimal or Fraction cache-hit and quality-gate values cannot be misreported through truthiness.

Analysis node telemetry arbitrary object bool fields use conservative fallback before diagnostics response shaping, so custom object truthiness cannot mark cache-hit or quality-gate diagnostics as true.

Analysis SSE stream replay metadata fields use snapshot-safe fallback before output, so malformed nested metadata payloads cannot interrupt replay output.

Analysis SSE stream replay structured report fields use snapshot-safe fallback before output, so malformed data trust or audit payloads cannot interrupt report_done or done replay output.

Analysis SSE stream replay done aggregate fields use snapshot-safe fallback before output, so malformed filenames, report collection, or pipeline sequence payloads cannot interrupt done replay output.

Analysis SSE stream replay workflow retry thread ids use safe text fallback before output, so malformed retry checkpoint thread identifiers cannot interrupt workflow retry replay output.

Analysis SSE stream replay count fields use integer-safe fallback before output, so malformed current, total, agent number, or pipeline-local count payloads cannot interrupt replay output.

Analysis SSE stream replay pipeline count fields use integer-safe fallback before output, so malformed pipeline index, agent total, or agent offset payloads cannot interrupt replay output.

Analysis SSE terminal fallback error messages use safe text fallback before output, so malformed job error fields cannot interrupt synthesized error events.

Analysis SSE terminal fallback cancellation messages use safe text fallback before output, so malformed cancelled job error fields cannot interrupt synthesized cancelled events.

Analysis SSE terminal fallback done identity fields use safe text fallback before output, so malformed job filename or pipeline fields cannot interrupt synthesized done events.

Analysis SSE terminal polling status checks use safe text fallback before terminal fallback, so malformed job status fields cannot interrupt polling or synthesize terminal events from untrusted status values.

Analysis SSE terminal fallback persistence checks use mapping-safe event rows before appending synthesized terminal events, so read-only job-store rows do not trigger duplicate fallback persistence.

Analysis SSE event collections use sequence-safe fallback before replay and terminal persistence checks, so malformed job-store collection payloads do not interrupt terminal fallback output.

Analysis SSE missing or empty job rows after stream setup emit terminal error fallbacks, so operational cleanup or empty job-store rows do not leave clients with only the intro event or heartbeat pings.

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
- `snapshot_integrity.status = verified` means the current `.data.json` content matches its recorded snapshot hash; `invalid` blocks automatic reuse and enters the report quality repair queue, while `unverified` keeps legacy or hashless snapshots in warning state.
- Report preview reading boundaries include snapshot integrity mismatch details when `snapshot_integrity.status = invalid`, so operators see the concrete hash evidence before opening the full report.
- Report preview reading boundaries derive a `snapshot_hash mismatch` detail from invalid snapshot integrity hashes when `hash` and `expected_hash` disagree but `errors` is missing, so preview notices keep hash evidence visible.
- Report preview reading boundaries prefer hash mismatch details over default generic snapshot integrity errors from the same record, so same-record hash evidence is not hidden by boilerplate blocker text.
- Report preview reading boundaries treat `snapshot_integrity.valid=false` as blocked even when status text is non-invalid, so contradictory snapshot metadata cannot mark a hash mismatch as ready to use.
- Report preview reading boundaries remove default generic snapshot integrity blocker text when the same error list contains specific provider or hash details, so preview notices show the actionable failure reason before opening the full report.
- Report preview reading boundaries deduplicate repeated snapshot integrity error details before display, so preview notices show each provider or hash detail once while preserving first-seen order.
- Report artifacts may use partitioned、分層的 `backend/output/YYYY-MM/TICKER/` storage or a legacy flat path; `verify-snapshots` and `storage-summary` 會遞迴掃描 both locations and report relative storage keys while ignoring symlink files.
- Report persistence accepts mapping-safe data snapshot payloads before saving `.data.json` and indexing metadata, so immutable snapshots preserve the same report confidence metadata in storage, index handoff, and API return payloads.
- Report refresh diffs accept mapping-safe data snapshot payloads before comparing data trust and source audit status, so immutable snapshots still show accurate stale-to-fresh and provider recovery evidence in preview responses.
- Report refresh stale-source detection accepts mapping-safe data snapshot payloads and source audit rows, so immutable snapshots with fresh high-frequency source evidence do not incorrectly mark market data or catalysts as stale.
- Report refresh source audit sequences treat lookup iterator failures as native-sequence fallbacks before stale-source classification, so malformed `source_audit` list wrappers cannot hide fresh market data or catalyst audit evidence.
- Report refresh source audit sequences treat lookup iterator creation failures as native-sequence fallbacks before stale-source classification, so malformed `source_audit` list wrappers cannot hide fresh market data or catalyst audit evidence before iteration starts.
- Report refresh source audit rows use Mapping traversal when `.items()` iterables fail lookup before stale-source classification, so readable source audit rows still preserve fresh market data or catalyst evidence.
- Report refresh source audit rows skip lookup item unpack failures before stale-source classification, so one malformed `.items()` pair cannot hide later fresh market data or catalyst fields in the same row.
- Report refresh source audit rows skip lookup key hash failures before stale-source classification, so one malformed `.items()` key cannot hide later fresh market data or catalyst fields in the same row.
- Report refresh source audit rows skip Mapping traversal key hash failures before stale-source classification, so one malformed mapping key cannot hide later fresh market data or catalyst fields when `.items()` access has already fallen back to key traversal.
- Report refresh source audit timestamps use safe text conversion instead of truthiness checks, so valid but falsey timestamp wrappers still preserve fresh source evidence.
- Report refresh refreshed-data payloads accept mapping-safe provider/cache responses before snapshot rebuild, so read-only data wrappers preserve refreshed prices, source audit rows, and trust metadata instead of being treated as fetch failures.
- Report rerun refreshed-data payloads accept mapping-safe provider/cache responses before full-pipeline reruns, so read-only refreshed data wrappers reach the pipeline runner with prices, source audit rows, and trust metadata intact.
- Report rerun existing snapshot data payloads use mapping-safe snapshot normalization before full-pipeline reruns, so read-only source audit and trust wrappers become pipeline-safe mutable data.
- Report final-recommendation rerun context data uses mapping-safe snapshot normalization before the final agent runs, so read-only source audit and trust wrappers remain editable for final rerun metadata.
- Report final-recommendation rerun context accepts mapping-safe rerun context payloads before Markdown fallback, so read-only previous-agent analyses do not force Markdown recovery or block partial reruns.
- Report rerun renderer snapshots use mapping-safe snapshot normalization before rerun metadata and integrity hashing, so read-only renderer payloads keep source audit, trust metadata, and valid snapshot hashes when saved.
- Report rerun render contexts use mapping-safe top-level normalization before partial-rerun metadata is added, so read-only pipeline contexts can still reach the renderer and saved snapshot with rerun provenance intact.
- Report rerun progress events accept mapping-safe payloads before job-store persistence, so read-only progress wrappers preserve phase, message, count, scope, and source filename for the rerun stream.
- Report rerun progress event details use snapshot-safe normalization before job-store persistence, so nested read-only source audit or metadata payloads remain serializable in rerun streams.
- Report rerun scalar progress fallbacks use integer-safe conversion before job-store persistence, so malformed progress counters cannot interrupt rerun streams or leak boolean counts.
- Report rerun progress event scope fields use safe text fallback before job-store persistence, so malformed progress scope payloads cannot interrupt rerun streams.
- Report rerun progress event control fields use safe text fallback before job-store persistence, so malformed type, phase, or level payloads cannot leak non-string event metadata into rerun streams.
- Report rerun progress event count fields use integer-safe normalization before job-store persistence, so malformed current or total payloads cannot leak boolean or binary progress counters into rerun streams.
- Report rerun progress event message fields use safe text fallback before job-store persistence, so malformed boolean, binary, or container messages cannot leak non-text operator copy into rerun streams.
- Report rerun progress event name fields use safe text fallback before job-store persistence, so malformed boolean, binary, or container names cannot leak non-text progress labels into rerun streams or logs.
- Report rerun progress event detail fields use safe text fallback before job-store persistence, so malformed boolean, binary, or container detail payloads cannot leak non-text runtime log suffixes into rerun streams or logs.
- Report rerun progress event agent number fields use integer-safe normalization before job-store persistence, so malformed agent identity payloads cannot leak boolean or binary agent numbers into rerun streams or job observability.
- Report rerun progress event pipeline identity fields use safe text fallback before job-store persistence, so malformed pipeline id or label payloads cannot leak boolean, binary, or container pipeline identities into rerun streams or job observability.
- Report rerun progress event metadata fields use mapping-safe normalization before job-store persistence, so malformed scalar or sequence metadata cannot leak non-mapping observability payloads into rerun streams or job observability.
- Report rerun API key failure events preserve source filenames before job-store persistence, so setup failures remain traceable to the original report in rerun streams.
- Report rerun queue enqueue failure events preserve source filenames before job-store persistence, so queue submission failures remain traceable to the original report in rerun streams.
- Report rerun queue enqueue failure messages use safe text fallback before job-store persistence, so malformed queue exception strings cannot interrupt rerun enqueue responses or block terminal error events.
- Report rerun attached job created flags use explicit boolean selection before enqueue decisions, so malformed created flag truthiness cannot interrupt rerun enqueue responses or trigger queue submissions from untrusted flag values.
- Report rerun attached job status checks use safe text fallback before queue recovery, so malformed existing job status rows do not interrupt rerun enqueue responses or trigger recovery from untrusted status values.
- Report rerun stream replay payloads use mapping-safe fallback before SSE output, so malformed non-mapping event payloads become warning status events instead of interrupting rerun streams.
- Report rerun stream replay payload type fields use safe text fallback before SSE output, so malformed non-string type controls become warning status events instead of interrupting rerun streams.
- Report rerun stream replay control fields use safe text fallback before SSE output, so malformed phase or level payloads cannot interrupt rerun streams.
- Report rerun stream replay message fields use safe text fallback before SSE output, so malformed boolean, binary, or container messages cannot interrupt rerun streams.
- Report rerun stream replay progress text fields use safe text fallback before SSE output, so malformed name or detail payloads cannot interrupt rerun streams.
- Report rerun stream replay filename fields use safe text fallback before SSE output, so malformed filename, markdown filename, data filename, or source filename payloads cannot interrupt rerun streams.
- Report rerun stream replay context fields use safe text fallback before SSE output, so malformed rerun scope, scope label, pipeline id, or pipeline label payloads cannot interrupt rerun streams.
- Report rerun stream replay count fields use integer-safe fallback before SSE output, so malformed current, total, or agent number payloads cannot interrupt rerun streams or leak binary counters.
- Report rerun stream replay status code fields use integer-safe fallback before SSE output, so malformed status code payloads cannot interrupt rerun streams or leak binary counters.
- Report rerun stream replay structured fields use snapshot-safe normalization before SSE output, so malformed data trust, partial rerun, metadata, or details payloads cannot interrupt rerun streams.
- Report rerun stream replay event rows use mapping-safe fallback before SSE output, so malformed non-mapping job-store rows become warning status events and do not interrupt later terminal events.
- Report rerun stream replay event id fields use integer-safe fallback before SSE output, so malformed boolean or binary job-store event ids become warning status events and cannot advance rerun stream cursors.
- Report rerun stream event collections use sequence-safe fallback before replay and terminal fallback checks, so malformed job-store collection payloads do not interrupt terminal fallback output.
- Report rerun stream resume id parsing treats negative `Last-Event-ID` values as malformed, so negative header cursors fall back before reaching job-store event queries.
- Report rerun stream missing job rows after SSE setup emit and persist terminal error fallbacks, so operational cleanup or missing job-store rows do not leave rerun streams or reconnects with only the intro event.
- Report rerun stream malformed job rows after SSE setup emit terminal error fallbacks, so corrupted job-store rows do not interrupt rerun streams after setup validation has already passed.
- Report rerun stream terminal fallback events preserve rerun scope and source filenames before job-store persistence, so synthesized error or cancelled events remain traceable to the original report in rerun streams.
- Report rerun stream terminal fallback messages and filenames use safe text normalization before job-store persistence, so malformed job rows cannot interrupt synthesized done, error, or cancelled SSE events.
- Report rerun stream terminal polling status checks use safe text fallback before terminal fallback, so malformed job status fields cannot interrupt polling or synthesize terminal events from untrusted status values.
- Report rerun stream terminal fallback scopes use safe text fallback before job-store persistence, so empty rerun pipeline scope rows default to final recommendation instead of losing rerun context.
- Report rerun stream task validation uses safe text fallback before SSE setup, so malformed rerun pipeline id rows return not found instead of interrupting the API response.
- Report rerun stream setup job rows use mapping-safe fallback before task validation, so malformed non-mapping job rows return not found instead of interrupting the API response.
- Report rerun stream task ticker validation uses safe text fallback before SSE setup, so malformed rerun job ticker rows return not found instead of interrupting the API response.
- Report rerun cancel job rows use mapping-safe fallback before cancellation requests, so malformed non-mapping job rows return not found instead of interrupting the API response.
- Report rerun cancel task validation uses safe text fallback before cancellation requests, so malformed rerun pipeline id rows return not found instead of interrupting the API response.
- Report rerun cancel task ticker validation uses safe text fallback before cancellation requests, so malformed rerun job ticker rows return not found instead of interrupting the API response.
- Report rerun source filename fields use safe text normalization before job-store persistence, so malformed source filename payloads cannot interrupt rerun streams or terminal events.
- Report rerun cancellation messages use safe text fallback before job-store persistence, so malformed cancellation exception strings cannot interrupt terminal cancelled events.
- Report rerun invalid scope errors are handled inside the job-store terminal event flow, so malformed or unsupported rerun scope payloads still mark the job error and remain visible in rerun streams.
- Report rerun HTTP error details use safe text fallback before job-store persistence, so malformed exception detail payloads cannot interrupt terminal error events.
- Report rerun HTTP error status codes use integer-safe fallback before job-store persistence, so malformed status code payloads cannot interrupt terminal error events.
- Report rerun unexpected exception messages use safe text fallback before job-store persistence, so malformed exception string conversion cannot mask the original error type or block terminal error events.
- Report rerun completion results use mapping-safe snapshot normalization before job-store events, so read-only data trust, partial rerun, and metadata payloads remain serializable in report_done and done events.
- Report rerun completion structured result fields use mapping-safe normalization before job-store events, so malformed data trust or partial-rerun payloads cannot leak non-mapping result context into report_done and done events.
- Report rerun completion identity fields use safe text normalization before job-store events, so malformed filename, markdown/data filename, scope label, or pipeline id values cannot leak boolean or binary identity payloads into rerun streams.
- Report refresh rerun checks accept mapping-safe data snapshot payloads before comparing decision-relevant fields, so immutable snapshots with changed prices, valuation inputs, trust reasons, or failure metadata still mark conclusions as needing rerun.
- `decision_freshness.status = current` means the investment conclusion was generated from the current snapshot.
- `decision_freshness.status = needs_rerun` means the snapshot was refreshed after the HTML/Markdown conclusion was written. Treat the old conclusion as historical until rerun finishes.
- Watchlist items use the same signal. Items marked `需重跑` are sorted first so the operator can rerun the stale conclusion before reviewing lower-priority names.

## Decision Tracking And Backtests

The decision tracking scheduler runs after the daily tracking refresh. It scans reports whose generated date has reached the 3, 6, or 12 month horizon, fetches historical market closes, and writes one idempotent result per `(report_filename, horizon_months)`.

Backtest results are visible in `報告與維運` under `決策回測`. The panel shows hit rate, average strategy ROI, horizon breakdown, and the latest evaluated reports. A `買入/買進` call earns market ROI, `避免/強烈放空` earns inverse market ROI, and `持有` is treated as a range call. A duplicate run on the same day is skipped by the unique result key.

The daily dashboard also builds an outcome calibration ledger from recent backtest details and report metadata. Use it to distinguish a miss caused by weak data quality or insufficient report evidence from a miss where the thesis itself was likely wrong. Missing report metadata stays `unknown` rather than being over-attributed.

When provider health is degraded, the daily dashboard includes a provider impact ledger. Core-source critical impact can block blind reruns and recommend waiting for provider recovery; optional-source critical impact is only a monitor notice. This distinction prevents rerunning reports repeatedly while the same core source is still unavailable.

Use `decision_queue.items` as the daily operating order. It ranks free-mode blockers, blocked report repairs, provider recovery waits, notification delivery repair, due backtests, reruns, model route budget warnings, watchlist runs, and screener candidates in one top-five queue. A due backtest can outrank a routine rerun, while blocked report quality, core provider impact, or failed notification delivery can still win over watchlist triggers. Report repair actions preserve `blocks_auto_rerun` and `reason_codes`, so an operator or automation can see why a report is blocked without turning it into a blind rerun. Daily decision queue report repair action `title` fields use string-safe conversion before priority ordering, so malformed title truthiness cannot interrupt the daily queue or hide which report needs operator attention. Daily decision queue report repair action `detail` fields use string-safe conversion before priority ordering, so malformed detail truthiness cannot interrupt the daily queue or erase concrete blocked-repair evidence. Daily decision queue report repair `filename` and `report_filename` aliases use string-safe selection before priority ordering, so malformed filename truthiness cannot interrupt the daily queue or erase artifact identity. The operator summary panel and the watchlist `今日工作台` both show the top queue, priority/source context, and how many secondary items remain so the UI does not hide work just because only the top few tasks are shown. `decision_queue.summary` exposes `source_labels` and `source_texts` beside raw `sources`, so consumers can render readable source distribution without rebuilding the source label map. `fix_notification_delivery` appears there as source `通知通道` with a `查看通知通道` CTA that opens the ops maintenance area, making delivery failure visible without relying on the failed external channel. The item preserves `failure_reason_counts` and `attention_contexts`, and adds a reason summary to `detail`, so operators can distinguish timeout, auth, rate limit, configuration, or network failures and see affected source/report context before opening raw audit rows. The operator summary panel and watchlist `今日工作台` render the same attention context summary in action detail, so affected ticker/report/CTA context stays visible before the maintenance panel opens. When no real work exists, the queue may still include a `monitor` fallback item for UI compatibility, but `summary.total_actionable` remains `0` and should not be rendered as pending work, counted as a quick action, or sent as a notification. Notification messages use `decision_queue.items` as the primary source when available, preserve source, priority score, ticker, filename, and pipeline context for real queue actions, and expose `queue_context` so external channels can see total actionable work, displayed count, secondary count, top priority, source distribution, `source_labels` for human-readable rendering while preserving raw source keys, and `source_texts` for label-plus-raw-key display while preserving raw source keys. `notification_plan.messages` and `delivery_outbox` preserve `reason_codes` from report repair queue actions, keeping blocked-repair causes visible to external sender channels and persisted delivery context. `notification_plan.delivery_outbox` also preserves report repair action `detail`, keeping concrete blocked-repair evidence such as snapshot hash mismatch visible to external sender channels and persisted delivery context. `fix_notification_delivery` is a UI/ops repair action with `suppress_notification = true`; it remains visible in the queue but does not create `notification_plan.messages` or `delivery_outbox`, avoiding attempts to notify about a broken external notification channel through that same channel. Notification messages also preserve action-specific metadata such as model `route` / `warning_id`, due `horizon_months`, `recommended_action`, `blocks_auto_rerun`, `severity`, and `action_label` when those fields exist. They include `target_panel` and `target_tab` so downstream channels can open the same provider SLA, decision backtest, model route health, market screener, or watchlist panel used by operator summary quick actions, plus `operator_action` and `operator_action_label` so the channel can render the same CTA semantics as the in-app action list. Each message includes `queue_rank`, `queue_displayed_count`, and `is_top_priority`, computed after excluding `monitor`, so external channels can preserve the same displayed order without re-sorting. Each message also includes `dedupe_key` and `message_id` based on stable identifiers such as source, type, report, route, horizon, and pipeline; title, detail, and priority are intentionally excluded so text or rank changes do not duplicate the same underlying action. `delivery_outbox` then creates one pending audit entry for each enabled channel and message pair, carrying `channel_id`, `message_id`, `dedupe_key`, `delivery_key`, `delivery_status`, and `attempt_count`; disabled channels stay out of the outbox and remain visible through `channels[].missing_env`. External senders should call `reconcile_outbox_with_audit()` before sending so entries already marked sent return `already_sent = true` and `should_send = false`; failed entries observe the retry backoff before the next send attempt and return `skip_reason = retry_wait`, `retry_wait_seconds`, `next_retry_at`, and `should_send = false` while waiting. Reconciled entries also expose `audit_context`, copied from the persisted audit context snapshot, so sender logs or repair screens can recover prior source, report, CTA, and queue-rank context even when the current outbox entry is minimal. After the backoff window, failed entries remain retryable until the default retry budget is exhausted, then return `retry_exhausted = true`, `skip_reason = retry_exhausted`, and `should_send = false`. Sender attempts should then be recorded through `notification_delivery_audit`, which stores one row per `delivery_key` in `operational.sqlite3` and updates status, attempt count, last error, response id, success timestamp, and a context snapshot copied from the outbox entry without touching report index state. The context snapshot lets local triage recover source, ticker, report filename, target panel/tab, CTA, and queue rank from audit history even when the original daily dashboard payload is gone. The audit summary includes `retry_exhausted_count` so operators can spot channels that need configuration or provider repair instead of silent infinite retries.

Daily decision queue report repair action `recommended_action` fields use string-safe conversion before action-type mapping, so malformed action truthiness cannot interrupt the daily queue or hide safe refresh, rerun, wait, or manual-review intent.

Daily decision queue display limits use integer-safe conversion before slicing rendered items, so malformed limit truthiness cannot interrupt daily queue assembly or inflate secondary-count calculations.

Daily decision queue integer conversions ignore malformed conversion failures before priority, horizon, display, and summary calculations, so broken numeric payloads fall back instead of interrupting queue assembly.

Daily decision queue integer conversions treat boolean values as malformed before priority, horizon, display, and summary calculations, so boolean payload drift cannot become synthetic `1` or `0` queue values.

Daily decision queue integer conversions treat fractional float values as malformed before priority, horizon, display, and summary calculations, so decimal payload drift cannot be silently truncated into queue values.

Daily decision queue integer conversions treat fractional exact numeric values as malformed before priority, horizon, display, and summary calculations, so Decimal or Fraction payload drift cannot be silently truncated into queue values.

Shared integer conversion treats boolean values as malformed numeric input before queue, repair, audit, and observability count projection, so boolean payload drift cannot become synthetic `1` or `0` counts.

Shared integer conversion treats fractional float values as malformed numeric input before queue, repair, audit, and observability count projection, so decimal payload drift cannot be silently truncated into synthetic counts.

Shared integer conversion treats fractional exact numeric values as malformed numeric input before queue, repair, audit, and observability count projection, so Decimal or Fraction payload drift cannot be silently truncated into synthetic counts.

Shared text conversion treats boolean values as malformed text input before queue, repair, audit, and notification payload projection, so boolean payload drift cannot become visible `"True"` or `"False"` strings.

Shared text conversion treats binary values as malformed text input before queue, repair, audit, and notification payload projection, so bytes payload drift cannot become visible Python byte-literal strings.

Shared text conversion treats memory view values as malformed text input before queue, repair, audit, and notification payload projection, so buffer-view payload drift cannot become visible nondeterministic memory-address strings.

Report quality repair queue identity fields use shared text conversion before repair action projection, so malformed ticker, filename, report filename, or pipeline fields cannot bypass the shared boolean, binary, and memory-view text guards.

Provider impact identity fields use shared text conversion before provider recovery projection, so malformed ticker, filename, report filename, or pipeline fields cannot bypass the shared boolean, binary, and memory-view text guards.

Data trust scoring audit source names use shared text conversion before trust reason-code projection, so malformed source audit keys cannot become synthetic optional-source errors or leak boolean, binary, or memory-view text into report trust metadata.

Data trust provider SLA trust metadata uses shared text conversion before merging existing status, reason codes, and notes, so malformed boolean, binary, or memory-view values cannot leak into report trust metadata.

Daily decision queue notification delivery summary maps use mapping-safe conversion before repair action projection, so immutable sender audit summary payloads cannot hide a visible notification-channel repair action.

Daily decision queue notification delivery count fields use integer-safe conversion before repair action projection, so malformed sender audit counts cannot interrupt queue assembly or hide a visible notification-channel repair action.

Daily decision queue notification delivery count fields and count maps use strict count conversion before repair action projection, so boolean, binary, or memory-view failed, exhausted, channel, and reason counts cannot become synthetic delivery-failure evidence.

Daily decision queue notification delivery health fields use string-safe conversion before warning-state checks, so malformed sender audit health truthiness cannot interrupt queue assembly or hide a visible notification-channel repair action.

Daily decision queue notification delivery nested count maps use mapping-safe conversion before repair action projection, so immutable sender audit channel and failure-reason maps still preserve triage context.

Daily decision queue notification delivery channel count maps use dict-safe conversion before repair action projection, so malformed sender audit channel-count truthiness cannot interrupt queue assembly or erase visible channel distribution context.

Daily decision queue notification delivery failure reason maps use truthiness-safe detail rendering before repair action projection, so malformed sender audit failure-reason truthiness cannot interrupt queue assembly or erase timeout/auth triage context.

Daily decision queue notification delivery failure reason item access failures fall back to native dict items before repair action projection, so malformed sender audit reason-map accessors cannot interrupt queue assembly or erase valid timeout/auth reason summaries.

Daily decision queue notification delivery failure reason count values fall back to integer-safe rendering before repair action projection, so malformed count text cannot erase valid timeout/auth reason summaries when integer conversion still works.

Daily decision queue notification delivery failure reason unrenderable counts are omitted from reason detail before repair action projection, so malformed count values cannot create misleading `reason=... 0` summaries.

Daily decision queue notification delivery failure reason non-positive counts are omitted from reason detail before repair action projection, so zero or negative sender audit counts cannot appear as active timeout/auth reason summaries.

Daily decision queue notification delivery failure reason boolean counts are omitted from reason detail before repair action projection, so boolean sender audit flags cannot appear as numeric timeout/auth reason summaries.

Daily decision queue notification delivery failure reason fractional counts are omitted from reason detail before repair action projection, so decimal or fractional sender audit counts cannot be truncated into active timeout/auth reason summaries.

Daily decision queue notification delivery failure reason malformed keys are omitted from reason detail before repair action projection, so non-string or blank sender audit reason keys cannot appear as synthetic timeout/auth reason summaries.

Daily decision queue notification delivery failure reason raw keys are omitted from reason detail before repair action projection, so raw exception strings or non-canonical sender audit reason keys cannot bypass low-cardinality timeout/auth/network bucket rendering.

Daily decision queue notification delivery failure reason duplicate buckets are aggregated in reason detail before repair action projection, so casing or whitespace drift cannot duplicate timeout/auth/network summaries.

Daily decision queue notification delivery failure reason partial item failures fall back to native dict items before repair action projection, so sender audit dict subclasses that stop mid-iteration do not erase later valid timeout/auth/network reason summaries.

Daily decision queue notification delivery attention context iterator failures fall back to native sequence items before repair action projection, so malformed sender audit context list wrappers cannot interrupt queue assembly or erase valid affected ticker/report/CTA context.

Daily decision queue notification delivery attention context partial iterator failures fall back to native sequence items before repair action projection, so sender audit context list wrappers that stop mid-iteration do not erase later affected ticker/report/CTA context.

Daily decision queue notification delivery attention context tuple payloads are preserved before repair action projection, so immutable sender audit context batches still reach operator triage.

Daily decision queue notification delivery attention context mapping rows normalize to plain dicts before repair action projection, so immutable sender audit context rows and nested context maps remain JSON-friendly.

Daily decision queue notification delivery attention context dict subclasses normalize to plain dicts before repair action projection, so custom sender audit context wrappers do not leak into queue API payloads.

Daily decision queue notification delivery attention context nested mappings normalize recursively to plain dicts before repair action projection, so nested sender audit metadata remains JSON-friendly.

Daily decision queue notification delivery attention context nested mapping item failures fall back to native dict items before repair action projection, so malformed metadata wrappers cannot interrupt queue assembly or erase valid nested context.

Daily decision queue notification delivery attention context nested sequence iterator failures fall back to native sequence items before repair action projection, so malformed metadata list wrappers cannot erase valid nested triage tags or CTA evidence.

Shared sequence conversion treats lookup iterator failures as native-sequence fallbacks before queue, repair, refresh, and audit payload projection, so `KeyError` or `IndexError` from malformed list or tuple iterators cannot erase underlying sequence evidence.

Shared sequence conversion treats lookup iterator creation failures as native-sequence fallbacks before queue, repair, refresh, and audit payload projection, so `KeyError` or `IndexError` from malformed list or tuple `__iter__` access cannot erase underlying sequence evidence before iteration starts.

Daily decision queue report repair collections use iterator-safe dict-list conversion before repair action projection, so malformed repair collection truthiness cannot interrupt daily queue assembly or suppress later valid report repair rows.

Daily decision queue report repair partial iterator failures fall back to native dict-list items before repair action projection, so repair list wrappers that stop mid-iteration do not erase later valid report repair rows.

Daily decision queue report repair reason code partial iterator failures fall back to native text-list items before repair action projection, so reason-code list wrappers that stop mid-iteration do not erase later blocked-repair causes.

Shared mapping dict conversion normalizes dict subclasses to plain dict copies before queue, repair, and audit payload projection, so custom mapping wrappers do not leak into JSON-facing API responses while native dict fields remain readable.

Shared mapping dict conversion uses mapping-item traversal when mapping key iteration fails before queue, repair, and audit payload projection, so Mapping wrappers with readable `.items()` still preserve fields even when `keys()` or `__iter__()` are unavailable.

Shared mapping dict conversion uses Mapping traversal when `.items()` lookup fails before queue, repair, and audit payload projection, so Mapping wrappers with readable keys and item access still preserve fields when custom `.items()` accessors raise `KeyError` or `IndexError`.

Shared mapping dict conversion uses Mapping traversal when `.items()` iterables fail lookup before queue, repair, refresh, and audit payload projection, so Mapping wrappers with readable keys and item access still preserve fields when custom `.items()` iterable wrappers raise `KeyError` or `IndexError` during iterator creation.

Shared mapping dict conversion skips lookup item failures during Mapping traversal before queue, repair, and audit payload projection, so one broken key lookup cannot erase later valid fields from custom Mapping wrappers.

Shared mapping dict conversion skips lookup key hash failures during Mapping traversal before queue, repair, refresh, and audit payload projection, so one malformed mapping key cannot erase later valid fields after `.items()` fallback.

Shared mapping dict conversion preserves safely empty Mapping wrappers as plain empty dicts before queue, repair, and audit payload projection, so optional empty metadata stays distinct from malformed mapping access failures.

Shared mapping item conversion preserves partial dict-subclass items when native fallback is empty before queue, repair, and audit payload projection, so custom item wrappers that yield valid metadata before stopping do not erase that partial evidence.

Shared mapping item conversion skips lookup item unpack failures before queue, repair, refresh, and audit payload projection, so custom `.items()` wrappers cannot erase later valid fields when one item pair raises `KeyError` or `IndexError` during unpacking.

Shared mapping item conversion skips lookup key hash failures before queue, repair, refresh, and audit payload projection, so custom `.items()` wrappers cannot erase later valid fields when one item key raises `KeyError` or `IndexError` during hash validation.

Shared mapping item conversion skips string-like malformed item pairs before queue, repair, and audit payload projection, so malformed custom item wrappers cannot turn two-character strings into synthetic mapping fields.

Shared mapping item conversion skips unhashable malformed item keys before queue, repair, and audit payload projection, so custom mapping wrappers cannot crash plain-dict normalization with list-like keys while later valid fields remain available.

Daily decision queue ops payloads use type-safe fallback before notification delivery and route warning projection, so malformed ops truthiness cannot interrupt daily queue assembly or suppress later valid ops warning rows.

Daily decision queue route warning projection suppresses `slow_route` latency warnings while preserving `retry_storm`, `quality_gate_failures`, and future actionable route warnings, so p95 latency noise stays out of frontstage actions without hiding retry-failure evidence.

Daily decision queue free-mode violation lists use string-safe conversion before fix-free-mode action output, so direct queue callers cannot leak non-string paid-dependency labels or drop tuple violation evidence.

Daily decision queue free-mode can-run flags use bool-safe fallback before fix-free-mode action projection, so malformed `can_run_without_paid_keys` truthiness cannot interrupt queue assembly or hide paid-dependency repair actions.

Daily decision queue explicit backtest collections use iterator-safe dict-list conversion before due-item projection, so malformed `due_backtests` or `backtest_due` truthiness cannot interrupt daily queue assembly or suppress valid backtest due rows.

Daily decision queue backtest evaluation `details` use iterator-safe dict-list conversion before computed due checks, so malformed evaluation detail truthiness cannot interrupt daily queue assembly or make due reports look already evaluated.

Daily decision queue computed backtest report rows use iterator-safe dict-list conversion before due-date checks, so malformed report collection truthiness cannot interrupt daily queue assembly or hide reports that are due for backtest.

Daily decision queue computed backtest report artifact fields use string-safe conversion before evaluated-key and due-date checks, so malformed filename or report filename truthiness cannot interrupt computed backtest due detection or hide due reports.

Daily decision queue computed backtest report date fields use string- and float-safe conversion before due-date checks, so malformed date or timestamp truthiness cannot interrupt queue assembly or hide later valid due reports.

Daily decision queue backtest due action text fields use string-safe conversion before title, artifact identity, and pipeline projection, so malformed ticker, filename, report filename, or pipeline truthiness cannot interrupt backtest due output or leak non-string display fields.

Daily decision queue rerun report collections use iterator-safe dict-list conversion before stale-report action projection, so malformed rerun collection truthiness cannot interrupt daily queue assembly or suppress valid rerun report rows.

Daily decision queue watchlist collections use iterator-safe dict-list conversion before watchlist action projection, so malformed watchlist collection truthiness cannot interrupt daily queue assembly or suppress valid watchlist rows.

Daily decision queue screener candidate collections use iterator-safe dict-list conversion before candidate action projection, so malformed candidate collection truthiness cannot interrupt daily queue assembly or suppress valid screener candidate rows.

Daily decision queue screener candidate action text fields use string-safe conversion before title and detail projection, so malformed ticker, company name, or reason truthiness cannot interrupt candidate action output or leak non-string display fields.

Daily decision queue report repair action `ticker` fields use string-safe conversion before title and payload output, so malformed ticker truthiness cannot interrupt the daily queue or leak non-string report identity into queue consumers.

Daily decision queue rerun report action `ticker` fields use string-safe conversion before title and payload output, so malformed ticker truthiness cannot interrupt stale-report rerun ordering or leak non-string report identity into queue consumers.

Daily decision queue rerun report action `pipeline_id` fields use string-safe conversion before title and payload output, so malformed pipeline truthiness cannot interrupt stale-report rerun ordering or leak non-string report identity into queue consumers.

Daily decision queue rerun report `filename` and `report_filename` aliases use string-safe selection before dedupe and payload output, so malformed filename truthiness cannot interrupt stale-report rerun ordering or erase artifact identity.

Daily decision queue rerun report action `detail` fields use string-safe fallback before payload output, so malformed rerun reason truthiness cannot interrupt stale-report rerun ordering or erase concrete stale-snapshot evidence.

Daily decision queue report key `ticker` fields use string-safe conversion before dedupe, so malformed ticker truthiness cannot interrupt report repair or stale-report rerun skip-key matching.

Daily decision queue report key `pipeline_id` fields use string-safe conversion before dedupe, so malformed pipeline truthiness cannot interrupt report repair or stale-report rerun skip-key matching.

Daily decision dashboard report envelopes use mapping-safe conversion before row projection, so malformed envelope accessors cannot hide sampled reports, rerun evidence, repair actions, or provider impacts.

Daily decision dashboard report row collections use iterator-safe dict-list conversion before repair, rerun, and provider-impact aggregation, so falsey report-list wrappers cannot hide sampled reports or rerun evidence.

Daily decision dashboard rerun report `filename` and `report_filename` aliases use string-safe selection before rerun dedupe and payload output, so malformed filename truthiness cannot interrupt rerun-bucket aggregation or leak non-string artifact identity.

Daily decision dashboard rerun reason fields use string-safe fallback before `rerun_reports` payload output, so malformed freshness reason truthiness cannot interrupt rerun-bucket aggregation or erase stale-snapshot evidence.

Daily decision dashboard rerun freshness flags use bool-safe fallback before rerun-bucket projection, so malformed flag truthiness cannot interrupt dashboard aggregation or hide fallback stale-report evidence.

Daily decision dashboard performance envelopes use mapping-safe conversion before outcome calibration and queue projection, so malformed performance accessors cannot hide backtest evidence, summary metrics, or due-backtest actions.

Daily decision dashboard watchlist envelopes use mapping-safe conversion before high-priority action projection, so malformed watchlist accessors cannot hide watchlist rerun actions or high-priority counts.

Daily decision dashboard watchlist `decision_priority` fields use string-safe conversion before high-priority action projection, so malformed priority truthiness cannot interrupt dashboard aggregation or hide other valid high-priority watchlist rows.

Daily decision dashboard screener envelopes use mapping-safe conversion before candidate projection, so malformed screener accessors cannot hide review-candidate actions or top-candidate counts.

Daily decision dashboard screener quality-funnel maps use mapping-safe conversion before candidate filtering, so immutable reject outcomes cannot surface rejected candidates as review-candidate actions.

Daily decision dashboard screener quality outcome fields use string-safe conversion before reject filtering and top-candidate output, so malformed outcome truthiness cannot interrupt dashboard aggregation or leak non-string quality labels.

Daily decision dashboard screener candidate text fields use string-safe conversion before top-candidate output, so malformed ticker, company, reason, or category truthiness cannot interrupt dashboard aggregation or leak non-string candidate labels.

Daily decision dashboard screener score fields use conversion-safe fallback before top-candidate payload output, so malformed score objects cannot leak into dashboard or action payloads.

Daily decision dashboard screener score fields use conversion-safe fallback before candidate ordering, so malformed scores cannot interrupt dashboard aggregation or outrank valid candidates.

Daily decision dashboard free-mode envelopes use mapping-safe conversion before dashboard and queue projection, so malformed free-mode accessors cannot hide paid-dependency violations or fix-free-mode actions.

Daily decision dashboard free-mode violation lists use string-safe conversion before dashboard and queue projection, so malformed violation truthiness cannot interrupt aggregation or leak non-string paid-dependency labels.

Daily decision dashboard free-mode boolean flags use bool-safe fallback before dashboard and queue projection, so malformed enabled or can-run flags cannot interrupt aggregation or hide paid-dependency repair actions.

Daily decision dashboard decision freshness maps use mapping-safe conversion before rerun-bucket projection, so immutable report freshness wrappers cannot hide reports that need full reruns from the dashboard summary.

Daily decision queue provider impact ledger objects use type-safe fallback before provider recovery filtering, so malformed ledger truthiness cannot interrupt daily queue assembly or suppress valid provider impact rows.

Daily decision queue provider impact ledger maps use mapping-safe conversion before provider recovery filtering, so immutable provider-impact ledgers cannot hide wait-provider-recovery actions from the daily operating queue.

Daily decision queue provider impact summary maps use mapping-safe conversion before provider recovery filtering, so immutable provider-impact summaries cannot hide blocking wait-provider-recovery flags from the daily operating queue.

Daily decision queue provider impact ledger `items` use iterator-safe dict-list conversion before provider recovery filtering, so malformed ledger item truthiness cannot interrupt provider recovery ordering or suppress later valid provider impact rows.

Daily decision queue provider impact `impacts[].message` fields use string-safe conversion before detail output, so malformed impact-message truthiness cannot interrupt provider recovery ordering or erase concrete provider evidence.

Daily decision queue provider impact `filename` and `report_filename` aliases use string-safe selection before payload output, so malformed filename truthiness cannot interrupt provider recovery ordering or erase artifact identity.

Daily decision queue provider impact `blocks_auto_rerun` fields use bool-safe conversion before provider recovery filtering, so malformed blocking-flag truthiness cannot interrupt daily queue assembly and unparseable flags remain non-blocking.

Daily decision queue provider impact `recommended_action` fields use string-safe fallback before action payload output, so malformed action truthiness cannot interrupt provider recovery ordering or hide wait/retry policy intent.

Daily decision queue provider impact `ticker` fields use string-safe conversion before title and payload output, so malformed ticker truthiness cannot interrupt provider recovery ordering or leak non-string source identity into queue consumers.

Daily decision queue provider impact `pipeline_id` fields use string-safe conversion before payload output, so malformed pipeline truthiness cannot interrupt provider recovery ordering or leak non-string pipeline identity into queue consumers.

Daily decision queue report repair action `pipeline_id` fields use string-safe conversion before title and payload output, so malformed pipeline truthiness cannot interrupt the daily queue or leak non-string report identity into queue consumers.

Daily decision queue report repair action `priority_score` fields use integer-safe conversion before priority ordering, so malformed priority truthiness cannot interrupt the daily queue or hide a valid report repair priority.

Daily decision queue report repair action `severity` fields use string-safe conversion before payload output, so malformed severity truthiness cannot leak non-string repair state into queue consumers.

Daily decision queue report repair action `action_label` fields use string-safe conversion before payload output, so malformed CTA label truthiness cannot leak non-string operator action text into queue consumers.

For a `review_candidate` queue item, the operator summary keeps the ticker, company name, score, and real screener reason visible, then offers three direct actions: `查看股票快照`, `加入追蹤`, and `選擇分析模式`. Snapshot and watchlist reuse the existing stock snapshot panel methods. Analysis only opens the analysis tab, fills the ticker, selects the current mode, and focuses the controls; it never submits a new analysis automatically.

`notification_plan.queue_context` preserves upstream `decision_queue.summary.source_labels` and `source_texts` when those fields are present, so sender channels keep the same display contract as the daily queue instead of recomputing labels from raw source counts. `notification_plan.queue_context` fills missing `source_labels` and `source_texts` from raw `sources` while preserving upstream overrides, so partial summary maps still cover every active source key. `notification_plan.queue_context` ignores blank upstream source display overrides so fallback labels stay readable. `notification_plan.queue_context` drops upstream source display overrides for keys absent from raw `sources`, keeping display maps scoped to the active source distribution. `notification_plan.queue_context` trims raw source distribution keys before exposing `sources`, `source_labels`, and `source_texts`, so sender channels do not receive mismatched raw and display-map keys. Notification message and `delivery_outbox` entries carry `source_label` and `source_text` so sender templates can render the same readable source wording without rebuilding the source label map. Notification messages and `delivery_outbox` entries preserve action-provided `source_label` and `source_text` before fallback labels, so persisted or external source wording is not overwritten by the default backend map. Notification messages and `delivery_outbox` entries ignore blank action-provided `source_label` and `source_text` before fallback labels, so empty action metadata cannot suppress readable sender wording. Notification messages and `delivery_outbox` entries trim raw action `source` keys before exposing source display context, so sender payloads keep the same canonical source key as their readable source text. Notification source display override values are trimmed before `queue_context`, `messages`, and `delivery_outbox` expose them, so persisted wording keeps its content without leaking formatting whitespace. Notification messages and `delivery_outbox` entries drop blank action `source` keys before exposing source display context, so sender payloads do not carry whitespace-only source keys. Notification messages and `delivery_outbox` entries drop orphan `source_label` and `source_text` fields when an action has no valid raw `source`, so malformed display-only metadata cannot bypass source key normalization. The audit context snapshot also derives `source_label` and `source_text` from raw `source` when a legacy outbox entry omits them. Audit context snapshots ignore blank `source_label` and `source_text` before deriving fallback labels, so persisted audit history does not keep empty source wording. Frontend attention context summaries prefer persisted `source_text` or `source_label` before local source maps, so audit history can keep its original source wording even when the browser label map changes later. Frontend attention context summaries ignore blank persisted `source_text` and `source_label` before local source maps, so legacy or external blank values cannot hide the readable source fallback. Frontend `sourceLabels` is contract-tested against backend `SOURCE_LABELS`; keep both label maps in sync when adding a daily queue source. Frontend source label helpers trim raw source keys before lookup, matching the backend source display contract. Backend `SOURCE_LABELS` is immutable and must cover every daily queue `SOURCE_ORDER` key, so new queue sources cannot silently fall back to raw technical keys. Backend source label helpers trim raw source keys before lookup, so accidental whitespace around a source key cannot bypass the canonical readable label. Backend source label helpers drop blank raw source keys before outputting display maps, so empty source distribution entries cannot leak into sender or API payloads as empty labels. Backend source display map helpers ignore non-mapping raw source distributions, so `source_labels` and `source_texts` cannot be generated from malformed list or tuple payloads. Backend source key helpers ignore non-string raw source keys before display maps, so numeric, boolean, or bytes payload keys cannot become synthetic source labels. Backend source count normalization ignores non-mapping raw source distributions, so malformed summary payloads do not interrupt source display generation. Backend source count normalization drops non-positive raw source counts before outputting source distribution maps, so zero, negative, or unparseable counts do not appear as active source rows. Backend source count normalization treats boolean and non-finite raw source counts as inactive, so `true`, `NaN`, or infinity cannot become source distribution rows. Backend source count normalization treats fractional raw source counts as inactive, so decimal counts are not silently truncated into active source rows. Backend source count normalization requires non-string numeric raw source counts to equal their integer value, so Decimal or Fraction payload values cannot be truncated into active source rows. Backend source display override helpers normalize active raw source keys before matching upstream overrides, so fallback and override maps use the same canonical source key set. Backend source display override helpers ignore non-mapping active source distributions, so malformed active source inputs cannot generate override maps. Backend source display helpers ignore mapping accessor failures, so broken `keys()` or `items()` accessors cannot interrupt source display generation. Backend source display helpers ignore malformed mapping items, so non-pair mapping entries cannot interrupt source count or override processing. Backend source display helpers ignore mapping item unpack failures, so one broken item entry cannot suppress later valid source rows. Backend source display helpers ignore malformed mapping keys, so string or bytes `keys()` payloads cannot be split into synthetic source labels. Backend source display override helpers ignore non-string override values before fallback labels, so numeric or boolean display overrides cannot replace canonical wording.

Backend source count normalization treats raw source count conversion failures as inactive, so malformed count objects cannot interrupt source distribution output or suppress later valid source rows.

Backend source count normalization treats arithmetic raw source count conversion failures as inactive, so divide-by-zero or arithmetic conversion failures cannot interrupt source distribution output.

Backend source count normalization treats arbitrary `__int__` count objects as inactive before outputting source distribution maps, so unknown numeric wrappers cannot synthesize active source rows.

Backend source count normalization accepts only plain string raw source counts, so string subclasses with custom numeric conversion cannot synthesize active source rows.

Backend source display helpers treat arithmetic mapping accessor failures as empty source distributions, so overflow-style source maps cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source display helpers treat mapping attribute lookup failures as empty source distributions, so malformed `keys` or `items` attributes cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source display helpers treat lookup failures as empty or skipped source entries, so `KeyError` or `IndexError` from mapping accessors, iterators, or item unpacking cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source key helpers treat raw source key trim failures as blank keys, so malformed string subclasses cannot interrupt source labels, source texts, source counts, or display override generation.

Backend source key helpers require raw source key trim results to remain strings, so malformed string subclasses cannot inject non-string source keys into labels, texts, counts, or display overrides.

Backend source display override helpers safely trim override values and require trim results to remain strings, so malformed override text cannot interrupt display-map generation or inject non-string display values.

Backend source text normalization requires trim results to be plain strings, so string subclasses with custom hash or equality behavior cannot reach source labels, texts, counts, or display overrides.

`notification_plan.queue_context` treats numeric conversion failures as zero before exposing count and priority fields, so malformed summary counts or priority scores cannot interrupt notification planning.

`notification_plan.queue_context` uses strict count conversion before exposing count and priority fields, so boolean, binary, or memory-view queue summary counts cannot become synthetic notification workload evidence.

Notification plan numeric conversion treats fractional float, Decimal, and Fraction values as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata, so fractional payload drift cannot be silently truncated into synthetic priority, horizon, or workload counts.

Notification plan numeric conversion treats negative values as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata, so impossible negative priority, horizon, or workload counts cannot leak into sender payloads.

Notification plan numeric conversion treats arbitrary `__int__` adapter objects as malformed before exposing queue context, message metadata, or `delivery_outbox` metadata, so unknown numeric wrappers cannot synthesize trusted priority, horizon, or workload counts.

Notification messages treat malformed dedupe identity values as fallback identity parts before exposing `dedupe_key` and `message_id`, so one broken title/report/route identifier cannot interrupt delivery identity generation.

Notification delivery reconcile preflight uses string-safe delivery key lookup, so malformed outbox delivery key truthiness cannot interrupt audit reuse or already-sent suppression when the key is stringable.

Notification delivery reconcile preflight matches byte-like stored delivery keys before sending, so legacy or repaired audit rows with BLOB delivery keys still suppress duplicate delivery when the decoded key matches the outbox item.

Notification delivery reconcile preflight matches whitespace-padded stored delivery keys before sending, so legacy or repaired audit rows with padded delivery keys still suppress duplicate delivery when the trimmed key matches the outbox item.

Notification delivery reconcile preflight matches control-whitespace-padded stored delivery keys before sending, so legacy or repaired audit rows with tab, newline, carriage-return, or space padding still suppress duplicate delivery when the stripped key matches the outbox item.

Notification delivery record upsert matches byte-like stored delivery keys before inserting, so a later delivery attempt updates the existing legacy or repaired audit row instead of creating a duplicate text-key row.

Notification delivery record upsert matches whitespace-padded stored delivery keys before inserting, so a later delivery attempt updates the existing legacy or repaired audit row instead of creating a duplicate trimmed-key row.

Notification delivery record upsert matches control-whitespace-padded stored delivery keys before inserting, so a later delivery attempt updates the existing legacy or repaired audit row instead of creating a duplicate stripped-key row.

Notification delivery reconcile preflight prefers sent duplicate decoded delivery keys before retrying, so older duplicate BLOB/TEXT audit rows cannot override an already-sent suppression signal.

Notification delivery reconcile preflight treats byte-like sent statuses as sent duplicate rows before retrying, so repaired audit rows with BLOB `delivery_status` values still preserve the already-sent suppression signal.

Notification delivery reconcile preflight treats normalized sent statuses as sent duplicate rows before retrying, so repaired audit rows with padded or uppercase `delivery_status` values still preserve the already-sent suppression signal.

Notification delivery record upsert preserves sent duplicate identity fields before writing failed attempts, so a late failed duplicate cannot replace the delivered message channel, message id, or dedupe key metadata.

Notification delivery record upsert preserves normalized sent duplicate statuses before writing failed attempts, so a late failed attempt cannot downgrade repaired audit rows whose stored `delivery_status` is padded or uppercase `sent`.

Notification delivery record upsert preserves sent duplicate decoded delivery keys before writing failed attempts, so a late failed duplicate cannot downgrade an already-sent audit row or reopen a delivered message for retry.

Notification delivery record upsert preserves sent duplicate last errors before writing failed attempts, so a late failed duplicate cannot leave a sent audit row with a misleading failure error message.

Notification delivery record upsert preserves sent duplicate response ids before writing failed attempts, so a late failed duplicate cannot replace the successful sender response id with an error response id.

Notification delivery record upsert preserves sent duplicate context snapshots before writing failed attempts, so a late failed duplicate cannot replace the delivered message source, ticker, report, or CTA context.

Notification delivery reconcile preflight treats missing outbox entries as an empty list, so optional sender payloads without delivery work return an empty preflight result instead of raising before audit lookup.

Notification delivery reconcile preflight evaluates tuple outbox entry batches before audit lookup, so immutable sender payloads do not lose pending delivery work.

Notification delivery reconcile preflight evaluates mapping outbox entries before audit lookup, so immutable entry payloads do not lose pending delivery work.

Notification delivery reconcile preflight skips malformed mapping outbox entries before audit lookup, so one broken immutable entry does not erase adjacent pending delivery work.

Notification delivery reconcile attempt counts use string-safe integer conversion, so malformed audit attempt metadata cannot interrupt retry budget or next-attempt calculation.

Notification delivery reconcile retry budgets treat `None` max attempts as the default retry budget, so optional caller configuration does not exhaust failed delivery after the first attempt.

Notification delivery reconcile retry timestamps use string-safe float conversion, so malformed audit last-attempt metadata cannot interrupt retry wait calculation.

Notification delivery reconcile success timestamps use finite-float conversion before sender preflight output, so repaired or mocked sent audit rows with NaN or Infinity `last_success_at` cannot leak non-standard JSON numbers into sender or API payloads.

Notification delivery reconcile retry backoff treats `None` as the default backoff window, so optional caller configuration does not bypass retry waiting and immediately resend failed delivery.

Notification delivery reconcile retry backoff uses finite-float conversion before wait calculation, so NaN or Infinity backoff values fall back to zero instead of creating infinite retry waits or sender preflight exceptions.

Notification delivery reconcile current time uses finite-float fallback before wait calculation, so NaN or Infinity `now` inputs fall back to runtime time instead of creating sender preflight exceptions.

Notification delivery reconcile statuses use string-safe text conversion, so malformed audit status truthiness cannot interrupt already-sent, retry-exhausted, or retry-wait decisions.

Notification delivery reconcile statuses are normalized before retry and already-sent decisions, so repaired or mocked audit rows with padded or uppercase `delivery_status` values still suppress duplicate sent messages and respect retry backoff windows.

Notification delivery reconcile text metadata uses string-safe conversion, so malformed audit `last_error` or `last_response_id` truthiness cannot interrupt sender preflight result assembly.

Notification delivery response ids are stripped before record and sender preflight output, so repaired or sender-returned response ids with tab, newline, or space padding do not leak padded identifiers into list, API, or sender preflight payloads.

Notification delivery reconcile audit context uses dict-safe conversion, so malformed persisted audit context truthiness cannot interrupt sender preflight context recovery.

Notification delivery audit context maps use JSON-safe dict conversion before reconcile and summary output, so direct or mocked audit context maps with NaN or Infinity values cannot leak non-standard numbers into sender preflight, ops, or daily queue summaries.

Notification delivery audit context JSON parsing uses string-safe conversion before loading persisted context, so repaired or mocked context payloads that are stringable JSON still recover source, ticker, report, and CTA context instead of becoming empty audit context.

Notification delivery audit context normalizes `reason_codes` with text-list safe conversion, so one malformed reason-code object cannot interrupt audit persistence or erase earlier valid blocked-repair causes.

Notification delivery audit context enumerates outbox metadata with mapping-item safe conversion, so malformed `.items()` accessors cannot interrupt audit persistence or erase source, ticker, report, CTA, queue-rank, or blocked-repair reason context.

Notification delivery audit context ignores non-string outbox metadata keys before JSON serialization, so mixed key types cannot interrupt sorted context snapshots or create synthetic persisted field names.

Notification delivery audit context normalizes metadata values before JSON serialization, so unstringable optional metadata cannot interrupt audit persistence or erase adjacent source, ticker, report, rank, and blocked-repair reason context.

Notification delivery audit context preserves mapping metadata values before JSON serialization, so immutable nested context remains structured instead of becoming stringified text.

Notification delivery audit context drops whitespace-only metadata before JSON serialization, so optional ticker, report, CTA, nested, or sequence context fields that contain only formatting whitespace do not become persisted audit history.

Notification delivery audit context drops empty collection metadata after normalization, so optional list or object context fields whose children were all removed do not remain as empty `[]` or `{}` audit history.

Notification delivery audit context normalizes sequence metadata values with sequence-safe conversion, so malformed list or tuple iterators cannot interrupt audit persistence or erase adjacent report, rank, and blocked-repair reason context.

Notification delivery audit context partial sequence metadata is normalized before empty collection filtering, so list wrappers that yield valid metadata before stopping are not discarded just because their native backing list is empty.

Notification delivery audit context drops non-finite numeric metadata before JSON serialization, so NaN or Infinity optional metadata cannot leak non-standard JSON numbers into persisted audit context while adjacent source, report, rank, and blocked-repair reason context stays available.

Notification identity branch selection sanitizes report, ticker, pipeline, route, and warning identifiers before choosing fallback identity parts, so malformed truthiness cannot interrupt derived delivery identity generation.

Notification identity parts use shared text conversion before composing `dedupe_key`, `message_id`, and `delivery_key`, so boolean, binary, or memory-view identity payloads fall back instead of leaking Python representations into sender idempotency fields.

Notification identity parts use identity and type-based empty checks before composing `dedupe_key`, `message_id`, and `delivery_key`, so arbitrary identity equality hooks cannot erase valid sender idempotency overrides by comparing equal to blank strings.

Notification messages normalize `filename` and `report_filename` aliases with string-safe selection before exposing message and `delivery_outbox` report context, so malformed filename truthiness cannot interrupt notification planning.

Notification message numeric metadata uses strict count conversion before exposing `priority_score` and `horizon_months` in messages and `delivery_outbox`, so boolean, binary, or memory-view values cannot leak as sender-visible priority or horizon payloads.

Notification message text metadata uses shared text conversion before exposing ticker, filename, report, pipeline, route, warning, recommended action, severity, and action label fields in messages and `delivery_outbox`, so boolean, binary, or memory-view values cannot leak as sender-visible context.

Notification message boolean metadata uses explicit bool-text conversion before exposing `blocks_auto_rerun` in messages and `delivery_outbox`, so string `false` stays false while binary or memory-view values cannot leak as sender-visible blocking flags.

Notification message and `delivery_outbox` context presence checks tolerate malformed equality comparisons before carrying optional metadata, so one broken action metadata value cannot interrupt notification planning.

Notification message and `delivery_outbox` context presence checks use identity and type-based empty checks before carrying optional metadata, so arbitrary metadata equality hooks cannot erase valid sender context by comparing equal to blank strings.

Notification suppression flag checks use explicit bool-text conversion before message filtering, treating malformed or binary `suppress_notification` values as unsuppressed while preserving bool/string true and type-based suppression, so string `false` cannot hide real actions.

Notification plan boolean conversion treats arbitrary string-like objects as malformed before message metadata or suppression checks, so unknown wrappers cannot synthesize blocking flags or suppress notifications through `__str__` tokens.

Notification action type lookups trim raw `type` before suppression, legacy queue context, CTA defaults, target defaults, and message envelope output, so whitespace-padded monitor or provider-recovery actions cannot become sender-visible noise or lose their deep-link defaults.

Notification plan external channel env checks require concrete nonblank string values before enabling SMTP, Telegram, Discord, or Slack, so boolean, binary, memory-view, or arbitrary string-like env payloads stay in `channels[].missing_env` instead of creating external delivery outbox entries.

Notification plan external channel env containers use mapping-safe conversion before missing-env checks, so malformed env payloads keep local notifications enabled while external integrations remain disabled.

Notification plan action collections use iterator-safe dict-list conversion before message and `delivery_outbox` assembly, so malformed `decision_queue.items` or legacy `actions` iterators cannot interrupt notification planning or suppress valid native actions.

Notification plan action collections accept list or tuple payloads before message and `delivery_outbox` assembly, so immutable repaired action batches are not silently ignored.

Notification plan decision queue context uses mapping-safe conversion before reading `decision_queue`, `summary`, and `sources`, so immutable repaired queue payloads are not downgraded to empty legacy actions.

Notification plan dashboard payloads use mapping-safe conversion before reading `decision_queue` or legacy `actions`, so immutable repaired dashboard responses do not interrupt notification planning.

Notification messages ignore malformed action-provided `dedupe_key` and `message_id` overrides before falling back to derived delivery identity, so external queue metadata cannot break sender idempotency handoff.

Notification operator CTA metadata selection uses string-safe action/label fallbacks, so malformed custom CTA truthiness cannot interrupt notification planning and stringable custom CTAs remain available to sender payloads.

Notification target metadata selection uses string-safe panel/tab fallbacks, so malformed custom target truthiness cannot interrupt notification planning and stringable custom targets remain available to sender payloads.

Notification custom CTA and target metadata selection trims action-provided values before fallback selection, so whitespace-only custom buttons or deep links cannot leak into visible sender messages or `delivery_outbox` entries.

Notification message envelope selection uses string-safe type/title/detail fallbacks, so malformed message envelope truthiness cannot interrupt notification planning and stringable notification fields remain available to sender payloads.

Notification message envelope selection uses shared text conversion for type/title/detail fields, so boolean, binary, or memory-view envelope payloads cannot leak as visible sender message text.

Notification message envelope selection trims type/title/detail fields before fallback selection, so whitespace-only envelope metadata cannot leak into visible sender messages or `delivery_outbox` entries.

Audit context source display presence checks use string-safe text conversion before deriving fallback labels, so malformed `source_label` or `source_text` truthiness cannot interrupt sender audit persistence.

Audit context source key normalization uses string-safe text conversion before deriving fallback labels, so malformed raw `source` truthiness cannot interrupt sender audit persistence and stringable source keys are trimmed before persistence.

Audit context snapshot presence checks tolerate malformed equality comparisons before preserving optional outbox metadata, so one broken context value cannot interrupt sender audit persistence.

Notification delivery attempt result fields use string-safe status, error, and response id conversion, so malformed sender result truthiness cannot interrupt audit persistence.

Notification delivery outbox identity fields use string-safe required text extraction, so malformed `delivery_key`, `channel_id`, `message_id`, or `dedupe_key` truthiness cannot interrupt audit persistence when the identity value is stringable.

Notification delivery audit persistence evaluates mapping outbox entries before identity and context extraction, so immutable entry payloads can still be written to the delivery audit.

Notification delivery audit persistence rejects malformed mapping outbox entries with required identity errors, so broken entry accessors do not leak low-level iterator failures.

Notification delivery audit listing uses string-safe integer limit conversion, so malformed list limit truthiness cannot interrupt audit record listing or delivery summary generation.

Notification delivery audit listing clamps explicit zero limits before querying records, so callers asking for a minimal sample do not accidentally receive the default audit page size.

Notification delivery audit row timestamps use finite-float conversion before record output, so legacy or repaired rows with Infinity timestamps cannot leak non-standard numeric values into sender preflight, summaries, or API responses.

Notification delivery audit row text fields use string-safe conversion before record output, so legacy or repaired rows with blob channel, message, status, error, or response-id values cannot leak bytes into sender preflight, summaries, or API responses.

Notification delivery audit row statuses are normalized before record output, so legacy or repaired rows with padded or uppercase `delivery_status` values still render as canonical lowercase statuses in sender preflight, summaries, or API responses.

Notification delivery audit row delivery keys are stripped before record output, so legacy or repaired rows with padded stored delivery keys do not leak formatting whitespace into sender preflight, summaries, or API responses.

Notification delivery audit row identity fields are stripped before record output, so legacy or repaired rows with padded `channel_id`, `message_id`, or `dedupe_key` values still render as canonical delivery identity metadata in sender preflight, summaries, or API responses.

Notification delivery audit text conversion decodes byte-like values before record output, so repaired BLOB channel, message, status, error, or response-id values render as readable text instead of Python bytes representations.

Notification delivery audit row attempt counts use string-safe integer conversion before record output, so legacy or repaired rows with malformed attempt-count values cannot interrupt sender preflight, summaries, or API responses.

Notification delivery audit context JSON parsing avoids truthiness checks before loading persisted context, so malformed persisted context payload truthiness cannot interrupt sender preflight, summaries, or API responses.

Notification delivery audit context JSON parsing drops non-finite numeric values before record output, so legacy persisted context payloads with NaN or Infinity cannot leak non-standard numbers into sender preflight, summaries, or API responses.

Notification attention context record serialization uses string-safe text, integer, and dict conversion, so malformed failed audit row truthiness cannot interrupt notification delivery summary output.

Notification attention context identity fields are stripped before summary output, so repaired or mocked failed audit rows with padded `delivery_key` or `channel_id` values do not leak formatting whitespace into ops, daily queue, or sender context summaries.

Notification attention context limit handling treats `None` as the default cap before summary output, so optional caller limit values do not erase failed delivery context from ops, daily queue, or sender summaries.

Notification attention context record serialization normalizes failed statuses before projection, so repaired or mocked audit rows with padded or uppercase `delivery_status` values still preserve affected source, ticker, report, and CTA context in delivery summaries.

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

Report recommendation legacy text surfaces next catalysts from structured outputs, so plain-text agent sections keep the same catalyst watchlist evidence that appears in report sidebars.

Report recommendation legacy text uses trigger fallback for blank next catalysts, so plain-text catalyst rows keep `待後續資料確認` instead of dropping the entire catalyst section when a catalyst event has no displayable trigger condition.

Report recommendation legacy text uses impact-direction fallback for invalid next catalysts, so plain-text catalyst rows show `volatile` instead of arbitrary model text when a catalyst direction is not one of bullish, bearish, or volatile.

Report recommendation legacy text uses trigger-length fallback for too-short next catalysts, so plain-text catalyst rows keep `待後續資料確認` instead of presenting non-actionable trigger fragments.

Report recommendation legacy text surfaces reasoning steps from structured outputs, so Agent 7/16/19 plain-text sections keep the investment reasoning chain near recommendation context while Agent 19 still ends with the final recommendation block.

Report downside-risk legacy text surfaces thesis summaries from structured outputs, so Agent 21 plain-text sections keep the bearish thesis before listing individual downside risks.

Report downside-risk legacy text uses thesis-summary fallback for single-character fragments, so Agent 21 plain-text sections keep the summary block but show `資料不足` instead of non-actionable one-character thesis scraps.

Report downside-risk legacy text uses analysis body fallback for single-character fragments, so Agent 21 plain-text sections end with `資料不足` instead of non-actionable one-character analysis body scraps.

Report downside-risk legacy text uses fallback row for empty risk lists, so Agent 21 plain-text sections show `下行風險 / 資料不足` instead of leaving an empty downside-risk block when no individual risks are displayable.

Report valuation legacy text surfaces valuation reasoning from structured outputs, so Agent 4/14 plain-text sections keep DCF, peer, and scenario reasoning with the target-price table.

Report valuation legacy text skips single-character valuation reasoning fragments, so Agent 4/14 plain-text valuation reasoning sections do not present non-actionable one-character DCF, peer, or scenario scraps.

Report valuation legacy text surfaces DCF scenario assumptions from structured outputs, so Agent 4/14 plain-text sections keep bear/base/bull model sensitivities beside the valuation reasoning.

Report downside-risk legacy text surfaces risk priority metadata from structured outputs, so Agent 21 plain-text risk rows keep impact, severity, and confidence beside each downside risk.

Report downside-risk legacy text separates impact from evidence in risk rows, so Agent 21 plain-text sections do not merge impact labels into evidence text when the evidence sentence has no trailing punctuation.

Report downside-risk legacy text uses evidence fallback for single-character fragments, so Agent 21 plain-text risk rows show `資料不足` instead of presenting non-actionable one-character evidence scraps.

Report downside-risk legacy text uses title fallback for single-character fragments, so Agent 21 plain-text risk rows show `下行風險` instead of presenting non-actionable one-character risk-title scraps.

Report downside-risk legacy text omits impact for single-character fragments, so Agent 21 plain-text risk rows keep the evidence and metadata without presenting non-actionable one-character impact scraps.

Report downside-risk legacy text uses severity fallback for invalid metadata, so Agent 21 plain-text risk rows show schema-aligned `warning` instead of arbitrary severity labels outside `warning`, `high`, or `critical`.

Report downside-risk legacy text uses confidence fallback for invalid metadata, so Agent 21 plain-text risk rows show schema-aligned `0.7` instead of arbitrary confidence labels or non-finite values outside 0 to 1.
