# 供應商 429 根因查證

日期：2026-09-05；以下時間均為台北時間。

## 結論與範圍

已重現目前 `gemma-4-31b-it` 的一項具體根因：匿名 key slot 3 所屬專案回傳免費層每模型每分鐘輸入 token 額度 **16000**。使用 2367 / 模式 C / Agent 18 出錯節點快照與已保存 RAG 來源重建的輸入，Google `count_tokens` 為 **24228**，同一支 key 實際生成請求再次回傳相同 TPM 429。

本機 `.env` 將此模型的 TPM 設為 **12000000**，是這個已核實專案上限的 **750 倍**。現有限速與重試未將「單次輸入超過已知容量」獨立處理，因此會對同一份過大輸入反覆嘗試、再進入模型冷卻。等待每日重置不會改變單次輸入過大的問題。

這個結論不等於全部 16 支 key、全部模型或全部歷史 429 都是同一種配額。當天另有 key slot 2 / 4 成功處理超過 16000 input tokens 的紀錄；其他專案額度與 quota 計算差異尚未透過各專案 AI Studio 驗證，不能推定全部 key 都適用 16000。

## 查證方法

- 以 runtime doctor、canonical operational DB、checkpoint、原始工作事件、Redis/RQ、已安裝 SDK 與現有程式碼交叉查證。
- API / Worker 仍位於 `/Volumes/X10 Pro Mac/stock-agent`；Worker PID 59030 使用既有 `report-rebuild-model-routes-20260905.json`。
- 未修改 `.env`、模型路由、金鑰、冷卻、佇列或報告；未重啟服務。
- 執行 2 次單一 key 的診斷生成請求與 1 次 token 計數。生成請求各最多輸出 8 tokens、HTTP timeout 20 秒、自動重試關閉，不輪換 key。第一次使用合成輸入取得配額細項，第二次使用重建的分析輸入核實。
- 診斷請求及白名單化的配額結果已記入 `api_usage_events`；未保存 key、供應商 consumer/project ID、原始回應全文或模型思考內容。這些有限的診斷用量寫入是本輪唯一的 runtime 資料變動；工作本身仍持續正常執行。

## 供應商證據

15:14:31 的真實分析輸入重現結果，canonical ledger ID **375921**：

```json
{
  "http_code": 429,
  "provider_status": "RESOURCE_EXHAUSTED",
  "key_slot": 3,
  "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_input_token_count",
  "quotaId": "GenerateContentInputTokensPerModelPerMinute-FreeTier",
  "quotaValue": "16000",
  "quotaDimensions": {
    "model": "gemma-4-31b",
    "location": "global"
  },
  "retryDelay": "28s"
}
```

這個回應明確指出 TPM，沒有 RequestsPerDay、RPM、金鑰無效或帳號封鎖訊號。`retryDelay=28s` 只反映當下重試提示，不能解讀成等待 28 秒後同一個超額輸入一定能通過。

較早合成輸入驗證的 ledger ID **375826** 也回傳相同 metric、quotaId、quotaValue，retryDelay 為 2 秒；其 213225 字元輸入不作為實際報告大小證據。

### 分析輸入大小

來源工作：`analysis-2367tw-v3-1788575699914-9bf7b7f7:v3`。

使用執行 Agent 18 前的 root checkpoint `1f1a8f7c-ebbe-6772-8005-fdc4d6d2ca4c`，並加入同一節點保存的 RAG/context digest，透過現行 prompt builder 與 Google prompt sanitizer 重建。沒有執行 RAG 抓取或重新產出整份報告。

- 重建輸入長度：57111 字元。
- SHA-256：`d3ab9c18c8181a660f4633bc4c34607ac67b761b5d3737fddde41268c81e0793`。
- Google token 計數：24228，ledger ID **375836**。
- 重建輸入的本機估算含 8192 預留：24509；扣除預留後為16317，比 Google input token 計數少7911。
- 原工作當時記錄的估算含預留為24388，與重建值不同，因此不是逐 byte 原始 request 重放；不能把24228冒充為當時原始請求的精確token數。
- token計數與第二次生成診斷使用相同SHA-256，確定這份重建輸入實際觸發相同的16000 TPM限制。

相對樣本也必須保留：原工作 Agent17 / slot2 成功回應有22278 input tokens，Agent20 / slot4 有21532。這些是供應商 usage，不應刪除或忽略，也不能以本輪 slot3 的上限推斷其他專案配置相同。

## 本機原因鏈

### 配額設定高估

`backend/.env:42` 的非機密設定為：

```text
TPM_LIMITS_JSON={"gemma-4-31b-it":12000000}
```

`backend/settings/models.py:227` 會讀入這個覆寫；以目前 Worker 使用的同一路由與環境重新載入設定，得到 Gemma TPM 12000000，RPM30。這個環境值覆蓋路由檔空的 TPM map。不能把它當成 Google 已核准的專案 quota。

### 單次輸入沒有容量檢查

