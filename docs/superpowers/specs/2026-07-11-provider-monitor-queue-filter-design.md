# Provider 非阻斷監控待辦過濾設計

## 目標

「今日待處理」不再提出本次資料抓取健康、且不阻擋自動重跑的 provider 監控提醒，避免非行動性訊號占用操作者待辦。

## 行為邊界

- 從 `daily_decision_queue` 排除 `blocks_auto_rerun=false` 的 `monitor_provider`。
- 保留 `blocks_auto_rerun=true` 的 `wait_provider_recovery`，因為核心資料來源異常仍需要人工處理。
- `provider_impact_ledger` 繼續保留 blocking 與 non-blocking impacts，供維運與報告診斷。
- 首頁、watchlist 今日工作台與通知計畫繼續共用過濾後的 decision queue，不加入前端例外。

## 資料流

`provider_impact` 照常建立完整 ledger。`daily_decision_queue._provider_items()` 在把 ledger row 轉成 operator action 時，只輸出 `blocks_auto_rerun=true` 的項目。如此可讓維運資料保持完整，同時讓待辦摘要、數量、排序與通知內容一致。

## 測試

- 新增回歸測試，同時輸入 non-blocking monitor 與 blocking provider recovery。
- 驗證 non-blocking monitor 不會出現在 decision queue。
- 驗證 blocking provider recovery 仍會出現，且保留 `provider_impact`、`wait_provider_recovery` 與高優先序語意。
- 保留 `provider_impact` 現有測試，確認 ledger 仍會產生 `monitor_provider`。

## 非目標

- 不刪除 provider impact ledger 或 SLA 資料。
- 不調整 provider 健康判定、資料抓取、重試或 fallback。
- 不隱藏會阻斷核心分析的 provider recovery 待辦。
