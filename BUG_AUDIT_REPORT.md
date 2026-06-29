# BUG_AUDIT_REPORT

Audit date: 2026-06-30  
Project: `stock-agent`

## 1. 範圍與系統架構摘要

本次依需求閱讀並追蹤下列主要區域：

- `README.md`, `docs/architecture.md`
- `main.py`
- `analysis_jobs.py`, `report_rerun_jobs.py`
- `backend/`
- `scripts/`
- `tests/`

主要資料流如下：

1. CLI 路徑：`main.py` 解析 ticker/pipeline，透過 `StockDataService` 抓取資料，再交給 `AnalysisPipelineRunner` 與 `ReportRenderer` 產生報告。
2. API 路徑：`backend/api.py` 建立 FastAPI app，掛載 analysis/report/performance/config 等 routers。
3. Analysis job：API 透過 `analysis_job_service` 與 `job_store` 建立 SQLite job/event，再送入 task queue；worker 執行 `backend/analysis_jobs.py`，最後用 `persist_report_bundle()` 寫入 HTML/Markdown/data snapshot。
4. Report rerun job：`backend/api_routes/reports.py` 建立 rerun job，worker 走 `backend/report_rerun_jobs.py` / `backend/report_rerun_service.py`，依 scope 讀舊報告 snapshot 或重新跑 pipeline。
5. 報告儲存：目前新報告會透過 `ReportStorage` 以 partitioned key 存放，例如 `YYYY-MM/ticker/filename`，並保留部分 legacy root-level filesystem 相容邏輯。
6. SSE：job events 存在 SQLite，`EventSourceResponse` 以 event id replay/resume，並在 job terminal status 時補送終止事件。
7. 快取與資料可信度：資料抓取、SQLite cache、data snapshot、metadata、decision freshness、temporal memory 共同影響最後投資分析結論。

## 2. 已執行指令與結果

| 指令 | 結果 |
| --- | --- |
| `pytest` | 失敗：shell 找不到 `pytest` 指令。專案需要使用 `scripts/project_python.sh` 的 Python runtime。 |
| `$(scripts/project_python.sh) -m pytest` | Baseline：`806 passed, 5 skipped, 6 warnings in 132.46s`。 |
| `$(scripts/project_python.sh) scripts/check_runtime.py --strict` | 通過：`Python runtime OK: 3.13.12`。 |
| `$(scripts/project_python.sh) -m pytest tests/test_report_storage_integration.py -q` | 修復後通過：`16 passed`。 |
| `$(scripts/project_python.sh) -m pytest tests/test_report_preview.py::test_rerun_report_endpoint_attaches_existing_active_job tests/test_report_preview.py::test_rerun_report_endpoint_mode_b_queues_job tests/test_report_preview.py::test_rerun_report_endpoint_full_report_queues_job tests/test_report_preview.py::test_rerun_report_stream_replays_terminal_event tests/test_report_preview.py::test_rerun_report_cancel_endpoint_requests_cancel -q` | 修復後通過：`5 passed`。 |
| `$(scripts/project_python.sh) -m pytest tests/test_job_store.py::test_create_or_attach_active_job_is_atomic_for_concurrent_requests tests/test_analysis_job_api.py::test_create_analysis_job_attaches_existing_active_job_without_duplicate_enqueue -q` | 修復後通過：`2 passed`。 |
| `$(scripts/project_python.sh) -m pytest tests/test_cli_main.py::test_cli_exits_before_fetch_when_api_keys_missing -q` | 修復後通過：`1 passed`。 |
| `$(scripts/project_python.sh) -m pytest tests/test_report_preview.py tests/test_report_storage_integration.py tests/test_cli_main.py tests/test_analysis_job_api.py tests/test_job_store.py -q` | 修復後通過：`72 passed`。 |
| `$(scripts/project_python.sh) -m compileall main.py` | 通過。 |
| `$(scripts/project_python.sh) -m compileall backend/api.py backend/job_store.py backend/job_store_lifecycle.py backend/api_routes/reports.py` | 通過。 |
| `$(scripts/project_python.sh) -m pytest -q` | 最終全量驗證：`811 passed, 5 skipped, 6 warnings in 127.04s`。 |
| `git diff --check` | 通過，無 whitespace error。 |

未啟動 `start_mac_lan.command`。理由：本次發現與修復集中於 backend job/report/CLI 邏輯，現有測試已直接覆蓋 API route、job store、report storage、rerun service；該啟動腳本會處理互動式 runtime/Redis/環境設定，對本次明確 bug 的重現不是必要條件。

## 3. 已確認並修復的 bug

### BUG-001: Partitioned report storage 造成 rerun/compare 找不到新報告

- 風險等級：P1
- 狀態：已修復，已有 regression tests
- 相關檔案與函式：
  - `backend/api_routes/reports.py`：`rerun_report()`
  - `backend/report_rerun_context.py`：`read_report_snapshot()`, `read_report_markdown()`
  - `backend/report_rerun_service.py`：`rerun_report_analysis()`, `_build_final_rerun_context()`
  - `backend/report_compare_service.py`：`compare_reports()`, `_metadata()`
