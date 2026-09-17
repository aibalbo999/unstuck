# Agent 備援與 Gemma 輸入效率：本機實作

日期：2026-09-17。承接全部 21 個 Agent 的備援評估。
本頁最初記錄已驗證的本機程式基線；當時未 commit、push、部署、重啟、重送報告或呼叫 provider。
後續發布準備以 `758242290e795146520f58f68ffa113cac35e52c` → `f494bec74e247cebca513faddef30cb1825a2968` 為程式範圍，包含先前一鍵自動重跑前端修正；部署成功仍須另核对 runtime identity、健康與重試排程，不能由提交紀錄推定。
既有一鍵重跑前端修改保留。有效 `model_routes_usage_aware_free.json`、`.env`、每日額度停用、品質 gate、正式 artifacts／checkpoint 與 OOS cohort 未修改。

## 已實作

### 1. 尚需生成的關鍵角色預檢

`agent_runtime/report_preflight.py` 由 `workflow_services.py` 在 RAG 建立前與每個 Agent 執行前呼叫；先檢查取消。
依四模式必要角色（A：4／7，B：14／16，C：19，D：24）的實際路由，只有全部候選均確知暫時不可用才沿用 `AgentDeferredError`／既有延後重試。
區分 provider 每日額度與暫時 cooldown，不清除標記、不預留 key、不提前發送模型請求。

- 有效且已完成的結果不要求重新取得模型；上游被安排重跑時仍重新檢查會受影響的下游。
- 未知可用性／設定查詢失敗不等於所有路由耗盡，留給原本單角色 admission 處理。
- 不在前序結果還沒產生時猜測下游 prompt 容量；每次實際模型嘗試仍檢查完整輸入。
- 此預檢不是「整份報告必能完成」的保證。已產出但有品質問題的結果，可能在 deterministic audit 判定需要重寫後，才因 rewrite 路由不可用而延後；不能無條件要求 audit 模型，誤擋本來不需重寫的報告。

### 2. 角色級 Lite 候選，預設關閉

`settings/model_candidates.py` 載入以下明確 opt-in 設定；只接受 JSON literal `true`，`"true"`、`1`、未知角色或格式錯誤不啟用。

| 設定 | JSON profile 對應 | 範圍／預設 |
| --- | --- | --- |
| `CRITICAL_LITE_FALLBACK_AGENTS_JSON` | `critical_lite_fallback_agents` | 4／7／14／16／19／24，各自 OFF |
| `AUDIT_REWRITE_LITE_FALLBACK_AGENTS_JSON` | `audit_rewrite_lite_fallback_agents` | 已知角色各自 OFF，與一般候選獨立 |
| `GEMMA_STATE_REFERENCE_COMPACTION_ENABLED` | `gemma_state_reference_compaction` | 全域 OFF；僅作用於合適的 Gemma 正常提示 |

啟用某角色時，只在其既有路由尾端加上 `gemini-3.5-flash-lite`，不改主模型或其他角色。
例如 `{"24":true}` 僅表示角色 24 的隔離候選設定，不是本次正式環境已設定。
一般明確 model override 不擴張；audit rewrite 仍沿用原本暫時覆寫為 audit 路由、之後還原的策略。reflection 不加入 Lite。
能力、容量、逐角色品質與問題類別適用性仍需驗收；程式有入口不代表候選已合格。

### 3. 模型歸因與未知品質

`workflow_telemetry_attribution.py`／`agent_runtime/attempt_telemetry.py` 的短期 receipt 綁定本次 node invocation 與回傳分析／structured output fingerprint。

- 實際回應、step cache 與 semantic cache 使用本次可追溯的模型身分，不再直接標示主設定模型。
- 不借用 checkpoint 的舊 tokens／重試數；沒有 usage 就保留 unknown。
- deterministic replacement／失敗佔位內容不歸功於先前模型。
- `quality_gate_pass` 不再等同 node success。現行角色流程沒有統一、明確的同結果品質 verdict 時維持 `null`；API 與 SSE 保留 `null`，不轉成 `false`。
- 未改寫歷史 telemetry。node latency 仍是整個節點時間，未知模型仍可能出現在 dashboard 的 unknown bucket；不可把它當 provider 回應延遲或品質成功率。

## Gemma：壓縮與分段的結論

### 可逆去重已實作，但仍保持 OFF

既有系統已有緊密 JSON、資料列表格與 freshness 重複引用。本批新增 `prompt_state_references.py`：在實際提示同時含完整財務 JSON 與 State 時，將固定白名單路徑的**完全同值副本**改為提示內引用。
保留財務區塊全文；不是摘要、刪資料或 Base64 壓縮，也不向外部網址取資料。

必須同時滿足：

1. 實際模型是 Gemma、flag 已明確啟用，且不是品質／身分修復或 model override。
2. 同一完整財務區塊確實且唯一出現在組裝後的任務文字。
3. 兩端 JSON 完全相同：日期、順序、負數、單位、null、缺欄、0、false 不得混淆。
4. 引用規則本身也算入 token 成本，至少再省 32 個估算 tokens 才採用。
5. 發現既有 `$prompt_ref`、不明／有損 table marker 或格式錯誤，原封不動保留整段 State。

嚴格 table decoder 只用於新壓縮路徑；既有 batching decoder 保持原預設。獨立覆核發現的「來源 table marker 含額外 warning 會遺失」已先以六個失敗測試重現，再修正為拒絕壓縮、完整保留來源。

### 三份既有 v4 快照的離線量測

來源為 1623.TW、2308.TW、2367.TW 在 2026-09-17 產出的三份現存快照，讀取前後 bytes 相同。
用同一份保存資料與分析 context、同一個初始化 State 重建前後兩種提示；包含 system／schema 的本機輸入估算。
**沒有當時完整 RAG 或原始 checkpoint，故不是逐 byte 還原當時實際請求，也不是全量報告樣本。**

