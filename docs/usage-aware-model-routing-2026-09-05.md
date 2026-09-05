# 每日用量與免費模型調整

## 評估範圍

資料來源為 X10 Pro Mac 上 canonical `backend/cache/operational.sqlite3` 的 `api_usage_events`。需求基準固定至台北 2026-09-05 20:02:05；本輪後續診斷另以 `diagnostic_*` 記錄，不混入日常 Agent 成功率。

這是本機已觀測 Agent 請求，不是 Google 帳單或完整 API 用量。舊版摘要、embedding 與語意快取命中未完整區分，故每日數字應視為容量規劃的部分證據；不能據此保證免費額度足夠。缺少 token 的紀錄維持未知。

## 每日需求

| 台北日期 | Agent 請求事件 |
| --- | ---: |
| 08-22 | 0 |
| 08-23 | 307 |
| 08-24 | 287 |
| 08-25 | 354 |
| 08-26 | 340 |
| 08-27 | 484 |
| 08-28 | 256 |
| 08-29 | 628 |
| 08-30 | 256 |
| 08-31 | 324 |
| 09-01 | 369 |
| 09-02 | 202 |
| 09-03 | 195 |
| 09-04 | 315 |
| 09-05，截至 20:02:05 | 1517 |

- 14 個完整台北日合計 4317，日均 308.4，最高 628；若只看有請求的 13 天，日均 332.1。
- 最近窗口合計尖峰為滾動 60 秒 76 個請求事件；這是跨模型、跨 key 合計，不是某個專案的 RPM。
- 今天截至基準時間：503 個成功事件、756 個供應商配額錯誤、463 個本機攔截、235 個其他錯誤。請求與結果時間不同，不能假設加總一定相等。
- Pacific 配額日與台北日期不同。相同基準下，最近 14 個完整 Pacific 日平均 371.4 次，最高 1197 次；包含今天台北 15:00 前的重跑尖峰。
- 有 provider usage 的 input-token 樣本：Gemma 24 筆，p95 23577；3.6 Flash 273 筆，p95 68384；Preview 109 筆，p95 40368。樣本包括有 usage 的失敗回應，不只是成功；舊紀錄覆蓋不足，不能推估成完整每日 token 用量。

## 有限實測

匿名 slot 3，SDK retry 關閉、順序執行，未輪換 key、未新增 project。所有結果包含失敗，一併保存至 canonical ledger。

| 測試 | 結果 | 決策 |
| --- | --- | --- |
| 3.5 Flash-Lite 數字抽取 | 通過，缺值保留 null | 繼續用途測試 |
| 3.5 Flash-Lite 真實摘要輸入 | digest 22841 input tokens、tear sheet 10139，兩者皆通過基本輸出檢查 | 替換摘要模型 |
| 3.7 Flash 四模式決策 | A/D 通過；B/C 首次與各一次補測均 503 | 不納入正式路由 |
| 3.8 Flash 四模式決策 | B/C/D 首次通過；A 首次 503、同輸入補測通過 | 限定決策節點採用，保留備援 |
| 3.8 Flash 一般分析樣本 | A4/B12/C21 503，D22 通過 | 不全面取代一般分析 |

3.8 決策樣本的 input tokens 約 28267 至 84458。驗證包含 native schema、正文存在、公司身分、prompt 洩漏與現行節點財務檢查；不是統計效能排名，也不是新產製的四份完整報告。診斷沒有改寫 checkpoint 或正式 report artifact。

## 已採用設定

版本化設定：`backend/model_routes_usage_aware_free.json`。`.env` 選用此 profile，並移除舊 Agent 7、舊摘要模型與 RPM/TPM map 的衝突或重複覆寫。

- Agent 7 / 16 / 19 / 24：`gemini-3.8-flash`，使用受支援的 `low` thinking。
- context digest / tear sheet：`gemini-3.5-flash-lite`。
- 一般分析與 audit 保留 Gemma，但本機單次預估輸入預算為 12000；超過時不選 key、不送 provider、不重試同一個過大輸入，直接交給已配置備援。
- 一般分析備援分流：奇數 Agent 優先 `gemini-3-flash-preview`，偶數 Agent 優先 `gemini-3.6-flash`；決策 7/19 優先 Preview、16/24 優先 3.6。不增加新 key 或額外專案。
- embedding 維持 `gemini-embedding-2`，沒有重建向量庫。
- 本機 Gemini 3.8 RPM 2、Lite RPM 5；Gemma RPM 1、TPM 16000。這些是保守操作預算，不是宣稱 Google 核發的全部專案額度。舊 Gemma TPM 12000000 已移除。
- Gemini 3.8 / 備援單次預估輸入上限 150000，Lite 64000。四個已測決策輸入皆可通過本機 admission check。
- RPD 以本日 AI Studio 額度表與使用者指定「16 key 均為獨立免費專案」為評估假設，不核對 key 編號；採用下列 80% 本機操作預算，不啟用付費。

