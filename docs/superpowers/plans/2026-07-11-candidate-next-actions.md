# 候選股票下一步操作 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將「進入候選清單」改成可直接查看股票快照、加入追蹤、或前往選擇分析模式的候選卡片，並確保任何動作都不會自動開始分析。

**Architecture:** 後端沿既有 daily decision dashboard 資料流保留候選的公司名稱與入選理由；前端 action mapper 建立 candidate 專用 view model，operator summary 只負責渲染與委派，`app_panels` callback 則重用既有 `StockSnapshotPanel` 與分析表單。不得新增另一套 watchlist 或 snapshot API，也不得使用 global event。

**Tech Stack:** Python 3.13、vanilla JavaScript、CSS、pytest、Node.js

---

## 實作前約束

- [ ] 先讀 `docs/superpowers/specs/2026-07-11-candidate-next-actions-design.md`，確認以下核准行為沒有被改寫：
  - 主要動作：`查看股票快照`
  - 次要動作：`加入追蹤`
  - 次要動作：`選擇分析模式`
  - `選擇分析模式` 只能預填、切頁、捲動與聚焦，不能自動開始分析。
- [ ] 執行 runtime doctor 與工作樹檢查：

  ```bash
  $(scripts/project_python.sh) scripts/doctor_runtime.py
  git status -sb
  ```

- [ ] 記錄以下檔案目前已有的使用者變更，不覆蓋、不還原：
  - `backend/daily_decision_dashboard.py`
  - `backend/daily_decision_queue.py`
  - `backend/static/operator_dashboard_actions.js`
  - `backend/static/operator_summary_panel.js`
  - `backend/static/app_panels.js`
  - `backend/static/styles/operator_summary.css`
  - `tests/test_daily_decision_dashboard.py`
  - `tests/test_daily_decision_queue.py`
  - `tests/test_static_history_filters.py`
- [ ] 本次不 stage、不 commit 正式程式碼；完成時只交付精確 diff 與測試證據，避免把大量既有 dirty/untracked 變更混入 commit。

## Task 1：後端保留候選名稱與真實理由

**Files:**

- Modify: `tests/test_daily_decision_dashboard.py`
- Modify: `tests/test_daily_decision_queue.py`
- Modify: `backend/daily_decision_dashboard.py`
- Modify: `backend/daily_decision_queue.py`

- [ ] 在 `tests/test_daily_decision_dashboard.py::test_daily_decision_dashboard_prioritizes_reruns_watchlist_and_free_mode` 先把通過品質閘門的候選 fixture 補成：

  ```python
  {
      "ticker": "2408.TW",
      "company_name": "南亞科",
      "score": 18680.0,
      "reason": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
      "quality_funnel": {"outcome": "pass"},
  }
  ```

- [ ] 加入精確斷言，證明 `top_candidates[0]` 保留使用者需要的內容，而非只剩 ticker/score：

  ```python
  candidate = dashboard["top_candidates"][0]
  assert candidate["ticker"] == "2408.TW"
  assert candidate["company_name"] == "南亞科"
  assert candidate["reason"] == "外資買超 15430 張、投信買超 3250 張、自營商 0 張"
  assert candidate["score"] == 18680.0
  ```

- [ ] 在 `tests/test_daily_decision_queue.py` 新增或擴充 candidate-specific 測試，輸入同一筆候選並斷言：

  ```python
  candidate_item = next(item for item in queue["items"] if item["type"] == "review_candidate")
  assert candidate_item == {
      "source": "screener",
      "type": "review_candidate",
      "priority_score": 420,
      "title": "2408.TW 南亞科",
      "detail": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
      "ticker": "2408.TW",
      "company_name": "南亞科",
      "reason": "外資買超 15430 張、投信買超 3250 張、自營商 0 張",
      "score": 18680.0,
  }
  ```

- [ ] 同一測試加入缺值退化案例：沒有 `company_name` 與 `reason` 時，title 仍有 ticker、detail 為 `市場掃描候選`，且三個前端動作所需的 ticker 不遺失。

