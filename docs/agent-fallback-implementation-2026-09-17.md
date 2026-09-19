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
- 原先 `report_rerun_service._run_full_pipeline_rerun()` 缺少持久化 checkpoint／thread ID；後續本機續接修正與驗收見下節，不能由本機測試推定正式 worker 已載入。
- 一般角色的路由優先順序調整仍等待正確歸因後的品質證據，本批沒有任意提前 Lite。

### 後續本機修正：完整重跑持久化續接

本次目標為提高成功率，減少額度耗盡與重試卡住。既有重跑入口在後段模型不可用後，重試會再次執行已完成的前段；隔離測試先重現模式 D 的 Agent 22／23 和模式 B 前段均執行兩次。

`report_rerun_jobs.py` 現在將 job ID 傳到 service；`report_rerun_checkpoint.py` 使用既有 runtime checkpoint 設定，以 job ID、來源檔名雜湊與 scope 隔離 graph thread。適用背景 `full_report`（四模式）與 `mode_b`，沒有 job ID 的直接 service 呼叫及 `final_recommendation` 維持原行為。

- 第一次執行沿用既有資料準備流程。重試先讀取該 graph 的原始 input，再由既有 persistent workflow 恢復完成節點、RAG 和品質草稿；不重抓另一份資料混入舊分析。
- 資料日期保持原值；續接不是刷新到最新交易日。要取得新資料需建立新的完整重跑任務，新 job 不使用另一 job 的 checkpoint。
- 來源 pipeline 改變或 checkpoint 缺少可核對的完整 input 時停止，不以重抓資料搭配舊進度繼續。
- 取消、既有品質阻擋和 provider 恢復時間不變。不增加即時重試次數，不啟用 Lite／batching，也不清除額度停用。

驗證：`tests/test_report_rerun_checkpoint_resume.py` 透過真實 job → service → pipeline runner → 四模式 graph → 隔離 SQLite，替換外部資料／模型和渲染輸出；每次呼叫重新建立 runner、服務及事件迴圈，模擬冷啟動續接。測試證明完成 Agent 只執行一次、失敗 Agent 執行兩次、同 job 不重抓資料，以及新 job、模式變更、取消和品質阻擋的邊界。這是離線工作流驗證，不是 provider 真實成功率。

最終驗證命令：

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_report_rerun_checkpoint_resume.py tests/test_analysis_retry_scheduling.py \
  tests/test_report_rerun_data.py tests/test_report_preview.py \
  tests/test_workflow_checkpoint_resume.py tests/test_report_publication_gate.py \
  tests/test_import_boundaries.py tests/test_runtime_paths.py \
  tests/test_settings_env_loading.py tests/test_storage_inventory.py \
  tests/test_report_artifacts.py -q --tb=short
```

結果 **694 passed in 15.28s**，DB 隔離且禁止網路。未呼叫正式 provider、重啟／部署、重送任務、修改模型路由或正式資料。既有等待任務在舊入口沒有保存的進度無法事後補回；新程式載入後開始保存的 checkpoint 才能續接。PostgreSQL 的既有 adapter 有測試，本次完整重跑 cold-resume 僅在 SQLite 驗證；尚未量測正式額度節省量與完成率提升。

### 模型呼叫最佳化續作：共用限速與 key 選擇

`llm_rate_limits.KeyRotator._try_key()` 原本只查看本機最早可用的 key，先扣本機 RPM／TPM，再向 Redis 共用 limiter 預留；共用 limiter 拒絕時，直接等待該 key，而未查看其他候選。

現在依本機可用時間檢查候選；共用限速拒絕時不扣本機／每日預算，繼續查看其他可用 key。只有全部候選均需等待才取最短已知等待時間。同步／非同步 admission 使用同一個 sync lock 保護本機檢查與扣帳，與既有工具後續請求的鎖定方式一致。每日 RPD 停用、model circuit、provider key 範圍、RPM／TPM 上限及模型路由不變；本機仍冷卻的 key 不會預扣共用預算。

可重現的離線前後差異（非正式服務的效能提升百分比）：

| 情境 | 修正前 | 修正後 |
| --- | --- | --- |
| 第一把 key 共用分鐘額度用完、第二把可用 | 等 60 秒再用第一把 | 立即使用第二把 |
| 第一把冷卻 30 秒、第二把冷卻 5 秒 | 等 30 秒 | 等 5 秒 |
| 共用 limiter 拒絕未送出的請求 | 已扣本機 RPM／TPM | 不扣本機 RPM／TPM／每日預算 |

新增 `tests/test_llm_key_admission.py` 使用真實 `KeyRotator`、共用 limiter 的 local fallback、token buckets 與隔離 daily SQLite，控制時間驗證同步／非同步行為。先取得 4 項預期失敗，再修正；模型選擇、每日預算、工具多次 HTTP 預留、容量、RPD 及架構檢查合計 **656 passed in 16.77s**：

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_llm_key_admission.py tests/test_llm_daily_budget.py \
  tests/test_llm_tool_rate_guard.py tests/test_shared_runtime_guards.py \
  tests/test_llm_rate_limit_buckets.py tests/test_llm_input_capacity.py \
  tests/test_llm_model_policy.py tests/test_import_boundaries.py -q --tb=short
```