## 每日預算與效率更新

| 模型 | 每專案參考 RPD | 每專案本機預算 | 16 專案合計本機預算 | 每專案本機 input TPM |
| --- | ---: | ---: | ---: | ---: |
| Gemma 4 31B | 14400 | 11520 | 184320 | 16000 |
| Gemini 3.8 Flash | 20 | 16 | 256 | 200000 |
| Gemini 3 Flash Preview | 20 | 16 | 256 | 200000 |
| Gemini 3.6 Flash | 20 | 16 | 256 | 200000 |
| Gemini 3.5 Flash-Lite | 500 | 400 | 6400 | 200000 |
| Gemini Embedding 2 | 1000 | 800 | 12800 | 24000 |

數字是規劃假設及本機限額，不代表已逐一驗證 16 個專案的 provider entitlement。`provider_limits_verified=false` 保留；設定另外記錄 `user_declared_independent_free_projects`，不再要求使用者核對 key。

- `llm_daily_budgets` 在 canonical operational SQLite，以 key hash / model / Pacific date 隔離。跨 API/Worker 原子預約，重啟不歸零，Pacific 午夜自動切日，包含夏令時間。
- 初始化讀取當日 `llm_provider_request` 與已知模型診斷的請求紀錄（smoke/quota probe/mode/analysis/summary canary），匿名 slot 可歸屬者按原本順序扣入，沒有 slot 的舊紀錄均分並向上取整保守預留；不重複扣 response/error/result，countTokens 診斷不視為生成請求。本機預檢不扣新額度。
- 這是「保守預約」，不是帳單：送出後失敗也不退回；Agent 2/13/18 的 SDK 工具迴圈預留最多 6 筆，即使實際呼叫較少也不自動退回。較低層語意快取命中可能已有預約，歷史漏記與其他程式用量無法完整扣帳。
- 每個模型路由 quota/auth 失敗最多 4 次後切換，不再因有 16 key 而必須嘗試 16 至 32 次。達到次數上限不宣稱所有 key 都失效；明確 RPD 429 仍只停用受影響的 key/model。
- 5xx 最多 2 次嘗試後使用備援。預算耗盡或資料庫暫時不可讀時走可恢復延後，不產生假完成報告，不降低品質檢查。
- Embedding 按估計輸入量分批，保留快取與索引順序，單筆過大不截斷。Agent 2/13/18 的 SDK 工具追加請求，會以同一 key/model 依實際 JSON 輸入逐筆檢查 RPM/TPM；首筆不重複扣除，最多允許 6 筆，SDK 內部 retry 固定為 1。TPM 是本機估計而非 Google tokenizer，仍可能遇到供應商限速。
- 並行數不變。以先前 Pacific 完整日樣本，3 倍決策嘗試平均約 210，低於 256 本機預算；3 倍一般分析平均約 904，不能全部交給合計 512 的兩個 Flash 備援，仍需 Gemma 可承接的短輸入與快取/重試削減。工具預留、重寫與尖峰可能使任務延至下一配額日，不能保證所有 3 倍尖峰即日完成。

## 程式保護

- 每日需求 service 分開台北日與 Pacific 日、完整日與今日、供應商配額錯誤與本機攔截。
- 保留安全的 quota 種類、數值、模型與 retry delay；解析有深度與節點數限制，不保存 consumer、project、key 或原始錯誤全文。
- 輸入估算包含 system/schema，不把輸出預留當成 input TPM。估算不是官方 tokenizer，仍需 provider usage 持續校準。
- TokenBucket 不再將過大需求裁成容量；sync/async KeyRotator 與 Redis 預約入口皆提前檢查。
- 容量失敗是獨立本機事件，不開啟模型失敗 circuit、不停用其他模型、不任意截斷 canonical 證據。
- 品質重寫、報告 conformance、圖表與 evidence gate 保留原行為。

## 官方依據

