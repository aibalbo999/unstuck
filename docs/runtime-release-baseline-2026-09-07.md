# Runtime release preflight baseline（唯讀）

盤點時間：2026-09-07 23:15:33（Asia/Taipei；UTC `2026-09-07T15:15:33.185669+00:00`）。本文件只記錄 F4 release 前基線，不代表已重啟或已送件。

執行入口：[`scripts/capture_runtime_release_baseline.py`](/Volumes/X10%20Pro%20Mac/stock-agent/scripts/capture_runtime_release_baseline.py)。輸出使用新且明確的 baseline path，工具不讀取 secrets 值、不送 mutation request，也不覆寫既有輸出。

- Git：HEAD `ae3bf2113edb5d21725aac6ccb102901f2d93860`，`dirty=false`。
- Process：Redis PID `69375`、Worker PID `69377`、API PID `69379`；Worker／API cwd 均為 `/Volumes/X10 Pro Mac/stock-agent/backend`。三者均於 2026-09-06 啟動，早於本分支目前 revision。
- Readiness：`/healthz=200`、`/readyz=200/ready`、`/api/observability/active-jobs=200` 且 `active_count=0`、`/api/decision-tracking=200` 且 `enabled_count=7`。
- Report index：`148` 筆、`current=109`、`needs_rerun=39`；baseline-specific sorted inventory hash `0d8ac037d8951bffb37bb15a8fc663914832f82899ac164d831d1d81ba52f643`。
- Revision gate：目前 live `/api/runtime-identity=404`；這是舊程序未載入本分支 endpoint 的直接證據，不能用 checkout HEAD 代替 live revision。
- DB：`stock_agent_cache.sqlite3` `8,769,073,152` bytes、`operational.sqlite3` `659,181,568` bytes；超過工具 `512 MiB` hash 上限，故只記大小與 `hash_status=too_large`，不讀取或改寫內容。

此 baseline 可在正式 reload 後重跑並逐欄比較；在取得核定報告範圍與 reload 授權前，不執行 POST、重啟或報告重建。
