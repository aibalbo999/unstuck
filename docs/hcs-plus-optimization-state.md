# HCS Plus Optimization State

更新時間：2026-07-04

## 專案目標

優化本機股票研究系統的前端工作台與報告體驗，讓操作者能更快判斷：

- 要跑哪一種分析模式。
- 目前資料、模型、任務與歷史決策是否可信。
- 哪些報告、追蹤項目或警示需要立即處理。

成功標準：

- 前端主工作流在 desktop 與 mobile 均可掃讀。
- 資料視覺化元件不依賴過小字級或顏色單一編碼。
- 重要 UI 決策有測試或截圖證據支撐。
- 每次優化都可用專案既有測試驗證。

## 執行範圍註記

本次採 HCS 四大類別的批次式落地優化：批判、創意、溝通、互動各完成三輪，並做一次三習慣綜合收斂。這是可交付的系統優化批次；若要嚴格符合「每個 HCS 單項習慣逐一三輪」的完整巡迴，仍可在後續從本狀態表繼續展開。

## 專案內容

- FastAPI 本機服務與靜態前端：`backend/static/`
- HTML 報告模板：`backend/templates/`
- 報告與資料可信度渲染：`backend/reporting/`
- 前端合約測試：`tests/test_static_history_filters.py`
- 設計審查 artifact：`~/.gstack/projects/aibalbo999-unstuck/designs/design-audit-20260704-065346/`

## 限制條件

- 優先做小範圍、可逆、可測的修改。
- 避免改動資料流程、模型路由與後端管線，除非前端驗收需要。
- 不提交 API key、cache、output 或本機敏感檔案。
- 目前不做大型 redesign；先修正掃讀、對比、行動裝置與操作回饋。

## 決策紀錄

- D1：本輪以「前端工作台可讀性與可驗證品質」為主要優化目標。
- D2：採用 CSS-first 策略，只有必要時才改 JS 或模板。
- D3：每個 HCS 模式至少落一個專案變更，並補上測試或可檢查點。
- D4：首頁模式選擇應直接說明決策用途，而不是只列風格名稱或 Agent 數。
- D5：首頁副標採用使用者結果語言：「研究報告與決策追蹤工作台」。
- D6：模式切換要提供即時 intent 提示，降低使用者選錯分析模式的機率。
- D7：前端模式名稱、用途、CTA 與清單顯示以 `StockAgentUi.PIPELINE_META` 作為共用資料來源。
- D8：watchlist 與 market screener 顯示模式時優先呈現決策語意，不再只顯示 `V1/V2/V3/V4` 代碼。
- D9：新增 `docs/pipeline-mode-contract.md` 作為前端模式、後端 pipeline 與報告模板的對照契約。
- D10：前端設計檢查點納入模式契約，UI 調整需同時檢查報告模板語意。

## 未解問題

- 是否要建立正式 `DESIGN.md` 作為專案設計系統基準。
- 是否要把截圖式視覺回歸納入 CI。
- 是否要將首頁資訊架構拆成更明確的「分析工作台 / 監控工作台」兩層。
- 後端 `pipeline_modes.py` 與前端 `PIPELINE_META` 仍是兩份資料；目前只先收斂前端漂移。

## 優化進度

| 輪次 | 模式 | 狀態 | 已修改 |
|---|---|---|---|
| 1 | 批判思考 | 完成 | `docs/frontend-design-checkpoints.md`、本狀態表 |
| 1 | 創意思考 | 完成 | 首頁 pipeline 模式用途文案 |
| 1 | 溝通思考 | 完成 | 首頁副標 |
| 1 | 互動思考 | 完成 | pipeline intent 即時提示 |
| 2 | 批判思考 | 完成 | 前端 mode metadata 單一來源合約 |
| 2 | 創意思考 | 完成 | `pipelineChoices()` / `pipelineCtaLabel()` 共用 helper |
| 2 | 溝通思考 | 完成 | 歷史追蹤、filter、watchlist select 使用共用模式語意 |
| 2 | 互動思考 | 完成 | watchlist 清單顯示可讀模式名稱 |
| 3 | 批判思考 | 完成 | 前後端模式漂移風險文件化 |
| 3 | 創意思考 | 完成 | 低成本模式契約文件 |
| 3 | 溝通思考 | 完成 | 每種模式報告模板拆解 |
| 3 | 互動思考 | 完成 | 下一步與 watchlist/報告用途對照 |
| 綜合 | 可驗證性 + 溝通設計 + 系統圖像 | 完成 | 前端設計檢查點納入模式契約 |

## 第 1 輪摘要

已改善內容：

- 把設計審查從一次性截圖轉成 repo 內可追蹤檢查點。
- 把首頁模式選擇從「模式名稱 + Agent 數」推進到「決策用途 + Agent 數」。
- 把副標從內部技術語言改為使用者工作成果。
- 在模式切換時提供即時 intent 提示，讓操作者知道該模式適合什麼判斷。

已落地修改：

