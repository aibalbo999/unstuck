# Worker、LangGraph 與儲存抽象化設計

## 目標

本次重構把 FastAPI、長時間分析工作、排程器與本機儲存責任拆成可獨立啟動、測試與替換的元件，同時保留現有 HTTP API、分析結果格式與報表相容性。

完成後系統必須具備以下性質：

- FastAPI 程序只處理 HTTP、查詢狀態與將可序列化任務送入 Redis Queue（RQ）。
- 分析 Worker、watchlist scheduler、decision tracking scheduler 與 maintenance loop 不在 FastAPI lifespan 中執行。
- 現有 `pipeline_modes.py` 定義的每個 Agent 都成為 LangGraph 節點；舊的 `_run_agent_groups` DAG 迴圈不再負責正式調度。
- 每個分析 run 以 `job_id` 作為 LangGraph `thread_id`，透過 SQLite checkpointer 保存節點邊界與 pending writes。
- 報表內容與快取透過介面注入；本機檔案、SQLite、Redis 與記憶體實作不洩漏到呼叫端。
- 每個程序自行建立及關閉 `StockDataService`、Redis client、LLM client 與 SQLite connection，不跨程序共享連線物件。

## 已確認的架構決策

### Queue transport

Web／Worker 分離模式固定使用 Redis + RQ。既有 `LocalAsyncQueue` 只保留給單程序測試與明確的內嵌開發情境，不得由 Web API 使用；否則 API 送入的記憶體任務無法被另一個程序取得。

`TASK_QUEUE_BACKEND` 的正式預設值改為 `rq`。`create_api_task_queue()` 在 Web 程序中會拒絕 `local`，並以清楚錯誤指出需啟動 Redis。一般 `create_task_queue()` 仍可在測試中建立 `LocalAsyncQueue`。

### 程序模型

新增 `backend/worker_main.py`，提供以下角色：

- `queue`：執行 RQ Worker，消費 `stock-analysis` queue。
- `schedulers`：在單一 asyncio event loop 中註冊 watchlist 與 decision tracking 兩個 scheduler task；它本身與 queue worker 是不同 OS 程序。
- `maintenance`：執行報表、快取與 index 清理週期。
- `all`：本機便利模式，以 `multiprocessing.get_context("spawn")` 啟動上述三個角色，轉送 SIGINT／SIGTERM 並等待子程序關閉。

使用 `spawn` 是強制條件。父程序不預先建立 SQLite、Redis 或 HTTP client，因此不會把鎖或 socket 複製到子程序。

### LangGraph 版本

依賴固定為 `langgraph==1.2.6` 與 `langgraph-checkpoint-sqlite==3.1.0`，並重新產生 `backend/requirements.lock`。測試使用 `InMemorySaver`，正式本機 Worker 使用 `AsyncSqliteSaver`。

## 元件設計

### 1. FastAPI 入口

`backend/api.py` 的 lifespan 僅執行輕量設定檢查，以及在 shutdown 關閉 API 程序自己建立的 HTTP／Redis client。下列行為全部移除：

- `analysis_task_queue.start_workers()`／`stop_workers()`
- `_mark_abandoned_local_jobs()` 與 local runtime file lock
- `_cleanup_reports_forever()`
- `create_watchlist_scheduler_task()`
- `create_decision_tracking_scheduler_task()`
- Worker 所屬 SQLite store cleanup

Router 仍透過 `AnalysisRouteDeps.get_analysis_task_queue` 取得 queue producer。enqueue 的 function 必須是 module-level importable callable；RQ payload 不得包含 `StockDataService`、lock、connection、closure 或 compiled graph。

### 2. Worker runtime container

新增 `backend/runtime_dependencies.py`，集中建立程序內資源：

- `WorkerRuntime.stock_data_service`
- `WorkerRuntime.report_storage`
- `WorkerRuntime.cache_backend`
- `WorkerRuntime.task_queue`
- `WorkerRuntime.checkpoint_path`