免費資格來自 [Google API 價格表](https://ai.google.dev/gemini-api/docs/pricing)；實際 RPM/TPM/RPD 需查各專案 [AI Studio](https://aistudio.google.com/rate-limit)。額度按 project 計算，不按 API key 相加。[官方限制說明](https://ai.google.dev/gemini-api/docs/rate-limits)

3.8 的 thinking 支援 low/medium/high，不支援 minimal。[模型文件](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)

## 先前路由部署驗證

2026-09-05 台北 20:51 以正式 `start_mac.command` 完成受控重啟，保留原有區網模式。新 launcher PID 13523、Worker PID 13574、API PID 13592。

- 重啟前確認 waiting / started / scheduled / deferred 皆為 0。先停止 Worker，執行 Redis SAVE 並啟用最後關閉儲存，再停止舊 launcher；新 Redis 日誌確認從 RDB 載回 634 筆、到期 0 筆。重啟後佇列仍全為 0。
- API 與 Worker process 的 `MODEL_ROUTES_FILE` 皆指向新版本化 profile；沒有繼續使用舊的 report-rebuild override。
- 執行中的 `/api/observability/api-quotas` 確認四個決策模型、兩個摘要模型與輸入 / RPM / TPM 預算皆與新設定相符，`provider_limits_verified` 仍為 false。
- 同一 API 實際回傳台北日均 308.4、完整日最高 628、今日 1517；Pacific 完整日均 371.4。每日統計 reader 個別實測約 0.05 至 0.32 秒，並非整個 API 的延遲承諾。
- 1401 項受影響回歸測試通過，涵蓋容量、配額解析、路由、可靠性、runtime/storage、四模式 schema / 模板 / 圖表等；不是整個 repo 全測試套件。
- Playwright 實測 1440 與 390 像素寬度：用量面板正常載入、文字沒有水平溢出、無 pageerror。截圖位於 `backend/cache/qa-usage-routing-20260905/`。
- runtime doctor 再確認 API 使用的 storage、operational state、report index 與 output 均在 X10 Pro Mac。

沒有刪除或重新產製既有報告，沒有清除 checkpoint、沒有啟用付費；之後啟動的新分析使用新路由。歷史錯誤警示保留，不會因換模型而歸零。本次修改尚未 commit / push。

## 本輪效率設定部署驗證

- 模型預算、RPD/TPM、retry、embedding、API panel、settings/runtime/storage 與報告邊界整合回歸共 1507 項通過；其中工具迴圈、每日預算、embedding、model policy 與 transport 的 113 項另以 `ResourceWarning` / `RuntimeWarning` 視為錯誤通過。`git diff --check` 無問題。
- 獨立審查提出的兩項問題均已修正：embedding 後續批次失敗會保留已成功向量；SDK 工具追加請求會逐筆限流，且 sync / async / stream 入口都將本機 guard 失敗轉成不可重試的 Agent 設定錯誤。
- 2026-09-05 台北 23:13 完成受控重啟。重啟前 active jobs 及四個 RQ queue 的 waiting / started / scheduled / deferred 均為 0；Worker 先正常停止，Redis `SAVE` 成功並設為 `60 1`，新 Redis 從 RDB 載回 634 筆、到期 0 筆。沒有清除佇列或觸發股票分析。
- 正式 runtime 為 launcher 48819、Redis 48839、Worker 48847、API 48850。API 與 Worker 都載入 `MODEL_ROUTES_FILE=backend/model_routes_usage_aware_free.json` 且保留 `LAN_ACCESS=1`；8080 實際監聽 `0.0.0.0`。
- 正式 `/api/observability/api-quotas` 已回傳 `rpd_enforcement=atomic_sqlite_per_key_model_pacific_day`、完整 RPM/TPM/RPD map、16 個 key、quota route 4 次與 5xx 2 次上限，以及可讀的 `daily_budget`。runtime doctor 確認 operational DB、report index、output 與 checkpoint 均留在 X10 Pro Mac。
- Playwright 直接讀取正式 API，在 1440 / 390 像素寬度確認本機剩餘 0 可正常呈現、沒有水平溢出與 pageerror。截圖在 `backend/cache/qa-model-budget-20260905/budget-live-*.png`。

### 正式本機預算狀態

Pacific 2026-09-05 啟用後的正式 API 顯示：3.8 剩 246/256、Preview 剩 150/256、3.6 剩 0/256、Lite 剩 6397/6400、Gemma 剩 184116/184320；Embedding 顯示 12800/12800，但只代表本機 ledger 沒有可初始化的既有紀錄，不代表 Google 實際使用為零。

3.6 會由本機預算暫停到下一個 Pacific 午夜（2026-09-06 台北 15:00），不以重啟清零規避既有用量。上述數字是本機保守預約，不是 Google 精確餘額。
