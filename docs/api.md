# API Reference

The API is local-first and intended for the bundled UI or trusted local automation.
FastAPI exposes the machine-readable contract at `/openapi.json`; mutating operations are annotated with the `MutationToken` API-key security scheme using the `X-Mutation-Token` header.

## Read Endpoints

```bash
curl http://127.0.0.1:8080/api/reports
curl http://127.0.0.1:8080/api/observability/provider-sla
curl http://127.0.0.1:8080/api/observability/active-jobs
curl http://127.0.0.1:8080/api/observability/api-quotas
curl http://127.0.0.1:8080/api/watchlist
curl http://127.0.0.1:8080/api/stocks/2330.TW/snapshot
```

Report rows include:

- `data_trust`: data-source quality and freshness.
- `decision_tracking`: performance since the report recommendation.
- `decision_freshness`: whether the conclusion still matches the current data snapshot.

Each report `.data.json` snapshot also includes `data_confidence_score`, `conclusion_guardrails.explicit_target_price`, and `reproducibility_packet`. When `data_confidence_score < 60`, explicit target prices are marked disallowed and consumers should treat only ranges or "data insufficient" language as valid. `reproducibility_packet.data_snapshot_hash` matches the final snapshot hash and also records ticker, pipeline, prompt version, full prompt fingerprint, model id, code commit, code dirty state, provider list, generated time, and source data time.

Watchlist rows also include `decision_priority`, `decision_alert`, and `latest_report` when a matching report exists. `decision_priority = high` means the latest data snapshot changed after the conclusion was generated and the report should be rerun.

Watchlist symbol suggestions are local/free and can be used before saving or importing rows:

```bash
curl "http://127.0.0.1:8080/api/watchlist/symbols?q=台積"
```

股票快照 API 提供一般股票頁需要的摘要結構，不需要 mutation token：

```bash
curl http://127.0.0.1:8080/api/stocks/{ticker}/snapshot
```

回傳內容包含 `identity`、`company_profile`、`quote`、`market_session`、`price_trend`、`performance_history`、`technical_summary`、`valuation`、`valuation_range`、`analyst_outlook`、`earnings_forecast`、`share_statistics`、`risk_liquidity`、`profitability_quality`、`dividends`、`dividend_profile`、`event_calendar`、`alert_suggestions`、`financial_health`、`financial_trends`、`peer_comparison`、`ownership_flow`、`events`、`news`、`chip`、`data_quality` 與 `mode_suggestions`。`company_profile` 會整理公司業務摘要、官網、產業、市場/交易所、幣別與員工數；`market_session` 會揭露今日行情、漲跌、日內區間、成交量與均量比較；`price_trend` / `performance_history` / `technical_summary` 會提供近一年趨勢、1M/3M/6M/1Y/3Y/5Y 多週期走勢、均線、52 週位置與動能訊號；`valuation_range` 與 `analyst_outlook` 分別提供 P/E 河流圖估值區間、分析師目標價、共識、Forward P/E 與 EPS 成長；`earnings_forecast` 會整理 Trailing EPS、Forward EPS、Forward EPS 變化、EPS/營收成長、下次財報日期與分析師覆蓋數；`share_statistics` 會整理在外股數、流通股數、內部人/機構持股、空單股數、short ratio 與空單占流通股比例；`risk_liquidity` 會整理 beta、52 週高點回撤、成交量相對均量、負債權益比與流動比率；`profitability_quality` 會整理毛利率、營業利益率、淨利率、ROE、ROA 與 FCF margin；`dividend_profile` 會整理年化股利、殖利率、配息率、近年配息歷史與 FCF 覆蓋；`event_calendar` 會整理財報日、除息日、股利發放日、最近財報季度等關鍵日期，並標出下一事件與距今天數；`alert_suggestions` 會把關鍵日期、分析師目標價、52 週高點與月營收創高等情境轉成可保存到 watchlist 的提醒建議；`financial_health` / `financial_trends` / `peer_comparison` 則把基本面摘要、近年營收/淨利/FCF YoY 與同業比較整理成一般股票頁可讀的摘要；`ownership_flow` 會將法人買賣超、外資/投信/自營商分類、融資券與 TDCC 股權集中度整理成籌碼結構摘要。`mode_suggestions` 則把 `v1` / `v2` / `v3` / `v4` 翻成使用者決策語言，供前端快速切換分析模式。