- `docs/hcs-plus-optimization-state.md`
- `docs/frontend-design-checkpoints.md`
- `backend/static/index.html`
- `backend/static/app.js`
- `backend/static/ui_helpers.js`
- `backend/static/styles/forms_controls.css`
- `tests/test_static_history_filters.py`

尚未解決的高風險問題：

- 目前模式 intent 只在首頁顯示，歷史報告、watchlist、market screener 的模式語意仍分散在不同 JS 檔案。
- 前端設計品質仍主要靠靜態合約與人工截圖，尚未形成正式視覺回歸流程。
- `DESIGN.md` 尚未建立，字級、密度、色彩與資料視覺化規則仍散落在 CSS 與測試中。

第 2 輪優先方向：

- 批判思考：檢查模式語意是否有多處來源，降低漂移風險。
- 創意思考：探索不大改架構的方式，讓 mode profile 成為前端共用資料。
- 溝通思考：改善歷史報告與 watchlist 的模式文案一致性。
- 互動思考：補強使用者從待處理項目進入正確下一步的回饋。

## 第 2 輪摘要

已改善內容：

- 將前端模式顯示資料收斂到 `StockAgentUi.PIPELINE_META`，新增 `pipelineChoices()` 與 `pipelineCtaLabel()`。
- 首頁 CTA、首頁模式選項、歷史報告 filter、market screener mode picker、watchlist select 與 watchlist 清單改用共用模式語意。
- 歷史追蹤卡不再維護自己的模式 label 表，降低後續模式命名漂移。
- watchlist 清單不再只顯示 `V1/V2/V3/V4`，改顯示「模式 A · 學術深度派」等可讀名稱。

已落地修改：

- `backend/static/ui_helpers.js`
- `backend/static/app.js`
- `backend/static/history_panel.js`
- `backend/static/market_screener_panel.js`
- `backend/static/watchlist_panel.js`
- `backend/static/ops_workspace.js`
- `backend/static/index.html`
- `tests/test_static_history_filters.py`

驗證證據：

- `tests/test_static_history_filters.py`：27 passed。
- 新增合約：`test_pipeline_mode_frontend_labels_share_single_metadata_source`。

尚未解決的高風險問題：

- 前後端模式定義尚未完全單一來源；後端仍由 `pipeline_modes.py` 定義 pipeline 行為。
- watchlist 顯示已改善，但從 operator action 直接進入正確下一步的引導仍可再強化。

第 3 輪優先方向：

- 批判思考：檢查前後端 pipeline 定義是否需要文件化同步規則。
- 創意思考：補一份低成本設計/模式契約文件，而不是大改架構。
- 溝通思考：讓報告模板與前端模式語意有可查對照。
- 互動思考：補強操作者從警示、待處理、重跑到下一步的行動提示。

## 第 3 輪摘要

已改善內容：

- 新增 `docs/pipeline-mode-contract.md`，把 `v1` 到 `v4` 的前端決策用途、後端模式、報告模板、摘要標題、決策標題、核心問題與下一步拆開。
- 將模式契約寫入 `docs/frontend-design-checkpoints.md`，讓 UI 修改時同時檢查模式語意與報告模板。
- 補上 `test_pipeline_mode_contract_documents_templates_and_decision_intents`，用後端 pipeline definition 與 report template profile 反向驗證文件內容。

已落地修改：

- `docs/pipeline-mode-contract.md`
- `docs/frontend-design-checkpoints.md`
- `docs/hcs-plus-optimization-state.md`
- `tests/test_report_mode_templates.py`

驗證證據：

- `tests/test_report_mode_templates.py`：4 passed。

尚未解決的高風險問題：

- 前端 `PIPELINE_META` 仍未由後端自動產生；目前透過測試與契約文件降低漂移。
- 尚未加入截圖式視覺回歸到 CI。

## 三習慣綜合優化

綜合視角：

- `#可驗證性`：每個模式的報告模板與決策用途必須有測試與文件可查。
- `#溝通設計`：操作者看到的是「該模式能幫我做什麼決策」，而不是內部 Agent 結構。
- `#系統圖像`：前端、後端 pipeline、報告模板、watchlist 與歷史追蹤共同構成一個決策系統，不能各自命名。

最終優化：

- 建立前端共用 mode metadata。
- 建立前後端模式契約文件。
- 把模式契約納入前端設計檢查點。
- 用靜態合約測試鎖定 UI、文件與報告模板。

驗收標準：

- 前端模式 label 與 CTA 由 `StockAgentUi.PIPELINE_META` 驅動。
- watchlist、market screener、歷史追蹤不再維護獨立模式語意表。
- `docs/pipeline-mode-contract.md` 必須包含每個模式的後端 label、short label、template id、summary heading、decision heading、core question 與決策用途。
- 相關測試需通過後才可視為本輪完成。

下一步：

- 若要進一步降低漂移，可把前端 mode metadata 改由後端輸出 JSON 或在 build/test 階段生成。
- 若要提升視覺可靠度，可把設計審查截圖或 Playwright 視覺回歸納入 CI。
