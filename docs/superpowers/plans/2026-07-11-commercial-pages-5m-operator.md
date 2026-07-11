# 商業版 500 萬操作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將三個商業版頁面從極簡任務頁升級為適合管理新台幣 500 萬資金的中密度操作台，補回部位、風險、估值與組合金額資訊，同時避免舊版的無效控制。

**Architecture:** 保留三個網址與現有 API，新增一個純函式 `operator_policy.js`，集中 500 萬資金、現金、單一持股與單筆風險規則。三個 page module 各自把 API 資料映射成操作摘要、資料列與分頁；所有規則衍生值均標示為操作試算，不修改後端投資結論。

**Tech Stack:** FastAPI static files、原生 HTML/CSS/JavaScript ES modules、pytest、Node.js 純函式測試、Playwright live browser verification。

**Design spec:** `docs/superpowers/specs/2026-07-11-commercial-pages-5m-operator-design.md`

---

## File Structure

### Create

- `backend/static/commercial/shared/operator_policy.js`：500 萬操作規則、金額格式、部位試算與超額部位換算。
- `tests/test_commercial_operator_policy.py`：使用 Node 匯入純 ES module，驗證所有資金與風險計算。

### Modify

- `backend/static/commercial/research-workbench.html`：增加操作護欄、工作摘要、有效篩選與五筆資料列容器。
- `backend/static/commercial/pages/decision_page.js`：映射建議、價格、報酬、目標價差、信心與資料時效。
- `backend/static/commercial/stock-detail.html`：增加部位試算表單與五個證據分頁。
- `backend/static/commercial/pages/stock_page.js`：部位試算、估值、基本面、事件與技術映射。
- `backend/static/commercial/portfolio-dashboard.html`：增加資金摘要、部位表與四個組合分頁。
- `backend/static/commercial/pages/portfolio_page.js`：CSV 金額換算、護欄建議與排序資料列。
- `backend/static/commercial/styles/components.css`：政策條、資料表、狀態籤、試算卡與數字樣式。
- `backend/static/commercial/styles/responsive.css`：375/768/1280 中密度響應式規則。
- `tests/test_commercial_layout_pages.py`：三頁中密度結構與一個主要 CTA 契約。
- `tests/test_commercial_static_http.py`：新增 operator policy 靜態資產。
- `tests/test_commercial_visual_optional.py`：成功態、篩選、部位試算、組合金額與響應式驗證。
- `docs/operator-guide.md`：新增 500 萬操作護欄與三頁使用方式。

---

### Task 1: 建立 500 萬操作規則純函式

**Files:**
- Create: `backend/static/commercial/shared/operator_policy.js`
- Create: `tests/test_commercial_operator_policy.py`
- Modify: `tests/test_commercial_static_http.py`

- [ ] **Step 1: 寫入失敗的操作規則測試**

建立測試 helper，以 Node 匯入 module 並回傳 JSON：

```python
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "backend/static/commercial/shared/operator_policy.js").as_uri()


def run_policy(expression: str):
    script = f"""
      import * as policy from {json.dumps(MODULE)};
      process.stdout.write(JSON.stringify({{value: {expression}}}));
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["value"]


def test_policy_amounts_use_five_million_operator_guardrails():
    assert run_policy("policy.policyAmounts()") == {
        "capital": 5_000_000,
        "cashReserve": 1_000_000,
        "deployableCapital": 4_000_000,
        "maxPosition": 750_000,
        "maxTradeRisk": 50_000,
    }


def test_position_plan_respects_risk_and_position_caps():
    plan = run_policy(
        "policy.positionPlan({entryPrice: 100, stopPrice: 90, targetPrice: 125})"
    )
    assert plan["shares"] == 5_000
    assert plan["investment"] == 500_000
    assert plan["maxLoss"] == 50_000
    assert plan["targetGain"] == 125_000
    assert plan["riskReward"] == 2.5
    assert plan["binding"] == "risk"


def test_position_plan_uses_position_cap_and_rejects_invalid_prices():
    capped = run_policy(
        "policy.positionPlan({entryPrice: 100, stopPrice: 99, targetPrice: 110})"
    )
    assert capped["shares"] == 7_500
    assert capped["investment"] == 750_000
    assert capped["binding"] == "position"
    assert run_policy(
        "policy.positionPlan({entryPrice: 100, stopPrice: 100, targetPrice: 110})"
    ) is None
```

