# 分析優化收尾驗收

本輪延續已核准的四模式、可靠性、報告圖表與外接碟啟動工作。原四模式與模型效率已由 PR #13（`c29b8108`）合併；本輪只收尾先前保留的變更及驗收發現的缺口。

## 本輪交付範圍

- 金融文字規則區分實際數值、假設與不同口徑；提示詞排除內部索引與向量，RAG 以整塊證據控制預算。
- 失敗草稿獨立保存，恢復時重新驗證；持久化失敗不把草稿發成正式報告。
- RQ 重試尊重恢復時間與額度；無匹配排程或排程讀寫失敗時明確結束為錯誤，不永久停留在等待重試。只記錄安全的例外類型。
- 四模式圖表、缺資料與 CDN 故障提示；正式回應只信任固定模板雜湊與固定 Chart.js 版本，任意報告腳本仍被阻擋。
- 啟動器驗證程序歸屬，保留自訂 queue 設定；重建預設保留歷史，選用清除必須精確選檔、確認與驗證過的可回復備份。
- 重建送出採非破壞性的既有任務附接；送出前原子保存 pending，全操作共用 manifest 鎖。回應遺失或接受後存檔失敗時停止自動重送，待人工核對 Job ID，不宣稱完整冪等。
- QA 正確處理全部缺值、第一組資料缺值及全零柱狀圖，不把合法資料狀態誤判為繪圖失敗。
- 明確日期的當日高低價綁定日 OHLC 的日期與 high／low 欄位，不再因接近收盤價而驗證通過。日期歧義、重複日期或缺欄位維持不可驗證；明確收盤／價格基準保留原有低頻資料語意。

## 正式報告端到端驗收

透過正式 API 新建 1623.TW 的四種模式，沒有覆寫／刪除舊報告，也沒有重置額度或降低稽核門檻。

| 模式 | 新報告 | 快照完整性 | 內容／輸出契約 | 證據抽查 |
| --- | --- | --- | --- | --- |
| A | `1623_TW_v1_report_job_2015d85fba52.html` | verified | warning，無 blocking issue | caution：4 項不可驗證 |
| B | `1623_TW_v2_report_job_474e2f9f5b3a.html` | verified | warning，無 blocking issue | caution：4 項不可驗證 |
| C | `1623_TW_v3_report_job_6ccb7b5901c9.html` | verified | warning，無 blocking issue | caution：2 項不可驗證 |
| D | `1623_TW_v4_report_job_3298c5baf555.html` | verified | warning，無 blocking issue | caution：1 項不可驗證 |

四份 `final_audit.status` 均為 `passed`，不代表沒有警告：A 仍有國際新聞揭露及三個 DCF 來源／假設差異警告；C 仍有國際新聞揭露警告。B 是等待、0% 部位且未編造目標或風報比；D 是 Neutral、不交易，保存 120 筆日 OHLCV 與技術指標；C 的獨立做空計畫明列進場、目標、回補停損及 60 交易日期間。A 本例護城河分數都有來源，未知值分支由自動測試覆蓋，不能宣稱此 live 樣本也測到未知值。

證據警告保留原始語意：信心分數及分析假設不是原始資料證據；本輪未為消除缺少同語意路徑／技術價位不可驗證的警告，而改用相同數值補成通過。以上驗收證明新版流程與契約已生效，不是投資正確性、勝率或所有內容均已驗證的保證。

D 的現場抽查揭露「2026-09-04 當日高點 210」原本對到低頻收盤 208，差距落在既有 1% 容忍內。報告價格本身有同日 OHLC high=210 佐證，但舊 matcher 的來源欄位錯配；新規則限定正確日期與欄位，不調寬容忍值。歷史 snapshot 與當時稽核紀錄不改寫，目前規則投影另行驗證。

### 正式 HTTP 與瀏覽器

四份新報告直接開啟 `/api/report/{filename}`，在 1280／375 寬度完成圖表狀態、非空像素、尺寸、tooltip 與 CSP 驗證，共 8 組通過；A／B／C／D 分別有 7／10／8／3 張圖表，沒有 page error。