- [ ] 執行 RED 測試，確認失敗原因正是欄位尚未保留與 detail 仍是 raw score：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_daily_decision_dashboard.py::test_daily_decision_dashboard_prioritizes_reruns_watchlist_and_free_mode \
    tests/test_daily_decision_queue.py -q
  ```

  Expected: 新增的 `company_name`、`reason` 或 candidate payload 斷言失敗；不得因 import、fixture typo 或既有無關錯誤而失敗。

- [ ] 在 `backend/daily_decision_dashboard.py::_top_candidates()` 的投影中加入：

  ```python
  "company_name": item.get("company_name") or "",
  ```

  保持既有 reject filtering、score 排序與最多五筆不變。

- [ ] 在 `backend/daily_decision_queue.py::_candidate_items()` 先正規化欄位，再建立 candidate item：

  ```python
  ticker = str(_field(candidate, "ticker") or "").strip()
  company_name = str(_field(candidate, "company_name") or "").strip()
  reason = str(_field(candidate, "reason") or "").strip()
  title = " ".join(value for value in (ticker, company_name) if value)
  ```

  Payload 必須保留 `ticker`、`company_name`、`reason`、`score`；`detail` 使用 `reason or "市場掃描候選"`。`priority_score` 仍供後端排序，但不能成為候選卡顯示內容。

- [ ] 執行 GREEN 測試：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_daily_decision_dashboard.py \
    tests/test_daily_decision_queue.py -q
  ```

  Expected: 全部通過。

## Task 2：建立 candidate 專用 action model 與三動作卡片

**Files:**

- Modify: `tests/test_static_history_filters.py`
- Modify: `backend/static/operator_dashboard_actions.js`
- Modify: `backend/static/operator_summary_panel.js`
- Modify: `backend/static/styles/operator_summary.css`

- [ ] 在 `tests/test_static_history_filters.py` 加入 Node behavior test，載入 `operator_dashboard_actions.js` 後傳入 `review_candidate`，斷言 mapping 結果：

  ```javascript
  {
    action: 'candidate-snapshot',
    label: '查看股票快照',
    type: 'review_candidate',
    ticker: '2408.TW',
    companyName: '南亞科',
    reason: '外資買超 15430 張、投信買超 3250 張、自營商 0 張',
    score: 18680.0
  }
  ```

  `detail` 可含真實理由與可讀來源名稱，但不得含 `score 18680.0` 或 `priority_score 420`，且 target 不得再是 `market-screener-panel`。

- [ ] 加入 operator summary renderer/behavior Node test。使用最小 mock DOM 觸發 `renderActions()` 與 action-list click，驗證 candidate HTML 具備：
  - `data-operator-action="candidate-snapshot"`
  - `data-operator-action="candidate-watchlist"`
  - `data-operator-action="candidate-prepare-analysis"`
  - 三個按鈕都有 `data-ticker="2408.TW"`
  - 顯示 `2408.TW`、`南亞科` 與真實理由
  - 三個 callback 各只被呼叫一次

- [ ] 加入缺少 ticker 的 behavior test：三個 candidate action 都不得呼叫 callback，必須呼叫 `notify.error('候選股票代號遺失，請重新整理後再試。')` 或等義固定訊息。