- [ ] **Step 2: 執行測試並確認 module 尚不存在**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_operator_policy.py -q
```

Expected: FAIL，Node 回報找不到 `operator_policy.js`。

- [ ] **Step 3: 實作操作規則 module**

建立：

```javascript
export const OPERATOR_POLICY = Object.freeze({
  capital: 5_000_000,
  cashReservePct: 20,
  maxPositionPct: 15,
  maxTradeRiskPct: 1,
});

const finite = value => Number.isFinite(Number(value)) ? Number(value) : null;

export function formatTwd(value) {
  const number = finite(value);
  if (number === null) return '資料不足';
  return new Intl.NumberFormat('zh-TW', {
    style: 'currency',
    currency: 'TWD',
    maximumFractionDigits: 0,
  }).format(number);
}

export function policyAmounts(policy = OPERATOR_POLICY) {
  const cashReserve = policy.capital * policy.cashReservePct / 100;
  return {
    capital: policy.capital,
    cashReserve,
    deployableCapital: policy.capital - cashReserve,
    maxPosition: policy.capital * policy.maxPositionPct / 100,
    maxTradeRisk: policy.capital * policy.maxTradeRiskPct / 100,
  };
}

export function amountForWeight(weightPct, capital = OPERATOR_POLICY.capital) {
  const weight = finite(weightPct);
  return weight === null ? null : capital * weight / 100;
}

export function positionPlan({ entryPrice, stopPrice, targetPrice, policy = OPERATOR_POLICY }) {
  const entry = finite(entryPrice);
  const stop = finite(stopPrice);
  const target = finite(targetPrice);
  if (entry === null || stop === null || entry <= 0 || stop < 0 || stop >= entry) return null;
  const amounts = policyAmounts(policy);
  const riskPerShare = entry - stop;
  const riskShares = Math.floor(amounts.maxTradeRisk / riskPerShare);
  const positionShares = Math.floor(amounts.maxPosition / entry);
  const shares = Math.max(0, Math.min(riskShares, positionShares));
  const investment = shares * entry;
  const maxLoss = shares * riskPerShare;
  const targetGain = target !== null && target > entry ? shares * (target - entry) : null;
  return {
    shares,
    investment,
    capitalPct: investment / policy.capital * 100,
    riskPerShare,
    maxLoss,
    targetGain,
    riskReward: targetGain === null || maxLoss <= 0 ? null : targetGain / maxLoss,
    binding: riskShares <= positionShares ? 'risk' : 'position',
  };
}

export function trimToPositionLimit(weightPct, policy = OPERATOR_POLICY) {
  const weight = finite(weightPct);
  if (weight === null || weight <= policy.maxPositionPct) return 0;
  return amountForWeight(weight - policy.maxPositionPct, policy.capital);
}
```

- [ ] **Step 4: 將資產加入 HTTP 契約並跑綠燈**

在 `tests/test_commercial_static_http.py` 的 assets tuple 加入：

```python
"/static/commercial/shared/operator_policy.js",
```

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_operator_policy.py \
  tests/test_commercial_static_http.py -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/static/commercial/shared/operator_policy.js \
  tests/test_commercial_operator_policy.py tests/test_commercial_static_http.py
git commit -m "feat: add five million operator policy"
```

---

### Task 2: 升級今日決策為五筆操作佇列

**Files:**
- Modify: `backend/static/commercial/research-workbench.html`
- Modify: `backend/static/commercial/pages/decision_page.js`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 增加失敗的頁面契約**

在 decision page 測試加入：

