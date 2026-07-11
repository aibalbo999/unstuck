# 商業版操作設定與輸入選擇器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓三個商業版頁面共用可保存的資金／風險設定，並加入股票代號與持股 CSV 的明確選擇方式。

**Architecture:** `operator_policy.js` 保持純資料與計算邊界，新 `operator_policy_ui.js` 封裝 DOM 編輯器與 localStorage；頁面模組只接收設定變更並重新渲染。股票選單合併既有 API，CSV 檔案選擇只在瀏覽器讀取文字，後端 API 不變。

**Tech Stack:** 原生 ES modules、DOM API、localStorage、FastAPI 現有 read APIs、pytest、Node.js、Playwright。

---

### Task 1: 可驗證與保存的操作設定

**Files:**
- Modify: `tests/test_commercial_operator_policy.py`
- Modify: `backend/static/commercial/shared/operator_policy.js`

- [ ] **Step 1: 寫失敗測試**

新增測試，要求 `normalizeOperatorPolicy({capital: 10000000, cashReservePct: 25, maxPositionPct: 12, maxTradeRiskPct: 0.8})` 保留合法值，無效欄位回到 `OPERATOR_POLICY`，且 `policyAmounts(custom)` 產生 250 萬現金、120 萬單股上限與 8 萬風險。

- [ ] **Step 2: 確認 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_operator_policy.py -q`

Expected: FAIL，指出 `normalizeOperatorPolicy` 尚未定義。

- [ ] **Step 3: 最小實作**

在 `operator_policy.js` 增加 `POLICY_STORAGE_KEY`、`normalizeOperatorPolicy`、`readOperatorPolicy(storage)` 與 `writeOperatorPolicy(storage, policy)`；儲存函式接收 storage 物件，讓 Node 測試不依賴瀏覽器全域。

- [ ] **Step 4: 確認 GREEN**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_operator_policy.py -q`

Expected: PASS。

### Task 2: 三頁共用設定編輯器

**Files:**
- Create: `backend/static/commercial/shared/operator_policy_ui.js`
- Modify: `backend/static/commercial/research-workbench.html`
- Modify: `backend/static/commercial/stock-detail.html`
- Modify: `backend/static/commercial/portfolio-dashboard.html`
- Modify: `backend/static/commercial/styles/components.css`
- Modify: `backend/static/commercial/styles/responsive.css`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 寫失敗結構測試**

要求三頁都有 `data-operator-policy-editor`，共用模組包含「套用設定」與「恢復預設」，CSS 定義 `.commercial-policy-editor`，並移除固定 500 萬標題。

- [ ] **Step 2: 確認 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py -q`

Expected: FAIL，指出設定編輯器尚不存在。

- [ ] **Step 3: 最小實作**

建立共用 DOM 編輯器，包含四個 number input、次要套用按鈕、重設按鈕、錯誤與保存狀態。三頁只提供掛載節點；元件套用後回呼頁面模組。

- [ ] **Step 4: 確認 GREEN**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py -q`

Expected: PASS。

### Task 3: 三頁改用目前設定

**Files:**
- Modify: `backend/static/commercial/pages/decision_page.js`
- Modify: `backend/static/commercial/pages/stock_page.js`
- Modify: `backend/static/commercial/pages/portfolio_page.js`
- Modify: `tests/test_commercial_visual_optional.py`

- [ ] **Step 1: 寫失敗瀏覽器測試**

在固定 API route 下把操作資金改為 `10000000`、現金 `25`、單股 `12`、風險 `0.8`，斷言政策摘要為 NT$10,000,000／NT$2,500,000／NT$1,200,000／NT$80,000，單股與組合試算跟著改變，重新載入另一頁仍保留設定。

- [ ] **Step 2: 確認 RED**

Run: `VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 $(scripts/project_python.sh) -m pytest tests/test_commercial_visual_optional.py -q`

Expected: FAIL，固定政策沒有更新。

- [ ] **Step 3: 最小實作**

三頁初始化 `activePolicy = readOperatorPolicy(window.localStorage)`，掛載編輯器並在回呼中重畫政策、部位試算或組合結果；所有百分比比較與金額換算改用 `activePolicy`。

- [ ] **Step 4: 確認 GREEN**

重跑 Step 2，Expected: PASS。

### Task 4: 股票與 CSV 選擇器

**Files:**
- Modify: `backend/static/commercial/stock-detail.html`
- Modify: `backend/static/commercial/pages/stock_page.js`
- Modify: `backend/static/commercial/portfolio-dashboard.html`
- Modify: `backend/static/commercial/pages/portfolio_page.js`
- Modify: `tests/test_commercial_layout_pages.py`
- Modify: `tests/test_commercial_visual_optional.py`

- [ ] **Step 1: 寫失敗測試**

要求單股頁有 `stock-ticker-select`，頁面會請求 `/api/watchlist/symbols`、`/api/decision-tracking` 與 `/api/reports` 並去重；要求組合頁有 `portfolio-csv-file`、`.csv` accept 規則與檔名狀態。

- [ ] **Step 2: 確認 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py tests/test_commercial_visual_optional.py -q`

Expected: FAIL，兩個選擇器尚不存在。

- [ ] **Step 3: 最小實作**

股票 `<select>` 選取後填入既有手動輸入，不自動送出；CSV file input 用 `File.text()` 讀入 textarea，空檔、錯誤副檔名與讀取錯誤寫入現有 alert 節點。

- [ ] **Step 4: 確認 GREEN**

重跑 Step 2，Expected: PASS。

### Task 5: 文件、完整驗證與提交

**Files:**
- Modify: `docs/operator-guide.md`
- Modify: `tests/test_commercial_docs.py`

- [ ] **Step 1: 更新文件與測試**

操作手冊說明設定會保存在本機瀏覽器、股票可選可輸入、CSV 可選檔或貼上，以及 market_value 使用檔案實際總額。

- [ ] **Step 2: 執行驗證**

Run:

```bash
for file in backend/static/commercial/shared/*.js backend/static/commercial/pages/*.js; do node --check "$file" || exit 1; done
VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 $(scripts/project_python.sh) -m pytest tests/test_commercial_operator_policy.py tests/test_commercial_layout_pages.py tests/test_commercial_static_http.py tests/test_commercial_visual_optional.py tests/test_commercial_docs.py -q
$(scripts/project_python.sh) -m pytest -q
$(scripts/project_python.sh) scripts/doctor_runtime.py --json
git diff --check
```

Expected: JavaScript syntax、聚焦測試、全專案測試與 runtime doctor 全部成功。

- [ ] **Step 3: 精確提交**

只 stage 上列商業版、測試與文件區塊；`docs/operator-guide.md` 若含使用者既有修改，使用互動式 partial staging 保留其他差異。
