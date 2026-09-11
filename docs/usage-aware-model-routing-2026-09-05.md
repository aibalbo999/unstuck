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

## 2026-09-09 自動降級備援

目前選用的 `model_routes_usage_aware_free.json` 保留原本 Preview／3.6 的分流順序，耗盡或不可用後再依序嘗試下列候選：

- 一般分析：追加 `gemini-3.8-flash`，最後追加 `gemini-3.5-flash-lite`。
- 估值 Agent 4／14 與 audit：追加 `gemini-3.8-flash`，不使用 Lite。
- 最終決策 Agent 7／16／19／24：主模型原本就是 3.8，保留 Preview／3.6 備援，不加入 Lite。
- 摘要、tear sheet 與 embedding 維持各自用途；embedding 不可作為文字分析備援。

使用既有 `single_agent` 的同步／非同步 route loop；每日本機預算耗盡、模型冷卻、單次輸入超限或請求設定不相容時會繼續下一個候選。新候選仍經相同 RPM／TPM／RPD、工具迴圈預留、輸入上限與品質檢查，沒有放寬任何額度或裁掉來源來強行通過。品質重寫沿用該節點路由；audit 的暫時路由覆寫保持獨立，不會混入一般節點的 Lite。

`model_fallback` 與 `llm_model_response` 事件保留實際模型，step cache 也保存模型身分。若全部候選仍不可用，沿用 `AgentDeferredError` 與 RQ 延後重試，不把等待狀態當成分析成功。Lite 的一般分析品質仍須由每次實際輸出通過現行檢查，不能將模擬測試當成完整報告品質證明。

設定需重載 API／Worker 才會生效。既有已排定的 RQ 工作保留原重試時間，路由更新本身不會提前 enqueue 或重新送出分析。回復本次 profile 差異並重載即可退回舊備援順序；不清除每日預算、checkpoint 或既有報告。

驗證入口：`tests/test_automatic_model_downgrade.py` 使用隔離 SQLite、兩個假金鑰與模擬 provider 回應，重現 6409 的 20156-token 請求超出 Gemma 12000-token 上限、兩個備援每日預算耗盡；驗證切換 3.8／Lite、所有候選耗盡仍 deferred、同步／非同步入口、實際模型事件與 audit／品質重寫路由邊界。

本次驗證：修改前隔離回歸為 8 failed／3 passed，失敗集中於原路由無法承接 3.8／Lite；修改後 15 個相關測試檔共 159 passed，涵蓋每日預算、輸入限制、品質草稿、重試排程、workflow adapter 與 storage 邊界。測試禁止存取正式 DB、Redis 及 provider，未實測 Lite 完整分析品質。

2026-09-09 22:03（台北）正式服務已重載：先確認 Worker idle、waiting／started 佇列為空，正常停止 Worker，Redis SAVE 後使用 `start_mac.command` 啟動。新 launcher／Worker／API 為 11636／11759／11762，仍監聽 127.0.0.1:8080；Redis 從 RDB 載回 302 筆，沒有到期遺失。正式 API 回傳 Agent 11 包含 3.8／Lite、Agent 14 僅追加 3.8，healthz=ok、readyz=ready。重載前後 `.env` 雜湊、每日預算各模型合計、analysis job 狀態與 updated_at、6409 的 RQ 狀態／剩餘重試／排定時間逐一相同。6409 仍等待 9/10 15:00 的原排程；本次未提前重跑或產製新報告。

## 2026-09-09 品質優先的使用效益改善

目標是維持報告可信度，同時減少可證明的本機額度浪費。現有原始資料、prompt、工具、品質 gate、模型輸入上限與 RPM／TPM／RPD 均不放寬。

基準為當日 Pacific 額度日（台北 15:00 起）的 `api_usage_events` 與 `llm_daily_budgets`：Gemma 有 213 筆 input-capacity 本機攔截；Preview 有 189 筆 provider-request 與 148 筆成功回應事件，3.6 為 134／58，3.8 為 71／19，其中 3.8 有 44 筆 server-5xx 錯誤。這些是 Agent 呼叫事件，並非逐 HTTP 請求數、品質通過率或報告完成率。Preview／3.6 的本機預留各為 256；帳本差額包含工具預留及未完整記錄的追加請求，不能推算成可回補額度。歷史 node telemetry 可能標示主路由，不能用它把備援成功算成 Gemma 品質證據。

