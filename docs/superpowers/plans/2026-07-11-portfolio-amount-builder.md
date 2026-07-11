# 組合持股金額建立器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把組合快速建立器改成輸入新台幣金額，並自動衍生權重與 Cash。

**Architecture:** `portfolio_holdings.js` 負責 CSV 格式轉換、金額持股、Cash 與權重衍生；`portfolio_page.js` 只處理 DOM 與目前操作資金。既有組合風險 API 不變，因為輸出的 `market_value` CSV 已包含完整 Cash。

**Tech Stack:** 原生 ES modules、DOM API、Node.js、pytest、Playwright。

---

### Task 1: 金額持股純函式

**Files:**
- Modify: `backend/static/commercial/shared/portfolio_holdings.js`
- Modify: `tests/test_commercial_portfolio_holdings.py`

- [ ] **Step 1: 寫失敗測試**

以 500 萬資金把 `2330.TW 45%`、`Cash 55%` 轉成 market_value；加入 AAPL 60 萬後，2330 保持 225 萬、AAPL 為 60 萬、Cash 為 215 萬。測試更新 AAPL、移除 AAPL 回補 Cash，以及非 Cash 超過 500 萬時保留原文並回傳錯誤。

- [ ] **Step 2: 確認 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_commercial_portfolio_holdings.py -q`

Expected: FAIL，`upsertAmountHolding`、`removeAmountHolding`、`parseAmountHoldings` 尚未定義。

- [ ] **Step 3: 最小實作**

```js
const result = upsertAmountHolding(csvText, {
  ticker: 'AAPL',
  amount: 600000,
  capital: 5000000,
});
const rows = parseAmountHoldings(result.text, 5000000);
const removed = removeAmountHolding(result.text, 'AAPL', 5000000);
```

轉換後統一輸出 `market_value`，非 Cash 合計決定 Cash；錯誤時不得修改輸入文字。

- [ ] **Step 4: 確認 GREEN 並提交**

重跑 Step 2，Expected: PASS。

### Task 2: 金額型快速建立器介面

**Files:**
- Modify: `backend/static/commercial/portfolio-dashboard.html`
- Modify: `backend/static/commercial/pages/portfolio_page.js`
- Modify: `backend/static/commercial/styles/components.css`
- Modify: `tests/test_commercial_layout_pages.py`
- Modify: `tests/test_commercial_visual_optional.py`

- [ ] **Step 1: 寫失敗結構與瀏覽器測試**

要求 `portfolio-holding-amount`、`投入金額`、金額／權重持股標籤，且不存在 `portfolio-holding-weight`。在 500 萬設定加入 2887.TW NT$600,000，斷言標籤顯示 12%、CSV 使用 market_value、Cash 為 NT$4,400,000；更新與移除後同步。

- [ ] **Step 2: 確認 RED**

Run: `VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 $(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py tests/test_commercial_visual_optional.py -q`

Expected: FAIL，頁面仍使用權重輸入。

- [ ] **Step 3: 最小實作**

```html
<input id="portfolio-holding-amount" type="number" min="1" step="1" inputmode="numeric">
```

```js
const result = upsertAmountHolding(input.value, {
  ticker: holdingTicker.value,
  amount: holdingAmount.value,
  capital: activePolicy.capital,
});
```

持股列用 `formatTwd(amount)` 與衍生 `weight` 呈現；Cash 列不顯示移除按鈕。

- [ ] **Step 4: 確認 GREEN 並提交**

重跑 Step 2，Expected: PASS。

### Task 3: 文件與完整驗證

**Files:**
- Modify: `docs/operator-guide.md`
- Modify: `tests/test_commercial_docs.py`

- [ ] **Step 1: 更新文件與失敗測試**

```markdown
- 快速建立持股輸入新台幣金額，系統自動換算權重並把剩餘操作資金列為 Cash。
- 股票金額超過操作資金時不會修改組合。
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

Expected: JavaScript、金額純函式、瀏覽器互動、完整測試與 runtime doctor 全部成功。

- [ ] **Step 3: 精確提交**

只 stage 商業版金額建立器、測試與操作手冊對應段落；保留工作區其他修改。
