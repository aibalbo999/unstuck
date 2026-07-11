# 模型路由警示待辦過濾設計

## 目標

「今日待處理」不再提出純效能型模型路由警示，避免正常但較慢或曾經重試的模型呼叫占用操作者待辦。

## 行為邊界

- 從 `daily_decision_queue` 排除 `slow_route` 與 `retry_storm`。
- 保留 `quality_gate_failures`，因為它代表分析品質未通過，仍需要人工注意。
- `model_route_budget` 繼續保留完整路由統計與警示，供維運面板診斷。
- 首頁、watchlist 今日工作台與通知計畫會自然繼承過濾後的 decision queue，不另外加入前端例外。

## 資料流

`model_route_budget` 仍產生所有路由警示。`daily_decision_queue._route_warning_items()` 在把警示轉成 operator action 前，僅接受需要操作者處理的警示類型。如此可讓維運資料保持完整，同時確保待辦摘要、數量、排序與通知內容一致。

## 測試

- 新增回歸測試，輸入 `slow_route`、`retry_storm` 與 `quality_gate_failures`。
- 驗證前兩者不會出現在 decision queue。
- 驗證 `quality_gate_failures` 仍會出現，且來源與 action type 維持 `model_route_budget`／`model_route_warning`。
- 保留 `model_route_budget` 現有測試，確認底層仍會產生完整警示。

## 非目標

- 不調整 P95 門檻、重試門檻或遙測寫入。
- 不刪除維運面板的路由資料。
- 不改變模型選擇、fallback 或重試策略。
