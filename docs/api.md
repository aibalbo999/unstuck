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

## Maintenance Dry Run

Cleanup APIs are dry-run unless `write=true` is explicit:

```bash
curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-analysis-history?retention_days=30"

curl -X POST -H "X-Mutation-Token: $TOKEN" \
  "http://127.0.0.1:8080/api/maintenance/cleanup-analysis-history?retention_days=30&write=true"
```