`backend/llm_rate_limits.py:244` 以字元數除以3.5估算，且呼叫處加上8192輸出預留。這不是 Google 的實際輸入 tokenizer，也沒有把 TPM 的輸入量與輸出預算分清楚。

只降低 TPM 設定仍不足以修復：

- `backend/llm_rate_limit_buckets.py:27` / `:50` 會把需求量裁成 bucket capacity。純記憶體驗證 `capacity=16000, amount=24228` 的 `peek_wait` 和 `reserve` 都回傳0，沒有拒絕過大輸入。
- Redis 的 `backend/shared_runtime_guards.py:30` 以完整 tokens 比較上限；若單次輸入永遠大於上限，即使下一分鐘沒有用量仍無法預約。`backend/llm_rate_limits.py:172` 的等待迴圈沒有過大請求的獨立停止條件。

因此應新增明確的輸入容量判定，選擇保留證據的縮減或符合額度的已配置路由；不能只把12000000改成16000而留下等待或再次429問題。

### 重試放大

15:02:52至15:03:30，2367/C/18 對 Gemma 記錄17個供應商配額錯誤，涵蓋匿名slots1至16，ledger範圍375664至375713。這些是在15:01恢復後發生，不是每日重置前的舊錯誤。

`backend/agent_runtime/retry_policy.py:227` 將一般429轉為換key與冷卻；沒有辨識「目前輸入已超過該專案單次可容納的TPM容量」。這類問題不應將未修改的大輸入依序送到所有key來解決；Google quota依專案而非API key計算。[Google rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

本機安裝 `google-genai 2.8.0`，`llm_transport._genai_http_options()` 未設 retry_options；此版本 `_api_client.retry_args(None)` 使用 `stop_after_attempt(1)`。不能直接引用其他版本SDK預設重試次數，聲稱上述17次是SDK暗中倍增。

### 診斷資訊被截斷

舊 `llm_model_error.error_message` 只剩約240字元，通常停在通用的 quota/billing說明；重試訊息又把detail截到150字元。

新版 `backend/agent_runtime/llm_call_events.py:93` 為避免洩露原始provider payload，改成固定 `LLM call failed.`，但尚未額外保留安全的quota白名單欄位。現有 `llm_errors.describe_quota_or_rate_error()` 只遍歷dict/list；若SDK把錯誤JSON放在message字串內，沒有遞迴解析該字串，所以實際quota細項無法單獨呈現。

本輪受控診斷以有深度上限的JSON解碼取得quotaMetric、quotaId、quotaValue、model/location與retryDelay，證明可以保留原因而不暴露key或consumer。這是建議的後續產品修復，不是本輪已上線的變更。

## 不是每筆 quota_error 都是供應商429

canonical `api_usage_events`，台北2026-09-05 00:00至15:03:31，限定 `operation=llm_model_error` 且 `status=quota_error`：

| 模型 | 供應商ClientError配額事件 | 本機冷卻／RPD攔截 |
| --- | ---: | ---: |
| gemma-4-31b-it | 293 | 8 |
| gemini-3.6-flash | 221 | 361 |
| gemini-3-flash-preview | 65 | 94 |
| 合計 | 579 | 463 |

總共1042筆中，463筆是 `ModelCircuitOpenError`（457）或 `AllKeysRpdDisabledError`（6），在取得key前就被攔截，並沒有新送出provider request。這是本機事件統計，不是Google帳單或完整HTTP request數。

舊Gemini/preview歷史紀錄缺乏完整quota details，因此不能逐筆判定其TPM/RPM/RPD，也不能將全部579筆都套用slot3本次結果。當天先前的RPD停用狀態與15:00後preview成功回應相容，但不能拿「停用後恢復」取代原始provider配額細項。

## 修正優先順序

1. 先保留安全的供應商quota欄位，將provider429與本機deferred/circuit事件拆開，避免後續繼續失去根因。
2. 以各專案AI Studio的實際額度校正模型輸入預算與TPM限制，不推定每個key相同。移除不符合核准額度的12000000假設，不以增加key或專案繞過供應商限制。
3. 在預約key前判定單次輸入是否能容納；過大時依既有證據邊界縮減資料或選擇已配置且有足夠額度的路由，並明確回報，不能無限等待或重送同樣的大輸入。
4. 以模型token計數或經實際usage校準的保守估算管理輸入；區分輸入TPM與輸出預留，並保留並行請求的共享額度。
5. 分別測試單次過大、分鐘窗口暫滿、每日耗盡、多種quota同時違規，以及冷卻後恢復。只有真正可等待恢復的情況才按照對應時間重試。

Google官方將RPM、輸入TPM、RPD分別計算，任何一項超限都可能429；額度依專案、模型與使用層級而異，RPD於Pacific午夜重置。本輪確認的是特定專案的TPM，不是帳號封鎖或所有模型每日額度耗盡。[官方配額說明](https://ai.google.dev/gemini-api/docs/rate-limits)