- [ ] 執行 RED 測試：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_static_history_filters.py -k 'candidate or operator_summary or daily_workbench' -q
  ```

  Expected: candidate mapping、三按鈕或 callback 斷言失敗。

- [ ] 修改 `backend/static/operator_dashboard_actions.js`：
  - 將 `review_candidate` 預設 mapping 改成 `['candidate-snapshot', '查看股票快照']`。
  - `mappedDashboardAction()` 額外保留 `type`、`companyName`、`reason`、`score`。
  - candidate 的 detail 只由 `reason/detail` 與可讀來源構成，不附加 `priority_score`。
  - 移除 `review_candidate -> market-screener-panel` 的 target mapping；其他 queue 類型維持原行為。

- [ ] 修改 `backend/static/operator_summary_panel.js`：
  - 保留現有 generic row renderer，新增只處理 `item.type === 'review_candidate'` 的 candidate renderer。
  - 一張 candidate card 只顯示一個主要按鈕 `查看股票快照`，以及兩個較低權重按鈕 `加入追蹤`、`選擇分析模式`。
  - 所有 candidate button 使用原生 `<button type="button">` 與同一筆 ticker。
  - `handleAction()` 對三個 candidate action 分別 await/delegate 到 `options.onCandidateSnapshot`、`options.onCandidateWatchlist`、`options.onCandidatePrepareAnalysis`。
  - candidate button 執行中 disabled 並顯示可讀 loading 文字，finally 恢復原標籤。
  - 缺少 ticker 時顯示 notify error，不能送出空 request。
  - 既有 rerun、watchlist、report、open-ops 行為不得改變。

- [ ] 修改 `backend/static/styles/operator_summary.css`，新增聚焦的 candidate class（命名可採 `.operator-candidate-card`、`.operator-candidate-actions`）：
  - primary CTA 全寬、視覺權重最高。
  - secondary CTA 兩欄排列，極窄/放大文字時允許自然換行。
  - 所有按鈕 `min-height: 44px`。
  - `:focus-visible` 有明確 outline；`:disabled` 有文字與視覺狀態。
  - 390px 不得產生水平 overflow。

- [ ] 加入 CSS contract 斷言，至少驗證 candidate class、`min-height: 44px`、focus-visible 與 mobile wrapping 規則存在。

- [ ] 執行 GREEN 測試：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_static_history_filters.py -k 'candidate or operator_summary or daily_workbench' -q
  ```

  Expected: 全部通過。

## Task 3：把三動作接回既有快照、追蹤與分析表單

**Files:**

- Modify: `tests/test_static_history_filters.py`
- Modify: `backend/static/app_panels.js`

- [ ] 先擴充 `test_app_panels_create_and_initialize_workspaces_without_app_entrypoint` 的 mock：
  - `StockAgentStockSnapshotPanel.create()` 回傳可記錄的 `load(ticker)` 與 `addToWatchlist(ticker)`。
  - `StockAgentOperatorSummaryPanel.create(options)` 保存並依序觸發三個 candidate callback。
  - `doc.getElementById('home-tab-analysis')` 可記錄 `.click()`。
  - `.pipeline-selector` 可記錄 `.scrollIntoView()`，其中 `input:checked` 可記錄 `.focus()`。
  - snapshot root 可記錄 `.scrollIntoView()`。
  - analyze button mock 可記錄 `.click()`，最後明確斷言從未被呼叫。

- [ ] 先執行 RED：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_static_history_filters.py::test_app_panels_create_and_initialize_workspaces_without_app_entrypoint -q
  ```

  Expected: operator summary 尚未收到 candidate callbacks。

- [ ] 修改 `backend/static/app_panels.js`，先建立 `stockSnapshotPanel`，再建立 `operatorSummary`，並注入三個 callback：

  ```javascript
  onCandidateSnapshot: async ticker => {
    byId(doc, 'home-tab-analysis')?.click();
    await stockSnapshotPanel.load(ticker);
    elements.stockSnapshotPanelEl?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  },
  onCandidateWatchlist: ticker => stockSnapshotPanel.addToWatchlist(ticker),
  onCandidatePrepareAnalysis: ticker => {
    if (elements.tickerInput) elements.tickerInput.value = ticker;
    byId(doc, 'home-tab-analysis')?.click();
    const selector = doc.querySelector?.('.pipeline-selector');
    selector?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    selector?.querySelector?.('input:checked')?.focus?.();
  }
  ```

  可依現有 lint/style 壓縮排版，但語意必須相同。不得呼叫 `analyzeBtn.click()`，不得直接呼叫分析 API。

- [ ] 確認 `onCandidateWatchlist` 只重用 `stockSnapshotPanel.addToWatchlist(ticker)`；該 helper 已負責目前 pipeline、idempotent save、toast 與 error handling，不得複製 `saveWatchlistItem()` payload。

- [ ] 確認 app panel module 仍符合既有限制：

  ```bash
  wc -l backend/static/app_panels.js \
    backend/static/operator_summary_panel.js \
    backend/static/operator_dashboard_actions.js
  ```

  Expected: 分別少於 130、105、90 行。若超限，先抽出 candidate render/helper 小模組並補 `index.html` script-order 與 module-size 測試，不能只提高限制。

- [ ] 執行 GREEN 與整個 static contract suite：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_static_history_filters.py::test_app_panels_create_and_initialize_workspaces_without_app_entrypoint \
    tests/test_static_history_filters.py -q
  ```

  Expected: 全部通過，且測試證明 prepare action 沒有觸發 analyze。

