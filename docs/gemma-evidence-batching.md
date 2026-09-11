# Gemma 原文證據分批（2026-09-11）

## 交付狀態

實作完成，採 **dark launch，預設 OFF**。本輪沒有修改正式路由開關、重啟、提交或推送。
`GEMMA_EVIDENCE_BATCHING_ENABLED=true` 或路由 JSON 的 `gemma_evidence_batching: true` 才會啟用；環境變數優先。
目前正式 profile 沒有啟用此欄位。套用或撤回開關均需要正常重載 runtime。

真實供應商驗證未通過，因此目前不宣稱增加正式成功率或已改善完整報告品質。
12,000 是現行系統設定的 Gemma 單次輸入預算，不應當成此驗證證明的供應商硬性 context 上限。

## 行為與品質邊界

- 僅 Agent 22（技術動能）及 Agent 23（籌碼結構）；只在 Gemma 原始提示超過輸入預算且尚有設定的備援模型時啟動。
- 放得下的原始請求、其他角色、audit/identity repair 與 model override 維持既有流程。
- 結構化來源轉成帶 JSON pointer 路徑的記錄；保留數字、正負號、日期、來源、null/0/false/缺值。單一過大來源不截斷，超過工作上限改走既有備援。
- 每批最多 9,000 **估算**輸入 tokens，最多 8 批。估算包含角色、公司身分、來源、研究 framing 和 system instruction；實際 token 數仍可能不同。
- 模型只摘錄原文，每批最多 5 筆、每筆 5–160 字元。程式驗證 batch ID、來源 ID、schema 與逐字吻合；不把逐字吻合當成語意、資料或投資結論已正確。
- 全批通過才形成附錄。整合模型保留其完整原始提示，附錄只是來源定位；資料限制與反證仍須核對。容量不足則保留原提示並明確記錄 `evidence_appendix_attached=false`。
- 分批成功不代表該 Agent 完成。既有備援模型仍負責最終輸出及品質驗證；Gemma 分批 response 不會被當成最終模型身分。

## 可用性、快取與記錄

每批逐一經既有 KeyRotator、共享 RPM/TPM、provider quota 控制。429/RPD 沿用 key+model 停用及恢復規則；500/504 為暫時錯誤，不視為額度耗盡。分批失敗轉入既有備援／延後恢復處理。

每批 provider 呼叫上限 60 秒（async 另有外層期限）；等待 key 前後及回應後都檢查取消。僅通過驗證的批次快取一小時；cache key 綁模型、角色、完整提示、摘錄規約、角色任務與分批上限。資料或規約改變不共用舊結果。部分成功可供下一次重試使用，但未完成附錄不得採用。

分批請求使用 request-local ContextVar 繞過一般 semantic cache，避免未驗證回應被重複採用。保留正常研究 framing，但不把來源中的「買進」等詞改寫，確保能逐字核對。

`gemma_evidence_call/request/response/error` 寫入既有使用量 ledger，保留 `call_purpose=evidence_batch` 與匿名 key slot；cache hit 不算新請求。分批 request 納入曾呼叫模型清單，只有正常最終 response 或 Agent step cache 才決定 Agent 模型身分。`gemma_evidence_appendix_prepared` 只說明提示是否附上摘錄，不等於供應商已成功整合。

此方法增加前處理呼叫和等待時間，不保證減少總 tokens 或其他模型用量。上線評估應分開看批次成功、摘錄採用、最終角色通過、完整報告品質及總呼叫成本。

## 驗證證據

對固定 12 份既有 v4 快照重建提示，僅離線讀取來源，沒有修改歷史報告或重新提交工作：

| 角色 | 原始估算輸入 | 超過 12,000 | 新批次 |
| --- | --- | --- | --- |
| Agent 22 | 12,444–13,224 | 12/12 | 每份 2 批，單批最多 8,995 |
| Agent 23 | 11,047–11,854 | 0/12 | 正常路由不啟動分批 |

最終隔離驗證 **608 passed**（14.21 秒），僅一項既有 RQ `datetime.utcnow()` 棄用警告；獨立覆核另有 31 passed，三項 P2 已修正。

數字證明來源可分裝，不能證明模型理解或報告正確。離線測試涵蓋來源完整性、quote 偽造、部分失敗、快取恢復、sync/async 路由、取消、timeout、transport cache、模型身分、ledger，以及附錄容量不足時保留原文。

真實 provider 使用既有 key 與額度控制，固定來源 `2610_TW_v4_report_job_6cc14cf8a0b6.data.json`，共兩次有界請求，未重跑報告：

| 請求 | 估算輸入 | 結果 |
| --- | --- | --- |
| 完整計畫的第一批，68 records | 8,953 | HTTP 504 / AgentServerError |
| 縮小的診斷批，8 records | 1,900 | HTTP 500 / AgentServerError |

兩次均匿名 slot 1，不代表已測試所有 key；均未取得有效摘錄、沒有 RPD 耗盡回饋。小批也失敗表示這兩次結果不能只用 12,000-token 超量解釋。測試後補上角色焦點說明，所以最終離線容量與上述 provider 請求大小略有差異；沒有把早期請求當成最終協定成功驗證。

啟用前仍需供應商在最終協定下完成全部分批及代表性角色的備援整合，並通過原品質檢查。完整報告品質與正式成功率留待實際產物驗證。