```python
for marker in (
    'id="decision-policy"',
    'id="decision-summary-metrics"',
    'id="decision-filters"',
    'data-filter="all"',
    'data-filter="rerun"',
    'data-filter="weak"',
):
    assert marker in html
for field in ("recommendation", "latestPrice", "returnPct", "targetGap", "confidence"):
    assert field in js
assert ".slice(0, 5)" in js
assert "renderFilteredTasks" in js
```

- [ ] **Step 2: 執行測試確認失敗**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py::test_decision_page_is_a_single_task_queue_without_demo_fallbacks -q
```

Expected: FAIL，缺少 `decision-policy`。

- [ ] **Step 3: 修改 HTML 結構**

在 page header 後加入 `commercial-policy-strip`，包含總資金、現金、單一上限、單筆風險；在答案卡加入 `decision-summary-metrics`；在工作清單前加入三個 `type="button"` filter，使用 `aria-pressed` 表示狀態。保留唯一 `.commercial-primary-action`。

- [ ] **Step 4: 實作五筆任務映射與篩選**

`mapItem()` 回傳：

```javascript
return {
  ticker,
  company,
  priority,
  reason,
  recommendation: tracking.recommendation || '資料不足',
  latestPrice: Number(tracking.latest_price),
  returnPct: Number(tracking.return_pct),
  targetGap: Number(tracking.target_12m_gap_pct),
  confidence: tracking.confidence || '資料不足',
  requiresRerun: Boolean(freshness.requires_rerun),
  refreshError: refreshStatus === 'error',
};
```

保留 `allTasks`，以 `.slice(0, 5)` 建立可見佇列；`renderFilteredTasks()` 根據 `activeFilter` 篩選並更新清單、件數與 `aria-pressed`。資料列用 `textContent` 產生，禁止 `innerHTML`。

- [ ] **Step 5: 執行契約與錯誤態測試**

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_commercial_visual_optional.py::test_decision_empty_and_api_error_states_never_render_sample_stocks -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/static/commercial/research-workbench.html \
  backend/static/commercial/pages/decision_page.js tests/test_commercial_layout_pages.py
git commit -m "feat: add operator detail to daily decisions"
```

---

### Task 3: 增加單股部位試算與五個證據分頁

**Files:**
- Modify: `backend/static/commercial/stock-detail.html`
- Modify: `backend/static/commercial/pages/stock_page.js`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 寫失敗契約**

要求 HTML 包含：

```python
for marker in (
    'id="stock-policy"',
    'id="stock-position-form"',
    'id="stock-entry-price"',
    'id="stock-stop-price"',
    'id="stock-position-metrics"',
):
    assert marker in html
for tab in ("plan", "valuation", "fundamentals", "events", "technical"):
    assert f'data-tab="{tab}"' in html
assert "positionPlan" in js
assert "renderPositionPlan" in js
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py::test_stock_page_has_one_snapshot_action_and_five_operator_tabs -q
```

Expected: FAIL，缺少部位試算表單。

- [ ] **Step 3: 修改 HTML**

保留股票更新 form 與唯一主要 CTA；在答案卡後加入 `stock-position-form`，包含數字型 entry/stop 輸入、規則說明與五個輸出欄。將四個 tabs 改為五個，預設 `plan`。

- [ ] **Step 4: 實作部位試算**

在快照成功後：

```javascript
const current = Number(data.quote?.price);
const sixMonthAverage = Number(data.technical_summary?.moving_averages?.ma_6m?.value);
entryInput.value = Number.isFinite(current) ? current.toFixed(2) : '';
stopInput.value = Number.isFinite(sixMonthAverage) && sixMonthAverage < current
  ? sixMonthAverage.toFixed(2)
  : (current * 0.92).toFixed(2);
renderPositionPlan();
```

`renderPositionPlan()` 呼叫 `positionPlan()`，以 `formatTwd()` 顯示投入、最大損失與目標潛在報酬；無效價格在 `role="alert"` 顯示「停損價必須低於進場價」。input 事件立即重算，不發網路請求。

