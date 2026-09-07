# 正式報告更新候選清單（唯讀盤點）

盤點時間：2026-09-07 14:23:04（Asia/Taipei）。本文件只記錄候選盤點，不代表已送件或重建。

- API：`http://127.0.0.1:8080/api/reports?limit=100&include_versions=true`
- schema：`stock-agent.report-update-candidates.v1`
- 完整 indexed reports：`148`（兩頁，100 + 48）；`current=109`、`needs_rerun=39`。
- 完整排序清單內容 hash：`0e870f7451506bdcccfd7753191a6661766d4db4774102aca5bf5c5d8c2417cd`。
- 追加唯讀 runtime 盤點（2026-09-07 22:30 Asia/Taipei）：`/api/observability/active-jobs` 回傳 `active_count=0`（10 筆歷史 job 均 `done`）；`/api/decision-tracking` 回傳 7 筆且 `enabled=7`，10 秒界線內約 4.03 秒完成。
- canonical DB 對帳：`backend/cache/stock_agent_cache.sqlite3` 的 `reports` 為 148 筆、`analysis_text_stale=39`；`backend/cache/operational.sqlite3` 的 tracking 為 7／7 enabled，`analysis_jobs` 沒有 queued／running／waiting_retry（僅 done／error／cancelled）。
- 代表報告的 `reproducibility_packet.code_commit`／`code_dirty` 仍為空／null；因此 indexed report 與 health 讀取不能反推執行中 API／Worker 已載入哪個 revision。
- 本分支新增 `/api/runtime-identity`（`stock-agent.runtime-identity.v1`）供重啟後驗證 process commit；目前 2026-09-06 啟動的 live 程序對此新路徑回 `404`，證實它尚未載入本分支新增 API。
- 代表 stale candidates：`1623.TW/v1`、`1623.TW/v4`、`2308.TW/v3` 均明示 `needs_rerun=true`，原因是 snapshot 已刷新而 HTML／Markdown 結論尚未重跑。
- 另以 `scripts/rebuild_tracked_reports.py prepare-indexed` 讀取同一 indexed API 建立 prepare-only manifest：148 筆版本收斂為 57 個 ticker／mode 最新群組，其中 29 個 `current`、28 個 `needs_rerun`；這 28 個只是候選清單，不是已核定送件數。
- `prepare-indexed` 只寫入新 manifest，並以 `prepare_only=true` 標記；`submit` 對此標記會在任何 POST 前拒絕，避免唯讀盤點被誤當成送件授權。

工具：[`scripts/inspect_report_update_candidates.py`](/Volumes/X10 Pro Mac/stock-agent/scripts/inspect_report_update_candidates.py)。工具要求明確新輸出路徑、逐頁核對 total／identity、記錄 HTML／Markdown／snapshot hash 與時間欄位，並以 exclusive create 防止覆寫。

目前只完成唯讀 prepare；尚未核定要更新的報告集合，也未送出 Job、重啟 API／Worker 或改寫正式 artifacts。若要進入 F4 submit，必須先確認每 ticker／mode 的範圍與目前程序 revision，再逐批核對 Job／artifact。
