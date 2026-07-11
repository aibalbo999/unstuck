# 組合持股選擇器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在組合健檢頁加入可從三個既有來源選擇、更新與移除持股的操作器，同步使用現有 CSV 分析流程。

**Architecture:** 新 `ticker_options.js` 封裝三來源載入、正規化與去重，供單股與組合頁共用；新 `portfolio_holdings.js` 只處理 CSV 持股新增、更新、移除與解析。`portfolio_page.js` 負責 DOM 綁定與可見狀態，不新增後端 API。

**Tech Stack:** 原生 ES modules、DOM API、現有 FastAPI read APIs、Node.js、pytest、Playwright。

---

### Task 1: 共用股票選項與 CSV 持股純函式

**Files:**
- Create: `backend/static/commercial/shared/ticker_options.js`
- Create: `backend/static/commercial/shared/portfolio_holdings.js`
- Create: `tests/test_commercial_portfolio_holdings.py`
- Modify: `backend/static/commercial/pages/stock_page.js`

- [ ] **Step 1: 寫失敗測試**

測試 `upsertWeightHolding()` 能新增與更新 ticker、保留 sector/country 欄，`removeHolding()` 能刪除指定列，`parseWeightHoldings()` 回傳可見持股；只有 `market_value` 的 CSV 回傳明確錯誤。另由結構測試要求 `loadTickerChoices()` 同時包含三個 API。

- [ ] **Step 2: 確認 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_portfolio_holdings.py tests/test_commercial_layout_pages.py -q`

Expected: FAIL，兩個共用模組尚不存在。

- [ ] **Step 3: 最小實作**

`ticker_options.js` 匯出 `loadTickerChoices()`；`portfolio_holdings.js` 匯出 `upsertWeightHolding(text, holding)`、`removeHolding(text, ticker)`、`parseWeightHoldings(text)`。股票頁刪除自己的三來源合併邏輯，改用共用函式。

```js
const choices = await loadTickerChoices();
const update = upsertWeightHolding(csvText, { ticker: '2330.TW', weight: 25 });
const nextText = removeHolding(update.text, '2330.TW');
const visibleRows = parseWeightHoldings(nextText);
```

- [ ] **Step 4: 確認 GREEN 並提交**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_portfolio_holdings.py tests/test_commercial_layout_pages.py -q`

Expected: PASS。

### Task 2: 組合頁持股建立器

**Files:**
- Modify: `backend/static/commercial/portfolio-dashboard.html`
- Modify: `backend/static/commercial/pages/portfolio_page.js`
- Modify: `backend/static/commercial/styles/components.css`
- Modify: `backend/static/commercial/styles/responsive.css`
- Modify: `tests/test_commercial_layout_pages.py`
- Modify: `tests/test_commercial_visual_optional.py`

- [ ] **Step 1: 寫失敗結構與瀏覽器測試**

要求頁面包含 `portfolio-ticker-select`、`portfolio-holding-weight`、`portfolio-holding-add`、`portfolio-holding-list`；瀏覽器從追蹤／報告／常用來源選擇 ticker，加入後 CSV 出現一列，再次加入更新同一列，移除後該列消失。

- [ ] **Step 2: 確認 RED**

Run: `VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 $(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py tests/test_commercial_visual_optional.py -q`

Expected: FAIL，持股建立器尚不存在。

- [ ] **Step 3: 最小實作**

在 CSV 區上方加入選股、權重與加入按鈕，頁面載入共用選項並固定加入 `Cash`。加入、textarea input、檔案載入與移除後都呼叫 `renderHoldingDraft()`；錯誤寫入 `portfolio-holding-error`。

```html
<select id="portfolio-ticker-select"></select>
<input id="portfolio-holding-weight" type="number" min="0" max="100" step="0.1">
<button id="portfolio-holding-add" type="button">加入／更新持股</button>
<ul id="portfolio-holding-list" aria-live="polite"></ul>
```

```js
portfolioHoldingAdd.addEventListener('click', updateHoldingDraft);
portfolioCsv.addEventListener('input', renderHoldingDraft);
```

- [ ] **Step 4: 確認 GREEN 並提交**

重跑 Step 2，Expected: PASS。

### Task 3: 文件與完整驗證

**Files:**
- Modify: `docs/operator-guide.md`
- Modify: `tests/test_commercial_docs.py`

- [ ] **Step 1: 更新文件與失敗測試**

操作手冊說明持股可從三類來源選擇、輸入權重後加入／更新、可移除，以及 `market_value` CSV 仍需用檔案或文字編輯。

```markdown
- 持股可從追蹤股票、既有報告與常用股票清單選擇；輸入權重後可加入、更新或移除。
- `market_value` CSV 不會被持股選擇器改寫，請使用檔案匯入或文字編輯。
```

- [ ] **Step 2: 執行完整驗證**

Run:

```bash
for file in backend/static/commercial/shared/*.js backend/static/commercial/pages/*.js; do node --check "$file" || exit 1; done
VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 $(scripts/project_python.sh) -m pytest tests/test_commercial_portfolio_holdings.py tests/test_commercial_layout_pages.py tests/test_commercial_visual_optional.py tests/test_commercial_docs.py -q
$(scripts/project_python.sh) -m pytest -q
$(scripts/project_python.sh) scripts/doctor_runtime.py --json
git diff --check
```

Expected: JavaScript、聚焦測試、全專案測試、runtime doctor 與三頁 console 檢查全部成功。

- [ ] **Step 3: 精確提交**

只 stage 商業版、測試與操作手冊的持股選擇段落；保留 `responsive.css` 與 `docs/operator-guide.md` 的其他既有未提交修改。
