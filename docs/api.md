# API Reference

The API is local-first and intended for the bundled UI or trusted local automation.

## Read Endpoints

```bash
curl http://127.0.0.1:8080/api/reports
curl http://127.0.0.1:8080/api/observability/provider-sla
curl http://127.0.0.1:8080/api/observability/active-jobs
curl http://127.0.0.1:8080/api/observability/api-quotas
curl http://127.0.0.1:8080/api/watchlist
```

Report rows include:

- `data_trust`: data-source quality and freshness.
- `decision_tracking`: performance since the report recommendation.
- `decision_freshness`: whether the conclusion still matches the current data snapshot.

Watchlist rows also include `decision_priority`, `decision_alert`, and `latest_report` when a matching report exists. `decision_priority = high` means the latest data snapshot changed after the conclusion was generated and the report should be rerun.

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
  -d '{"ticker":"2330.TW","pipeline_id":"mode_a","force":false,"resume":true}'
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