`WorkerRuntime.close()` 只關閉自己建立的資源，並呼叫現有 thread-local SQLite store close functions。API 使用獨立的 `ApiRuntime`，不建立 `StockDataService` 或 checkpointer。

### 3. LangGraph state

保留 `backend/agent_state.py` 的 Pydantic `AgentState` 作為領域驗證模型。新增 JSON-compatible `AgentGraphState` TypedDict 作為 LangGraph channel schema，直接包含：

- `run_id`, `ticker`, `company_name`, `pipeline_id`
- `raw_financial_data`, `provider_values`, `normalized_financials`
- `source_audit`, `validation_issues`, `circuit_breaker`
- `peer_context`, `quant_metrics`, `tool_results`
- `agent_reports`, `risk_flags`, `execution_trace`
- `analyses`, `structured_outputs`, `blocking_issues`, `final_audit`
- `started_at`, `total_time`, `status`, `retryable_error`

State 只保存 JSON／msgpack 可序列化資料，不保存 rotator、HTTP client、callback、lock、RAG object 或 compiled graph。`agent_reports`、`analyses`、`structured_outputs` 與 trace 使用 reducer 合併平行節點輸出，避免 concurrent update collision。

Pydantic `AgentState` 與 `AgentGraphState` 之間由明確 adapter 轉換；每個節點輸入與 checkpoint 恢復後都會重新驗證領域欄位，避免 TypedDict 讓無效資料悄悄流入後續 Agent。

### 4. Graph topology

`backend/workflow_graph.py` 依 `pipeline_modes.get_pipeline_definition()` 建立一張 graph：

```text
START
  -> initialize
  -> validate_data
      -> repair_data -> validate_after_repair
      -> prepare_analysis
  -> configured agent nodes/groups
  -> final_audit
  -> tear_sheet
  -> finalize
  -> END
```

`validate_data` 與 `validate_after_repair` 使用 conditional edge：

- circuit breaker closed：進入 `prepare_analysis`。
- circuit breaker open 且 repair attempts 尚未達上限：進入 `repair_data`。
- repair 後仍 open 或已達上限：進入 `blocked_finalize`，產生資料衝突狀態並結束，不執行估值 Agent。

現況並非固定七個 Agent：v1、v2、v3、v4 分別有 10、8、5、3 個分析模組。因此實作以設定檔為準，為每個 configured Agent 建立節點；同一 `groups` tuple 內的節點在同一 super-step 平行執行，下一組使用 join edge 等待所有節點完成。這同時涵蓋舊文件提到的七個核心分析引擎，也不會犧牲現有模式。

每個 Agent node 會建立當次的 legacy compatibility context，呼叫既有 `run_agent_with_quality_gates_async()`，再只回傳該 Agent 產生的 state delta。節點不直接 mutate 共用 dict。當所有 graph 測試通過後，`pipeline_async.py` 只保留 thin compatibility wrapper，舊 `_run_agent_groups` 調度碼移除。

### 5. Checkpoint、429 與恢復

正式 graph 使用 `backend/cache/langgraph_checkpoints.sqlite3`，或 `LANGGRAPH_CHECKPOINT_PATH` 指定的位置。初始化 connection 時設定：

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=30000;
PRAGMA synchronous=NORMAL;
```

Agent node 配置 `RetryPolicy`，僅對明確認定的 timeout、連線錯誤與 HTTP 429／rate-limit 錯誤做指數退避。輸入驗證、程式錯誤與不可恢復的模型錯誤不自動重試。

RQ job wrapper 的流程：

1. 以 `job_id` 組出 `{"configurable": {"thread_id": job_id}}`。
2. 若沒有 checkpoint，呼叫 `graph.ainvoke(initial_state, config)`。
3. 若存在未完成 checkpoint，呼叫 `graph.ainvoke(None, config)`，從最後成功 super-step 繼續。
4. rate-limit 重試耗盡時，將 job store 狀態標記為 `waiting_retry` 後向 RQ raise；RQ 的延遲 retry 重新呼叫同一 wrapper。
5. 已完成 graph 再次收到相同 job id 時回傳既有 final state，不重複產生報表。

平行 super-step 中已完成節點的 pending writes 由 LangGraph checkpointer 保存；另一節點失敗後恢復時不重做成功的 LLM 呼叫。

### 6. ReportStorage

新增 `backend/storage/report_storage.py`：

```python
class ReportStorage(Protocol):
    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport: ...
    def get_report(self, key: str) -> StoredReportContent | None: ...
    def delete_report(self, key: str) -> bool: ...
    def exists(self, key: str) -> bool: ...
    def list_reports(self, *, prefix: str = "") -> list[StoredReport]: ...
