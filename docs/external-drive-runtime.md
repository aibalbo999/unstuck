# 外接硬碟執行

## 位置與啟動

系統實體位置：`/Volumes/X10 Pro Mac/stock-agent`。

在 Finder 開啟該資料夾，雙擊 `start_mac_lan.command`，保留終端機視窗。
本機入口為 `http://127.0.0.1:8080`，區網入口以啟動視窗列出的 IP 為準。
只需本機存取時可使用 `start_mac.command`。

請直接使用上述實體路徑。2026-09-06 查驗時，舊的
`/Users/balbomacmini/Desktop/onstock/stock-agent` 不存在，不能假設桌面符號連結仍可使用。
硬碟必須先掛載為 `X10 Pro Mac`；執行期間不要退出或拔除硬碟。
退出硬碟前，先在啟動視窗按 Ctrl+C，等 API、Worker 與本次啟動的 Redis 停止。

## 環境與資料

- Python 虛擬環境在新位置重建；不要直接搬用舊位置的 `.venv`。
- Homebrew Python 3.13 與 Redis 仍由這台 Mac 提供，並非可直接插到任意電腦執行的封裝。
- 設定、追蹤清單與 SQLite 資料庫跟隨專案保存；不要更動 `.env` 的金鑰。
- 報告索引：`backend/cache/stock_agent_cache.sqlite3`。
- 追蹤與任務狀態：`backend/cache/operational.sqlite3`。
- 報告檔案：`backend/output`，仍由 artifact locator 解析月份與股票子目錄。
- 啟動器建立的 Redis 使用 `backend/cache/redis`，沿用原本不做週期性持久化的設定。
- `TASK_QUEUE_BACKEND`、`REDIS_URL`、`TASK_QUEUE_NAME` 優先保留啟動環境的設定，
  未指定時讀取 `backend/.env`，最後才採用本機預設值；啟動器不改寫既有 `.env`。
- 8080 若由無法確認為同專案的程序占用，啟動器會拒絕啟動並保留該程序。
  舊 Worker PID 也會先核對命令與實體工作目錄，不會僅憑 PID 檔停止程序。

## 檢查

磁碟名稱含空白，Python 路徑展開需加引號：

```bash
cd "/Volumes/X10 Pro Mac/stock-agent"
"$(scripts/project_python.sh)" scripts/doctor_runtime.py --json
```

如需重建環境：

```bash
PYTHON_BIN=/opt/homebrew/bin/python3.13 scripts/bootstrap_venv.sh
scripts/setup_visual_regression.sh
```

## 追蹤報告重建

`scripts/rebuild_tracked_reports.py` 的正常流程是 `prepare` → `submit` → `status`。
`prepare` 建立新的 manifest，記錄已啟用追蹤股票、模式及既有 artifact 的內容雜湊；
`submit` 經一般分析 API 批次提交，保留歷史報告，已有 `job_id` 的項目不重複提交。
提交使用 `force=false, resume=true`：若同股票／模式已有執行中工作，沿用該工作而不取消；
沒有執行中工作時仍建立新 ID 與新分析。這不是跨工作生命週期的冪等保證。
請先確認 manifest 列出的股票與模式符合本次意圖。

重建不會更換模型路由、重置額度或恢復暫停的佇列。API 拒絕請求時立即停止該次提交；
已接受的工作仍由既有 Worker 並行設定、配額檢核及延後重試機制處理。
每次 POST 前會原子保存 `submission_state=pending` 與 `submission_started_at`，
取得有效工作 ID 並成功存檔後才標記 `accepted`。若逾時、回應不明或接受後存檔失敗，
`status` 顯示 `pending_confirmation`，再次 `submit` 會停止整批，不自動重送。
請依股票、模式與送出時間核對既有工作，先停止操作此 manifest 的命令，
再由維護人員將查證所得的 `job_id` 附回對應項目；可一併將 `submission_state` 改為 `accepted`，
保留原始送出時間，執行 `status` 確認後再繼續。不要刪除 pending 標記或另建相同批次繞過核對；
查不到確定工作 ID 時，須先釐清伺服器是否接受，不能將「未找到」視為安全重送依據。
再次 `submit` 只接續尚未嘗試送出的項目。舊版 manifest 若曾送出但未記錄 ID，
也必須先人工核對，不能只依缺少 pending 標記推論未送出。
所有操作以 manifest 旁的專用空鎖目錄序列化，鎖內重新讀取檔案；
請勿在命令執行期間移除 `.<manifest 檔名>.lock` 目錄或手動編輯 manifest。

`purge` 是選用維護動作，不是重建前置條件。必須同時提供 `--confirm-purge`、
逐一指定的 `--report-key`，以及輸出目錄以外、尚不存在的 `--backup-dir`。
只允許清除 manifest 中已記錄且內容未變的精確檔案；刪除前重新檢查執行中工作，
在 report storage lock 內完成備份與逐檔驗證，再保存備份清單後刪除。
未選取的歷史檔不受影響。備份失敗不刪來源；舊 manifest 若沒有內容雜湊，須重新 prepare。
需要還原時，依 manifest 的 `purge_backups`、相對 key 與 SHA-256 核對備份，
由維護人員還原並同步報告索引，不得直接覆蓋後來產生的新版報告。

歷史批次的 manifest 或臨時路由檔不代表目前執行設定。
目前 runtime 以 doctor、啟動程序及 `/api/observability/api-quotas` 的已載入政策為準；
未覆寫 `MODEL_ROUTES_FILE` 時使用 `backend/model_routes.json`。
