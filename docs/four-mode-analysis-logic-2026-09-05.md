# 四模式分析邏輯優化

本批依使用者核准的三批方向實作。修改位置為 `/Volumes/X10 Pro Mac/stock-agent`，保留同 checkout 其他任務的未提交變更。

## 模式行為

| 模式 | 本批調整 |
| --- | --- |
| A 長線研究 | 護城河未知值維持 null／未評估，包含 legacy parser 與 HTML；統一最終 recommendation 提示與 schema，不再一面要求建議、一面禁止相同欄位。 |
| B 部位決策 | 檢查進場、停損、同期間目標、部位與風報比；依建議區分 Long／Short。等待＋0% 是合法不交易，但不能同時指示進場。 |
| C 泡沫／反證 | 不預設必須放空；Agent 21 挑戰空方論點。分開估值、催化時機和可執行空單；反證不足不補造風險數量。 |
| D 極短線 | 同次既有行情抓取產生日 OHLCV，供 22／24 讀取日線與技術指標、未來14日事件；回測使用5／10交易日，不再當作3／6／12月預測。 |

「避免」表示不建立新部位，不等於預測價格下跌。持有的策略報酬跟隨既有多頭部位，不再固定為0；避免的現金策略報酬為0，明示不計現金利息。

## 證據與修復一致性

- 護城河缺值不補1、0、預設分數，也不把其他已知維度平均成未知的整體分數。
- 日線最多保存120筆；提示詞一般顯示20筆、compact顯示5筆。SMA5/10/20/60、RSI14、MACD12/26/9、ATR14與量能採確定性計算，暖機／欄位不足維持null。
- 事件保留日期、來源與確認程度；排除窗口外事件，無日期事件不冒充已確認的近期催化。
- 日線、指標與事件列入核心 snapshot 保存欄位，超尺寸縮減也保留這些來源。
- 摘要hash使用完整可見上游正文、structured outputs及prompt版本，依實際pipeline群組辨識依賴，不靠Agent編號大小。
- 舊版本摘要不可直接沿用。前序內容與State衍生報告共用總預算，整欄省略，不切碎JSON或價格；原始財務與工具證據優先。
- 成功採納修復時同步AgentState；失敗草稿不替換正式分析。checkpoint回讀以最新版報告重建Agent風險，保留外部風險，避免舊結論再次倒灌。

## 交易契約與回測邊界

- Long驗證 `stop < entry < target`；Short驗證 `target < entry < stop`，以完整進場區間的最不利價格驗算。
- B可選 `target_price` 必須是同期間交易目標，不能借用recommendation的12月目標。
- B／C可選 `horizon_trading_days` 為1–252整數；未知為null，不推定期間。缺少明確期間時不產生交易回測。
- B／C／D可選 `transaction_cost` 為每股來回成本金額，非百分比。缺值不補0；明確提供成本才產生淨報酬。
- 日OHLC區分未成交、先目標、先停損、期滿退出、同根先後不明及資料不足；不將未知／未成交列算成命中或失敗。
- 只支援明確價格、價格區間與單純突破／跌破觸發。複合事件條件缺少可驗證事件歷史時保留資料不足。
- 不交易計畫沿用最終稽核的相同契約；若文字仍指示進場，或缺少觀察理由／重新檢查條件，回傳 `invalid_observation_contract`，不取價、不儲存回測，也不產生虛構的現金報酬。
- 區間部分觸及時，模擬成交價必須位於當日OHLC與進場區間的交集。跳空停損按不利開盤價處理。
- 新交易結果使用獨立 `trade_evaluation_results_v1`；不改寫舊月回測列。API分開提供 `summary/by_horizon` 與 `trade_summary/trade_by_horizon`，畫面區分月份與交易日，未知報酬顯示N/A。
- 歷史記憶只讀同ticker、同模式；讀取實際 `strategy_roi_pct/outcome` 與新交易狀態。沒有benchmark或回撤資料時保留null。

## 已知限制

- B續抱／減碼若缺原始成交持倉紀錄，回測維持 `existing_position_history_required`，不虛構進場。
- 日OHLC不是逐筆成交資料，無法確定同根K線的先後順序；沒有支援的事件歷史就不模擬複合條件。
- 預設呈現每部位毛價格報酬，未自動納入股利、融券費或公司行動調整；成本未知時淨報酬保持null。
- 測試通過不代表投資勝率改善；尚未用線上LLM重新生成四模式報告，也未做樣本外績效比較。
- 原始實作驗收時未commit／push；後續共享服務已由模型效率任務統一受控重啟。本次提交不另外重啟，也不重寫歷史報告。既有fresh cache若缺新日線／技術欄位，會在下一次正常取數時失效重抓。

## 原始整合驗證

所有測試使用 `tests/run_prompt_boundary_tests.py` 隔離SQLite、Redis與網路；未讀寫正式回測資料，也未消耗模型額度。

- 最終整合涵蓋40個測試檔案：**2762 passed、1 skipped、75 subtests passed**，耗時275.95秒。範圍包含四模式、提示詞、結構化輸出、摘要依賴、稽核、報告、回測、State／修復／checkpoint、資料快照與模組邊界；不是整個專案的全套測試。
- 唯一跳過項目為 `test_browser_runs_charts_but_blocks_injected_scripts`，需另設 `VISUAL_REGRESSION_REQUIRED=1` 執行真實 Chart.js 瀏覽器檢查；本輪未執行該線上視覺驗證。
- 六項任務的獨立規格審查與程式品質審查全部通過；最後不交易契約旁路另經獨立10例複驗，無剩餘阻擋。
- `performance_panel.js`、`temporal_memory_panel.js` 通過 Node 語法檢查；相關新測試也使用 Node 執行真實 JavaScript 行為。`git diff --check` 通過。
- 實作與驗收清單：`docs/superpowers/plans/2026-09-05-four-mode-analysis-logic.md`。以上為原始共用工作目錄驗證紀錄；尚未重新生成四模式正式報告。

## 提交範圍

- 依使用者另行核准的commit／push要求，基於模型效率提交 `740d3ebe`，僅納入四模式分析邏輯、必要共用證據helper及對應測試／文件。
- 混合檔案按修改區塊拆分；其他報告圖表、啟動器與可靠性修改保留未暫存，不隨本次提交。
- 提交前補查並更新 `test_repair_context.py` 的舊預期：修復時整數與字串格式的同一Agent舊資料都須清除，不能保留舊結論。
- 僅由Git暫存內容匯出的乾淨副本，執行45個測試檔案：**2802 passed、75 subtests passed**，耗時308.63秒，沒有跳過測試。SQLite／Redis／網路全程隔離；不依賴未暫存程式或正式資料。
- 87個暫存檔案的獨立範圍審查通過，未含`.env`、金鑰檔、DB、cache或output；兩個績效介面JavaScript語法檢查及暫存差異檢查通過。