- 風險：
  - 新報告由 `persist_report_bundle()` 存到 partitioned storage key，例如 `2026-06/2308.TW/<filename>`。
  - 但部分 rerun/compare 邏輯仍只檢查 `output_dir/<filename>` 或 root-level data snapshot。
  - 使用者可能在歷史報告列表看得到報告，卻無法重跑或比較，造成 404 或報告工作流中斷。
- 重現步驟：
  1. 使用 `LocalFileStorage` 或 `InMemoryStorage` 只在 partitioned key 寫入 HTML/data snapshot。
  2. 呼叫 `POST /api/report/{filename}/rerun?scope=mode_b`。
  3. 或呼叫 `compare_reports(left, right, output_dir=...)`。
- 原本行為：
  - route/service 只看 root path，回傳 404 或讀不到 data snapshot。
- 預期行為：
  - 應透過 report storage candidate key 找到 partitioned report bundle，並保留 legacy root path fallback。
- 新增 failing tests：
  - `tests/test_report_storage_integration.py::test_report_rerun_route_queues_partitioned_storage_report`
  - `tests/test_report_storage_integration.py::test_rerun_report_analysis_reads_partitioned_source_storage`
  - `tests/test_report_storage_integration.py::test_compare_reports_reads_partitioned_local_storage`
- 修復摘要：
  - rerun route 改用 `existing_storage_key()` 檢查 HTML/data。
  - rerun context 讀 snapshot/markdown 時優先讀 `ReportStorage`，再 fallback legacy filesystem。
  - compare service 改用 `report_storage_candidates_for_filename()` 尋找 partitioned HTML/data。

### BUG-002: 同一份報告重複送 rerun 可能造成 500 或重複狀態衝突

- 風險等級：P1
- 狀態：已修復，已有 regression test
- 相關檔案與函式：
  - `backend/api_routes/reports.py`：`rerun_report()`
  - `backend/api.py`：report router dependency wiring
  - `backend/job_store.py`：`create_or_attach_active_job()`
  - `backend/job_store_lifecycle.py`：`create_or_attach_active_job()`
- 風險：
  - SQLite job table 有 active `(ticker, pipeline_id)` 唯一性約束。
  - rerun route 原本直接呼叫 `create_job(filename, f"rerun:{scope}")`。
  - 使用者快速雙擊同一 rerun scope 時，第二次可能撞 unique constraint 並變成 500。
- 重現步驟：
  1. 對同一 `filename` 與同一 `scope` 連續 POST rerun。
  2. 第二個 request 在第一個 job 仍 active 時進入 `create_job()`。
- 原本行為：
  - 第二個 request 可能 500，或產生與 job store active uniqueness 不一致的錯誤。
- 預期行為：
  - 應 attach 到既有 active rerun job，且不重複 enqueue。
- 新增 failing test：
  - `tests/test_report_preview.py::test_rerun_report_endpoint_attaches_existing_active_job`
- 修復摘要：
  - report route 支援 `create_or_attach_job` dependency。
  - FastAPI wiring 使用 `job_store.create_or_attach_active_job(..., preserve_ticker_case=True)`。
  - `preserve_ticker_case=True` 是必要的，因 rerun job 的 `ticker` 欄位實際存的是 report filename，不能被 `.upper()` 改變檔名大小寫。

### BUG-003: CLI 缺少 Gemini API key 時沒有 fail fast，可能晚到資料抓取後才失敗

- 風險等級：P2
- 狀態：已修復，已有 regression test
- 相關檔案與函式：
  - `main.py`：`main_async()`, `main()`
- 風險：
  - CLI 若缺少必要 API key，原本仍會先進入 banner/data fetch/pipeline 前置流程。
  - 對批次或人工使用者來說，錯誤訊息可能出現得太晚，也可能浪費資料供應商 call。
- 重現步驟：
  1. 清空 Gemini API key 設定。
  2. 執行 `main.py --ticker 2330.TW --no-report`。
- 原本行為：
  - 未在資料抓取前明確停止。
- 預期行為：
  - 解析參數後立即檢查 `has_api_keys()`，缺 key 時輸出設定提示並 exit code 1。
- 新增 failing test：
  - `tests/test_cli_main.py::test_cli_exits_before_fetch_when_api_keys_missing`
- 修復摘要：
  - 新增 `MissingApiKeyConfiguration`。
  - `main_async()` 在任何 fetch 前檢查 API key。
  - `main()` 捕捉該錯誤並 `sys.exit(1)`。

## 4. 尚未修復但建議追蹤的風險

### RISK-001: Report rerun attach 到 active job 時未確認 queue task 是否仍存在

- 風險等級：P2
- 相關檔案與函式：
  - `backend/api_routes/reports.py`：`rerun_report()`
  - `backend/report_rerun_jobs.py`
  - `backend/job_store.py`