本輪改善的是工具呼叫的預留結算：原流程每輪先保留最多 6 次請求，未使用部分不會歸還。現在仍原子保留全輪上限，並在同一交易建立 receipt；工具 scope 結束後，只歸還未被 HTTP hook claim 的部分。1 次 claim 歸還 5 次，3 次 claim 歸還 3 次，6 次 claim 不歸還。每次已 claim 的失敗、取消或不確定送出仍保守計入；完全沒有 hook 證據時維持全扣。每分鐘限流仍逐請求執行。

Receipt 存於 canonical operational DB 的 `llm_budget_reservations`，只保存隨機識別碼、原 Pacific 日期、模型與 key hash，以及 reserved／accounted units，沒有金鑰原文。結算以條件 UPDATE 防止重複歸還，與原日／原 key-model 的預算更新同一交易；失敗回滾，不影響原 provider／取消例外。Scope 關閉與新 claim 共用鎖。未完成 receipt 不自動回補，也不根據舊 event 差額回補歷史扣帳；回復程式後舊扣帳及新增記錄可保留。

| 模型 | 本輪分工判斷 |
| --- | --- |
| Gemma | 適用輸入維持原路由；超限繼續備援，不刪來源以湊入上限。 |
| Preview／3.6 | 保留一般備援與品質重寫；工具流程結算可減少未使用預留。 |
| 3.8 | 保留最終決策與已配置備援；不把供應商 5xx 判成推理品質低落。 |
| Lite | 摘要及一般分析最後降級；估值／決策／audit 不新增 Lite。 |
| Embedding | 維持檢索用途，不用於生成分析。 |

驗證：新增行為初次為 11 failed／76 passed；修正後 scoped tests 為 97 passed，包含跨日、並行獨立連線重複結算、SQL 失敗回滾、sync／async／stream、取消及無 hook 證據。18 個相關測試檔的整合驗證為 248 passed；獨立唯讀審查重跑 scoped tests 97 passed，未發現重大問題。測試全部使用隔離 DB 與模擬 HTTP，沒有消耗正式模型額度。以 12 次本機預算、每輪實際只用 1 次的測試，連續 7 輪均能執行，每輪啟動前仍必須能預留完整 6 次；此為機制驗證，不是完整股票報告吞吐量。

這是減少已確認浪費的一輪改善，不能宣稱全模型品質／成本的全域最優；真實報告完成率與 Lite 分析品質尚需後續實際工作累積證據。

2026-09-09 22:18（台北）部署核對：使用正式 `start_mac.command`，新 launcher／Worker／API 為 91102／91129／91132，healthz=ok、readyz=ready，Worker idle 且有 heartbeat。舊 Worker 的排程子程序需追加 SIGINT 才結束；第一次新啟動因舊 API 正常關閉超過 launcher 兩秒期限而中止，待舊程序退出後重新啟動成功，未修改啟動器。Redis 在關閉前已 SAVE。正式 API 初始化新 receipt table，當時為 0 筆；前後各日模型預算合計、所有 analysis jobs 的 status／updated_at、6409 的 RQ status／retries／schedule，以及 `.env` 和驗證程式內容雜湊均相同。6409 仍排定 9/10 15:00，沒有提前執行；本輪沒有正式 provider 診斷請求或新報告產製。

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


## 2026-09-09 Gemma 輸入效率與品質分工

本節更新前述路由與 prompt 策略。Gemma 仍採本機 12000 input-token 上限與原 RPM／TPM／RPD；額度不是 Google 官方 entitlement。目的為增加可通過容量檢查且保留必要證據的請求，並非增加無效呼叫。

- 每個實際模型建立自己的 prompt；Gemma 使用緊密 JSON，等欄位資料列改成 `__record_table__=1`、`columns`、`rows`，索引物件另有 `row_keys`。提示詞包含展開規則。數字、null、false、0、順序與來源值完整保留；異質欄位／非字串鍵不強行轉表。
- Agent 11／15／17／20／22／23 依既有角色契約省略不相關的完整區塊與交易所同產業登錄名單，並在 `prompt_scope` 明列範圍。公司身分鎖、來源、日期、單位、品質警示、相關新聞與 State 證據保留。其他角色只使用無損表示，不套此角色投影。
- Gemma 不再以原 compact formatter 只留前幾則新聞／警示，不以通用字元截斷器裁切完整 prompt。仍超限就走既有完整資料備援。已由模板放入的完全相同 RAG 區塊不再額外附加一次。
- Agent 4 使用 3.6 Flash、Agent 14 使用 Flash Preview，互相備援並保留 3.8；最終決策仍使用 3.8，最終審核改用 3.8（Preview／3.6 備援），以上不使用 Lite 或 Gemma。
- 一般 Agent 的品質重寫若有其他候選，就跳過 Gemma。品質／audit／identity 修復 prompt 皆停用 compact／角色省略，防止第一個 Flash 修復時漏掉後面的反證與品質警示。
- 本次以表示法與角色資料選取取得容量改善，未引入新的多輪模型摘要或分批合併流程；超大的新聞／逐字稿仍保留完整資料交給備援。原始快照、State、歷史報告與已排定工作不因此重寫。

