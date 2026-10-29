# LLM 請求、冷卻與品質觀測

本次改善在既有 `api_usage_events` 增加零單位診斷事件，沿用 `analysis_events` 與任務 current state。不改配額判定、重試次數、退避時間、模型清單、來源資料或報告品質閘門。`llm_quota_details.extract_quota_details` 仍是原決策入口；新增 `llm_quota_observation_details.observe_quota_details` 僅提供觀測，不可直接接入每日停用判定。

## 關聯與計數

| 識別／事件 | 定義 |
|---|---|
| `logical_call_id` | 一次角色呼叫；同次呼叫內的重試、分批與模型切換共用，下一次品質修復呼叫另建識別 |
| `attempt_id` / `attempt_number` | 一次應用層嘗試；在取得 key 前建立，包含尚未送出的拒絕 |
| `transport_attempt_id` | 一次實際進入 SDK callback 的識別，並行 callback 各自隔離；不是 HTTP 送達收據 |
| `guard_attempt_id` | 既有共享 guard admission owner 的安全識別，獨立於應用層 attempt |
| `cooldown_id` | 模型、guard generation 與該輪開始時間綁定；開啟、探測、恢復可關聯；重新退避為新輪次 |
| `observation_event_id` | 路由／附錄事件識別，用來去除同一事件在兩份帳本的重複投影 |
| `llm_transport_observation` | SDK callback 開始與結束，`units=0`；語意快取命中不產生此事件 |
| `llm_wait_interval` | key admission 或重試退避的實際耗時，使用 monotonic clock；計畫時間另存 |
| `llm_admission_decision` | 冷卻、容量、設定拒絕與備援選擇；均未代表新 provider request |
| `llm_evidence_progress` | 分批快取與附錄採用；單批有效、全批完成、附錄採用、角色輸出與報告品質各自判定 |
| `llm_report_quality_observation` | 原 `assert_report_publishable` 當下的通過／阻擋及安全 gate 狀態，不代表已存檔或公開發布 |

SDK callback 同時涵蓋正文、分批、context digest、tear sheet、audit reflection 與 embedding；未能識別用途時保留 `auxiliary_generation_unspecified`。原 Agent 請求帳本的計數範圍保留，不能將新 callback 次數與舊請求事件相加。transport 終點存在時優先使用其用量與錯誤；終點漏記仍保留已保存的應用層錯誤，不將開始事件當作成功。

## 配額細項與保密

新觀測保留安全的 quota ID、metric、種類及可選限制值；缺 `quotaValue` 時 `limit=null`，不丟棄已知 RPM/RPD 種類。`detail_status` 分為 `parsed`、`partial`、`unrecognized`、`parse_error`、`no_supported_details`、`sdk_fields_absent`、`observation_unavailable`，另有 parser／SDK 版本、來源欄位及截斷旗標。沒有 SDK 欄位不能證明 Google 原回覆沒有細項。

不保存 API key、完整提示、授權標頭、原始例外全文或 Google consumer/project 字串。`key_ref` 是以 API key 作為 HMAC secret 的用途限定匿名識別，可跨 slot 調序關聯；不輸出原 key 或其直接 SHA。project 對應維持 `unknown`，不能由 key 數或匿名識別推定獨立專案數。`source_sha256` 只綁輸入／批次識別，不證明來源內容正確。

觀測使用 best effort；寫入失敗保留原回應、例外及取消行為。每個程序保留觀測缺口累計，下一次成功寫入會帶上該程序的累計缺口；API 自身健康只代表 API 程序，無法代表所有 worker。程序在恢復寫入前退出時，該缺口不一定能持久化，不能宣稱觀測零遺失。

## 查詢與比較

`GET /api/observability/api-quotas` 的 Gemini `usage.execution_observation` 提供當前 Pacific 配額日的有界彙總。預設最多讀取 10,000 筆 API 事件與 10,000 筆指定 legacy analysis 事件、100 個最近任務；超出上限會標示 `sample_truncated`。讀取使用 SQLite `mode=ro`，不回填或更改歷史帳本。技術面板顯示實際 Agent 模型明細，預算預留紀錄另行標示。

歷史冷卻跳過、容量拒絕及附錄可由既有 analysis 事件投影；其缺失的 request ID、等待時間及品質通過證據不推測補值。新 ledger 與 legacy analysis 的相同 `observation_event_id` 僅計一次。

任務內的實際等待以時間區間聯集合併，不將並行等待直接相加，也不跨任務累加成單一報告延遲。缺 tokens 保留 null，提供樣本數與覆蓋率；不能當作完整 Google 帳單。品質結果須以同一 job 與具體 pipeline 綁定，缺 pipeline 不可借用其他報告的通過結果；`done` 不能自行提升為品質通過。

可比較 429 可分類比例、每角色多次嘗試後取得回應的比例、callback 延遲 p50/p95、冷卻恢復、分批有效／附錄採用／同報告 gate 通過、各任務觀測請求／已知 tokens／排隊及完成歷時。比較前核對 `configuration_versions`、用途、輸入識別與觀測覆蓋；重試後成功只支持關聯，不宣稱因果改善。新增紀錄需要程序載入新程式後才會產生，歷史 SDK callback 為零代表未觀測，不能解讀為沒有呼叫。

## 驗證入口

使用 `tests/run_prompt_boundary_tests.py`，隔離 SQLite 與網路。相關測試涵蓋缺 quotaValue、保密、觀測失敗、取消、sync/async、同一嘗試內並行 callback、重試 unwind、cache、legacy 去重、品質模式綁定、未知 tokens 及重疊等待。runtime/storage 必跑組另依 AGENTS.md 執行。不得以驗證為由提交額外模型請求或清除正式冷卻／每日停用狀態。