- 可疑原因：
  - analysis job path 有 queue task 存在性檢查與 stale job 處理。
  - report rerun 現在會 attach active job，但尚未像 analysis path 一樣確認 RQ task 是否仍在 queue/worker。
- 可能後果：
  - 若 SQLite job active 但 queue task 遺失，下一次 rerun request 會 attach 到卡住的 job，而不是重新 enqueue。
- 建議：
  - 將 analysis job 的 task queue 存在性檢查抽成共用 helper，套用到 report rerun active attach。
  - 補測：建立 active rerun job，但 fake queue 回報 task missing，確認第二次 request 會建立或恢復可執行 job。

### RISK-002: Retention/orphan cleanup 可能未涵蓋 partitioned report storage

- 風險等級：P3
- 相關檔案與函式：
  - `backend/report_history_service.py`：`cleanup_expired_reports()`, `cleanup_orphan_markdown_reports()`
- 可疑原因：
  - cleanup 邏輯主要以 `os.listdir(output_dir)` 掃 root-level 報告。
  - 新報告可能位於 `YYYY-MM/ticker/filename`。
- 可能後果：
  - 過期或 orphan markdown/data snapshot 不會被清掉，長期造成 storage 膨脹。
- 建議：
  - 將 cleanup 改走 `ReportStorage.list_reports()` 或 report index storage candidates。
  - 先補 integration test，確認 partitioned 報告也受 retention policy 管理。

### RISK-003: yfinance ticker resolve invalid 時仍可能進入降級資料流程

- 風險等級：P2
- 相關檔案與函式：
  - `backend/data_fetch/yfinance_core_fetch.py`
  - `backend/data_fetch/adaptive_fetcher.py`
  - `backend/analysis_jobs.py`：data trust blocking
- 可疑原因：
  - `provider.resolve_stock()` 回傳 `is_valid=False` 時，部分流程會繼續使用 fallback/default payload。
  - data trust blocking 可攔住明顯 critical failure，但仍需要確認「invalid ticker + 部分預設值」是否可能產生可出報告的 degraded result。
- 可能後果：
  - 使用者輸入錯誤台股 `.TW` / `.TWO` 或無效 ticker 時，系統可能產生看似完整但其實資料基礎錯誤的投資分析。
- 建議：
  - 用 fake provider 建立無網路 deterministic test：`resolve_stock(...).is_valid=False` 且 market data 空/半空。
  - 預期應 fail closed 或明確標記 blocking，不應產生可誤解的數字。

### RISK-004: SSE disconnect event 可能造成事件表噪音；terminal fallback 無 event id

- 風險等級：P3
- 相關檔案與函式：
  - `backend/sse_service.py`
  - report rerun stream route
- 可疑原因：
  - client disconnect 時會 append `client_disconnected` event。
  - 高頻 reconnect 可能累積大量非業務事件。
  - terminal fallback 可以補 terminal payload，但若原 terminal event 遺失，fallback payload 不一定有持久化 event id。
- 可能後果：
  - correctness 風險低，但會影響 event store 成長、debug noise，以及特定 resume client 的一致性。
- 建議：
  - 設定 disconnect event sampling 或不要持久化 client-side disconnect。
  - 為 terminal fallback 補明確可 replay 的 event model，或確認現有設計已被客戶端接受。

## 5. 建議修復順序

1. 已完成：修正 partitioned report storage 造成 rerun/compare 找不到報告。
2. 已完成：修正重複 report rerun active job attach 與避免重複 enqueue。
3. 已完成：CLI 缺少 API key 時 fail fast。
4. 下一步：補 report rerun active job 的 queue task 存在性檢查，避免 stale active job 卡死。
5. 下一步：讓 retention/orphan cleanup 支援 partitioned storage。
6. 下一步：為 `.TW` / `.TWO` invalid fallback 與資料缺漏建立 deterministic tests，確認不會產生誤導性分析。
7. 後續：整理 SSE disconnect/terminal fallback 的事件持久化策略。

## 6. 已用測試重現 vs 需要人工確認

已用 failing test 重現並保留 regression tests：

- BUG-001 partitioned report storage rerun/compare 404。
- BUG-002 重複 report rerun active job 500/重複 enqueue 風險。
- BUG-003 CLI missing API key 未 fail fast。

目前屬於可疑風險，尚需更精準測試或人工確認：

- RISK-001 report rerun active job attach 未檢查 queue task 是否仍存在。
- RISK-002 retention/orphan cleanup 對 partitioned storage 覆蓋不足。
- RISK-003 invalid ticker / provider fallback 是否可能產生誤導性 degraded report。
- RISK-004 SSE disconnect event noise 與 terminal fallback replay 一致性。

## 7. 變更原則

- 未新增大型依賴。
- 未大幅重構架構。
- 未改變對外 API contract；僅修正明確錯誤行為：
  - partitioned report 現在可被 rerun/compare 正確讀取。
  - 同一 active rerun job 會被 attach，不再造成第二次 request 500。
  - CLI 缺 API key 時明確停止並回傳 exit code 1。
