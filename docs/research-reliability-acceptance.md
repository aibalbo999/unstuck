# 研究可靠性驗收矩陣

驗收分為「資訊可追溯、數值及失敗狀態可重現」與「選股預測有效」。第一項可用工程與客觀小樣本核對，第二項需要真正事前資料、事先固定政策、基準、成本和自然到期结果，不能由測試數或描述性命中率取代。

| 項目 | 可測標準 | 本次證據與狀態 |
|---|---|---|
| 来源與日期 | 每筆來源日期來自來源列；scan/report生成時間不得代填；同股身分與最後bar日期核對 | 新篩選保存逐筆price/flow/volume日期和provider/取得時間。報告快照另列source、日期及hash。五筆皆可讀，3筆10/1對齊、2筆法人仍9/30；舊篩選訊號未改寫 |
| raw/adjustment/actions | 調整設定≠原始交換價格證明；未知或公司行動不自動通過 | 5筆歷史快照基準仍未知。既有provider設定/公司行動fail-closed通過回歸；完整跨期基準尚未驗收 |
| 數字重算 | 同日外資+投信股數/同日成交股數可重算；缺20筆量均不得顯示0倍 | 四個實際官方回應離線重播，10筆日期完整法人占量可重算，自營商未知。5筆10/1 OHLC官方核對相符，但5筆量皆不完全同值，禁止混用 |
| 主張與證據 | SMA矛盾/方向範圍不符阻擋；生成分析不得當独立證據 | 既有內容與證據gate保持，1301/1101撤回、gray/unknown研究用途不放寬。未證明全報告每一主張已獨立核實 |
| 時間與分母 | 全索引觀察槽、未成熟、缺结果、無成交分開；首次版本與同股不重疊不看outcome | 858報告/1716槽；主集合166。全槽未成熟676、主集合未成熟76。歷史不回算；日曆未知fail-closed |
| 成本隔離 | 未知不補0；有來源日期的假設只能稱假設，不冒充真實成交 | 可比成本假設淨结果仍0，無實際fills/佣金/滑價可恢復證據；未建立未授權成本情境 |
| 正式端到端與UI | 正式GET返回相同scope，實際服務JS載入并顯示兩種日期、unknown/gray，原件hash不变 | 正式測試、官方安全重啟與live API/JS驗證後記入工作區摘要；Node DOM harness不是目視瀏覽器QA |
| 失敗及復原 | 缺檔/坏JSON/錯ticker/bar日期/未来日期回unavailable；恢复原件後下次讀取可恢復，不抓provider代填 | 使用真實artifact locator測試6類失敗與恢復；hash不符的capture重播拒絕，無網路、無營運寫入 |
| 預測效力 | 事前可用資料、固定政策/embargo/控制基準、可核對淨结果、到期後評估 | 未通過。官方事後價格不能恢復point-in-time；76個主集合窗口須自然到期，成熟後仍需價格基準/成本。非承諾股票會上漲 |

## 工程變更

`candidate_report_observations` 透過 ReportArtifactLocator 只讀data companion，不要求HTML或Markdown。按ticker驗證，保存原件hash；快照日期另在 `report_evidence`，不寫入舊 `evidence` 或 metrics、不重算舊篩選數字。兩套來源無法相互代填。

新 institutional candidate 即使沒有價格也保存法人來源列日期；有同日daily row才保存成交量與價格日期并normalize。technical candidate保存逐筆行情/量日期，未足20筆過去量樣本時avg/ratio为null。scan流程補上实际provider与取得時間，cache新namespace避免重用缺日期缓存；import沿既有trigger保存metadata，不回填舊watchlist。

以 `scripts/replay_screener_observations.py --capture-dir <工作區捕捉目錄> --scan-date 2026-10-01` 重播四个已捕捉TWSE回应；SHA256核对不匹配立即拒絕，adapter session只回本機內容，無營運状态寫入。取得時間是10/2，不能補為10/1當時可用。

## 剩餘依賴與可觀測完成條件

1. 下次自然每日篩選將產生新的逐筆來源日期/來源；正式舊名單仍留原件，不為消除unknown做無證據回填。
2. 完整raw/actions及原報告價位同基準核對，才可能通过價格可比性；本次五筆客觀OHLC核對只覆盖10/1單日。
3. 成本需可追溯假設或真正成交记录。假設結果可做敏感度研究，但不是實際报酬；沒有成本時始终unknown。
4. 固定10交易日窗口按交易日曆自然成熟；population未成熟數下降可以觀測，不能造結果。即使成熟，仍不能自行升格為策略有效。
5. 真实point-in-time、benchmark/control資料供既有離線holdout入口；基準齐備且控制偏誤後，才可评估预测有效性。工程修正不能恢復未保存的歷史發布時間或實際成交。
