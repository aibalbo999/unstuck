# Stock Agent Maintenance Guide

本檔是給 AI agent 與工程師的進場導航。目標是避免查錯資料庫、走錯啟動流程、或直接拼錯報告檔路徑。

## 先做這三件事

1. 讀 [docs/system-architecture-map.md](docs/system-architecture-map.md)。
2. 執行 runtime doctor：

```bash
scripts/project_exec.sh "$(scripts/project_python.sh)" scripts/doctor_runtime.py
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
- 來源 JSON 快取與冷卻狀態使用獨立的 `backend/cache/provider_json_cache.sqlite3`（`JSON_CACHE_DB_PATH`）；切換前須停止舊寫入者，完整複製 `cache_entries` 的鍵、值、到期時間與更新時間並核對。不得以空白新庫取代舊快取或重設冷卻狀態；原報告／checkpoint 資料庫保留原位。專案啟動與 `scripts/project_exec.sh` 會匯出此路徑，缺少必要遷移證據時拒絕來源快取操作。
- Operational state 是 `backend/cache/operational.sqlite3`。
- Decision tracking 的 current state 在 `operational.sqlite3`，不是 `backend/cache/decision_tracking.sqlite3`。
- `backend/cache/decision_tracking.sqlite3` 是 legacy migration source；不要用它驗證目前畫面狀態。

## 報告檔案規則

- 本專案的持久資料只存外接碟：正式資料留在 `/Volumes/X10 Pro Mac/stock-agent`；隔離副本、備份與查核證據放 `/Volumes/X10 Pro Mac/stock-agent-archives`，不要新增內建磁碟上的專案副本。
- 已搬移的歷史工作目錄位於 `/Volumes/X10 Pro Mac/stock-agent-archives/local-workspaces`；舊本機路徑是相容用 symlink，不是第二份資料。外接碟未掛載時應停止寫入，不得在本機建立替代資料夾。
- Mac 正式啟動會自動載入 `scripts/project_environment.sh`；其他專案命令使用 `scripts/project_exec.sh <command> [args...]`，將暫存、pip／工具快取固定到外接碟。外接碟未掛載或路徑離開外接碟時停止，不改用本機。
- Mac 隔離測試入口會自動將 `tempfile` 與 pytest 沙盒設在外接碟的 `backend/cache/tmp` 並於結束清理。備份、查核及其他持久結果使用外接碟的 `stock-agent-archives`（命令環境提供 `STOCK_AGENT_ARCHIVE_DIR`），不要另寫 `Documents/Codex`、Desktop 或本機 `/tmp`；不要搬動共用工具的全域設定或工作階段資料。

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
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_tracking_refresh_workflow.py \
  tests/test_decision_tracking_workflow.py \
  tests/test_report_refresh_incremental.py \
  tests/test_report_artifacts.py \
  tests/test_runtime_paths.py \
  -q
```

## 修改 runtime/storage 時必跑

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_runtime_paths.py \
  tests/test_settings_env_loading.py \
  tests/test_storage_inventory.py \
  tests/test_report_artifacts.py \
  -q
```

## 常用查驗

一般測試一律使用 `tests/run_prompt_boundary_tests.py`，隔離 SQLite 並禁止連線正式 Redis／API／模型供應商。不得以裸 `pytest` 驗證正式 checkout；需網路的瀏覽器測試另設臨時資料庫且僅放行測試必要網址。

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
pgrep -fl 'start_mac.command|worker_main.py --role all|uvicorn api:app'
scripts/project_exec.sh "$(scripts/project_python.sh)" scripts/doctor_runtime.py --json
```
