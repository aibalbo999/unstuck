# 來源證據、完成狀態與刷新保存

來源不足包含不同原因：沒有取得資料、有資料但未進入可引用目錄、引用的單位或主體錯誤、輸出截斷，以及刷新後無法確認原分析輸入。本次沿用原品質閘門，分別處理這些原因。

## 已實作的契約

- `trade_source_contract.py` 的 `trade-sources:v2` 目錄增加法人、持股、RSI、MACD、量比及有日期與連結的新聞。只有適合的價格資料可作進出場價位依據；非價格數值不能成為價格來源。
- `institutional_evidence.py` 與 `trade_catalog_evidence.py` 將值、單位、主體、期間、觀測日及來源綁在一起。法人合計不能代替外資，千股不能直接寫成股，持股比例不能跨門檻或日期借用。單點資料不證明連續趨勢。新聞採逐字標題引用，不把已發生新聞當成未來事件排程。這是有界契約，不是全面自然語言事實驗證。
- `llm_completion_provenance.py` 與 `structured_output_runtime.py` 保存綁定原回應及本機清理結果雜湊的完成憑據。已知 `MAX_TOKENS`、其他不完整結束或未完成串流，不因重新解析、草稿恢復、語意快取而升格為完整。Agent 23/24 使用新 step cache 身分；Agent 24 語意快取另有完成契約。
- `report_analysis_evidence.py` 在分析前凍結輸入證據，隨既有 checkpoint 保存，輸出時另記原始量化資料、manifest 與必要的 render 量化資料。刷新不覆蓋原輸入，也不以舊輸入解除 `needs_rerun`。上限 512 KiB，超量明示省略並保留雜湊；歷史無法確認的輸入保持未知。雜湊不是供應商真實性的簽章。
- `source_observation_freshness.py` 將抓取時間和資料觀測日分開。法人資料使用七個日曆日的保守檢查，不能宣稱已核對最新交易日；缺日期、未來日期和過期資料不當新鮮。TDCC 缺少持股級距不補零。
- `.TWO` 融資券改走 [TPEx 官方 OpenAPI](https://www.tpex.org.tw/openapi/)，使用 `tpex_mainboard_margin_balance`，依官方欄位與 EDIS S23 的仟股單位解析。借券不在此端點，維持 unavailable；上市股票沿用既有 TWSE 來源。無匹配、重複標的、連線失敗不當成零。
- 事件日曆只有在來源成功且涵蓋明確區間時，才可表達該區間沒有事件；來源失敗、日期不明或未來 as-of 不等於沒有事件。此狀態不代表全市場沒有任何事件。
- `provider_correlation.py` 讓新工作經 job/fetch/operation/attempt 身分關聯 source audit 與 usage，usage 的既有 SLA event ID 可精確連接 SLA 紀錄。實際 callback 嘗試與 aggregate 列分開；不把 callback 次數當 HTTP 請求次數，也不補造歷史工作歸屬。取消、執行緒與並行工作各自保留身分。

## 驗證與正式修復邊界

隔離測試涵蓋上述契約、持久 checkpoint、快取、刷新、來源與品質閘門；歷史離線回放不呼叫模型或改寫 artifact。正式修復使用既有完整重跑 API，依原 quota、fallback 和 deferred retry 規則執行。已排程不等於完成，服務 ready 也不證明模型或品質通過。

第一輪正式驗證發現完整重跑入口未凍結分析輸入、trade manifest 未經 graph 帶回 renderer，以及明確 `macd: value` 缺少同語意證據路徑。後續修正以真正入口與 SQLite 恢復測試驗收；歷史 checkpoint 沒有保存的原始輸入仍保持未知。MACD、signal、histogram 分別驗證，不互借數字。來源修復與 prompt 共用可引用路徑判定，只在有實際可用證據時發出一次完成的修復呼叫，並說明失敗的主張與所需主體、期間、日期和單位；這不保證模型一定能產生完整結果。

本次稽核對 3105 模式 B 的補充：既有規則正確排除「等待進場條件」，不能將它認定為零部位仍下買單；該案例仍有獨立 DCF 來源問題，須依實際品質結果处理。

詳細離線與部署證據存於本機 `stock-source-optimization-20260921.8ayim7zj`，各階段結果以該次實際 revision、測試紀錄及新報告為準。

## 2026-09-22 正式案例後續修正

今天的正式驗證發現，法人定性「買超趨勢」可能跨過另一個主體與買賣超動詞，誤抽後方數字；零活動分項後的合計、同期間接續也有解析缺口。修正以保存的原輸入與原分析作 regression fixture，只有已匹配的來源才能提供期間與觀測日期；中途切換日期或期間不承接，零活動分項須有同期間、同觀測日的零紀錄。錯主體、錯單位、錯數字格式及未能明確配對的分項仍阻擋。

模式 D 的來源檢查將末尾明示的「等待…後再重新評估」視為未來條件，不能把它當作已發生的連續買超；只處理單一末尾子句，後面還有新事實、句號、分號或非數字逗號時維持原文驗證。此投影不補造來源，也不讓 Long/Short 省略引用。來源修復安排在品質及身分重寫之後，候選仍須過相同品質檢查；final-audit 重寫另在原有兩次／每工作上限內檢查新來源缺口，不新增模型重試迴圈。

本機保守 Neutral fallback 明示 `local_fallback` 與來源 `degraded`，不宣稱模型 `STOP` 或來源通過。只有原 manifest 與輸入仍一致時才保存 prompt receipt；修復拒絕或取消時，輸出、manifest 及完成憑據一併回復。Agent 23/24 step cache 與 Agent 24 response-cache 的相關契約版本更新，其他角色快取不因此失效。

技術指標的 `Signal` 僅在局部明示 MACD 語境映射到 `macd_signal`；ATR 指定期間須相符，bare ATR 另須來源 calculation policy 唯一指向 ATR14。來源日期、供應者、可用性、重複別名與數值仍核對，不提高容差。這些規則不宣稱能理解所有自然語言敘述。

當日稽核與後續實作證據分別在本機 `stock-execution-verification-20260922.u669ilu1` 與 `stock-source-followup-20260922.iygy7dzs`；正式重跑結果以實際新報告為準，離線通過不能替代模型與來源驗證。
