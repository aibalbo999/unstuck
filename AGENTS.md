# Stock Agent Maintenance Guide

本檔是給 AI agent 與工程師的進場導航。目標是避免查錯資料庫、走錯啟動流程、或直接拼錯報告檔路徑。

## 先做這三件事

1. 讀 [docs/system-architecture-map.md](docs/system-architecture-map.md)。
2. 執行 runtime doctor：

```bash
$(scripts/project_python.sh) scripts/doctor_runtime.py
```

3. 看目前 git 狀態，確認哪些變更不是你做的：

```bash
git status -sb
```

## Runtime 真相

- 正式本機啟動入口是 `./start_mac.command`。
- 8080 應該是 `start_mac.command` 啟動的 `uvicorn api:app`。
- Worker 應該是 `worker_main.py --role all`。
- Report index 是 `backend/cache/stock_agent_cache.sqlite3`。
- Operational state 是 `backend/cache/operational.sqlite3`。
- Decision tracking 的 current state 在 `operational.sqlite3`，不是 `backend/cache/decision_tracking.sqlite3`。
- `backend/cache/decision_tracking.sqlite3` 是 legacy migration source；不要用它驗證目前畫面狀態。

## 報告檔案規則

- 報告 artifact 可能在 `backend/output/2026-07/TICKER/...`，也可能有 legacy flat path。
- 不要直接假設 `backend/output/<filename>`。
- 新程式請使用 `report_artifacts.ReportArtifactLocator` 或現有 storage helper。
- `report_index.data_snapshot_filename` 是檔名，不保證是完整相對路徑。

## Module 放置規則

- API wiring 放 `backend/api.py`，route 行為放 `backend/api_routes/*`。
- 長流程先放 service/workflow Module，再由 route 注入依賴。
- Runtime path 真相請走 `backend/runtime_paths.py`。
- 報告 artifact 查找請走 `backend/report_artifacts.py`。
- 追蹤刷新多報告共用資料抓取請走 `backend/tracking_refresh_workflow.py`。
- 外部資料來源請走 `data_fetch` 與 provider audit，不要在 route 直接呼叫 provider。

## 修改追蹤股價刷新時必跑

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_tracking_refresh_workflow.py \
  tests/test_decision_tracking_workflow.py \
  tests/test_report_refresh_incremental.py \
  tests/test_report_artifacts.py \
  tests/test_runtime_paths.py \
  -q
```

## 修改 runtime/storage 時必跑

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_runtime_paths.py \
  tests/test_settings_env_loading.py \
  tests/test_storage_inventory.py \
  tests/test_report_artifacts.py \
  -q
```

## 常用查驗

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
pgrep -fl 'start_mac.command|worker_main.py --role all|uvicorn api:app'
$(scripts/project_python.sh) scripts/doctor_runtime.py --json
```