離線證據：最近 12 個保存快照 × 6 個角色，共 72 個重建 prompt（含初始化 State，無前序分析與 RAG），以實际輸入估算器計入 system／schema 後，可進入 12000 預算的樣本從 0 增至 45。這是容量准入量測，不是報告完成率或品質通過率。6409 的保存 checkpoint 獨立重播，Agent 11 由 19500 降至 11257 tokens；複製檔、原資料、State 與 RAG index 均未改動。實際執行準備階段還可能加入檢索內容，因此不保證所有請求都能由 Gemma 完成。

驗證：`tests/test_gemma_prompt_efficiency.py` 涵蓋資料還原、null／false／0 與數字鍵、角色證據、旗標恢復、同步／非同步模型准入與完整備援；`tests/test_gemma_checkpoint_replay_optional.py` 支援明確指定唯讀離線 checkpoint。相關 28 份測試合計 480 passed、1 個需指定 checkpoint 的測試 skipped；該 checkpoint 測試另行實際執行通過。獨立覆核發現的「第一個 Flash 修復仍裁減」問題已修正並回歸通過。


線上小量驗證與載入結果：首次表格格式驗證遇到 provider `ServerError`；一次有限重試後，Gemma 正確還原指定兩列，數值、null／bool、日期與 URL 與輸入完全一致。另使用 6409 保存資料與詞彙檢索的 RAG 片段呼叫實際總經節點，完整估算由 20156 降至 11913（約減少 40.9%），通過本機准入；provider 未在 90 秒內完成，回傳 `AgentTransientError`，因此未取得可評估的總經正文，也未證明正式報告品質或完成率提升。這是診斷呼叫，未重跑排程中的工作或改寫其報告。

2026-09-09 22:52 最終核對已透過正式 `start_mac.command` 載入。Worker 為 idle，`/healthz=ok`、`/readyz=ready`；正式 quota API 已反映 Agent 4／14 的新模型、Gemma 12000 上限不變。重啟前後所有 job status／updated_at、daily-budget aggregates、6409 的 RQ scheduled 時間與重試欄位、`.env` 及已驗證程式雜湊逐項相同。診斷呼叫使用既有額度與限流機制；這裡的額度不變是指診斷完成後的重啟區間。原等待重試工作仍保留原排程。


最後核對另發現 `.env` 的 `AUDIT_MODEL=gemma-4-31b-it` 會蓋過 profile；已只將該項改為 `gemini-3.8-flash`，其餘 `.env` 位元內容保留，舊檔以限制權限備份。再次正式載入後，以上 health／ready、queue／job／budget 與檔案雜湊檢查均通過；新程序設定讀回審核 3.8。最終環境下重跑同一組測試仍為 480 passed、1 skipped。


## 2026-09-09 全部 Gemma 角色盤點

本輪正式 6409 工作的 Agent 11（22:55:36，輸入估算 11,913）及 Agent 20（23:02:31，輸入估算 11,144）已有 Gemma 完整回應；Agent 20 曾遇 5xx，重試後成功。這證明個別角色呼叫成功，不能等同三份報告已完成或最終品質稽核已通過。Agent 1／2／3／5 的實際輸入超出本機 12,000 token admission，已轉其他模型。

以下是最新 12 份非空 job snapshot × 15 角色的離線重建，使用初始化 State、不含後续分析和 RAG；未呼叫模型、未改寫正式 DB。這是容量測量，不能當成功率或實際 checkpoint replay。41/180 符合本機輸入上限；執行中 State、來源快照及 RAG 會改變大小，因此不能拿這次重建數字取代上方實際呼叫紀錄。

