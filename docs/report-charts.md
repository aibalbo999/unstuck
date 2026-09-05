# 模式報告圖表

HTML 報告依 `reporting.mode_templates` 選擇圖表，資料由保存的 snapshot 提供。

| 模式 | 圖表配置 |
| --- | --- |
| A 研究 | 營收／淨利、利潤率、FCF、ROE、護城河、估值情境、P/E 河流圖 |
| B 實戰 | 近三個月股價、法人每日／分類買賣超，加上研究與估值圖表 |
| C 逆勢 | 近三個月股價、法人每日／分類買賣超、P/E 河流圖，加上法證財務趨勢 |
| D 事件波段 | 近一個月股價、法人每日／分類買賣超 |

`reporting.market_chart_context` 讀取 `price_history_ranges` 與 `institutional_trading`，按日期排序、過濾未來日期並保留缺值。沒有近月／近季序列時，才回退 `price_history`，標明「歷史股價（低頻資料）」。法人數值單位為千股，零買賣超是有效資料。來源、資料日期及股價調整口徑顯示在圖下。

沒有有效估值情境時，不會只以當前股價畫出情境比較。沒有有效數據的 canvas 顯示缺資料訊息；Chart.js 載入失敗則顯示連線提示。`data-chart-state` 為 `ready`、`empty` 或 `unavailable`，供自動檢查使用。

## 網頁安全設定

正式報告 API 只允許目前模板中固定圖表程式的 SHA-256 與指定版本的 Chart.js CDN 路徑。
雜湊來自受版本控制的模板，不從報告檔案中的任意腳本產生；未知或被修改的腳本仍被封鎖，
也不開放 inline 事件處理器或 `unsafe-eval`。模板程式變動後，舊 HTML 的腳本可能不符合雜湊，
需要重新呈現報告才能使用新版圖表。一般錯誤頁與沒有固定圖表程式的 HTML 維持禁止腳本。

## 驗證

一般報告回歸可執行 `tests/test_report_market_charts.py`、`tests/test_report_html_chart_context.py`、`tests/test_report_chart_modules.py`、`tests/test_report_mode_full_alignment.py`。

真實 Chart.js 瀏覽器測試需要 Playwright Chromium 與 CDN 連線；斷言失敗會使測試失敗，不會當成瀏覽器缺失而跳過：

```bash
VISUAL_REGRESSION_REQUIRED=1 "$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_report_chart_visual_optional.py tests/test_report_chart_security_policy.py \
  tests/test_qa_report_charts.py -q
```

以現有報告快照重建 QA 樣本並驗證 1280px／375px、有效數值、圖區像素、尺寸、提示框與 CDN 失敗狀態：

```bash
"$(scripts/project_python.sh)" scripts/qa_report_charts.py \
  --output-dir .gstack/qa/report-charts \
  <A報告檔名.html> <B報告檔名.html> <C報告檔名.html> <D報告檔名.html>
```

此工具透過 `ReportArtifactLocator` 找原始快照，輸出 HTML 副本、PNG 和 `results.json`。不呼叫模型、不刷新資料，也不覆寫原始報告或索引。歷史 HTML 是靜態產物，不會自動套用新模板；圖表正常不代表分析內容或資料可信度審核通過。

離線副本不會套用 API 的 HTTP 安全標頭，交付前仍需以正式 `/api/report/{filename}` 頁面驗證圖表；
`test_report_chart_security_policy.py` 的瀏覽器案例同時驗證正式安全標頭允許圖表、阻擋插入腳本。

QA 將全部缺值的 tooltip 標為不適用，第一組資料缺值時改找其他有效資料點；全零柱狀圖依零值幾何與實際座標軸像素驗證，不把零值當缺值，也不讓真正空白畫面通過。

2026-09-06 已以四份新生成報告完成正式 HTTP 的 1280／375 寬度驗收，詳見 [收尾驗收](remaining-analysis-delivery-2026-09-06.md)。