| 股票／角色 | 現行估算 tokens | 引用壓縮後 | 是否落在本機 12,000 預算內 |
| --- | ---: | ---: | --- |
| 1623／22 | 14,034 | 13,334 | 否 |
| 2308／22 | 13,108 | 12,363 | 否 |
| 2367／22 | 13,779 | 12,780 | 否 |
| 1623／23 | 13,195 | 12,801 | 否 |
| 2308／23 | 12,187 | 11,781 | 是，原本超限 |
| 2367／23 | 12,345 | 11,946 | 是，原本超限 |

這六個重建輸入中兩個由超限變為可 admission；不是 33% 報告成功率，也未證明 Gemma 正確理解引用。
Agent 22 省約 700–1,000 tokens 仍超限，不能宣稱靠本次壓縮全面解決。
12,000 是目前系統設定的本機輸入預算，並非本次證明的 provider context 上限；未修改此值或 TPM/RPM。

### 分段可行，但不是免費擴大模型記憶

沿用 [Gemma 證據分批](gemma-evidence-batching.md) 的既有摘錄協定；本批沒有擴大角色、啟用旗標或傳送模型請求。
以上三個 Agent 22 提示的財務來源都可離線分成兩批，單批最大分別為 8,136／8,989／8,916 tokens；兩批總估算為 14,176／13,455／13,633，之後**還要加整合模型的完整輸入**。

- 分段只有摘錄／定位證據；全批 schema、source ID、逐字 quote 都通過才可採用。
- 完整原始提示仍交給既有備援模型整合，因此不是讓 Gemma 自己產完長報告，也不能解決最後決策模型沒有額度。
- 單一來源字串仍超限時不直接切字；它可能破壞句子、引用與反證。應改做帶來源範圍與驗證的分層證據協定，另行設計與驗收。
- 多次請求不會自動獲得累積上下文；若每次附全部歷史，總量反而增加。摘要再整合則有漏證據風險，不能代替目前完整 evidence gate。
- 過去 HTTP 500／504 的失敗證據沒有被本次離線 pass 推翻，所以 batching 仍 OFF。

建議先驗本次可逆去重；仍超限就用已合格的大容量路由。分批只在完整鏈路有可用整合候選、且額外成本值得時驗證，不把所有 21 個 Agent 全改成多次摘錄。

## 驗收狀態與剩餘工作

本次已建立同步／非同步 admission、資料 round-trip、取消、cache 身分、正常／audit 候選、未知可用性與 SQLite cold-resume 回歸。
29 個相關測試檔合計 **1,141 passed in 17.98s**，只有兩個既有 legacy API 棄用警告；結果記錄於本機交付的 `offline-tests.xml`。全部使用禁止正式 DB／Redis／provider 連線的隔離 runner，涵蓋專案規定的 runtime/storage 與 import-boundary 檢查。
路由與壓縮相互獨立覆核，沒有以放寬品質閘門讓測試通過。
發布前另完成 14 個測試檔的 **654 passed in 17.45s**，涵蓋一鍵重跑、閱讀限制、重跑資料／品質流程、啟動器與 runtime/storage 邊界；與前一組有重疊，不相加作為不重複案例數。

尚未完成、不能宣稱上線的部分：

- 六個關鍵角色及 audit rewrite 新候選的真實品質與成功率。
- 完整凍結 checkpoint／RAG／工具／反思的候選提示容量矩陣，尤其 Agent 7／19 的 64k 風險。
- Gemma 新引用協定的真實理解、批次摘錄與最終整合品質。
- 四模式端到端正式 artifact 驗收、部署與重啟。
- `report_rerun_service._run_full_pipeline_rerun()` 尚未傳入持久化 checkpoint／thread ID；完整重跑任務的自動重試不等於從失敗 Agent 原地接續。正常分析既有 checkpoint 與本批 cold-resume 測試不能當作此重跑入口已接線的證據。
- 一般角色的路由優先順序調整仍等待正確歸因後的品質證據，本批沒有任意提前 Lite。

### 後續集中模型驗收預算提案（尚未執行／未自動取得授權）

一次集中確認後，分兩階段；總上限建議 **64 次 HTTP send、400 萬 input tokens、16 萬 output tokens、45 分鐘**，任何一項先到就停止。
重試、function-call 往返、備援與反思均計入同一上限，不能以 logical call 代替 HTTP 計數。計數／上限保護須在 live harness 準備完成並離線驗證後才可使用；此文件不是已存在的整批執行器。

1. 第一階段最多 24 次 HTTP：六個關鍵角色各兩個完整案例、四個角色／問題類別代表性的 audit rewrite 案例、兩個 Gemma 引用案例與兩份各兩批的 Gemma 摘錄；剩餘額度才可用於有界重試。送出前超限者記為 capacity blocked，不截斷、不送件。
2. 只有第一階段合格者才可進入第二階段，最多 40 次 HTTP 做 A／B／C／D 各一份端到端 canary。少量案例只能支持試點，不能宣稱長期成功率。
3. 沿用現有 key／已核准資料範圍／既有 provider，不新增計費、project 或額度；金鑰不進提示或產物。實際凍結資料清單需隨同總預算集中列明，不假設舊的六次測試授權可無限重用。
4. 原 evidence、公司、日期、單位、估值／交易計畫一致性與品質 gate 全保留。未知模型身分、prompt 洩漏、未解 critical、必要證據遺失或任何預算無法確認均停止，不發布不完整產物；失敗保持候選 OFF，不清除正式 quota 標記。