| Agent | 角色 | 12 份中可容納 | 輸入估算範圍 |
| --- | --- | --- | --- |
| 1 | 商業模式與整體分析 | 0/12 | 13,000–16,105 |
| 2 | 五年財務深度分析 | 0/12 | 13,309–16,414 |
| 3 | 競爭護城河評估 | 0/12 | 15,505–18,610 |
| 5 | 未來成長潛力 | 0/12 | 13,914–17,019 |
| 6 | 多空辯論 | 0/12 | 13,497–16,602 |
| 11 | 總經環境與產業週期 | 10/12 | 11,139–12,942 |
| 12 | 商業模式與競爭護城河 | 0/12 | 15,238–18,343 |
| 13 | 財務排雷與體質評估 | 0/12 | 14,172–18,203 |
| 15 | 籌碼流動與市場情緒 | 10/12 | 11,289–13,094 |
| 17 | 泡沫情緒與極端預期 | 0/12 | 12,258–16,424 |
| 18 | 法證財務與籌碼派發 | 0/12 | 14,738–17,929 |
| 20 | 管理層語氣與法說會分析 | 11/12 | 10,372–12,173 |
| 21 | 紅軍與空頭反證 | 0/12 | 14,017–17,744 |
| 22 | 技術動能分析師 | 0/12 | 12,104–13,958 |
| 23 | 主力籌碼分析師 | 10/12 | 11,094–13,008 |

總經、籌碼情緒、管理層語氣與部分短期角色較有機會直接使用 Gemma；其餘仍需更精確的角色資料契約，或按來源分塊並保留可追溯證據後再驗證。這輪未新增多階段模型摘要，不以任意裁切、放寬 admission 或降低品質 gate 換取 Gemma 使用率。估值、最終決策與總稽核維持既有較強模型。


## 2026-09-10 可還原格式壓縮第二批

`prompt_record_tables.py` 支援欄位順序相容的 superset schema，以 `absent` 記錄缺欄；缺欄、null、0、false 不互換。`prompt_builder.py` 僅在 dense 模式，對指定的 data_freshness.source_freshness 做型別敏感、完整 JSON 同值比較；相同時以本 payload 根層 source_freshness 的 $ref 取代重複副本。沒有刪除來源紀錄、調高輸入上限或放寬品質檢查；非 Gemma 路徑不啟用。

使用同一批最新 12 份快照 × 15 角色配對重建，180 組皆可還原成原本相同的 payload，原始 snapshot 沒有變動。符合本機 12,000 輸入上限的組合由 41/180 升至 51/180，每組節省 301–1,898 估算 tokens。新增可容納主要分布於技術、籌碼與部分情緒角色；大型財務與護城河角色仍需另外設計證據分塊流程，本輪不冒稱全部可直接使用 Gemma。

驗證：261 項相關隔離測試通過，獨立覆核 27 項通過。Gemma 真實格式還原診斷嘗試兩次均遇供應商 HTTP 500，未取得可驗證回覆，因此未執行後續技術角色診斷；上述數字僅代表容量改善與程式還原性，不代表模型理解或報告成功率。


## 2026-09-10 依供應商回饋判定額度耗盡

依使用者要求，正式 usage-aware profile 啟用 `provider_quota_authoritative: true`。本機 `rpd_limits` 改為參考值，計數仍持續累計，工具迴圈仍以 receipt 歸還未使用預留；達到本機值不排除 key，不冒稱供應商已耗盡。RPM／TPM 節流、輸入容量與品質檢查保留。

只有 provider 明確 RPD 回饋所建立的 key+model 停用狀態，才是每日額度耗盡證據；同 key 的其他模型不受影響。一般 429、500／503、逾時及暫時 circuit 是等待原因，不是已確認每日耗盡。各角色維持原有可用模型邊界，先嘗試其餘路徑，所有可用路徑受限才保存進度排程等待。明確 RPD 耗盡等待至 reset；其他模型可用性問題以 300 秒起退避、最長 1800 秒（更長 provider cooldown 優先）。

RQ 的有限重試計數不再使模型可用性錯誤成為終止原因：`analysis_job_retry.py` 只對 AgentRateLimitError／AgentTransientError 補足後續一次 retry，沿用相同 job、checkpoint 與 durable meta。完整分析與報告重跑入口都捕捉這兩類錯誤。取消、永久設定錯誤、資料／報告品質阻擋，以及無法確認排程的基礎設施錯誤仍依原本邊界處理；不假造成功或未知排程。

API `rpd_enforcement=provider_feedback_only`、`availability_retry_policy=persistent_with_backoff`，用量面板明示本機數字僅供觀測。歷史本機攔截和 provider 錯誤紀錄保持原樣。357 項相關測試通過，包括真實 RQ Job.retry 的補額與排程契約，以及 sync／async key 選擇、工具預留結算、完整分析與局部重跑入口。