### Pipeline Mode Catalog

前端模式選項可由唯讀 catalog API 載入：

```bash
curl http://127.0.0.1:8080/api/pipeline-modes
```

回應使用 `schema_version = "pipeline_modes.v1"`，`modes` 會包含 `v1`、`v2`、`v3`、`v4` 與 `both`。每個項目同時提供 canonical id、執行用 label/hint、決策語意、`agentCount`、`optionLabel` 與 CTA 文案。catalog 的 runtime source 是 `backend/pipeline_mode_catalog.py`；首屏 fallback 由 `scripts/generate_pipeline_mode_fallback.py` 產生到 `backend/static/pipeline_mode_fallback.js`，CI 會用 `--check` 阻擋產物漂移。API 成功後由 `pipeline_mode_catalog.js` 合併更新，API 暫時不可用時不阻擋既有分析流程。

## Mutation Token

```bash
TOKEN="$(curl -fsS http://127.0.0.1:8080/api/client-config | python -c 'import json,sys; print(json.load(sys.stdin)["mutation_token"])')"
```

Use it with modifying requests:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/report/<filename>/refresh/data

curl -X DELETE -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/reports/<filename>
```

## Analysis Jobs

新分析請優先使用正式 job API。建立任務是 mutation，必須帶 `X-Mutation-Token`：

```bash
curl -X POST http://127.0.0.1:8080/api/analysis-jobs \
  -H "Content-Type: application/json" \
  -H "X-Mutation-Token: $TOKEN" \
  -d '{"ticker":"2330.TW","pipeline_id":"v1","force":false,"resume":true}'
```

回應包含：

```json
{
  "job_id": "analysis-2330tw-v1-...",
  "ticker": "2330.TW",
  "pipeline_id": "v1",
  "status": "queued",
  "events_url": "/api/analysis-jobs/{job_id}/events",
  "status_url": "/api/analysis-jobs/{job_id}"
}
```

同一個 `ticker + pipeline_id` 在 `queued/running/waiting_retry` 期間只會有一個 active job。重複建立會回傳既有 job；`force=true` 會先把舊 active job 標記 `cancelled`，再建立新 job。

查詢狀態：

```bash
curl http://127.0.0.1:8080/api/analysis-jobs/<job_id>
```

讀取 SSE：

```bash
curl -N http://127.0.0.1:8080/api/analysis-jobs/<job_id>/events
curl -N "http://127.0.0.1:8080/api/analysis-jobs/<job_id>/events?since_id=42"
```

SSE endpoint 只讀事件，不建立任務。瀏覽器或 client reconnect 時可用 `Last-Event-ID` header、`last_event_id` query，或 `since_id` query 從最後收到的 event id 繼續。沒有新事件時 server 會逐步 backoff polling，並送出 `event: ping` heartbeat：

```text
event: ping
data: {"ts":"2026-06-29T00:00:00Z"}
```

取消任務：

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  http://127.0.0.1:8080/api/analysis-jobs/<job_id>/cancel
```

Queued job 會盡量從 RQ queue 移除並標記 `cancelled`。Running job 會標記 `cancel_requested`，worker 在資料抓取、pipeline segment、report rendering 等安全 checkpoint 檢查後中止。

Node telemetry：

```bash
curl http://127.0.0.1:8080/api/analysis-jobs/<job_id>/telemetry
```

回傳每個 LangGraph node / agent 的 `node_name`、`model`、時間、latency、status、retry count、token 欄位（目前可能為 `null`）、quality gate 結果與已清理過的錯誤摘要。

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

## Runtime Health And Ops Dashboard

Liveness 只確認 API process 還能回應：