本機證據保存在 `.gstack/qa/remaining-delivery-20260906/` 的 `live-results.json` 與 `live-*.png`。測試只放行本機正式網址與固定 Chart.js CDN；Google Fonts 沿用原 CSP 的限制而使用備援字型，沒有因此放寬安全政策。舊 HTML 若未匹配目前固定腳本，仍可能沒有圖表，不能用任意 script 雜湊繞過限制。

### 舊失敗任務

歷史 manifest 的 28 個最新 Job ID 原為 27 `done`、1 核心資料不足 `error`；後補 12 個 Job ID 全為 `done`，兩組不能相加當成不重複股票／模式數。

唯一失敗的 2308.TW／C，本輪正常重試 `analysis-2308tw-v3-1788626786310-8a55cbf0` 已完成，產物 `2308_TW_v3_report_job_d1a3bc998e2d.html`，快照完整性 verified，無 blocking issue，仍有信心／證據警告。原失敗 Job 及 manifest 的 attempts 紀錄保留，只將 manifest 的目前 Job 指向已確認的新產物。28 個目前目標均已有成功生成的 Job，不表示 28 份內容品質全綠。

這份 C 報告含營收或價格的複合觸發條件，不在 OHLC 回測支援範圍，維持 `insufficient_data / unsupported_conditional_entry`，不能宣稱已完成可回測的交易；D 的 14 日事件投影沒有可用事件，保留 unavailable／空清單，未把窗外事件補成近期催化。

## 測試與發布紀錄

初次全套巡檢揭露舊提示詞版本、重試政策 fixture，以及新增交易驗算欄位的舊預期。本輪依已核准的新契約修正測試，不倒退 production 行為；另外透過 TDD 修正無排程／Redis 失敗、程序誤停、歷史保護與 QA 邊界。

所有一般測試均使用 `tests/run_prompt_boundary_tests.py` 隔離 SQLite、Redis 與 Python 網路；真實瀏覽器僅放行測試必要網址。正式報告重跑則明確使用正常 API 與既有模型額度，與單元測試隔離。

最終由 Git index 匯出的乾淨快照（tree `0febfa3c2833b26b5d12641d72fc98516b908f09`）涵蓋全部 264 個測試檔，分成三個互斥分片：

| 分片 | 結果 | 時間 |
| --- | --- | --- |
| 0 | 3165 passed，14 skipped | 475.56 秒 |
| 1 | 1948 passed，5 skipped，75 subtests passed | 47.97 秒 |
| 2 | 4325 passed，1 skipped | 575.59 秒 |

合計 **9438 passed、20 skipped、75 subtests passed，0 failed**。20 個略過項目中，6 個圖表瀏覽器案例已另以 `VISUAL_REGRESSION_REQUIRED=1` 啟用：QA／正式 CSP／視覺三檔共 **13 passed**；其餘為 4 個外部資料、8 個其他商用頁面、1 個 Redis Worker smoke 與 1 個指定歷史 checkpoint 的可選驗證，不宣稱本輪已全部執行。

同一乾淨快照另套用正式使用的 `model_routes_usage_aware_free.json`，路由、模型政策、重試、架構與工作流程轉接共 **80 passed**。80 個暫存檔案的獨立範圍審查與密鑰掃描通過，未包含 `.env`、cache、output 或資料庫；shell／既有績效介面 JavaScript 語法及差異檢查通過。程式已凍結，後續只補交付驗證紀錄。

初次分片發現的模組大小門檻、等待重試 fixture 與日期價格邊界，均完成修正及獨立複審後，才重新匯出上述最終快照；未把失敗那一輪當成通過。

正式受控重啟與遠端發布紀錄於完成後補入。

## 保留限制

PostgreSQL 的 live checkpoint、樣本外投資績效、舊報告全面重建均不在本輪驗收成果中。日 OHLC 無法重建同根先後順序或未知事件歷史；缺值、複合事件和未知交易成本仍維持不可驗證，不補造。
