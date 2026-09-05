# Agent 可靠性修復交付紀錄

日期：2026-09-05，時區 Asia/Taipei。

## 交付範圍

本輪承接已核准的 Agent 失敗根因修復。正式程式與資料均位於 `/Volumes/X10 Pro Mac/stock-agent`。修正已載入本機 API 與 Worker，但歷史報告必須實際重跑後才能重新判定符合性；程式測試通過不代表所有報告已合格。本輪未 commit 或 push，也未撤銷原有圖表、搬遷及其他工作區變更。

## 修正內容

1. 財務誤判：百分比不再從小數尾端取值；成長率不跨越不相關財務指標；區分條件預測與同期間實際營收；區分供應鏈聲譽與會計商譽，以及公債殖利率與個股股息。真正的估值重複計算、高股息買入風險、會計商譽風險及實際算術矛盾仍保留攔截。
2. 提示內容：對模型輸入建立不修改原始 state 的證據投影，移除內部向量、embedding 及索引；保留檢索證據、canonical path 與計算。RAG 截取以完整片段為單位並受 Agent 預算限制。
3. 回應診斷：正常、短文、空文、工具回應、阻擋、逾時及取消都有可辨識事件。記錄有限的 finish reason、usage、串流狀態、工具名稱與次數；不保存 key、工具參數、原始 SDK payload 或思考內容。SDK 未提供的原因維持未知。
4. 暫時不可用：修正空路由與硬排除設定模型；模型冷卻的本機攔截不會再被當成新 provider 失敗而延長冷卻。全部設定路由不可用時延後工作，RQ 重試不早於已知恢復時間；重試耗盡則明確失敗，不永久顯示等待。
5. 品質草稿：重寫失敗的原文只作為未通過草稿保留，不交給正式報告 renderer。分析工作的同一 checkpoint saver 保存原文、結構化資料與 RAG 來源；恢復時重做品質檢查。草稿保存失敗會阻止發布。
6. 測試隔離：補齊 `config.TASK_DB_PATH` 隔離，新增防止修復冷卻表使用正式資料庫的測試。完整驗證入口禁止測試連線正式 SQLite、Redis、API 或供應商。

主要新增模組：`financial_claim_context.py`、`prompt_evidence.py`、`agent_runtime/rag_prompt_budget.py`、`llm_response_diagnostics.py`、`agent_runtime/deferred.py`、`analysis_job_retry.py`、`agent_runtime/quality_drafts.py`、`workflow_quality_drafts.py`。

## 驗證證據