```bash
curl http://127.0.0.1:8080/healthz
```

Readiness 會檢查 runtime storage 與 task queue；若 Redis/RQ 或 SQLite path 不可用，會回 HTTP 503：

```bash
curl http://127.0.0.1:8080/readyz
```

Operator dashboard 是 read-only 聚合端點，不需要 mutation token：

```bash
curl http://127.0.0.1:8080/api/observability/dashboard
curl http://127.0.0.1:8080/api/ops/dashboard
```

回傳內容包含報告完成耗時 `p50/p95/p99`、active job count、stuck job warning、node/model telemetry summary、`prompt_budget` token 摘要、RQ queue depth/registry counts、provider 24 小時 degradation alerts、API quota ledger 摘要、`notification_delivery` sender audit health，以及 `free_mode` 免費模式合約摘要。`notification_delivery` 會揭露 `failed_count`、`retry_exhausted_count`、`channel_counts`、`failure_reason_counts`、`attention_contexts` 與 `health`；`attention_contexts` 是低量 failed delivery context snapshot，讓 operator 或 repair flow 可定位受影響 source、ticker、report 與 CTA。當 delivery audit 出現 failed 或 retry exhausted 時，dashboard `status` 會升為 `warning`。`status` 可能是 `ok`、`warning` 或 `critical`。

Prometheus `/metrics` 也輸出 notification delivery audit 摘要：`stock_agent_notification_delivery_count{status="failed"}`、`stock_agent_notification_delivery_count{status="retry_exhausted"}`、`stock_agent_notification_delivery_channel_count{channel="..."}`、`stock_agent_notification_delivery_failure_reason_count{reason="timeout|auth|rate_limited|configuration|network|other|unknown"}` 與 `stock_agent_notification_delivery_health{state="ok|warning"}`。這些都是目前 audit rows 的 gauge；health 會固定輸出 `state="ok"` 和 `state="warning"` 兩條 one-hot series，failure reason 只使用低基數分類，不把 raw `last_error` 放進 label，讓外部監控在 in-app 工作台之外也能穩定告警通知通道故障。

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

Notification delivery reconcile preflight uses string-safe delivery key lookup, so malformed outbox delivery key truthiness cannot interrupt audit reuse or already-sent suppression when the key is stringable.

Notification delivery reconcile attempt counts use string-safe integer conversion, so malformed audit attempt metadata cannot interrupt retry budget or next-attempt calculation.

Notification delivery reconcile retry timestamps use string-safe float conversion, so malformed audit last-attempt metadata cannot interrupt retry wait calculation.

Notification delivery reconcile statuses use string-safe text conversion, so malformed audit status truthiness cannot interrupt already-sent, retry-exhausted, or retry-wait decisions.

Notification delivery reconcile text metadata uses string-safe conversion, so malformed audit `last_error` or `last_response_id` truthiness cannot interrupt sender preflight result assembly.

Notification delivery reconcile audit context uses dict-safe conversion, so malformed persisted audit context truthiness cannot interrupt sender preflight context recovery.

每日決策儀表板整合近期報告、watchlist、auto-screener、決策回測與免費模式狀態：

```bash
curl http://127.0.0.1:8080/api/watchlist/daily-dashboard
```