若 ticker 不是 `.TW` / `.TWO`，停用兩個試算輸入並顯示「海外股票需要匯率才能換算 500 萬台幣部位」；不得直接用外幣股價計算新台幣部位。

- [ ] **Step 5: 實作五分頁資料映射**

`linesFor()` 或結構化 renderers 分別使用：

- plan：股數、資金占比、最大損失、風險報酬比。
- valuation：PE、Forward PE、PB、PS、目標價。
- fundamentals：營收成長、毛利率、營業利益率、ROE、FCF、現金/負債。
- events：事件日期與 days_until。
- technical：三條均線、52 週位置/回撤、三段動能。

- [ ] **Step 6: 執行測試**

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_operator_policy.py \
  tests/test_commercial_layout_pages.py \
  tests/test_stock_snapshot.py -q
```

Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/static/commercial/stock-detail.html \
  backend/static/commercial/pages/stock_page.js tests/test_commercial_layout_pages.py
git commit -m "feat: add stock position planning"
```

---

### Task 4: 將組合權重換成 500 萬實際金額

**Files:**
- Modify: `backend/static/commercial/portfolio-dashboard.html`
- Modify: `backend/static/commercial/pages/portfolio_page.js`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 寫失敗契約**

```python
for marker in (
    'id="portfolio-policy"',
    'id="portfolio-capital-metrics"',
    'id="portfolio-position-table"',
):
    assert marker in html
for tab in ("allocation", "exposure", "thesis", "actions"):
    assert f'data-tab="{tab}"' in html
assert "amountForWeight" in js
assert "trimToPositionLimit" in js
assert "renderPositionTable" in js
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py::test_portfolio_page_translates_risk_into_five_million_amounts -q
```

Expected: FAIL，缺少資金摘要。

- [ ] **Step 3: 修改 HTML**

將 CTA 文案改為 `分析 500 萬組合`；在答案卡內加入 `portfolio-capital-metrics`，並在 tabs 下加入可水平包覆但不造成頁面水平捲動的 table wrapper。分頁改成 allocation/exposure/thesis/actions 四個。

- [ ] **Step 4: 實作資金與調整金額**

對 API positions 使用：

```javascript
const amount = amountForWeight(position.weight_pct);
const trimAmount = trimToPositionLimit(position.weight_pct);
```

資金摘要顯示總資金、已配置、現金、最大部位與最大國家曝險。調整清單先處理超過 15% 的持股，文案為：

```javascript
`${ticker} 由 ${weight}% 降至 15%，減少 ${formatTwd(trimAmount)}`
```

若現金低於 20%，加入補足現金的金額；其後才使用 API 國家/產業風險與論點缺口。

- [ ] **Step 5: 執行測試**

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_operator_policy.py \
  tests/test_commercial_layout_pages.py \
  tests/test_portfolio_risk.py -q
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add backend/static/commercial/portfolio-dashboard.html \
  backend/static/commercial/pages/portfolio_page.js tests/test_commercial_layout_pages.py
git commit -m "feat: add portfolio capital allocation"
```

---

### Task 5: 建立中密度共用視覺層與響應式規則

**Files:**
- Modify: `backend/static/commercial/styles/components.css`
- Modify: `backend/static/commercial/styles/responsive.css`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 寫失敗 CSS 契約**

```python
for selector in (
    ".commercial-policy-strip",
    ".commercial-data-table",
    ".commercial-status-badge",
    ".commercial-position-planner",
    ".commercial-filter-bar",
):
    assert selector in components
assert "font-variant-numeric: tabular-nums" in components
assert "overflow-x: auto" in components
assert "@media (max-width: 760px)" in responsive
```

- [ ] **Step 2: 執行測試確認失敗**

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py -q
```

Expected: FAIL，缺少共用 selector。

- [ ] **Step 3: 實作 CSS**

