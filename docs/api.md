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

Each report `.data.json` snapshot also includes `data_confidence_score`, `conclusion_guardrails.explicit_target_price`, and `reproducibility_packet`. When `data_confidence_score < 60`, explicit target prices are marked disallowed and consumers should treat only ranges or "data insufficient" language as valid. `reproducibility_packet.data_snapshot_hash` matches the final snapshot hash and also records ticker, pipeline, prompt version, model id, code commit, provider list, generated time, and source data time.

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

回傳內容包含報告完成耗時 `p50/p95/p99`、active job count、stuck job warning、node/model telemetry summary、`prompt_budget` token 摘要、RQ queue depth/registry counts、provider 24 小時 degradation alerts、API quota ledger 摘要，以及 `free_mode` 免費模式合約摘要。`status` 可能是 `ok`、`warning` 或 `critical`。

每日決策儀表板整合近期報告、watchlist、auto-screener、決策回測與免費模式狀態：

```bash
curl http://127.0.0.1:8080/api/watchlist/daily-dashboard
```

The daily dashboard also returns `notification_plan`. Local UI notifications are always free; SMTP, Telegram, Discord, and Slack are enabled only when the operator supplies the corresponding environment variables/webhook URLs.

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