The daily dashboard also returns `notification_plan`. Local UI notifications are always free; SMTP, Telegram, Discord, and Slack are enabled only when the operator supplies the corresponding environment variables/webhook URLs. `decision_queue.summary` exposes `source_labels` and `source_texts` beside raw `sources`, so API consumers can render readable source distribution while preserving raw source keys. Backend source label helpers trim raw source keys before lookup, preventing accidental surrounding whitespace from bypassing canonical labels. Backend source label helpers drop blank raw source keys before outputting display maps, so empty source distribution entries cannot leak into sender or API payloads as empty labels. Backend source display map helpers ignore non-mapping raw source distributions, so `source_labels` and `source_texts` cannot be generated from malformed list or tuple payloads. Backend source key helpers ignore non-string raw source keys before display maps, so numeric, boolean, or bytes payload keys cannot become synthetic source labels. Backend source count normalization ignores non-mapping raw source distributions, so malformed summary payloads do not interrupt source display generation. Backend source count normalization drops non-positive raw source counts before outputting source distribution maps, so zero, negative, or unparseable counts do not appear as active source rows. Backend source count normalization treats boolean and non-finite raw source counts as inactive, so `true`, `NaN`, or infinity cannot become source distribution rows. Backend source count normalization treats fractional raw source counts as inactive, so decimal counts are not silently truncated into active source rows. Backend source count normalization requires non-string numeric raw source counts to equal their integer value, so Decimal or Fraction payload values cannot be truncated into active source rows. Backend source display override helpers normalize active raw source keys before matching upstream overrides, so fallback and override maps use the same canonical source key set. Backend source display override helpers ignore non-mapping active source distributions, so malformed active source inputs cannot generate override maps. Backend source display helpers ignore mapping accessor failures, so broken `keys()` or `items()` accessors cannot interrupt source display generation. Backend source display helpers ignore malformed mapping items, so non-pair mapping entries cannot interrupt source count or override processing. Backend source display helpers ignore mapping item unpack failures, so one broken item entry cannot suppress later valid source rows. Backend source display helpers ignore malformed mapping keys, so string or bytes `keys()` payloads cannot be split into synthetic source labels. Backend source display override helpers ignore non-string override values before fallback labels, so numeric or boolean display overrides cannot replace canonical wording. Frontend source label helpers trim raw source keys before lookup too, so browser-only action details follow the same source display contract. `decision_queue.items` can include `fix_notification_delivery` when notification sender audit health is degraded; that item is an in-app/ops repair action with `suppress_notification = true`, carries low-cardinality `failure_reason_counts` for local triage, and stays out of `notification_plan.messages` and `delivery_outbox`. `notification_plan.messages` uses `decision_queue.items` as the primary source when that contract is present, trims raw action `source` keys before exposing message/outbox source context, drops blank action `source` keys before exposing sender payloads, preserves action metadata such as `route`, `warning_id`, `horizon_months`, `recommended_action`, `blocks_auto_rerun`, `severity`, and `action_label`, preserves action-provided `source_label` / `source_text` before fallback labels, trims source display override values before exposing queue/message/outbox payloads, ignores blank action-provided source display fields before fallback labels, adds `target_panel` / `target_tab` for operator workspace deep links, adds `operator_action` / `operator_action_label` for CTA rendering, adds `queue_rank` / `queue_displayed_count` / `is_top_priority` for displayed-order rendering, adds stable `dedupe_key` / `message_id` fields based on source, type, report, route, horizon, and pipeline identifiers while excluding title/detail/priority changes, adds `delivery_outbox` / `delivery_summary` records for enabled channel/message pairs with stable `delivery_key` and pending delivery status, and `notification_plan.queue_context` exposes the total actionable count, displayed count, secondary count, top priority score, and source distribution for downstream notification channels. When `decision_queue.summary.source_labels` or `source_texts` are present, `notification_plan.queue_context` preserves those upstream maps instead of rebuilding display text from raw source counts; when a partial map omits an active source key, the omitted key is filled from raw `sources` fallback while upstream overrides still win. Blank upstream source display overrides are ignored so fallback labels stay readable, overrides for keys absent from raw `sources` are dropped so display maps match the active source distribution, and raw source distribution keys are trimmed before exposing `sources`, `source_labels`, and `source_texts`. When a sender records a `delivery_outbox` attempt, `notification_delivery_audit` stores a context snapshot from the outbox entry so audit history can still expose source, ticker, report filename, target panel/tab, CTA, and queue rank after the original dashboard response has expired. Audit context snapshots ignore blank `source_label` / `source_text` before deriving fallback labels from raw `source`, preventing empty source wording from becoming persisted operational history. Frontend attention context summaries apply the same blank-display fallback before local source maps, so legacy or external blank snapshot values do not suppress readable source wording.

