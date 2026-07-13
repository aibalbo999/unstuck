# 候選股票下一步操作設計

## 問題

「2408.TW 進入候選清單」目前只提供「查看候選」。按下後會跳到市場掃描頁，但該頁可能顯示「尚無掃描候選」，也不會保留 2408.TW 的選取狀態，因此使用者無法判斷後續要查看、追蹤或分析。

## 已核准方向

採用候選卡片三動作設計：

1. 主要動作「查看股票快照」。
2. 次要動作「加入追蹤」。
3. 次要動作「選擇分析模式」。

候選卡片顯示 ticker、公司名稱與真實入選理由，不再以 `score 18680.0`、`priority_score` 等內部排序值作為主要說明。

## 互動行為

### 查看股票快照

- 切換到「分析」頁籤。
- 將候選 ticker 帶入股票代號欄位。
- 使用既有 `StockSnapshotPanel.load(ticker)` 載入快照。
- 載入後將快照區捲入視野。
- 沿用既有 loading、error 與 snapshot action 狀態。

### 加入追蹤

- 使用既有 `StockSnapshotPanel.addToWatchlist(ticker)`，以目前選定的分析模式建立或更新追蹤。
- 按鈕執行期間 disabled，完成後沿用現有成功或失敗通知。
- 行為必須維持 idempotent，不新增另一套 watchlist API 呼叫規則。

### 選擇分析模式

- 切換到「分析」頁籤並帶入候選 ticker。
- 將分析模式選擇區捲入視野，焦點移至目前選中的模式。
- 不自動按下「開始分析」，避免誤觸消耗模型額度。

## 資料流

`daily_decision_dashboard._top_candidates()` 保留 screener item 的 `company_name`、`reason`、`score` 與 ticker。`daily_decision_queue._candidate_items()` 將公司名稱與入選理由投影到 candidate action；score 仍可保留為資料欄位，但前端 detail 優先顯示 reason。

`operator_dashboard_actions` 把 `review_candidate` 映射為 candidate 專用 action model。`operator_summary_panel` 對 candidate item 使用專用卡片 renderer，產生三個語意明確的 `<button>`。`app_panels` 以 callback 把三個 action 接到既有 stock snapshot、watchlist 與分析表單，不使用 global event 或前端自行重建 provider/API 邏輯。

## 視覺與無障礙

- 一張候選卡只有一個主要 CTA；兩個次要 CTA 視覺權重較低。
- 所有按鈕高度至少 44px，手機可直接點擊。
- 按鈕使用完整文字標籤，保留 keyboard focus ring 與 disabled 狀態。
- 狀態不能只靠顏色表達；loading、success 與 error 都要有文字。
- 手機寬度下次要動作維持兩欄；極窄或放大文字時允許換行，不得水平溢出。

## 錯誤處理

- 快照失敗：沿用 snapshot panel 的可讀錯誤，不切到空的市場掃描頁。
- 加入追蹤失敗：恢復按鈕並顯示既有 error toast。
- 缺少 ticker：candidate action 不執行並顯示可讀錯誤，不能送出空請求。
- company name 或 reason 缺失：退化為 ticker 與「市場掃描候選」，仍保留三個動作。

## 測試與驗證

- Backend test：top candidate 與 decision queue 保留 `company_name`、`reason`、ticker；detail 不再只顯示 raw score。
- Frontend contract test：candidate renderer 有三個 action、正確 ticker 與 44px touch target CSS。
- Frontend behavior test：快照 action 呼叫既有 snapshot loader；追蹤 action 呼叫既有 watchlist method；選擇模式只預填與聚焦，不觸發分析。
- Browser QA：桌機與 390px 手機均驗證三個按鈕、loading/error 狀態、無水平溢出與 keyboard focus。
- Runtime QA：live candidate 點擊後不再導向空的市場掃描頁。

## 非目標

- 不改變 market screener 排名或候選產生演算法。
- 不新增自動下單或自動開始分析。
- 不重做股票快照、watchlist 或分析 API。
- 不把 candidate card 擴張成新的 modal 或 drawer。
