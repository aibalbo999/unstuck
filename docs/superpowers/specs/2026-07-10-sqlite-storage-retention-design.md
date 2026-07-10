# SQLite 容量治理設計

## 背景

本機 runtime 將 report index 與 LangGraph checkpoint 共用 `stock_agent_cache.sqlite3`。既有 SQLite 維護流程依 `cache_db`、`task_db`、`checkpoint_db` 標籤逐一處理，未依 canonical path 去重，因此 `cache_db` 與 `checkpoint_db` 會對同一檔案重複備份、checkpoint 與 `VACUUM`。備份目錄也沒有保留政策，造成 39 份備份累積至 18.09 GiB。

## 目標

- 同一個 canonical SQLite path 每輪只備份、checkpoint、`VACUUM` 一次。
- 每日備份預設只保留最近 3 個 UTC 日曆日，可由環境變數調整。
- 備份輪替只處理符合系統命名規則的 SQLite 備份，不碰未知檔案。
- 提供終態分析任務 checkpoint 的 dry-run/write 清理命令；預設不由 Worker 自動刪除。
- 保留既有報告、追蹤資料與執行中／待重試任務 checkpoint。

## 方案比較

### A. 只做人工清理

變更最少，但下一輪每日維護仍會產生重複備份與大型 WAL，問題會復發。不採用。

### B. 路徑去重、備份輪替、顯式 checkpoint 清理

在既有 maintenance boundary 內修正，保留 SQLite/local-first 架構。備份輪替自動執行；checkpoint 清理必須由操作員先 dry-run 再加 `--write`。採用此方案。

### C. 立即拆分 checkpoint DB 或遷移 PostgreSQL

長期可改善高併發，但涉及 runtime migration、部署與回復策略，超出本次容量事故範圍。不採用。

## 設計

### Canonical path 去重

`runtime_sqlite_paths()` 仍維持 `cache_db`、`task_db`、`checkpoint_db` 優先序，但新增 path identity 去重。路徑以 `expanduser().resolve(strict=False)` 正規化；較早加入的標籤保留，後續相同 path 不再加入維護清單。

目前預設設定下，輸出只包含：

- `cache_db -> stock_agent_cache.sqlite3`
- `task_db -> operational.sqlite3`

因此不再建立語意重複的 `checkpoint_db-YYYYMMDD.sqlite3`，也不再對 report/checkpoint DB 執行兩次 `VACUUM`。

### 備份保留政策

新增 `SQLITE_BACKUP_RETENTION_DAYS`，預設 3。維護回傳值加入 `backup_pruning`，列出 cutoff、候選檔、刪除檔與 dry-run 狀態。

輪替只匹配：

```text
cache_db-YYYYMMDD.sqlite3
task_db-YYYYMMDD.sqlite3
checkpoint_db-YYYYMMDD.sqlite3
```

cutoff 使用本輪維護的 UTC 日期，保留當日及前 `retention_days - 1` 天。未知檔名、目錄與非 SQLite 檔案一律跳過。dry-run 只回報；`write=True` 才刪除。

### 終態 checkpoint 清理

新增 `checkpoint_maintenance.py`：

1. 從 `TASK_DB_PATH.analysis_jobs` 讀取 `done`、`error`、`cancelled` job IDs。
2. 從 checkpoint DB 讀取 distinct `thread_id`，以第一個 `:` 前綴映射 job ID。
3. 只選取映射到終態 job 的 threads；`queued`、`running`、`waiting_retry` 或無法映射的 threads 保留。
4. dry-run 回報 threads、`checkpoints` rows、`writes` rows 與 payload bytes。
5. `write=True` 以批次 transaction 先刪 `writes`，再刪 `checkpoints`。

命令入口：

```bash
scripts/maintenance.sh cleanup-terminal-checkpoints
scripts/maintenance.sh cleanup-terminal-checkpoints --write
```

此命令不自動執行 `VACUUM`。操作員應在服務停止且 dry-run 已確認後，再執行既有 SQLite 維護完成 checkpoint、壓縮與備份。

## 失敗與安全邊界

- 備份建立失敗時，不宣稱該 DB 已受保護；錯誤沿用既有 sanitized error 回報。
- 輪替不處理未知檔名，避免刪除人工封存檔。
- checkpoint schema 或 task schema 缺失時回傳 `exists/schema_ready=false`，不刪資料。
- active/unmatched thread 永遠不列入刪除候選。
- 實際清理前必須停止 `start_mac.command`，且不得直接刪除 `*.sqlite3-wal`。

## 驗證

- 單元測試：相同 canonical path 只出現一次。
- 單元測試：3 天 cutoff、dry-run、write、未知檔名保留。
- 單元測試：只有終態 job threads 被清理，active/unmatched threads 保留。
- 回歸測試：既有 maintenance、runtime/storage tests 全部通過。
- runtime 驗證：正式啟動後 8080、Worker、報告列表、watchlist 與 decision tracking API 可用。