Backend source count normalization treats raw source count conversion failures as inactive, so malformed count objects cannot interrupt source distribution output or suppress later valid source rows.

Backend source count normalization treats arithmetic raw source count conversion failures as inactive, so divide-by-zero or arithmetic conversion failures cannot interrupt source distribution output.

Notification messages and `delivery_outbox` entries ignore non-string action-provided `source_label` and `source_text` before fallback labels, so numeric or boolean action metadata cannot replace canonical source wording.

`notification_plan.queue_context` maps non-string legacy action source keys to `unknown` before exposing source distribution maps, so numeric or boolean legacy sources cannot create synthetic source rows.

`notification_plan.queue_context` uses a string-safe legacy action type filter before excluding `monitor` fallback actions, so malformed legacy action type truthiness cannot interrupt notification planning or inflate legacy actionable counts.

`notification_plan.queue_context` treats numeric conversion failures as zero before exposing count and priority fields, so malformed summary counts or priority scores cannot interrupt notification planning.

Notification messages treat malformed dedupe identity values as fallback identity parts before exposing `dedupe_key` and `message_id`, so one broken title/report/route identifier cannot interrupt delivery identity generation.

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

Backend source display helpers preserve valid mapping items before iterator failures, so an iterator error after a valid entry does not erase already parsed source rows or overrides.

Backend source display helpers preserve valid mapping keys before iterator failures, so an iterator error after a valid key does not erase already parsed source labels, source texts, or active override matches.

Auto-screener 候選清單支援商業版前端的篩選與分頁。常用 query 包含 `category`、`min_score`、`fundamental_revenue_growth_yoy_min/max`、`technical_rsi_min/max`、`technical_macd_min`、`technical_macd_histogram_min`、`institutional_total_net_buy_min`、`institutional_foreign_net_buy_min`、`institutional_investment_trust_net_buy_min`、`institutional_dealer_net_buy_min`、`sort_by`、`sort_direction`、`limit` 與 `offset`：

```bash
curl "http://127.0.0.1:8080/api/watchlist/screener?min_score=70&fundamental_revenue_growth_yoy_min=10&technical_rsi_max=70&institutional_total_net_buy_min=1000000&sort_by=score&sort_direction=desc&limit=20"
```

Watchlist paste/CSV import is a mutation endpoint. It accepts `ticker`/`symbol`, optional `pipeline`, `schedule_slots`, `tags`, and `enabled`; four-digit Taiwan symbols are normalized to `.TW`.

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8080/api/watchlist/import \
  -d '{"text":"ticker,pipeline,schedule_slots\n2330.TW,v2,pre_market|post_market\nAAPL,v1,post_market"}'
```

Portfolio CSV 風控是本機研究工具，不接券商、不下單；因使用 POST body，仍需 mutation token：

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  http://127.0.0.1:8080/api/watchlist/portfolio/risk \
  -d '{"csv":"ticker,weight,sector,country\n2330.TW,55,Semiconductors,TW\nAAPL,45,Technology,US"}'
```

### Deprecated Compatibility Endpoint

`GET /api/analyze/{ticker}` 保留給舊 UI / 舊腳本相容，回應會帶 `Deprecation: true` header，SSE 的 job metadata 也會包含 `deprecated: true`。新整合請改用：

1. `POST /api/analysis-jobs`
2. `GET /api/analysis-jobs/{job_id}/events`
3. `GET /api/analysis-jobs/{job_id}`

## Maintenance Dry Run

Cleanup APIs are dry-run unless `write=true` is explicit:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-analysis-history?retention_days=30"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-analysis-history?retention_days=30&write=true"
```

SQLite backup/checkpoint/vacuum maintenance is also dry-run by default:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/sqlite-maintenance"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/sqlite-maintenance?write=true"
```

`write=true` creates one daily backup for each runtime SQLite DB under `SQLITE_BACKUP_DIR`, then runs `PRAGMA wal_checkpoint(TRUNCATE)` and `VACUUM`.