### 自動測試

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py tests -q --maxfail=5
```

結果：**8965 passed, 16 skipped, 75 subtests passed in 1129.41s**。略過包括需明確啟用的歷史重播與可選 live 測試；因此另做下述歷史與實際模型驗證。

最後品質草稿、冷啟動匯入、checkpoint、工作延後與模組邊界整合測試：**551 passed in 19.37s**。

完整回歸後，改變測試執行順序又發現 1 個測試隔離斷言失敗：設定測試會移除並重載 `config`，已匯入的修復模組仍持有舊物件。存取仍在隔離 runner 的暫存資料庫內，未觸及正式資料。fixture 現在同時隔離目前與被持有的舊設定物件，並新增專用回歸。修正後相同順序的 runtime/storage/草稿/重試/audit 測試為 **143 passed, 75 subtests passed**；再含新案例與模組邊界的回歸為 **634 passed, 75 subtests passed in 20.23s**。此最後調整僅影響測試 fixture 與測試檔，產品程式未再變更；未再次執行整套 8965 項回歸。

第一輪完整回歸的 9 個失敗來自隔離 runner：8 個可選 live 測試未將禁止網路的 AssertionError 視為不可連線，以及 1 個暫存快取檔名不符既有契約。調整 runner 使用 OSError 與 canonical basename 後，先驗證 2 passed / 8 skipped，再得到上述完整回歸結果；沒有以停用產品品質規則解決測試失敗。

品質恢復使用真實 LangGraph 與 SQLite saver 驗證：平行分支、一支完成一支延後、關閉再開啟資料庫、超過 100000 字草稿、步驟快取關閉、不同輸入與不同 thread 隔離、來源延續、中途修正後的原文與結構化資料，以及保存失敗時禁止發布。

### 歷史原文與快照

從 canonical `analysis_events` 重建四個原始成功串流，再經結構化輸出處理與新版 financial validator；四份皆回傳空 issues：

| 股票 / 模式 / Agent | 原誤判 |
| --- | --- |
| 2308 / B / 14 | WACC 9.88% 被誤讀為高成長 |
| 2308 / B / 16 | 條件式月營收年增 15% 被當成實際主張 |
| 2367 / B / 12 | 供應鏈商譽被當成會計資產 |
| 6282 / B / 15 | 美國公債殖利率 4.784% 被當成股票高股息買入 |

1623/C 原 checkpoint 有 48 個 RAG chunks，其中 13 個含 3072 維向量。六個 Agent 的模型輸入在防截斷前重播，估算 token（含固定 8192 回應預留）由 321250 至 323545 降為 21881 至 24176，個別減少 **92.53% 至 93.19%**。這是本機估算，不是供應商帳單 token；checkpoint 雜湊、檔案大小、修改時間及輸入 state 均未變。

### 單次實際模型驗證

使用 2308/B 既有 checkpoint 的資料，以新版 prompt 呼叫 Agent 16 的設定路由 `gemini-3.6-flash`，僅一次請求，不發布測試報告。

- 完成時間 66.24 秒；API key 僅記匿名 slot 1。
- 處理後分析原文 3934 字元；financial issues 為空。
- 串流 105 chunks，`stream_completed=true`，finish reason 為 `STOP`。
- 供應商 usage：input 56598、output 2705、total 62486。total 不強行改成 input 加 output，保留 SDK 回傳值。
- 用量已記入 canonical `api_usage_events`，識別碼 `agent-reliability-canary-20260905`。
- 本次只證明此實際呼叫及財務檢查成功，不代表整份報告的 evidence gate、final audit 或所有模式均已通過。

## Runtime 與待辦恢復

本節為 2026-09-05 的歷史操作紀錄，PID 與暫時模型設定不代表目前 runtime。後續任務完成狀態與正式驗收見 [2026-09-06 收尾驗收](remaining-analysis-delivery-2026-09-06.md)。

約 14:38 使用正式 `start_mac_lan.command` 啟動入口重載；保留既有 `MODEL_ROUTES_FILE=backend/cache/report-rebuild-model-routes-20260905.json`，未修改金鑰或繞過配額。新 API PID 59104、Worker PID 59030、Redis PID 59008、launcher PID 58903。

重啟前使用 Redis SAVE 保存佇列狀態。重啟後 17 筆 model/key RPD 停用項目雜湊與重啟前相同，原 14 筆待辦順序雜湊亦一致。重啟後 scheduler 放回 3 筆舊重試；逐筆確認 canonical DB 已是 `cancelled` 且 `cancel_requested=1` 後，只取消它們的 RQ 項目，保留 SQL 工作歷史。

`doctor_runtime.py --json` 確認 report index、checkpoint、output、operational 與 tracking 均指向外接硬碟。`/healthz` 為 `ok`，`/readyz` 為 `ready`，storage / queue 均 pass。

單次實測成功後，將維護期間的無限期暫停恢復成原定 **15:01:00.433796** 自動到期，不提前執行。原 14 個待辦保留，再透過正式 `/api/analysis-jobs` 為 12 份 blocked 報告建立 `force=true, resume=false` 的新分析工作，共 26 個待辦。兩份 warning 報告未額外重跑，本輪未刪除現有報告。

**15:01:20 實際恢復驗證：** 暫停 key 已到期（TTL -2）；`analysis-2367tw-v3-1788575699914-9bf7b7f7` 在 canonical DB 為 `running`，RQ started registry 也有同一工作；另 25 個在等待。26 個 ticker/mode 組合無重複，未包含已取消工作。當時 `/healthz` 仍為 `ok`、`/readyz` 為 `ready`；首頁另驗證 HTTP 200 且為 HTML。

### 受阻報告重跑識別碼

| 股票 | 模式 | 新工作 ID |
| --- | --- | --- |
| 1623.TW | v3 | analysis-1623tw-v3-1788591378544-b35f5f70 |
| 1623.TW | v1 | analysis-1623tw-v1-1788591378568-c80ff636 |
| 6282.TW | v2 | analysis-6282tw-v2-1788591378573-6b39d79b |
| 3653.TW | v4 | analysis-3653tw-v4-1788591378579-a6492fc1 |
| 3324.TWO | v4 | analysis-3324two-v4-1788591378584-b59d9b9c |
| 3017.TW | v4 | analysis-3017tw-v4-1788591378588-c4d3411f |
| 2367.TW | v4 | analysis-2367tw-v4-1788591378592-608d52e2 |
| 2367.TW | v2 | analysis-2367tw-v2-1788591378596-e00d0f13 |
| 2367.TW | v1 | analysis-2367tw-v1-1788591378600-936ed9be |
| 2308.TW | v2 | analysis-2308tw-v2-1788591378603-2f784b89 |
| 2308.TW | v1 | analysis-2308tw-v1-1788591378606-cc711212 |
| 1623.TW | v4 | analysis-1623tw-v4-1788591378610-2f3bf164 |

原重建 manifest 保持原歷史，以上另列的補跑工作需連同該 manifest 查驗，不能只看原來的 14 done 就判定重建已完成。

## 測試隔離事故

約 13:54:16 至 13:54:51，4 個既有 `AuditRuleTests` 的 setup 呼叫清理修復冷卻函式。原 fixture 只隔離 job_store 的路徑，未隔離 `config.TASK_DB_PATH`，因此對正式 operational DB 的 `repair_429_circuit_breakers` 發出 4 次全表 DELETE。沒有事前快照，無法確定刪除筆數或原始 agent 名單，不宣稱原表本來就是空的。

這張表是品質修復的 429 冷卻表，不是 Redis 的模型 circuit 或每日 RPD 停用紀錄；後兩者未因測試被清除。當時分析佇列暫停，查詢事故相關時段的 canonical API usage 未見額外請求事件。已補上 TASK_DB_PATH fixture 隔離與回歸測試，之後所有整合與完整回歸均使用禁止正式資料庫與網路存取的 runner。此事已向使用者揭露。

## 尚存邊界

- 26 個工作排入佇列不等於 26 份報告已完成；須以實際 job、artifact、conformance 與 evidence gate 驗收。供應商仍可能回傳 quota、timeout 或 overload。
- 草稿恢復保存原文、結構化資料與來源，品質檢查會重新執行；未承諾保存所有品質重試計數。終止工作的既有 checkpoint 清理仍可能清除整個 thread。
- 本輪以 SQLite 做完整持久化驗證，沒有 live PostgreSQL 驗證。PostgreSQL blob version 的程式契約已處理，仍需其實際環境驗收。
- 既有 report rerun 路徑已套用延後排程，但完整 rerun service 原先未帶持久化 graph thread；不能宣稱其所有內部節點均可斷點恢復。因此這 12 份使用新 analysis job 重跑。
- 非 RAG 的既有整份 prompt 中段截斷機制未全面改寫。SDK 的 AFC 計數僅代表可觀測欄位，不保證涵蓋所有隱藏 SDK 子呼叫。
- 不降低 data trust / evidence gate；缺少 canonical evidence 的內容仍維持不可驗證。
