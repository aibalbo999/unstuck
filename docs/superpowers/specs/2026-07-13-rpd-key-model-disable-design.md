# Gemini RPD Key/Model 自動停用設計

## 目標

當 Google Gemini API 對特定 API key 與模型回傳明確的 `429 RequestsPerDay`（RPD）額度耗盡訊號時，暫停該 `key + model` 組合，直到下一個 Pacific Time 午夜自動恢復。

這個改動只處理 RPD。RPM、TPM、服務忙碌、驗證失敗與其他錯誤維持既有處理方式。

## 行為邊界

- RPD 停用粒度是 `API key + model ID`。
- 同一把 key 的其他模型不受影響。
- 同一模型的其他 key 不受影響。
- 只有錯誤內容明確包含 `RequestsPerDay`、`requests_per_day`、`per-day` RPD quota metric，或等價結構化 quota metadata 時才觸發。
- 只有一般 `429 RESOURCE_EXHAUSTED`、`free_tier`、RPM 或 TPM 訊號時，不得誤判為 RPD。
- 停用期限是下一個 `America/Los_Angeles` 午夜；夏令時間由 IANA timezone database 處理。
- TTL 到期後自動恢復，不需要重啟服務或人工修改 `.env`。

## 元件設計

### RPD 判定

`backend/llm_errors.py` 提供獨立、可測試的 RPD 判定 helper。判定會檢查例外文字與結構化 `details`，但不記錄或回傳 API key。

### 共享停用狀態

現有 `backend/shared_runtime_guards.py` 的 Redis-backed limiter 延伸 RPD disable 能力：

- Redis identity 使用 API key 與 model ID 的短 SHA-256 雜湊。
- Redis key 不包含 API key 或 model ID 明文。
- Redis value 只保存無敏感性的狀態標記。
- TTL 設為距離下一個 Pacific Time 午夜的秒數。
- Redis 無法使用時，退回 process-local 記憶體狀態；粒度與期限保持一致。

### KeyRotator

`backend/llm_rate_limits.py` 在選擇候選 key 時查詢 RPD disable 狀態：

- 已對目前模型停用的 key 不列入可用候選。
- 成功選出的 key 維持既有 RPM/TPM reserve 行為。
- 如果目前模型的所有 key 都被停用，回報一個帶最早恢復等待時間的明確錯誤，讓既有 model fallback 流程切換下一個模型。
- 不進行無限 busy loop，也不輸出 key 明文或 preview。

### RPD 錯誤處理

`backend/agent_runtime/retry_policy.py` 在 quota error 分支中：

- 明確 RPD：呼叫 `disable_until_pacific_midnight(key, model)`。
- 非 RPD quota：維持既有 `penalize(key, model, retry_delay)`。
- 產生的 retry exception 保留 `key_slot`、`key_count` 與 quota 類型，供 retry stop policy 與觀測事件使用。

## 資料流程

1. Agent 使用 `KeyRotator` 取得指定模型的可用 key。
2. Google 回傳 429。
3. quota parser 判斷是否為明確 RPD。
4. 若是 RPD，將該 `key + model` 寫入 Redis，TTL 到 Pacific 午夜。
5. 下一次選擇同一模型時跳過該 key。
6. 該模型仍有其他 key 時繼續既有 retry；全部停用時交由既有 model fallback 流程處理。
7. TTL 到期後該組合自動重新進入候選集合。

## 錯誤與降級

- Redis 不可用：使用 process-local 狀態；此狀態無法跨 process 或跨重啟共享，必須留下 warning，但不能因此重新把 Redis 內已知停用的 key 判為可用。
- 時區資料異常：以安全的最長 24 小時停用作 fallback，避免立即重試 RPD key。
- 所有 key 對目前模型皆停用：回傳可分類的 unavailable error，包含最早恢復秒數，不包含任何 secret。
- 無法明確判定 RPD：不得長時間停用，沿用短期 quota cooldown。

## 測試需求

1. 結構化與文字型 `RequestsPerDay` 429 可被辨認。
2. RPM、TPM、一般 429 與 `free_tier` 不會被辨認成 RPD。
3. RPD 只停用觸發錯誤的 `key + model`。
4. 同 key 的其他模型仍可選用。
5. 同模型的其他 key 仍可選用。
6. Pacific 午夜前保持停用，午夜後自動恢復，涵蓋夏令時間邊界。
7. Redis 與 local fallback 使用相同 identity 與到期語意。
8. Redis storage key 不包含 API key 或 model ID 明文。
9. 所有 key 都停用時不 busy-loop，並提供最早恢復時間。
10. 現有 RPM/TPM cooldown 與一般 key rotation 測試維持通過。

## 非目標

- 不刪除或改寫 `backend/.env`。
- 不永久撤銷 Google API key。
- 不在本次改動建立 project registry。
- 不改變 RPM/TPM 配額值或 Agent 並行度。
- 不新增跨供應商 fallback。
