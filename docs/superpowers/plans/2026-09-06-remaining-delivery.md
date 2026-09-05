# 未完成優化收尾

延續使用者已核准的四模式、可靠性、報告圖表與外接碟啟動工作，不新增投資策略或降低品質門檻。

- [x] 確認 PR #13 已合併（`c29b8108`）；原四模式與模型路由不重複發布。
- [x] 協調其他任務停止共享 Git／服務操作；保留現有未提交內容，依領域審查。
- [x] 核對可靠性規格與失敗回復、重試、提示詞證據邊界；補齊無排程與排程保存失敗的 terminal 邊界。
- [x] 核對圖表及 CSP；現場四模式 QA 副本在 1280／375 寬度、像素、tooltip、缺資料及 CDN 中斷通過；正式 HTTP 新報告另外驗收。
- [x] 補齊啟動器 owner 驗證與重建腳本歷史保護、防不明回應重送；不實際刪除歷史報告。
- [x] 修正全套回歸揭露的契約／測試問題，完成隔離全套測試與獨立複審：264 檔，9438 passed／20 skipped／75 subtests passed；另啟用圖表瀏覽器 13 passed、正式路由設定 80 passed。
- [x] Scoped commit／push 並確認正式服務載入對應程式；程式 `c0ffa00f`，受控重啟與狀態保留驗證完成，合併紀錄以 [PR #14](https://github.com/aibalbo999/unstuck/pull/14) 為準。
- [x] 核對既有重建任務，按四模式驗收正式報告產物與品質狀態；四模式與舊失敗的 2308.TW／C 新任務已完成，警告完整保留。

## 邊界

測試使用隔離 runner，不操作正式 SQLite／Redis。保留 `.env`、密鑰、cache、output；舊測試不得把已核准的新版契約改回舊行為。正式報告的 job `done` 只表示生成流程完成，必須另看 conformance、content credibility、evidence 與 artifact；未通過要明列原因，不能假報驗收成功。

## 本輪正式驗收任務

同一既有追蹤股 `1623.TW`，透過正常 API 新建；`force=true`、`resume=false`，保留所有舊報告，不變更模型額度。

| 模式 | Job ID |
| --- | --- |
| D | `analysis-1623tw-v4-1788626177305-e90fd28f` |
| C | `analysis-1623tw-v3-1788626177390-19a6a74c` |
| B | `analysis-1623tw-v2-1788626177396-dee36721` |
| A | `analysis-1623tw-v1-1788626177401-43b63dfd` |

歷史盤點：原重建 manifest 的 28 個最新 Job ID，在正式 operational DB 為 27 `done`、1 `error`（2308.TW／C，核心資料不足）。後補 12 個 Job ID 全為 `done`；這些數字不等同內容品質通過，亦不應相加當成不重複 ticker／mode 數量。