一般 Agent 的 key acquisition 後續已補上等待上限與取消，見下節。正式 worker 尚未重載這些本機修改，未實測 provider 成功率或延遲。已觀察到的 provider 503、每日額度耗盡與本機 admission 等待需分開處理；本次沒有將額度增加、解除停用或放寬品質當作解法。

### 模型呼叫最佳化續作：取得 key 的等待上限與取消

`llm_key_admission.py` 提供 task-local 的 admission scope；一般 Agent 的同步／非同步單次呼叫透過 `agent_runtime/llm_waiting.py` 啟用。取得 key 使用該 route 原有的 timeout 作為獨立等待上限；取得後的 provider 生成逾時維持原設定，兩者不是合併的總 deadline。顯式 timeout <= 0 沿用不設期限的原語意。沒有 scope 的其他直接 rotator 使用者維持原行為。

- 等待時每秒檢查有提供的取消 callback，不在每次檢查時重複預留 token；無 callback 時不做每秒輪詢。這是 cooperative cancellation，不能中斷正在執行的同步 Redis／SQLite 呼叫。
- 本機等待逾時記為 `local_admission_wait`，尚未送出 provider request；既有 retry stop 立即轉往已設定的下一候選。全部候選暫時不可用時沿用 deferred retry，不增加立即重試、不標示 provider RPD 耗盡，也不開啟新的 model circuit。
- 取消保持原 job cancellation exception，不被改寫成 provider timeout 或繼續嘗試其他模型。scope 在成功、逾時、取消時都還原，不污染後續呼叫。
- 新增測試先證明原程式會在取消／逾時後仍送件，再驗證同步／非同步停止、無 provider send、等待期間不扣每日額度；另走真實 `single_agent` 路由及 `KeyRotator`，確認僅對備援送出一次完整原始 prompt。
- `api_usage_recorders.py` 將未送出的等待事件獨立記為 `local_admission_wait`／0 units；daily usage 計入 local blocks，route dashboard 不將它當作 provider error。保留事件供核對，不回寫歷史紀錄，也不拿本機等待污染 provider 失敗率或 token usage 覆蓋分母。

整合測試中的舊工具模擬時鐘同步接入新的 admission clock，保留原工具行為斷言；不是放寬 production deadline 來通過測試。最終驗證 **783 passed in 18.29s**：

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_llm_key_admission.py tests/test_llm_call_diagnostics.py \
  tests/test_llm_model_policy.py tests/test_llm_daily_budget.py \
  tests/test_llm_tool_rate_guard.py tests/test_llm_transport.py \
  tests/test_shared_runtime_guards.py tests/test_automatic_model_downgrade.py \
  tests/test_agent_reliability.py tests/test_analysis_retry_scheduling.py \
  tests/test_report_rerun_checkpoint_resume.py tests/test_architecture_services.py \
  tests/test_import_boundaries.py tests/test_runtime_paths.py \
  tests/test_settings_env_loading.py tests/test_storage_inventory.py \
  tests/test_report_artifacts.py -q --tb=short -o faulthandler_timeout=30