以現有 semantic tokens 建立：四欄政策條、資料列/表格、狀態 badge、filter bar、position planner 與 sticky-free mobile table。桌面四欄、平板兩欄、手機單欄；table wrapper 可局部捲動但 `documentElement` 不可水平溢出。互動維持 44 px 與可見 focus ring。

- [ ] **Step 4: 執行靜態與響應式測試**

```bash
VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 \
  $(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_commercial_visual_optional.py::test_commercial_pages_keep_operator_flow_visible_and_responsive -q
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/static/commercial/styles/components.css \
  backend/static/commercial/styles/responsive.css tests/test_commercial_layout_pages.py
git commit -m "style: add operator dashboard density"
```

---

### Task 6: 完成真實瀏覽器流程、文件與快照

**Files:**
- Modify: `tests/test_commercial_visual_optional.py`
- Modify: `docs/operator-guide.md`
- Modify: `backend/static/commercial/research-workbench.png`
- Modify: `backend/static/commercial/stock-detail.png`
- Modify: `backend/static/commercial/portfolio-dashboard.png`

- [ ] **Step 1: 增加 live browser 行為測試**

在檔案頂端加入 `import json`，再新增：

```python
def test_five_million_operator_controls_have_visible_results():
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        decision_payload = {
            "items": [
                {
                    "ticker": "2330",
                    "company_name": "台積電",
                    "last_refresh_status": "success",
                    "latest_report": {
                        "ticker": "2330.TW",
                        "company_name": "台積電",
                        "decision_tracking": {
                            "recommendation": "買進",
                            "latest_price": 100,
                            "return_pct": 4.5,
                            "target_12m_gap_pct": 25,
                            "confidence": "8/10",
                        },
                        "decision_freshness": {"requires_rerun": True},
                    },
                },
                {
                    "ticker": "2308",
                    "company_name": "台達電",
                    "last_refresh_status": "success",
                    "latest_report": {
                        "ticker": "2308.TW",
                        "company_name": "台達電",
                        "decision_tracking": {
                            "recommendation": "持有",
                            "latest_price": 80,
                            "return_pct": -3,
                            "target_12m_gap_pct": 8,
                            "confidence": "6/10",
                        },
                        "decision_freshness": {"requires_rerun": False},
                    },
                },
            ]
        }
        page.route(
            "**/api/decision-tracking",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(decision_payload),
            ),
        )
        page.goto(f"{BASE_URL}/static/commercial/research-workbench.html", wait_until="networkidle")
        assert "NT$5,000,000" in page.locator("#decision-policy").inner_text()
        assert page.locator("#decision-task-list li").count() == 2
        page.get_by_role("button", name="需重跑").click()
        assert page.locator("#decision-task-list li").count() == 1
        assert "2330.TW" in page.locator("#decision-task-list").inner_text()

        stock_payload = {
            "ticker": "2330.TW",
            "identity": {"company_name": "台積電"},
            "quote": {"price": 100, "price_label": "NT$100", "as_of": "2026-07-11"},
            "valuation": {
                "pe_ratio": {"label": "20x"},
                "forward_pe": {"label": "18x"},
                "pb_ratio": {"label": "5x"},
                "ps_ratio": {"label": "8x"},
                "analyst_target": {"price": 125, "label": "NT$125", "upside_pct": 25},
            },
            "analyst_outlook": {
                "label": "目標價上行",
                "consensus": {"recommendation_label": "買進"},
                "signals": ["目標價上行 +25%"],
            },
            "technical_summary": {
                "moving_averages": {"ma_6m": {"value": 90}},
                "signals": ["現價高於 6M 均線"],
            },
            "financial_health": {},
            "profitability_quality": {"signals": []},
            "event_calendar": {"events": [], "next_event": {}},
            "data_quality": {"score": 90, "status": "fresh"},
        }
        page.route(
            "**/api/stocks/*/snapshot",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(stock_payload),
            ),
        )
        page.goto(f"{BASE_URL}/static/commercial/stock-detail.html?ticker=2330.TW", wait_until="networkidle")
        assert "NT$500,000" in page.locator("#stock-position-metrics").inner_text()
        page.locator("#stock-stop-price").fill("95")
        assert "NT$37,500" in page.locator("#stock-position-metrics").inner_text()

        portfolio_payload = {
            "total_positions": 3,
            "positions": [
                {"ticker": "2330.TW", "weight_pct": 22, "sector": "Semi", "country": "TW"},
                {"ticker": "AAPL", "weight_pct": 68, "sector": "Software", "country": "US"},
                {"ticker": "CASH", "weight_pct": 10, "sector": "Cash", "country": "TW"},
            ],
            "concentration": {
                "top_position": {"ticker": "AAPL", "weight_pct": 68},
                "sector_weights": {"Software": 68, "Semi": 22, "Cash": 10},
                "country_weights": {"US": 68, "TW": 32},
            },
            "thesis_health": {"invalidated": [], "missing": ["AAPL"]},
            "risk_flags": ["single_position_over_40_pct"],
        }
        page.route(
            "**/api/watchlist/portfolio/risk",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(portfolio_payload),
            ),
        )
        page.goto(f"{BASE_URL}/static/commercial/portfolio-dashboard.html", wait_until="networkidle")
        page.get_by_role("button", name="分析 500 萬組合").click()
        page.locator("#portfolio-capital-metrics").wait_for()
        assert "NT$5,000,000" in page.locator("#portfolio-capital-metrics").inner_text()
        assert "NT$350,000" in page.locator("#portfolio-position-table").inner_text()
        browser.close()
```

