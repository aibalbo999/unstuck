# 四模式 HTML 報告閱讀層

## 範圍與界線

`report_reader.html.j2` 是 A 長線研究、B 部位管理、C 下跌風險、D 短線觀察共用的閱讀層，
各模式仍保留自己的決策欄位與觀察期間。摘要、資料限制、圖表判讀與原始分析可分開閱讀。

- D 的交易方向 `Neutral` 顯示為「觀望（暫不建立新交易）」，不與持有、買入或避免直接換算。
- 研究評級的中性顯示為「觀望（研究尚未形成明確買賣傾向）」，不套用 D 的短線含義。
- 「不適用」用於明確不建立交易時的空白執行條件。
- 「尚未提供」用於缺少輸入、未設定來源或原報告未填欄位；原因未記錄時明說未記錄。
- 「尚未確認」用於估值、評分、事件日期或來源涵蓋尚未核實的情況，保留原有缺漏說明。
- 「來源異常」只依明確失敗狀態或限流、服務錯誤、逾時等紀錄判斷，並呈現保存的原因。
- 有效快取、單純查無公告、補充來源不完整，不自動當成抓取失敗。

上述規則同時處理摘要、看板、表格與舊 Markdown 的整段粗體欄位。
非交易語境的「市場情緒中性」不改寫。有效數字、部位 0%、事件日期與品質警示不補推或改判。
淺色介面使用深色文字與圖表標示；重繪既有圖表只調整顏色，不修改資料或座標範圍。

原文、來源引用與品質紀錄仍可展開查核。停用 JavaScript 時呈現原報告，
而非宣稱已套用新的白話顯示。CSP 只允許與固定閱讀程式完全相符的雜湊，
不信任報告內任意程式，也不放行行內事件處理器。

## 更新既有報告

請使用 `scripts/upgrade_report_readability.py`，不要手動拼接報告路徑或重跑分析。
先以實際 runtime 路徑盤點，清單與預覽均放在版本控制以外：

```bash
"$(scripts/project_python.sh)" scripts/upgrade_report_readability.py \
  --index backend/cache/stock_agent_cache.sqlite3 \
  --output backend/output \
  --manifest /tmp/onstock-reader-dry-run.json \
  --preview-dir /tmp/onstock-reader-preview
```

確認盤點、預覽與原始資料保全後，才套用同一份清單：

```bash
"$(scripts/project_python.sh)" scripts/upgrade_report_readability.py \
  --index backend/cache/stock_agent_cache.sqlite3 \
  --output backend/output \
  --prepared /tmp/onstock-reader-dry-run.json \
  --manifest /tmp/onstock-reader-applied.json \
  --apply
```

工具透過既有 artifact locator 支援月份／股票子目錄及 legacy 路徑。
套用前核對索引、HTML、sidecar 及預備清單的雜湊；並保留 HTML 修改時間。
只更新 HTML、其 sidecar 與索引的 `html_hash`，不修改 Markdown、資料快照、分析或品質欄位。
索引更新失敗時會恢復該檔 HTML、sidecar 與原修改時間。

閱讀區塊可移除，移除後須與原 HTML 逐位元組一致。
本工具不為資料缺口補值，也不將舊分析變成新預測。完整清單可能含報告內容與本機狀態，
不應將清單、報告原件、資料庫、環境設定或驗證截圖一併推送。

## 驗證

```bash
"$(scripts/project_python.sh)" tests/run_prompt_boundary_tests.py \
  tests/test_report_mode_templates.py \
  tests/test_report_reader.py \
  tests/test_report_reader_migration.py \
  tests/test_report_chart_security_policy.py -q
```

有 Playwright 的環境可執行離線模式／狀態與邊界測試：

```bash
node scripts/check_report_reader_browser.cjs
```

瀏覽器程式預設拒絕外部請求。預覽回放可用 `--preview-dir`、`--output-dir`、
`--chart-js` 指定預覽、證據目錄及本機固定版本 Chart.js；只有對應 Chart.js 網址會由本機檔案回覆。
`scripts/check_report_reader_inventory.cjs` 可使用盤點清單與預覽 CSP 逐份回放，不連正式資料庫或模型。

2026-10-18 本機套用結果：A 28、B 21、C 67、D 743，共 859 份。
859 份顯示重播通過；原 HTML 移除閱讀層後的雜湊與修改時間、1,719 個非 HTML 檔案，
以及索引中除 `html_hash` 外的欄位保持一致。四模式正式閱覽／下載共 8 個回應為 200，
並完成桌面、手機、列印與 CSP 注入防護檢查。這些是閱讀與保存完整性證據，
不是逐份重新核實投資結論；A 的護城河缺值圖仍維持缺資料提示，不補畫零分。

本次 Git 提交僅包含相關原始碼、工具、測試與本說明；本機報告遷移另行完成，
不重跑模型、不放寬品質檢查，也不包含其他未提交的來源或分析功能。
