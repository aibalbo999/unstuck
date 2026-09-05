# Agent 可靠性修復實作計畫

> 使用者已核准前一輪根因診斷的修復方向；本計畫在同一工作階段實作、整合與驗證。

**目標：** 修正誤判、無效重寫、提示內容膨脹及冷卻擴散，同時保留資料可信度與正式報告的品質邊界。

**架構：** 沿用既有 financial validator、AgentState view、agent runtime、workflow 與 RQ 邊界。模型供應暫時不可用須成為可延後的工作狀態，不得當成分析內容寫入新正式報告。

**技術：** Python、pytest、Google GenAI transport、LangGraph、SQLite、Redis/RQ。

## 工作與驗收

- [x] 財務規則：以 2308/B/14 的 WACC 9.88%、2308/B/16 的條件式 15%、2367/B/12 的供應鏈商譽、6282/B/15 的公債殖利率 4.784% 建立失敗測試。修改 `audit_rule_engine.py`、`prompts/audit_rules.json`、`financial_output_validator.py` 的最小相關邏輯；真正高成長重複估值、高股息風險、會計商譽及同期間算術矛盾仍須失敗。四份真實歷史原文重播均不再誤判。
- [x] 提示內容：在 `state_memory.py` 與 `agent_runtime/prompting.py` 邊界排除內部 RAG 向量與索引，保留檢索後證據、canonical path 及財務計算。原快照六個 Agent 重播估算減少 92.53% 至 93.19%，checkpoint 雜湊及輸入 state 不變。
- [x] 回應診斷：在 `llm_transport.py` 與 `agent_runtime/llm_calls.py` 保存有限且匿名的 finish reason、阻擋原因、工具呼叫計數與 token usage；空文字與短文字都留下可核對事件，不記錄 key 或思考內容。fake stream 覆蓋正常、空白、工具、阻擋、逾時與取消路徑，隔離測試 83 passed。
- [x] 重試路由：修正 `agent_runtime/quality_retry.py` 的模型硬排除，拒絕空路由；重寫失敗保留原文作為未通過草稿及診斷，不將其標成合格。
- [x] 冷卻與工作延後：本機冷卻攔截不新增或延長 provider circuit；重試依該模型可用 key 集合停止。全部路由不可用時透過現有 job/RQ 邊界延後，不繼續產出缺段報告，並保留恢復時間與原因。
- [x] 整合驗證：各部分先紅後綠、整合測試與完整回歸，檢查既有 dirty changes 未被撤銷；使用真實歷史輸出重播四個誤判。產品程式完整隔離回歸為 8965 passed、16 skipped、75 subtests passed；最後測試設定物件隔離補強後的相關回歸為 634 passed、75 subtests passed。
- [x] 本機交付：停止舊 worker/API 後透過正式啟動入口重新載入；保留配額停用狀態並遵守原定最早恢復時間。2308/B/16 單次實際請求成功；原 14 個待辦與新排 12 個受阻報告共 26 個工作。2026-09-05 15:01:20（台北）確認暫停已到期，1 個正在執行、25 個等待。歷史報告未宣稱已修好，詳見 `docs/agent-reliability-2026-09-05.md`。

## 邊界

- 不刪除或覆寫本輪之前的 dirty changes，不變更 API key，不降低 evidence gate。
- 不將情境預測或缺 canonical path 的數字改為已驗證。
- 不透過放寬配額、移除 RPD 禁用或增加跨 key 重試處理供應商限制。
- 已產出的失敗報告須經過實際重跑才算修復；程式通過測試不等於報告全部合格。