固定 route payload 避免外部行情波動；另在同一測試斷言頁面沒有 `fallback` 或 sample row。

- [ ] **Step 2: 執行 live 行為測試**

```bash
VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 \
  $(scripts/project_python.sh) -m pytest tests/test_commercial_visual_optional.py -q
```

Expected: PASS，三頁皆顯示 500 萬操作數字且互動結果可觀察。

- [ ] **Step 3: 更新操作手冊**

在 `Commercial Investment Workspace` 小節增加：

```markdown
### 500 萬操作護欄

- 預設現金保留 20%（NT$1,000,000）。
- 單一持股上限 15%（NT$750,000）。
- 單筆最大風險 1%（NT$50,000）。
- 單股部位與組合調整金額是操作規則試算，不是後端投資建議或下單指令。
```

- [ ] **Step 4: 用 8080 runtime 擷取三頁成功態**

在 1280 × 720 下等待 API 成功狀態，確認主要 CTA、操作護欄與第一個資料區可見後，覆寫三張 PNG。另以 375 × 812 與 768 × 900 檢查無頁面水平捲動。

- [ ] **Step 5: 執行完整驗證**

```bash
for file in backend/static/commercial/shared/*.js backend/static/commercial/pages/*.js; do
  node --check "$file" || exit 1
done

VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 \
  $(scripts/project_python.sh) -m pytest \
  tests/test_commercial_operator_policy.py \
  tests/test_commercial_layout_pages.py \
  tests/test_commercial_home_entry.py \
  tests/test_commercial_static_http.py \
  tests/test_commercial_visual_optional.py \
  tests/test_commercial_docs.py \
  tests/test_frontend_http_e2e.py \
  tests/test_stock_snapshot.py \
  tests/test_portfolio_risk.py \
  tests/test_decision_tracking_workflow.py -q

$(scripts/project_python.sh) -m pytest -q
$(scripts/project_python.sh) scripts/doctor_runtime.py --json
git diff --check
```

Expected: JavaScript syntax、聚焦測試、全專案測試與 runtime doctor 均成功；沒有商業版主控台 error/warning。

- [ ] **Step 6: Commit**

```bash
git add tests/test_commercial_visual_optional.py docs/operator-guide.md \
  backend/static/commercial/research-workbench.png \
  backend/static/commercial/stock-detail.png \
  backend/static/commercial/portfolio-dashboard.png
git commit -m "test: verify five million operator workflow"
```