```

上述整合測試後的觀測分類覆核，先以 3 項預期失敗證明 ledger／route／daily projection 缺口，再修正；相關模型等待、daily usage、路由、runtime observability、額度面板、provider quota authority 與 import boundaries 共 **701 passed, 1 warning in 13.75s**（既有 RQ `datetime.utcnow()` 棄用警告）。與 783 項整合測試有重疊，不能加總作為獨立案例數。

正式環境的唯讀檢查：API 仍回報 `980c579afa07a7a2ac75f0d6976b6ef5de3e887d`／clean，未載入本機修改；25 筆等待任務存在 Redis scheduled queue，另有 48 筆 RPD 停用標記。Redis 由目前 `start_mac.command` 擁有，且 `save` 為空、`appendonly=no`；直接重啟啟動器會關閉這個 Redis，因此載入修改前必須保存並核對 queue 排程與 quota 到期時間，不能用重啟清掉額度停用。已保存唯讀 runtime／Redis baseline，尚未重啟或改寫正式 queue／quota。

### 2026-09-18 正式套用紀錄

使用者明確回覆「套用到正式服務」後，於臺北時間 07:03–07:06 完成上述完整重跑續接、共用限速 key 選擇、admission 等待／取消與觀測分類修正的正式重載。這段紀錄更新前述「尚未重啟」的歷史狀態；Lite、Gemma 引用與 batching 的未驗收限制仍然適用。

- 程式基線為 `980c579afa07a7a2ac75f0d6976b6ef5de3e887d` 加已驗證的工作目錄修改，沒有 commit／push。重啟前後核對 18 個檔案的 SHA-256，均符合保存的測試版本；正式 API 回報同一 HEAD、`dirty=true`。沿用前述 783／701 項結果（有重疊），未因純重啟重跑不變的離線測試。
- 先暫停 RQ 消費、保存 Redis，暫時設定關閉時保存 RDB，再正常停止舊啟動器。Redis 日誌證明退出前完成最終快照；以 `start_mac.command` 啟動新 API／worker／Redis，並以 `PIP_NO_INDEX=1` 保留已驗證的套件環境。恢復後解除暫停並再次保存，避免磁碟快照留下暫停狀態；Redis 原本 `save=""`、`appendonly=no` 設定已恢復。
- 25 筆 scheduled job 的 ID／排程時間完全相同，48 筆 RPD 標記的 key／毫秒絕對到期時間完全相同；沒有清除配額或提前重送。最早既有排程為 2026-09-18 15:00（Asia/Taipei）。
- `/healthz`、`/readyz`、runtime identity、active jobs、decision tracking 均 HTTP 200；API PID 37940、worker supervisor PID 37938、RQ consumer PID 37947、Redis PID 37936，均由新啟動器 PID 37910 啟動或衍生。RQ consumer idle、無執行中的任務，六個 queue 的 scheduler lock 所屬程序存活，佇列未暫停。
- 562 份報告的 API 索引摘要完全相同（含檔名、內容 hash 欄位、日期與 freshness），digest 為 `e37b395f81d20bf975734316e075877eb3d46b92e8c97d836027309c00b50953`；current 493、needs_rerun 69，追蹤啟用數仍為 8。這是索引／hash 欄位核對，沒有逐一重新計算所有 artifact bytes。
- Operational DB 的 waiting_retry 維持 25、error 69、cancelled 3；done 歷史數由 1203 降為 1187。既有啟動 maintenance 會清除超期 terminal job／events，與此現象一致；未保存刪除前逐筆 job 清單，因此不能將所有 DB 內容宣稱為完全不變。報告索引與等待排程均已獨立核對。

部署證據與 Redis 回復快照位於 `/Volumes/X10 Pro Mac/stock-agent-optimization-deploy-20260918.ro4j1fej`，包含 `verified-files.json`、`runtime-before.json`、`runtime-after.json`、`restore-check.json`、`verification.json`、來源備份及三階段 RDB。該目錄僅限擁有者存取；未納入 Git。

正式套用已完成，但本次沒有新增模型請求或手動重送任務。實際 provider 完成率、額度節省幅度與新 checkpoint 在後續正式重試中的成效尚未量測；既有未保存的重跑進度不能事後補回。

### 2026-09-19 續作：5xx 共用冷卻與來源修復指引

承接 9/18 正式紀錄：395 次 HTTP 503，8 個完整重跑 job 共 9 次續接，續接較最早 retry_at 晚約 26–133 分鐘。503 後有同模型再次成功的案例，因此保留原本有效 profile 的每模型 2 次 server-error 嘗試；不以增加 worker 或刪減證據來追求表面吞吐量。

- `model_policy.record_model_failure()` 在既有 route 重試次數耗盡後，對 `AgentServerError` 開啟 `LLM_SERVER_ERROR_MODEL_COOLDOWN_SECONDS`（預設 60 秒）的短冷卻；`deferred.record_route_failure()` 同時發布到既有共用 limiter。另一 Agent／job 會沿原路由跳過冷卻模型，全部候選冷卻時維持 deferred/checkpoint 流程。既有 quota、auth、一般 timeout 與品質重寫次數不變，不以 5xx 停用 API key 或標示日額度耗盡。繼承其他 Agent 的冷卻不續期；到期可重新嘗試，較長既有冷卻不被縮短。Redis 無法使用時仍採既有本機 fallback，不能宣稱跨 process 冷卻保證。
- `market_context_assessment.py` 保留原本 critical 判定與顯示 projection，但提供欄位專屬的引用修復指引。只有可信且完整可見的 manifest 才列出該來源欄位可用的 refs；來源被省略或憑據不符時不提供引用白名單。要求模型重新核對內容、impact、reason 與本次完整來源，不得只替換引用碼，不自動修改輸出或放寬 gate。這只處理可定位的來源修復資訊不足，沒有宣稱修好所有 B/C 交易計畫與估值矛盾。

新增行為檢查先重現 4 項冷卻失敗與 5 項修復指引缺口。冷卻測試涵蓋同步／非同步呼叫、獨立 rotator、Redis adapter（隔離 fake client）與本機 fallback、到期恢復、全路由延後、繼承冷卻不續期及單次 503 後恢复成功；同樣兩個全路由失敗任務的隔離案例由 8 次嘗試降為 4 次，第二個任務直接延後。沒有對正式 provider 送測試請求。

24 個相關測試檔 **889 passed, 2 warnings in 18.32s**（既有 legacy API 棄用警告），使用隔離 runner，包含 runtime/storage 必跑組、checkpoint、品質 gate、模型 policy、共用 limiter 與 import boundaries。另唯讀重播昨天 25 個保存 checkpoint，來源判定、critical/warnings 與 projection 前後完全一致，其中 7 個案例的修復指引更具體；這不是重新生成報告或真實模型修復成功率。

本輪於臺北時間 **2026-09-19 01:07–01:09** 沿用先前正式套用授權完成重載。先保存 Redis，正常關閉時再次寫出 RDB，再由 `start_mac.command` 啟動新程序；確認恢復後解除暫停並保存磁碟快照。啟動器 PID 18955、Redis 18981、worker supervisor 18983、API 18985、RQ consumer 18992。健康／readiness 與 runtime identity 均正常，六個 scheduler lock 的程序存活；HEAD 仍為 `980c579afa07a7a2ac75f0d6976b6ef5de3e887d` 加已驗證 dirty checkout，未 commit／push。

33 筆 scheduled job ID／原定 9/19 15:00 時間、48 筆 RPD key／毫秒絕對到期時間逐筆相同。577 份報告索引摘要也完全相同，digest `7b5907709c564714afba04cc7c823f7868805d20163d24f02d313da04300a195`。啟動 maintenance 清理 34 筆已完成 job 歷史；以部署前逐筆清單核對，恰好等於既有 30 天保留期限與保留最近 20 筆規則的清理集合，未變更等待 job 或其他既有 job 的狀態。

本輪 baseline、24 個修改檔案 SHA-256、來源備份、Redis 三階段快照、`verification.json` 與啟動日誌位於 `/Volumes/X10 Pro Mac/stock-agent-optimization-deploy-20260919.10vmy7we`（擁有者專用，未納入 Git）。發布後只追加本段文件，runtime 程式與已測試版本相同。未新增 provider 測試請求或提前重送；實際等待時間下降幅度與修復後品質通過率，仍需後續正常執行資料驗證。

### 後續集中模型驗收預算提案（尚未執行／未自動取得授權）

一次集中確認後，分兩階段；總上限建議 **64 次 HTTP send、400 萬 input tokens、16 萬 output tokens、45 分鐘**，任何一項先到就停止。
重試、function-call 往返、備援與反思均計入同一上限，不能以 logical call 代替 HTTP 計數。計數／上限保護須在 live harness 準備完成並離線驗證後才可使用；此文件不是已存在的整批執行器。

1. 第一階段最多 24 次 HTTP：六個關鍵角色各兩個完整案例、四個角色／問題類別代表性的 audit rewrite 案例、兩個 Gemma 引用案例與兩份各兩批的 Gemma 摘錄；剩餘額度才可用於有界重試。送出前超限者記為 capacity blocked，不截斷、不送件。
2. 只有第一階段合格者才可進入第二階段，最多 40 次 HTTP 做 A／B／C／D 各一份端到端 canary。少量案例只能支持試點，不能宣稱長期成功率。
3. 沿用現有 key／已核准資料範圍／既有 provider，不新增計費、project 或額度；金鑰不進提示或產物。實際凍結資料清單需隨同總預算集中列明，不假設舊的六次測試授權可無限重用。
4. 原 evidence、公司、日期、單位、估值／交易計畫一致性與品質 gate 全保留。未知模型身分、prompt 洩漏、未解 critical、必要證據遺失或任何預算無法確認均停止，不發布不完整產物；失敗保持候選 OFF，不清除正式 quota 標記。


## 2026-09-19 品質修復與契約一致性

正式紀錄的 4 件模式 C 品質失敗可由原本 deterministic fallback 重現：觀望建議缺少明確不開倉條件，且 thesis_invalidation 文字未符合既有可重新評估的依據。模式 B 的「等待可驗證進場條件」亦被誤判為交易指令。

本輪修正模式 B/C 的備援條件與模式 C 正文、情境動作，使其一致表達等待驗證及不建立新部位；不捏造價格、借券或既有持倉。交易詞檢查只排除完整的「等待可驗證／明確進場條件」觀察片語，後續買入、放空、進場等指令仍阻擋。

修復候選採用前共用既有模式結構契約與建議／報酬一致性檢查；模型候選不合格時，以具體問題使用既有剩餘改寫次數，備援不合格則拒絕採用。拒絕或取消會恢復原分析、結構與阻擋原因，保留已消耗的修復次數。單一 Agent 通過僅顯示候選已通過契約、仍待整份稽核；事件保留 ok 相容欄位，新增 validation_scope=agent_contract、final_report_passed=null。

驗證：新增案例修改前 11 failed / 4 passed，修正後相關 15 檔 suite 686 passed、75 subtests passed（27 個既有 legacy API deprecation warnings）。涵蓋同步／非同步、修復上限、429 circuit、429 回應、品質重寫耗盡、拒絕後狀態保護、錯誤候選第二次改寫，以及真實交易指令仍拒絕。所有測試透過隔離 runner，未呼叫正式 Redis 或模型供應商。

另以今天 4 件模式 C 失敗任務的保存 checkpoint 做唯讀匯出、隔離重播：在相同資料上套用舊備援，各有 2 項最終跨 Agent 稽核 critical；套用新備援後均為 0 critical（4 passed）。這不是正式重新產報或發布驗證，也不代表 provider 額度已恢復、其他 4 件品質問題已修復。持有 5–30% 等報酬政策門檻及完整 evidence／publication gates 維持原狀。

本輪備份與證據：`/Volumes/X10 Pro Mac/stock-agent-quality-deploy-20260919.e2vcgypf`。正式更新結果另見該目錄 verification.json。

## 2026-09-19 完整備援與報告層觀測

本輪使用者授權完成既有最佳化並套用正式服務。有效 profile 為 `backend/model_routes_usage_aware_free.json`，新增 critical Lite 角色 4/7/14/16/19/24 與所有已知角色 audit rewrite opt-in；主模型、fallback 順序、每日額度標記及完整品質 gate 保留。全流程 canary 與 provider 驗證結果另記於本輪 release evidence。設定啟用不等同所有角色均已有實際品質驗證。

- 修復次數以 checkpoint 保存的已用額度計算，每次進入 rewrite loop 最多只使用剩餘次數；同步與非同步行為一致。
- Gemma 分批的 key admission 套用有期限且可取消的共用等待；引用原文、全批驗證及完整原始輸入不變。只有真實批次與整合驗證通過才啟用 batching。
- ModelCircuitOpenError 與其他本機攔截不再算供應商失敗，舊 ledger 的 error_kind 也納入排除；key 日誌只顯示匿名 slot。
- `/api/observability/model-routes` 新增 `report_execution`，以近期有限 ledger 樣本呈現整份報告的 observed requests、已完成歷時（含排隊及重試）、最近階段與跳過原因。沒有請求證據時為 null，不以零補值，也不把請求成功率當報告成功率。

本輪驗收補充：B/C/D 先行任務（3653.TW / 3324.TWO / 2367.TW）已完成存檔，final_audit passed、report_lint passed、critical 空集合；仍保留 report_conformance warning 與 evidence_exit_gate caution，不宣稱全部內容可信度警示消失。B/D 的 final-audit rewrite 實際使用 Lite。三份報告的 HTML/Markdown/data 共 9 個雜湊符合 index，checkpoint 輸入 hash 各只有一種。

Gemma Agent 22 真實保存提示規劃為 2 批，第一批約 8,144 tokens 的兩次請求分別出現 HTTP 504 與 timeout；縮小為約 3,444 tokens 的首批仍回 HTTP 503。沒有取得完整有效 batches，因此 batching 保持 OFF；不會以程式測試通過宣稱 provider 驗證通過。修正了 admission 在 route exception handler 外，使分批失敗可能直接中止 Agent 的問題；現在沿用正常路由記錄失敗並切換下一個模型。

報告指標只涵蓋 v1-v4 與 rerun:full_report，排除局部重算。observed request 計數目前涵蓋 Agent 正文與 Gemma evidence batch ledger，不含 context digest / reflection，API request_scope 與前端均明示範圍。

### 2026-09-19 Gemma 摘錄延遲改善

Gemma evidence extraction 現在明確使用 `thinking_level=minimal`，只改證據摘錄請求，最終 Agent 分析設定不變。分批快取 identity 納入 thinking level，避免新設定的驗證誤用舊回應；事件同時記錄 thinking level 與 timeout。單次 60 秒、最多 2 次嘗試、預設批次容量 9,000 tokens 與既有跨模型備援均保留，沒有因 HTTP 504 全面放大等待上限。

另修正供應商回應以單一 Markdown JSON 程式碼框包覆時的解析相容性；仍拒絕外圍說明、多個程式碼框、錯誤批次／來源 ID、額外欄位及非逐字摘錄。完整原始資料與所有批次驗證維持原狀。同步／非同步及備援路徑等 4 個相關測試檔共 **57 passed**，另 runtime/storage 必跑組 **21 passed**，均以隔離 runner 執行；這不是全套測試或完整報告品質證明。

同一個真實小批次的前輪配對由 49.91 秒降至 33.94 秒，兩次均通過引用驗證，但只有一組配對，不能推算長期失敗率。本輪以正式 9,000-token 規劃驗證：Agent 22 共兩批，首批重試後取得 5 筆有效摘錄，第二批在兩次嘗試後仍遇服務錯誤；因此不宣稱 504 已解決，也不啟用 `GEMMA_EVIDENCE_BATCHING_ENABLED`。詳細 provider 事件、正式路由整合檢查與部署狀態保存於 `/Volumes/X10 Pro Mac/stock-agent-gemma-minimal-release-20260919.z610_gwx`。

後續在獨立驗證程序啟用 batching、沿實際路由整合：Agent 22 重用第一批已驗證快取、成功取得第二批，兩批共 10 筆引用且完整保留 51 筆來源記錄；Lite 實際生成整合結果，完整 fallback prompt 與原始輸入 hash 均驗證不變。這是 Agent 路由整合驗證，沒有發布新報告或宣稱通過整份報告的 final audit。Agent 23 首批兩次請求後仍以 HTTP 504 結束，因此正式 profile 維持 batching OFF。


### 2026-09-19 Gemma 504 follow-up: bounded evidence choices

- 原先發生 504 的 1623 v4 來源重測：Agent 22、23 各三批，final-canary 六批全部通過原有來源 ID、5–160 字元及逐字驗證；每批 3.17–3.54 秒，無 504／500／429。這是有界重現驗證，不是長期供應商錯誤率保證。
- 摘錄改用 `gemma-4-26b-a4b-it`、minimal thinking；`gemma-4-31b-it` 仍為原分析路由與超容量觸發模型。兩者的身份、額度與錯誤歸屬分開。
- 模型只回傳最多五個整數選項 ID。程式從完整來源建立可引用欄位，再按選項取回原文，最後通過既有 quote validator。長字串、反證、null、日期、符號仍完整存在於輸入；只是不把超長值列為短引用選項。所有選項所增加的輸入皆納入批次容量估算。
- batch/cache identity 綁定新版協定、實際摘錄模型、完整提示、角色及 thinking 設定；舊協定快取不混用。摘錄失敗沿正常備援路由繼續，錯誤記在實際摘錄模型。
- Agent 22／23 正常路由整合均成功（10.25／11.02 秒，使用上述已驗證分批快取），完整原始提示及資料 hash 保留；最終模型為 Flash Lite。Agent 23 曾遇一次未提供細項的 429，既有 key 備援後成功。這不是新完整報告的 final audit 證明；沒有發表測試報告。
- 同期間較慢的 31B paced baseline 兩批為 37.54、40.23 秒，一批引用不合格、一批成功；本次兩批未重現 504。先前真實 504 記錄仍保留，不能把耗時下降當作統計顯著的 504 率下降。
- 高頻 A/B 實驗後段兩模型皆出現未提供細項的 429，結果全部保留，未當作成功或排除。串流、自由引用及字串選項等失敗方案不採用。
- `model_routes_usage_aware_free.json` 啟用分批；26B 的本機 admission 參考為 RPM 1、TPM 16000、input 12000，未新增推定 RPD entitlement。每日禁用標記、排程、報告、完整來源與品質 gates 均保留。
- 隔離測試：103 passed。正式啟用證據以此次 deployment/verification.json 及後續 canary 為準。
- 私有實驗與完整失敗紀錄：`/Volumes/X10 Pro Mac/stock-agent-gemma-504-compare-20260919.5gl8zhdl`。

### 2026-09-19 最終品質、429 與跨標的驗證

- 成交量由已知 yfinance adapter 明確標記 `shares`，經每日行情與技術指標保留；舊快照缺少單位時維持未知。Agent 22/24 不得自行宣稱股／張，已知台股單位可檢查千倍錯置。Agent 23/24 將融資賣出、融券賣出、今日及前日餘額分開比對；null 不能借用其他欄位或變成零。問題進入既有品質修復與最終稽核，不降低 gate。
- 429 解析 `Retry-After` 秒數／HTTP 日期及 `RetryInfo`（包括九位小數），採較長有效提示。沒有提示的被拒 key/model 至少冷卻 60 秒，其他可用 key 仍可有界嘗試；未知 429 不推定為 RPD。Redis 原子操作只延長冷卻，並在本機保存期限以承受 Redis 暫時故障；既有 RPD 保護保留。
- 隔離 runner 的 39 組相關測試共 **723 passed、75 subtests passed**，3 項既有 deprecation warnings。真實 Redis 併發冷卻測試使用私人 Unix socket、TCP port 0，不連正式 Redis。
- 私有完整 v4 canary 使用三份固定真實快照（1623、6715、6257），停用驗證程序的回應快取，沿正式模型路由及正常品質修復生成 HTML／Markdown。三個標的均至少取得一份 `final_audit=passed`、lint 通過、evidence approved 的報告；原資料 hash 保持不變。1623 保留來源可信度警示，6715 與 6257 conformance passed；未發布私人驗證報告。
- 初始兩輪六次執行為三次成功、三次因 429 有界延期；6715 成功報告亦曾在 429 後換可用 key 修復。這證明錯誤可退出及部分備援可恢復，不代表供應商額度充足或長期 429 頻率已下降。後續 paced repeats、正式重啟／版本校驗與持續觀察以證據目錄更新結果為準。
- 數字檢查屬特定欄位與句型保護，不是所有歷史數字的全面驗證；三個標的小樣本及先前十二個有效 Gemma 批次亦不能推算長期 504 率。Google 官方說明額度以 project 計算，不能由多把 key 推定多個獨立額度（https://ai.google.dev/gemini-api/docs/rate-limits）。
- 完整失敗、測試、來源 hash、發布 manifest、部署及持續觀察證據：`/Volumes/X10 Pro Mac/stock-agent-final-optimization-20260919.ccemjg5q`。