## Task 4：整合、runtime 與手機驗證

**Files:**

- Verify only: all files above
- Verify: running local app at `http://localhost:8080`

- [ ] 執行本功能的完整 targeted regression：

  ```bash
  $(scripts/project_python.sh) -m pytest \
    tests/test_daily_decision_dashboard.py \
    tests/test_daily_decision_queue.py \
    tests/test_static_history_filters.py \
    tests/test_frontend_http_e2e.py -q
  ```

- [ ] 執行全套測試：

  ```bash
  $(scripts/project_python.sh) -m pytest -q
  ```

  Expected: 不新增失敗；如遇既有失敗，必須先證明與本 diff 無關，不能略過。

- [ ] 以正式入口重啟 runtime，保留目前手機需要的 LAN 模式；若既有 tmux session 名稱為 `stock-agent`，沿用它，不另起第二份 uvicorn/worker：

  ```bash
  tmux kill-session -t stock-agent
  tmux new-session -d -s stock-agent 'cd /Users/balbomacmini/Desktop/onstock/stock-agent && LAN_ACCESS=1 ./start_mac.command'
  ```

  重啟前先用 `tmux ls`、`lsof -nP -iTCP:8080 -sTCP:LISTEN` 確認實際狀態；若 session 不存在，不把 `kill-session` 的非零狀態誤判為功能失敗。

- [ ] 驗證 runtime 真相：

  ```bash
  $(scripts/project_python.sh) scripts/doctor_runtime.py --json
  lsof -nP -iTCP:8080 -sTCP:LISTEN
  curl -fsS http://127.0.0.1:8080/api/ready
  ```

  Expected: 8080 綁定 `0.0.0.0`，API ready，worker 與正式路徑一致。

- [ ] 使用瀏覽器在桌機寬度與 390×844 各驗證一次：
  - 今日待處理卡顯示 `2408.TW`、`南亞科`、真實入選理由。
  - 不顯示 `score 18680.0`、`priority_score 420`。
  - 三個按鈕完整可見，無水平 overflow，實測高度至少 44px。
  - `查看股票快照` 切到分析頁、載入 2408.TW 快照並捲到快照區，不再前往空的市場掃描頁。
  - `選擇分析模式` 預填 2408.TW、捲到模式選擇區並聚焦目前選項；network/job 狀態證明沒有建立分析工作。
  - 用 Tab/Enter 驗證三按鈕可聚焦與啟動。

- [ ] Live QA 不點擊 `加入追蹤`，避免改動使用者正式 watchlist；以 Task 2/3 的 Node behavior test 證明它正確委派到既有 `addToWatchlist(ticker)`。若需要端到端 mutation，先取得使用者對該筆 watchlist 變更的明確授權。

- [ ] 最後檢查只包含預期差異：

  ```bash
  git diff -- \
    backend/daily_decision_dashboard.py \
    backend/daily_decision_queue.py \
    backend/static/operator_dashboard_actions.js \
    backend/static/operator_summary_panel.js \
    backend/static/app_panels.js \
    backend/static/styles/operator_summary.css \
    tests/test_daily_decision_dashboard.py \
    tests/test_daily_decision_queue.py \
    tests/test_static_history_filters.py
  ```

- [ ] 交付時列出：修改檔案、targeted/full test 結果、desktop/mobile QA 結果、LAN URL，以及「未在 live 點擊加入追蹤」的資料安全界線。