```

`LocalFileStorage`：

- root 預設為 `OUTPUT_DIR`。
- 拒絕 absolute path、`..` 與任何逃出 root 的 resolved path。
- 以同目錄 temporary file + `os.replace` 做 atomic write。
- 不把 `Path` 當作介面回傳值，避免未來 S3 實作被本機路徑綁死。
- metadata 由 `StoredReport` dataclass 表示。

`InMemoryStorage` 使用 lock 保護私有 dict，內容一律複製，供單元測試與 graph 測試注入。

既有 `report_repository.py` 繼續只負責 SQLite metadata index；它不與 `ReportStorage` 合併。`analysis_jobs.py`、CLI 報表輸出與 report route 的內容讀寫改由 `ReportStorage` 完成，metadata index 仍由原 repository 更新。

### 7. CacheBackend

新增 `backend/cache_backends.py`：

```python
class CacheBackend(Protocol):
    def get_json(self, key: str) -> object | None: ...
    def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> bool: ...
    def close(self) -> None: ...
```

實作包含：

- `LocalRedisCache`：使用 `redis-py`、namespace prefix、UTF-8 JSON、Redis TTL；Redis 錯誤不靜默降級成程序內 cache，避免不同 Worker 看見不同資料。
- `SqliteCacheBackend`：包裝現有 SQLite cache 行為，保留單程序相容性。
- `InMemoryCache`：測試用、具 TTL 語意。

既有 `cache_store.py` 的 function API 成為 compatibility facade，委派給設定工廠建立的 backend，讓既有 data fetcher 可逐步遷移而不需要一次修改所有呼叫端。

### 8. Dependency injection

新增設定：

- `REPORT_STORAGE_BACKEND=local|memory`，正式預設 `local`。
- `CACHE_BACKEND=redis|sqlite|memory`；Worker 預設 `redis`，測試明確使用 `memory`。
- `LANGGRAPH_CHECKPOINT_PATH`。
- `WORKER_ROLE` 與 RQ retry/backoff 參數。

`runtime_dependencies.py` 提供 pure factory：

- `create_report_storage(settings)`
- `create_cache_backend(settings)`
- `create_api_runtime(settings)`
- `create_worker_runtime(settings)`

FastAPI dependency 只從 `request.app.state.runtime` 取介面；Agent／workflow node 從 LangGraph runtime context 或建圖時注入的 immutable dependency bundle 取得介面。測試可以直接傳入 `InMemoryStorage`／`InMemoryCache`，不需 monkeypatch module global。

## 資料與控制流程

1. HTTP route 建立 job store 記錄並送出 RQ job，只回傳 `job_id`。
2. RQ Worker import module-level job wrapper，在子程序內建立 workflow dependencies。
3. wrapper 檢查相同 `thread_id` 是否已有 checkpoint，再選擇 initial invoke 或 resume invoke。
4. graph 驗證與 repair 資料，按 pipeline definition 平行或循序執行 Agent。
5. 每個節點完成時寫 checkpoint；job store progress callback 只寫可觀測事件，不進 checkpoint state。
6. finalize node 透過 `ReportStorage` 原子保存 HTML、Markdown 與資料快照，再更新 metadata index。
7. API 持續從 job store 讀狀態與事件，完全不持有分析 coroutine。

## 錯誤處理

- Redis 無法連線：API health/startup 顯示 queue unavailable，mutation route 回傳 503，不接受會永久遺失的分析任務。
- Worker Redis 中斷：RQ 自身重連；程序以非零狀態退出時交由 launchd、Docker Compose 或其他 supervisor 重啟。
- HTTP 429／暫時網路錯誤：LangGraph node 短期 retry，超過上限後交由 RQ 延遲重試並以 checkpoint resume。
- circuit breaker：只走 repair 一次；仍失敗時走 blocked finalize，禁止估值與最終建議引用衝突數據。
- SQLite busy：WAL + 30 秒 busy timeout；所有 transaction 保持短小，不在 LLM await 期間持有 transaction。
- report write 失敗：temporary file 不取代正式檔；metadata index 只在內容成功落地後更新。
- scheduler 單次錯誤：記錄錯誤後等待下一 interval；CancelledError 正常向外傳遞以便 shutdown。

## 測試策略

### API／Worker

- 驗證 FastAPI lifespan 不呼叫 queue worker、scheduler 或 maintenance。
- 驗證 Web 使用 local queue 時 fail fast。
- 驗證 `worker_main` 各 role 只初始化自己需要的依賴。
- 驗證 `all` 使用 spawn、轉送 termination 並等待子程序。

### LangGraph

- 驗證 validation closed 直接進入 Agent。
- 驗證 open circuit 進 repair，修復成功後進入 Agent。
- 驗證 repair 後仍 open 時進 blocked finalize，Agent 不執行。
- 驗證 pipeline group 產生正確節點與 join edge。
- 以暫存 SQLite checkpointer 模擬某 Agent 第一次拋出 429；第二次相同 `thread_id` 從失敗節點恢復，先前成功節點 invocation count 保持 1。
- 驗證 parallel reducer 不遺失任一 Agent report。

### Storage／Cache

- `LocalFileStorage` atomic save、read、list、delete。
- path traversal 與 absolute path 被拒絕。
- `InMemoryStorage` 不洩漏 mutable reference。
- Redis key namespace、JSON round-trip、TTL、delete 與 connection error。
- SQLite compatibility facade 與 InMemory TTL。
- FastAPI／Worker factory 能由設定選擇實作，Agent node 只依賴 protocol。

### 回歸驗證

- 執行新增測試檔。
- 執行完整 `pytest`。
- 執行專案既有 `scripts/check_runtime.py` 與 import-boundary 測試。
- 以無外部 API 呼叫的 fake Agent graph 做一次 RQ enqueue／worker integration smoke test。

## 文件與操作方式

README 與 operator guide 必須加入：

```bash
redis-server
python backend/worker_main.py --role all
uvicorn api:app --app-dir backend
```

也要記錄正式部署可將角色拆為三個服務、health check、checkpoint DB 備份方式，以及 `local` queue 不支援 Web／Worker 跨程序的原因。

## 不在本次範圍

- AWS S3、ElastiCache、Postgres checkpointer 的正式實作。
- Celery 或 Redis Streams 的第二套 queue backend。
- 重寫既有 Agent prompt、評分規則或報表視覺設計。
- 將所有 metadata SQLite repository 一次搬到雲端資料庫。
- 變更既有 HTTP response schema 或前端 polling protocol。

## 驗收條件

- 啟動 FastAPI 不會產生分析 worker task、scheduler task 或 cleanup task。
- API enqueue 後，可由另一個 OS 程序的 RQ Worker 消費。
- kill Worker 後以相同 job id 重跑，已 checkpoint 的 Agent 不重複執行。
- validation circuit breaker 的三條路徑都有自動化測試。
- 報表與 cache 呼叫端可在不修改業務邏輯下切換 local、Redis 或 memory backend。
- 完整測試套件通過，且未留下正式 DAG group runner 作為主要執行路徑。
