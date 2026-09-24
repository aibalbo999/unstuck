# Agent 有效設定與執行證據

`GET /api/observability/agent-settings` 是 API 程序當下載入的唯讀設定快照，包含全部編號 Agent 的設定與有效模型順序、角色 Lite 旗標、品質及稽核重寫路由、實際 generation profile、native schema／工具、各候選模型輸入限制與輔助角色。

`configured_fallback_models` 保留原始設定；`effective_model_sequence` 會包含路由函式追加的 Lite。`supplementary_context_budget_tokens` 是包含 system/schema/tools 預留量的補充 context 規劃額度，不代表完整來源已通過輸入 admission；實際請求仍須通過 input、TPM 及 context window 檢查。歷史分析與 RAG 字元上限仍按主模型設定，欄位明示此口徑。

`model_routes_file_sha256` 僅識別來源路由檔。`effective_settings_sha256` 另外覆蓋環境覆寫後的有效路由、角色旗標、generation/schema/tools、提示雜湊、context 與 runtime policy。API 程序與 worker 的設定可能不同，故 API 永遠標示 `snapshot_scope=api_process` 與 `worker_settings_verified=false`。驗證 worker 時須檢查新產生的 `llm_provider_request` 事件中相同欄位的雜湊，並以事件時間、工作 ID、實際 `model_id` 和 generation 設定辨識該次呼叫；舊事件或 hash 相同都不證明供應商現在健康。

成功模型回應的雜湊會進入報告 model execution receipt。臨時稽核路由或品質重試覆寫以每次事件的實際 `model_id` 為準。worker 對 import-time policy 的雜湊採程序內快取，policy 更新需要重啟程序。

Provider readiness 只回傳 provider 名稱與已載入 credential 數量，不包含金鑰、system prompt、來源資料或環境內容。Credential 數量可能即時刷新，因此不納入 policy hash；載入 credential 不代表服務可用，也不能證明不同 key 屬於不同 quota project。無可驗證 project 對應時保留 `unknown` 與 `independent_project_count=null`。

報告重跑與 SSE 原先使用通用秘密欄位过滤，誤把 `generation_config.max_output_tokens` 當 token 秘密移除。目前僅對 generation 設定使用嚴格數值／enum 白名單，保留可驗證的輸出上限，並移除 request body、system instruction、schema 內容與 credential。既有事件不回填推測值。
