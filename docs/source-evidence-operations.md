# 資料來源取得與證據判讀

來源改善不會降低報告的 data trust、引用或品質 gate。`success` 只描述該筆觀測的範圍；來源有回應不代表足以支持投資結論。

## 新聞與商品適用性

- 近期新聞以固定分析 cutoff 和設定的 30 天視窗篩選；未知日期、未來日期及舊聞不占近期名額。原連結與日期保留於快照，`news_selection` 記錄排除原因及不足；過大的快照可裁背景，必須標示截斷。
- `source_applicability.py` 是 planner、merge、freshness、trust 的共同能力表。市場沿用既有台股／美股辨識；ETF 必須由明確 quoteType 判定，不以數字代號猜測。
- 台股不因 SEC 空缺告警；ETF 不抓一般公司財報。現有公司估值流程尚無持倉／NAV 分析能力，因此 ETF 分析明確攔下，不產生一般公司 DCF 結論。

## 部分資料與共用快取

- 匯率分 Bank of Taiwan、open.er-api.com、FRED 實際上游；第三方 USD/TWD spot 沒有銀行 bid/ask，也不代表 EUR/JPY 完整。
- FRED 各 series 分開取得、共用與恢復。籌碼保存 TDCC、融資券、借券各自狀態；合併不會把 partial/stale 改成完整成功。
- 籌碼取得成功但觀測日期缺失時，保留數值並標 `date_status=unknown`、部分覆蓋；不補造日期，也不把未知說成過期。
- PE 的歷史分位與情境假設在 prompt、快照、圖表及審計分開標示。預設倍數不列為取得歷史分位資料。
- 宏觀、匯率、SEC mapping 與職缺／社群使用既有 JSON cache；Redis named lock 或 SQLite file lock 合併同時請求。取得時間不因其他標的命中快取而更新。
- 搜尋冷卻以 provider/endpoint/credential scope 保存，重啟仍有效。429 尊重 Retry-After；拒絕、付費限制與未知 432 不冒稱日額度耗盡。MOPS 安全拒絕頁記為 access_denied，不繞過。
- MOPS 法說會來源發生已分類錯誤時，改查 [TWSE WebPro 公開站外法說會索引](https://webpro.twse.com.tw/WebPortal/vod/101/?categoryId=170)。僅保存相符公司的已完成場次日期與連結，不擷取摘要、影音或逐字稿；保留 MOPS 錯誤，實際 provider 標 WebPro，覆蓋仍為 partial。索引沒有可用場次不代表公司沒有法說會。
- WebPro 每次最多查一頁三筆，成功 metadata 共用快取一天、有效空結果五分鐘；錯誤沿用持久冷卻。快取保留原取得時間，實際 HTTP 與外層 aggregate 分開計數。MOPS 正常回傳空結果時維持既有本年度／前年度查詢規則。

法人籌碼由 `data_fetch/institutional_provider.py` 統一同步及 registry 取得。共享快取以股票與 lookback 分開：近期觀測沿既有六小時期限，過期觀測十五分鐘再查、有效空結果一分鐘再查；強制刷新仍可繞過資料快取，但不繞過 provider 冷卻。快取保留原 acquisition 時間，另以 `latest_date`／`observed_at` 判斷觀測新鮮度，重新組裝報告不能刷新它們。

缺列不推定零交易。只計相符股票、有效日期與有限非負買賣股數；原始觀測日及實際筆數保留。近期資料仍可能只有部分期間覆蓋，完整五個交易日無法確認時，`last_5_trading_days_net_buy_thousand_shares` 保留空值。來源例外與成功空回應分開記錄，SDK callback 不當作 HTTP 已送出的證據。

## 觀測與年度日曆

SLA v4 僅新增 `details_json`，保留舊資料。新事件保存有界的 correlation、HTTP、cache/stale、error_kind、retry_at 與分項覆蓋；不保存 key、query 或 response body。HTTP 請求、callback/aggregate、快取與本機冷卻分開計數；舊觀測不回填猜測。來源面板的「取得資料率」仍是供應商觀測口徑，不是報告成功率。

Typed 來源錯誤在報告中顯示可讀原因；HTTP code、回應大小、雜湊與 parser 版本保留於結構化診斷，不嵌入報告訊息而被誤認為財務數字。

Agent 19 的原始「避免」輸出，只有原始進場、回補、風險及重評條件共同通過明確無部位契約，normalizer 才保留原文；不將已驗證回補欄位改成 `N/A`，也不替原始缺漏或衝突補造無部位證據。僅更新 Agent 19 快取版本，品質 gate 仍拒絕缺乏明確語意的原始 `N/A`，也不放寬已有部位或附帶價格的檢查。

Agent 19 的非 Gemma 財務 JSON 只移除字串外的排版空白；所有欄位、數值、字串內空白及引用保持不變。輸入仍使用相同容量上限，State、market context 與原始證據不裁切；這與會轉換資料形狀的 dense/table 編碼分開。

品質重寫在 `repair_candidate_history` 保存同輸入、prompt 與上游證據範圍內最近 16 項退件問題，供後續完整重寫做回歸檢查；它不是目前品質判定，也不增加重試次數。Agent 19 在清除候選結構之前，使用既有價格解析與報酬門檻產生前次決策診斷。建議、目標或交易方案改變後必須重新評估市場來源，不複製舊結論的 `market_context_assessment`；證據不足仍保留警示。退件清單沿既有 graph/draft checkpoint 保存，新 metadata 可增加一個 draft 版本，但重複 defer 不重建初稿或重複新增相同版本。

Agent 19 的交易欄位診斷會將通用檢查的 `entry_zone`、`target_price`、`stop_loss` 對回真正 JSON 路徑 `short_setup.entry_trigger`、`downside_target`、`cover_stop`，列出候選原值與同一交易價格解析器的結果。解析成功不等於來源已驗證，無法解析不等於零；不從現價、均線或其他欄位自動代填。回應 schema 說明相同語意，只有 Agent 19 的 step cache 另行分版，品質門檻及模型修復次數不變。

交易日曆保存來源、版本與適用年度。缺年度資料時標 unknown，行情快取使用較短門檻。事件日曆只有成功且明確覆蓋完整未來窗口，才能判定該窗口沒有事件。

每年更新日曆時，從交易所官方年度公告核對 holidays、early closes、timezone、open/close；保留公告 URL、查驗日期與內容 hash，透過版本審查更新 `BUILTIN_MARKET_CALENDARS`。再用正式 Python 執行 `backend/maintenance.py update-market-calendars --year YYYY --market tw --market us`；已有檔案預設不覆寫，確定差異後才指定 `--overwrite`。執行相關 calendar/freshness 測試，並確認載入的 valid_year、calendar_version。沒有官方年度資料時維持 unknown，不複製前一年日期。

RQ 使用 `worker_rq_scheduler.BoundedSchedulerWorker`，維護檢查及閒置 dequeue 等待上限為三十秒，處理重啟快照中的舊排程鎖自然過期後接手過慢的情況。沿用 RQ 的原子 NX 鎖、排程到期條件與 SimpleWorker 執行方式；worker heartbeat 存活期限、工作逾時與 provider 冷卻不變。worker 忙於執行工作時仍依既有執行模型處理，三十秒不是所有排程延遲的保證上限。

## 發布驗證邊界

先執行隔離 behavior checks、歷史快照離線回放及有界來源探測，再部署、確認 runtime commit/health/queue，最後做單一完整報告 canary。canary 必須以 completed job 和新 artifact 的來源／引用／品質結果驗證；`waiting_retry` 不是完成。先通過代表案例才擴大重跑，歷史 artifact 不覆蓋。

OpenAI/Anthropic 未配置有效憑證時，不得標成已驗證的跨供應商備援。沒有近期新聞、未取得法說公告、未驗證年度日曆均保留不足標示。
