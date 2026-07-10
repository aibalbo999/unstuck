# 商業版三頁簡化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將商業版「今日決策、單股研究、組合健檢」重建為三個低複雜度、每頁單一主要 CTA、所有按鈕都有可驗證結果的任務頁面。

**Architecture:** 保留三個既有 URL 與三條 API，移除單一超大型 `commercial_pages.js` / `commercial_pages.css`，改成無建置步驟的 ES modules。共用 Module 只處理 API、非同步狀態、來源狀態與導覽；三個 page module 各自擁有資料映射與 DOM，不互相讀取頁面 state。

**Tech Stack:** FastAPI static files、原生 HTML/CSS/JavaScript ES modules、pytest、FastAPI TestClient、Playwright（optional live browser verification）。

**Design spec:** `docs/superpowers/specs/2026-07-11-commercial-pages-simplification-design.md`

---

## File Structure

### Create

- `backend/static/commercial/shared/api.js`：同源 JSON request、mutation token 與結構化錯誤。
- `backend/static/commercial/shared/async_state.js`：按鈕 loading/disabled 與 live-region 狀態。
- `backend/static/commercial/shared/shell.js`：ticker 正規化、跨頁 URL、三頁導覽與 tab 鍵盤操作。
- `backend/static/commercial/shared/source_status.js`：真實資料、空資料與錯誤狀態渲染。
- `backend/static/commercial/pages/decision_page.js`：今日決策清單、優先序與單股深連結。
- `backend/static/commercial/pages/stock_page.js`：股票快照載入、四個證據分頁與錯誤恢復。
- `backend/static/commercial/pages/portfolio_page.js`：CSV 驗證、風險 POST、健康度與三項建議。
- `backend/static/commercial/styles/tokens.css`：商業版 semantic tokens。
- `backend/static/commercial/styles/shell.css`：頁面框架、導覽與內容寬度。
- `backend/static/commercial/styles/components.css`：答案卡、證據卡、表單、CTA、tabs、status。
- `backend/static/commercial/styles/responsive.css`：375 / 768 / 1280 responsive rules。
- `tests/test_commercial_visual_optional.py`：live Playwright 密度、首屏、響應式與主要流程驗證。

### Replace

- `backend/static/commercial/research-workbench.html`：今日決策任務頁。
- `backend/static/commercial/stock-detail.html`：單股研究任務頁。
- `backend/static/commercial/portfolio-dashboard.html`：組合健檢任務頁。
- `tests/test_commercial_layout_pages.py`：以任務契約取代 14,000+ 行 selector inventory。

### Modify

- `backend/static/index.html`：商業版入口改為今日決策主入口與兩個次級入口。
- `backend/static/styles/history_shell_commercial.css`：首頁商業版 launchpad 降密度。
- `backend/static/styles/responsive.css`：首頁商業版入口 mobile layout。
- `tests/test_static_history_filters.py`：更新首頁商業版入口契約。
- `tests/test_frontend_http_e2e.py`：驗證新 static assets 可由 FastAPI 取得。
- `docs/operator-guide.md`：新增三頁使用流程與 Demo/真實資料界線。

### Delete after migration

- `backend/static/commercial/commercial_pages.js`
- `backend/static/commercial/commercial_pages.css`

四張既有 PNG 不先刪除；Task 8 會以新 runtime 截圖覆寫，避免文件或人工比較引用舊畫面。

---

### Task 1: 建立共用 API、狀態與頁面基礎

**Files:**
- Create: `backend/static/commercial/shared/api.js`
- Create: `backend/static/commercial/shared/async_state.js`
- Create: `backend/static/commercial/shared/shell.js`
- Create: `backend/static/commercial/shared/source_status.js`
- Create: `backend/static/commercial/styles/tokens.css`
- Create: `backend/static/commercial/styles/shell.css`
- Create: `backend/static/commercial/styles/components.css`
- Create: `backend/static/commercial/styles/responsive.css`
- Replace: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 將舊 selector inventory 測試替換為共用資產失敗契約**

用以下內容開始新的 `tests/test_commercial_layout_pages.py`：

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL_DIR = ROOT / "backend" / "static" / "commercial"


def read(relative: str) -> str:
    return (COMMERCIAL_DIR / relative).read_text(encoding="utf-8")


def test_commercial_shared_modules_define_request_state_and_navigation_contracts():
    api = read("shared/api.js")
    async_state = read("shared/async_state.js")
    shell = read("shared/shell.js")
    source_status = read("shared/source_status.js")

    assert "export class ApiError" in api
    assert "X-Mutation-Token" in api
    assert "export async function requestJson" in api
    assert "export function setAsyncState" in async_state
    assert "export function normalizeTicker" in shell
    assert "export function isValidTicker" in shell
    assert "export function stockPageHref" in shell
    assert "export function focusPageHeading" in shell
    assert "export function bindTabs" in shell
    assert "export function renderSourceStatus" in source_status


def test_commercial_styles_define_single_task_layout_and_responsive_contracts():
    tokens = read("styles/tokens.css")
    shell = read("styles/shell.css")
    components = read("styles/components.css")
    responsive = read("styles/responsive.css")

    assert "--commercial-primary" in tokens
    assert "width: min(100% - 32px, 1200px)" in shell
    assert ".commercial-primary-action" in components
    assert "min-height: 44px" in components
    assert "@media (max-width: 560px)" in responsive
    assert "grid-template-columns: 1fr" in responsive
```

- [ ] **Step 2: 執行測試並確認新檔案尚不存在**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py -q
```

Expected: FAIL，第一個錯誤為 `FileNotFoundError`，指出 `backend/static/commercial/shared/api.js` 不存在。

- [ ] **Step 3: 建立共用 API client**

建立 `backend/static/commercial/shared/api.js`：

```javascript
let clientConfigPromise;

export class ApiError extends Error {
  constructor(status, message, payload = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

async function clientConfig() {
  if (!clientConfigPromise) {
    clientConfigPromise = fetch('/api/client-config', { credentials: 'same-origin' })
      .then(response => response.ok ? response.json() : {});
  }
  return clientConfigPromise;
}

async function requestOptions(options = {}) {
  const next = { credentials: 'same-origin', ...options };
  const method = String(next.method || 'GET').toUpperCase();
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return next;
  const config = await clientConfig();
  const headers = new Headers(next.headers || {});
  const token = String(config.mutation_token || '');
  if (token) headers.set(config.mutation_header || 'X-Mutation-Token', token);
  next.headers = headers;
  return next;
}

export async function requestJson(url, options = {}) {
  const response = await fetch(url, await requestOptions(options));
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload.detail === 'string'
      ? payload.detail
      : `${response.status} ${response.statusText}`;
    throw new ApiError(response.status, detail, payload);
  }
  return payload;
}
```

- [ ] **Step 4: 建立非同步狀態與來源狀態 Module**

建立 `backend/static/commercial/shared/async_state.js`：

```javascript
export function setAsyncState(button, statusRoot, state, message) {
  const loading = state === 'loading';
  if (button) {
    if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent.trim();
    button.disabled = loading;
    button.setAttribute('aria-busy', loading ? 'true' : 'false');
    button.textContent = loading ? '載入中…' : button.dataset.idleLabel;
  }
  if (statusRoot) {
    statusRoot.dataset.state = state;
    statusRoot.textContent = message || '';
  }
}
```

建立 `backend/static/commercial/shared/source_status.js`：

```javascript
export function renderSourceStatus(root, { state, message, source = '', updatedAt = '' }) {
  if (!root) return;
  root.dataset.state = state;
  root.replaceChildren();
  const strong = document.createElement('strong');
  strong.textContent = message;
  const detail = document.createElement('span');
  detail.textContent = [source, updatedAt].filter(Boolean).join(' · ');
  root.append(strong, detail);
  root.setAttribute('role', state === 'error' ? 'alert' : 'status');
  root.setAttribute('aria-live', state === 'error' ? 'assertive' : 'polite');
}
```

- [ ] **Step 5: 建立導覽、ticker 與 tab Module**

建立 `backend/static/commercial/shared/shell.js`：

```javascript
export function normalizeTicker(value) {
  const ticker = String(value || '').trim().toUpperCase();
  if (/^\d{4}$/.test(ticker)) return `${ticker}.TW`;
  return ticker;
}

export function isValidTicker(value) {
  return /^(?:\d{4}\.(?:TW|TWO)|[A-Z][A-Z0-9.-]{0,9})$/.test(normalizeTicker(value));
}

export function stockPageHref(ticker, from = '') {
  const query = new URLSearchParams({ ticker: normalizeTicker(ticker) });
  if (from) query.set('from', from);
  return `/static/commercial/stock-detail.html?${query.toString()}`;
}

export function tickerFromLocation(fallback = '2330.TW') {
  return normalizeTicker(new URLSearchParams(window.location.search).get('ticker') || fallback);
}

export function focusPageHeading(id) {
  window.requestAnimationFrame(() => document.getElementById(id)?.focus({ preventScroll: true }));
}

export function bindTabs(tabList, onChange) {
  if (!tabList) return;
  const tabs = Array.from(tabList.querySelectorAll('[role="tab"]'));
  const activate = tab => {
    tabs.forEach(item => {
      const active = item === tab;
      item.setAttribute('aria-selected', active ? 'true' : 'false');
      item.tabIndex = active ? 0 : -1;
    });
    onChange(tab.dataset.tab);
  };
  tabList.addEventListener('click', event => {
    const tab = event.target.closest('[role="tab"]');
    if (tab) activate(tab);
  });
  tabList.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    const current = tabs.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    const next = tabs[(current + delta + tabs.length) % tabs.length];
    next.focus();
    activate(next);
  });
}
```

- [ ] **Step 6: 建立最小但完整的設計 tokens 與 layout CSS**

建立四個 CSS 檔，內容如下；不要引入舊 `commercial_pages.css`：

```css
/* styles/tokens.css */
:root {
  --commercial-bg: #08111d;
  --commercial-surface: #101b2a;
  --commercial-surface-strong: #162437;
  --commercial-border: #2b3b50;
  --commercial-text: #edf4fb;
  --commercial-muted: #9bacc0;
  --commercial-primary: #2dd4bf;
  --commercial-primary-ink: #042f2e;
  --commercial-warning: #f4b860;
  --commercial-danger: #fb7185;
  --commercial-radius: 12px;
}

/* styles/shell.css */
* { box-sizing: border-box; }
body { margin: 0; background: var(--commercial-bg); color: var(--commercial-text); font: 16px/1.5 system-ui, sans-serif; }
a { color: inherit; }
.commercial-topbar { position: sticky; top: 0; z-index: 10; display: flex; justify-content: space-between; gap: 24px; padding: 14px 24px; background: rgba(8, 17, 29, .96); border-bottom: 1px solid var(--commercial-border); }
.commercial-brand { text-decoration: none; font-weight: 750; }
.commercial-nav { display: flex; gap: 8px; }
.commercial-nav a { min-height: 44px; display: inline-flex; align-items: center; padding: 0 14px; border-radius: 9px; text-decoration: none; color: var(--commercial-muted); }
.commercial-nav a[aria-current="page"] { color: var(--commercial-text); background: var(--commercial-surface-strong); }
.commercial-page { width: min(100% - 32px, 1200px); margin: 0 auto; padding: 40px 0 72px; }
.commercial-page-header { margin-bottom: 24px; }
.commercial-page-header h1 { margin: 4px 0 6px; font-size: clamp(1.8rem, 4vw, 2.8rem); }

/* styles/components.css */
button, input, textarea { font: inherit; }
button, .commercial-primary-action, .commercial-secondary-action { min-height: 44px; }
.commercial-answer, .commercial-panel { padding: 22px; border: 1px solid var(--commercial-border); border-radius: var(--commercial-radius); background: var(--commercial-surface); }
.commercial-answer h2 { margin: 4px 0 8px; font-size: clamp(1.4rem, 3vw, 2.1rem); }
.commercial-eyebrow, .commercial-muted { color: var(--commercial-muted); }
.commercial-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.commercial-metric { padding: 14px; border: 1px solid var(--commercial-border); border-radius: 10px; }
.commercial-metric span, .commercial-source-status span { display: block; color: var(--commercial-muted); }
.commercial-primary-action { display: inline-flex; align-items: center; justify-content: center; padding: 0 18px; border: 0; border-radius: 9px; background: var(--commercial-primary); color: var(--commercial-primary-ink); font-weight: 750; text-decoration: none; cursor: pointer; }
.commercial-primary-action:disabled { cursor: wait; opacity: .58; }
.commercial-secondary-action { display: inline-flex; align-items: center; padding: 0 14px; border: 1px solid var(--commercial-border); border-radius: 9px; background: transparent; color: var(--commercial-text); }
.commercial-task-list, .commercial-recommendations { display: grid; gap: 10px; padding: 0; list-style: none; }
.commercial-task-link { display: grid; gap: 3px; padding: 14px; border: 1px solid var(--commercial-border); border-radius: 10px; text-decoration: none; }
.commercial-tabs { display: flex; gap: 6px; margin: 22px 0 12px; }
.commercial-tabs button { padding: 0 14px; border: 1px solid var(--commercial-border); border-radius: 9px; background: transparent; color: var(--commercial-muted); }
.commercial-tabs button[aria-selected="true"] { color: var(--commercial-text); border-color: var(--commercial-primary); }
.commercial-source-status { margin-top: 16px; padding: 12px 14px; border-left: 3px solid var(--commercial-primary); background: var(--commercial-surface); }
.commercial-source-status[data-state="error"] { border-color: var(--commercial-danger); }
.commercial-field { display: grid; gap: 6px; margin-bottom: 14px; }
.commercial-field input, .commercial-field textarea { width: 100%; min-height: 44px; padding: 10px 12px; color: var(--commercial-text); background: var(--commercial-bg); border: 1px solid var(--commercial-border); border-radius: 9px; }
.commercial-field textarea { min-height: 150px; resize: vertical; }
:focus-visible { outline: 3px solid color-mix(in srgb, var(--commercial-primary) 70%, white); outline-offset: 3px; }

/* styles/responsive.css */
@media (max-width: 768px) {
  .commercial-topbar { align-items: flex-start; flex-direction: column; gap: 8px; padding: 10px 16px; }
  .commercial-nav { width: 100%; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .commercial-nav a { justify-content: center; padding: 0 8px; text-align: center; }
  .commercial-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 560px) {
  .commercial-page { width: min(100% - 24px, 1200px); padding-top: 24px; }
  .commercial-metrics { grid-template-columns: 1fr; }
  .commercial-answer, .commercial-panel { padding: 16px; }
  .commercial-primary-action { width: 100%; }
}
```

- [ ] **Step 7: 執行共用契約測試**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py -q
```

Expected: `2 passed`。

- [ ] **Step 8: 提交共用基礎**

```bash
git add backend/static/commercial/shared backend/static/commercial/styles tests/test_commercial_layout_pages.py
git commit -m "refactor: establish commercial page foundations"
```

---

### Task 2: 重建今日決策頁

**Files:**
- Replace: `backend/static/commercial/research-workbench.html`
- Create: `backend/static/commercial/pages/decision_page.js`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 新增今日決策失敗契約**

在 `tests/test_commercial_layout_pages.py` 追加：

```python
def test_decision_page_is_a_single_task_queue_without_demo_fallbacks():
    html = read("research-workbench.html")
    js = read("pages/decision_page.js")

    assert 'data-commercial-page="decision"' in html
    assert '<h1 id="decision-title">今日決策</h1>' in html
    assert html.count("commercial-primary-action") == 1
    assert 'id="decision-task-list"' in html
    assert 'type="module" src="/static/commercial/pages/decision_page.js' in html
    assert "/api/decision-tracking" in js
    assert "stockPageHref" in js
    assert "fallbackTickers" not in js
    assert "localStorage" not in js
```

- [ ] **Step 2: 執行測試並確認仍載入舊 bundle**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py::test_decision_page_is_a_single_task_queue_without_demo_fallbacks -q
```

Expected: FAIL，缺少 `data-commercial-page="decision"` 或 `pages/decision_page.js`。

- [ ] **Step 3: 以單一任務 HTML 取代研究工作台**

`backend/static/commercial/research-workbench.html` 使用以下完整結構：

```html
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OnStock 今日決策</title>
  <link rel="stylesheet" href="/static/commercial/styles/tokens.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/shell.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/components.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/responsive.css?v=20260711-simple">
</head>
<body data-commercial-page="decision">
  <header class="commercial-topbar">
    <a class="commercial-brand" href="/" aria-label="回到主頁">OnStock AI</a>
    <nav class="commercial-nav" aria-label="商業版投資工作區">
      <a href="/static/commercial/research-workbench.html" aria-current="page">今日決策</a>
      <a href="/static/commercial/stock-detail.html">單股研究</a>
      <a href="/static/commercial/portfolio-dashboard.html">組合健檢</a>
    </nav>
  </header>
  <main class="commercial-page">
    <header class="commercial-page-header">
      <span class="commercial-eyebrow">每日投資流程</span>
      <h1 id="decision-title" tabindex="-1">今日決策</h1>
      <p class="commercial-muted">先處理風險、過期資料與需重跑的股票。</p>
    </header>
    <section class="commercial-answer" aria-labelledby="decision-answer-title">
      <span class="commercial-eyebrow">今天最重要</span>
      <h2 id="decision-answer-title">正在整理待處理項目…</h2>
      <p id="decision-answer-detail" class="commercial-muted"></p>
      <ul id="decision-task-list" class="commercial-task-list" aria-label="今日待處理股票"></ul>
      <a id="decision-primary" class="commercial-primary-action" href="/static/commercial/stock-detail.html" hidden>開始檢查</a>
      <a id="decision-empty-action" class="commercial-secondary-action" href="/#home-tab-tracking" hidden>設定追蹤股票</a>
    </section>
    <section id="decision-source-status" class="commercial-source-status" aria-live="polite"></section>
  </main>
  <script type="module" src="/static/commercial/pages/decision_page.js?v=20260711-simple"></script>
</body>
</html>
```

- [ ] **Step 4: 實作真實清單、優先序與深連結**

建立 `backend/static/commercial/pages/decision_page.js`：

```javascript
import { requestJson } from '../shared/api.js';
import { focusPageHeading, stockPageHref } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const title = document.getElementById('decision-answer-title');
const detail = document.getElementById('decision-answer-detail');
const list = document.getElementById('decision-task-list');
const primary = document.getElementById('decision-primary');
const emptyAction = document.getElementById('decision-empty-action');
const statusRoot = document.getElementById('decision-source-status');

function mapItem(item) {
  const report = item.latest_report || (item.latest_reports || [])[0] || {};
  const tracking = report.decision_tracking || {};
  const freshness = report.decision_freshness || {};
  const refreshStatus = String(item.last_refresh_status || '');
  const returnPct = Number(tracking.return_pct);
  let priority = 10;
  let reason = '例行檢查';
  if (freshness.requires_rerun) { priority = 40; reason = '報告需要重跑'; }
  else if (refreshStatus === 'error') { priority = 30; reason = '資料更新失敗'; }
  else if (Number.isFinite(returnPct) && returnPct < 0) { priority = 20; reason = '報酬轉弱，檢查原論點'; }
  return {
    ticker: String(report.ticker || item.ticker || '').toUpperCase(),
    company: report.company_name || item.company_name || '',
    priority,
    reason,
  };
}

function taskLink(task) {
  const link = document.createElement('a');
  link.className = 'commercial-task-link';
  link.href = stockPageHref(task.ticker, 'decision');
  const ticker = document.createElement('strong');
  ticker.textContent = [task.ticker, task.company].filter(Boolean).join(' · ');
  const reason = document.createElement('span');
  reason.textContent = task.reason;
  link.append(ticker, reason);
  return link;
}

async function loadDecisionQueue() {
  renderSourceStatus(statusRoot, { state: 'loading', message: '正在讀取追蹤清單' });
  try {
    const payload = await requestJson('/api/decision-tracking');
    const allTasks = (payload.items || []).map(mapItem).filter(item => item.ticker)
      .sort((left, right) => right.priority - left.priority);
    const tasks = allTasks.slice(0, 3);
    list.replaceChildren(...tasks.map(taskLink));
    if (!tasks.length) {
      title.textContent = '尚無追蹤股票';
      detail.textContent = '先建立追蹤清單，系統才會整理每日待辦。';
      primary.hidden = true;
      emptyAction.hidden = false;
    } else {
      title.textContent = `今天有 ${allTasks.length} 件事要處理`;
      detail.textContent = '依需重跑、更新錯誤與報酬轉弱排序。';
      primary.href = stockPageHref(tasks[0].ticker, 'decision');
      primary.textContent = `開始檢查 ${tasks[0].ticker}`;
      primary.hidden = false;
      emptyAction.hidden = true;
    }
    renderSourceStatus(statusRoot, { state: 'success', message: '追蹤清單已更新', source: 'Decision Tracking API' });
  } catch (error) {
    title.textContent = '目前無法讀取今日決策';
    detail.textContent = '請確認服務狀態後重新整理頁面。';
    list.replaceChildren();
    primary.hidden = true;
    emptyAction.hidden = true;
    renderSourceStatus(statusRoot, { state: 'error', message: error.message, source: 'Decision Tracking API' });
  }
}

focusPageHeading('decision-title');
loadDecisionQueue();
```

- [ ] **Step 5: 執行今日決策契約與 HTTP static smoke**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_frontend_http_e2e.py::test_frontend_shell_static_assets_and_report_history_flow \
  -q
```

Expected: 所選測試全部 PASS。

- [ ] **Step 6: 提交今日決策垂直切片**

```bash
git add backend/static/commercial/research-workbench.html backend/static/commercial/pages/decision_page.js tests/test_commercial_layout_pages.py
git commit -m "feat: simplify commercial decision queue"
```

---

### Task 3: 重建單股研究頁

**Files:**
- Replace: `backend/static/commercial/stock-detail.html`
- Create: `backend/static/commercial/pages/stock_page.js`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 新增單股頁失敗契約**

追加：

```python
def test_stock_page_has_one_snapshot_action_and_four_evidence_tabs():
    html = read("stock-detail.html")
    js = read("pages/stock_page.js")

    assert 'data-commercial-page="stock"' in html
    assert html.count("commercial-primary-action") == 1
    assert [f'data-tab="{name}"' in html for name in ("answer", "fundamentals", "events", "technical")] == [True] * 4
    assert "/api/stocks/" in js and "/snapshot" in js
    assert "bindTabs" in js
    assert "fallbackTickers" not in js
    assert "fallbackSnapshot" not in js
```

- [ ] **Step 2: 執行測試並確認舊八分頁結構失敗**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py::test_stock_page_has_one_snapshot_action_and_four_evidence_tabs -q
```

Expected: FAIL，因 HTML 仍包含舊 `commercial_pages.js` 或缺少 `pages/stock_page.js`。

- [ ] **Step 3: 以四證據分頁 HTML 取代單股頁**

以以下完整 HTML 取代 `backend/static/commercial/stock-detail.html`：

```html
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OnStock 單股研究</title>
  <link rel="stylesheet" href="/static/commercial/styles/tokens.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/shell.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/components.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/responsive.css?v=20260711-simple">
</head>
<body data-commercial-page="stock">
<header class="commercial-topbar">
  <a class="commercial-brand" href="/" aria-label="回到主頁">OnStock AI</a>
  <nav class="commercial-nav" aria-label="商業版投資工作區">
    <a href="/static/commercial/research-workbench.html">今日決策</a>
    <a href="/static/commercial/stock-detail.html" aria-current="page">單股研究</a>
    <a href="/static/commercial/portfolio-dashboard.html">組合健檢</a>
  </nav>
</header>
<main class="commercial-page">
  <header class="commercial-page-header">
    <span class="commercial-eyebrow">股票快照</span>
    <h1 id="stock-title" tabindex="-1">單股研究</h1>
  </header>
  <form id="stock-form" class="commercial-panel">
    <label class="commercial-field" for="stock-ticker"><span>股票代號</span><input id="stock-ticker" name="ticker" autocomplete="off" required></label>
    <button id="stock-load" class="commercial-primary-action" type="submit">更新股票快照</button>
  </form>
  <section class="commercial-answer" aria-labelledby="stock-answer-title">
    <span id="stock-company" class="commercial-eyebrow"></span>
    <h2 id="stock-answer-title">輸入股票代號以載入快照</h2>
    <p id="stock-answer-detail" class="commercial-muted"></p>
    <div id="stock-metrics" class="commercial-metrics"></div>
  </section>
  <div id="stock-tabs" class="commercial-tabs" role="tablist" aria-label="股票研究證據">
    <button type="button" role="tab" aria-selected="true" data-tab="answer">結論</button>
    <button type="button" role="tab" aria-selected="false" tabindex="-1" data-tab="fundamentals">基本面</button>
    <button type="button" role="tab" aria-selected="false" tabindex="-1" data-tab="events">事件</button>
    <button type="button" role="tab" aria-selected="false" tabindex="-1" data-tab="technical">技術</button>
  </div>
  <section id="stock-evidence" class="commercial-panel" aria-live="polite"></section>
  <section id="stock-source-status" class="commercial-source-status" aria-live="polite"></section>
</main>
<script type="module" src="/static/commercial/pages/stock_page.js?v=20260711-simple"></script>
</body>
</html>
```

- [ ] **Step 4: 實作股票快照與四種證據映射**

建立 `pages/stock_page.js`。核心必須使用 API 已存在的 keys，不能猜測報告欄位：

```javascript
import { requestJson } from '../shared/api.js';
import { setAsyncState } from '../shared/async_state.js';
import { bindTabs, focusPageHeading, isValidTicker, normalizeTicker, tickerFromLocation } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const form = document.getElementById('stock-form');
const input = document.getElementById('stock-ticker');
const button = document.getElementById('stock-load');
const company = document.getElementById('stock-company');
const answer = document.getElementById('stock-answer-title');
const detail = document.getElementById('stock-answer-detail');
const metrics = document.getElementById('stock-metrics');
const evidence = document.getElementById('stock-evidence');
const statusRoot = document.getElementById('stock-source-status');
let snapshot = null;
let activeTab = 'answer';

function label(value, fallback = '資料不足') {
  return value === null || value === undefined || value === '' ? fallback : String(value);
}

function metric(name, value) {
  const root = document.createElement('div');
  root.className = 'commercial-metric';
  const key = document.createElement('span'); key.textContent = name;
  const strong = document.createElement('strong'); strong.textContent = label(value);
  root.append(key, strong);
  return root;
}

function renderSummary(data) {
  const recommendation = data.analyst_outlook?.consensus?.recommendation_label || '資料不足';
  const upside = data.valuation?.analyst_target?.upside_pct;
  const nextEvent = data.event_calendar?.next_event || {};
  company.textContent = [data.ticker, data.identity?.company_name].filter(Boolean).join(' · ');
  answer.textContent = data.analyst_outlook?.label || `共識${recommendation}`;
  detail.textContent = (data.analyst_outlook?.signals || []).join(' · ') || '目前證據不足，請查看來源狀態。';
  metrics.replaceChildren(
    metric('現價', data.quote?.price_label),
    metric('共識', recommendation),
    metric('目標空間', Number.isFinite(upside) ? `${upside > 0 ? '+' : ''}${upside.toFixed(1)}%` : null),
    metric('下一事件', nextEvent.label || nextEvent.date),
  );
}

function linesFor(tab, data) {
  if (tab === 'fundamentals') return [
    data.profitability_quality?.label,
    ...(data.profitability_quality?.signals || []),
    data.financial_health?.label,
  ];
  if (tab === 'events') return (data.event_calendar?.events || []).map(item => [item.label, item.date].filter(Boolean).join(' · '));
  if (tab === 'technical') return [data.technical_summary?.label, ...(data.technical_summary?.signals || [])];
  return [data.analyst_outlook?.label, ...(data.analyst_outlook?.signals || []), data.data_quality?.status && `資料狀態：${data.data_quality.status}`];
}

function renderEvidence() {
  const lines = snapshot ? linesFor(activeTab, snapshot).filter(Boolean).slice(0, 6) : [];
  const list = document.createElement('ul');
  list.className = 'commercial-recommendations';
  lines.forEach(text => { const item = document.createElement('li'); item.textContent = text; list.append(item); });
  evidence.replaceChildren(list);
}

async function loadSnapshot(ticker) {
  const normalized = normalizeTicker(ticker);
  if (!isValidTicker(normalized)) {
    input.setCustomValidity('請輸入 2330.TW、2330 或 AAPL 格式的股票代號'); input.reportValidity(); return;
  }
  input.setCustomValidity('');
  setAsyncState(button, statusRoot, 'loading', `正在載入 ${normalized}`);
  try {
    const next = await requestJson(`/api/stocks/${encodeURIComponent(normalized)}/snapshot`);
    snapshot = next;
    renderSummary(next);
    renderEvidence();
    const url = new URL(window.location.href); url.searchParams.set('ticker', normalized); window.history.replaceState({}, '', url);
    renderSourceStatus(statusRoot, { state: 'success', message: '股票快照已更新', source: next.data_quality?.status || 'Stock Snapshot API', updatedAt: next.quote?.as_of || '' });
  } catch (error) {
    renderSourceStatus(statusRoot, { state: 'error', message: error.message, source: 'Stock Snapshot API' });
  } finally {
    setAsyncState(button, null, 'idle', '');
  }
}

bindTabs(document.getElementById('stock-tabs'), tab => { activeTab = tab; renderEvidence(); });
form.addEventListener('submit', event => { event.preventDefault(); loadSnapshot(input.value); });
input.value = tickerFromLocation();
focusPageHeading('stock-title');
loadSnapshot(input.value);
```

- [ ] **Step 5: 執行單股頁與 API 回歸**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_stock_snapshot.py \
  -q
```

Expected: 全部 PASS。

- [ ] **Step 6: 提交單股研究垂直切片**

```bash
git add backend/static/commercial/stock-detail.html backend/static/commercial/pages/stock_page.js tests/test_commercial_layout_pages.py
git commit -m "feat: simplify commercial stock research"
```

---

### Task 4: 重建組合健檢頁

**Files:**
- Replace: `backend/static/commercial/portfolio-dashboard.html`
- Create: `backend/static/commercial/pages/portfolio_page.js`
- Modify: `tests/test_commercial_layout_pages.py`

- [ ] **Step 1: 新增組合頁失敗契約**

```python
def test_portfolio_page_validates_csv_and_posts_one_real_risk_request():
    html = read("portfolio-dashboard.html")
    js = read("pages/portfolio_page.js")

    assert 'data-commercial-page="portfolio"' in html
    assert html.count("commercial-primary-action") == 1
    assert 'id="portfolio-csv"' in html
    assert 'id="portfolio-recommendations"' in html
    assert "/api/watchlist/portfolio/risk" in js
    assert "validatePortfolioCsv" in js
    assert "fallbackPortfolio" not in js
    assert "localStorage" not in js
```

- [ ] **Step 2: 執行測試並確認舊 80+ 模組頁失敗**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py::test_portfolio_page_validates_csv_and_posts_one_real_risk_request -q
```

Expected: FAIL，缺少 `pages/portfolio_page.js` 或新的單一 CTA 結構。

- [ ] **Step 3: 以健康度、三建議與三次級分頁 HTML 取代組合頁**

以以下完整 HTML 取代 `backend/static/commercial/portfolio-dashboard.html`：

```html
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OnStock 組合健檢</title>
  <link rel="stylesheet" href="/static/commercial/styles/tokens.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/shell.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/components.css?v=20260711-simple">
  <link rel="stylesheet" href="/static/commercial/styles/responsive.css?v=20260711-simple">
</head>
<body data-commercial-page="portfolio">
<header class="commercial-topbar">
  <a class="commercial-brand" href="/" aria-label="回到主頁">OnStock AI</a>
  <nav class="commercial-nav" aria-label="商業版投資工作區">
    <a href="/static/commercial/research-workbench.html">今日決策</a>
    <a href="/static/commercial/stock-detail.html">單股研究</a>
    <a href="/static/commercial/portfolio-dashboard.html" aria-current="page">組合健檢</a>
  </nav>
</header>
<main class="commercial-page">
  <header class="commercial-page-header">
    <span class="commercial-eyebrow">Portfolio Health</span>
    <h1 id="portfolio-title" tabindex="-1">組合健檢</h1>
  </header>
  <form id="portfolio-form" class="commercial-panel" novalidate>
    <label class="commercial-field" for="portfolio-csv">
      <span>持股 CSV</span>
      <textarea id="portfolio-csv" aria-describedby="portfolio-csv-help portfolio-csv-error">ticker,weight,sector,country
2330.TW,45,Semiconductor,TW
2308.TW,22,Power,TW
AAPL,14,Software,US
Cash,19,Cash,TW</textarea>
    </label>
    <p id="portfolio-csv-help" class="commercial-muted">必要欄位：ticker，以及 weight 或 market_value。</p>
    <p id="portfolio-csv-error" role="alert"></p>
    <button id="portfolio-run" class="commercial-primary-action" type="submit">產生調整建議</button>
  </form>
  <section class="commercial-answer" aria-labelledby="portfolio-answer-title">
    <span class="commercial-eyebrow">組合答案</span>
    <h2 id="portfolio-answer-title">貼上持股資料以開始健檢</h2>
    <p id="portfolio-answer-detail" class="commercial-muted"></p>
    <div id="portfolio-metrics" class="commercial-metrics"></div>
    <ol id="portfolio-recommendations" class="commercial-recommendations"></ol>
  </section>
  <div id="portfolio-tabs" class="commercial-tabs" role="tablist" aria-label="組合研究證據">
    <button type="button" role="tab" aria-selected="true" data-tab="exposure">曝險</button>
    <button type="button" role="tab" aria-selected="false" tabindex="-1" data-tab="scenario">情境</button>
    <button type="button" role="tab" aria-selected="false" tabindex="-1" data-tab="contribution">貢獻</button>
  </div>
  <section id="portfolio-evidence" class="commercial-panel" aria-live="polite"></section>
  <section id="portfolio-source-status" class="commercial-source-status" aria-live="polite"></section>
</main>
<script type="module" src="/static/commercial/pages/portfolio_page.js?v=20260711-simple"></script>
</body>
</html>
```

- [ ] **Step 4: 實作 CSV validation、mutation POST 與三建議**

建立 `pages/portfolio_page.js`，核心如下：

```javascript
import { requestJson } from '../shared/api.js';
import { setAsyncState } from '../shared/async_state.js';
import { bindTabs, focusPageHeading } from '../shared/shell.js';
import { renderSourceStatus } from '../shared/source_status.js';

const form = document.getElementById('portfolio-form');
const input = document.getElementById('portfolio-csv');
const errorRoot = document.getElementById('portfolio-csv-error');
const button = document.getElementById('portfolio-run');
const answer = document.getElementById('portfolio-answer-title');
const detail = document.getElementById('portfolio-answer-detail');
const metrics = document.getElementById('portfolio-metrics');
const recommendations = document.getElementById('portfolio-recommendations');
const evidence = document.getElementById('portfolio-evidence');
const statusRoot = document.getElementById('portfolio-source-status');
let report = null;
let activeTab = 'exposure';

export function validatePortfolioCsv(text) {
  const lines = String(text || '').trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return '至少需要標題列與一筆持股。';
  const headers = lines[0].split(',').map(value => value.trim().toLowerCase());
  if (!headers.includes('ticker') && !headers.includes('symbol')) return '標題列缺少 ticker。';
  if (!headers.includes('weight') && !headers.includes('weight_pct') && !headers.includes('market_value')) return '標題列需要 weight 或 market_value。';
  const width = headers.length;
  const invalid = lines.slice(1).findIndex(line => line.split(',').length !== width);
  return invalid >= 0 ? `第 ${invalid + 2} 列欄位數與標題列不同。` : '';
}

function metric(name, value) {
  const root = document.createElement('div'); root.className = 'commercial-metric';
  const key = document.createElement('span'); key.textContent = name;
  const strong = document.createElement('strong'); strong.textContent = String(value ?? '資料不足');
  root.append(key, strong); return root;
}

function healthScore(payload) {
  const flagPenalty = (payload.risk_flags || []).length * 12;
  const invalidPenalty = (payload.thesis_health?.invalidated || []).length * 12;
  const missingPenalty = Math.min((payload.thesis_health?.missing || []).length * 5, 20);
  return Math.max(0, 100 - flagPenalty - invalidPenalty - missingPenalty);
}

function recommendationLines(payload) {
  const top = payload.concentration?.top_position || {};
  const lines = [];
  if ((payload.risk_flags || []).includes('single_position_over_40_pct')) lines.push(`降低 ${top.ticker || '最大部位'} 權重；目前 ${top.weight_pct}%`);
  if ((payload.risk_flags || []).includes('sector_over_60_pct')) lines.push('降低最大產業集中度，避免單一產業超過 60%。');
  if ((payload.risk_flags || []).includes('country_over_80_pct')) lines.push('增加不同市場曝險，避免單一市場超過 80%。');
  if ((payload.thesis_health?.invalidated || []).length) lines.push(`複查失效論點：${payload.thesis_health.invalidated.join('、')}`);
  if ((payload.thesis_health?.missing || []).length) lines.push(`補齊投資論點：${payload.thesis_health.missing.join('、')}`);
  return lines.length ? lines.slice(0, 3) : ['目前沒有超過門檻的集中風險；維持例行檢查。'];
}

function renderReport(payload) {
  const score = healthScore(payload);
  const top = payload.concentration?.top_position || {};
  answer.textContent = `健康度 ${score}｜${(payload.risk_flags || []).length ? '需要調整' : '風險在門檻內'}`;
  detail.textContent = `${payload.total_positions || 0} 個部位 · ${recommendationLines(payload).length} 項下一步`;
  metrics.replaceChildren(
    metric('健康度', score),
    metric('最大部位', top.ticker),
    metric('最大權重', top.weight_pct === undefined ? null : `${top.weight_pct}%`),
    metric('風險旗標', (payload.risk_flags || []).length),
  );
  recommendations.replaceChildren(...recommendationLines(payload).map(text => { const item = document.createElement('li'); item.textContent = text; return item; }));
  renderEvidence();
}

function renderEvidence() {
  if (!report) { evidence.textContent = '完成健檢後顯示細節。'; return; }
  if (activeTab === 'scenario') evidence.textContent = '情境分析使用目前風險旗標：' + ((report.risk_flags || []).join('、') || '無');
  else if (activeTab === 'contribution') evidence.textContent = '持股權重由高至低：' + (report.positions || []).map(item => `${item.ticker} ${item.weight_pct}%`).join('、');
  else evidence.textContent = '產業曝險：' + Object.entries(report.concentration?.sector_weights || {}).map(([key, value]) => `${key} ${value}%`).join('、');
}

bindTabs(document.getElementById('portfolio-tabs'), tab => { activeTab = tab; renderEvidence(); });
focusPageHeading('portfolio-title');
form.addEventListener('submit', async event => {
  event.preventDefault();
  const error = validatePortfolioCsv(input.value);
  errorRoot.textContent = error;
  if (error) { input.focus(); return; }
  setAsyncState(button, statusRoot, 'loading', '正在分析組合');
  try {
    report = await requestJson('/api/watchlist/portfolio/risk', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ csv: input.value, thesis_health: {} }),
    });
    renderReport(report);
    renderSourceStatus(statusRoot, { state: 'success', message: '組合健檢已更新', source: 'Portfolio Risk API' });
  } catch (requestError) {
    renderSourceStatus(statusRoot, { state: 'error', message: requestError.message, source: 'Portfolio Risk API' });
  } finally {
    setAsyncState(button, null, 'idle', '');
  }
});
```

- [ ] **Step 5: 執行組合頁與 mutation API 回歸**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_portfolio_risk.py \
  -q
```

Expected: 全部 PASS。

- [ ] **Step 6: 提交組合健檢垂直切片**

```bash
git add backend/static/commercial/portfolio-dashboard.html backend/static/commercial/pages/portfolio_page.js tests/test_commercial_layout_pages.py
git commit -m "feat: simplify commercial portfolio health"
```

---

### Task 5: 簡化首頁商業版入口

**Files:**
- Modify: `backend/static/index.html:411`
- Modify: `backend/static/styles/history_shell_commercial.css`
- Modify: `backend/static/styles/responsive.css`
- Modify: `tests/test_static_history_filters.py:7278`

- [ ] **Step 1: 將首頁測試改成一主兩次入口契約**

把 `test_home_commercial_tab_is_a_restart_safe_product_launchpad` 相關舊 assertions 改為：

```python
def test_home_commercial_tab_prioritizes_today_decisions():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    commercial_css = (STATIC_DIR / "styles" / "history_shell_commercial.css").read_text(encoding="utf-8")

    assert 'id="home-panel-commercial"' in index_html
    assert 'class="commercial-entry-primary"' in index_html
    assert 'href="/static/commercial/research-workbench.html"' in index_html
    assert '今天先處理什麼' in index_html
    assert index_html.count('class="commercial-entry-secondary"') == 2
    assert '產生 AI 報告' not in index_html
    assert '建立再平衡單' not in index_html
    assert '.commercial-entry-primary' in commercial_css
    assert '.commercial-entry-secondary' in commercial_css
```

- [ ] **Step 2: 執行測試並確認舊三張等權卡片失敗**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py::test_home_commercial_tab_prioritizes_today_decisions -q
```

Expected: FAIL，缺少 `.commercial-entry-primary`。

- [ ] **Step 3: 替換首頁商業版 launchpad markup**

將 `home-panel-commercial` 內 launchpad 改為：

```html
<section class="commercial-entry-launchpad" aria-label="商業版投資工作區">
  <p class="history-kicker">商業版投資工作區</p>
  <a class="commercial-entry-primary" href="/static/commercial/research-workbench.html">
    <span>今日決策</span>
    <strong>今天先處理什麼</strong>
    <small>依風險、資料時效與需重跑狀態整理待辦</small>
    <b>查看今日決策</b>
  </a>
  <div class="commercial-entry-secondary-grid">
    <a class="commercial-entry-secondary" href="/static/commercial/stock-detail.html"><span>單股研究</span><strong>研究一檔股票</strong><small>先看結論，再查基本面、事件與技術證據</small></a>
    <a class="commercial-entry-secondary" href="/static/commercial/portfolio-dashboard.html"><span>組合健檢</span><strong>檢查整體持股風險</strong><small>查看集中度與最多三項調整建議</small></a>
  </div>
</section>
```

移除原本 command row、status grid、三張 metrics/action pills 與可能誤導的假功能文案。

- [ ] **Step 4: 實作首頁主次層級 CSS**

`history_shell_commercial.css` 僅保留 launchpad 需要的 selectors：

```css
.commercial-entry-launchpad { display: grid; gap: 16px; text-align: left; }
.commercial-entry-primary, .commercial-entry-secondary { display: grid; gap: 6px; padding: 20px; border: 1px solid rgba(148, 163, 184, .22); border-radius: 14px; color: inherit; text-decoration: none; }
.commercial-entry-primary { background: linear-gradient(135deg, rgba(45, 212, 191, .16), rgba(15, 23, 42, .65)); border-color: rgba(45, 212, 191, .5); }
.commercial-entry-primary strong { font-size: clamp(1.35rem, 3vw, 2rem); }
.commercial-entry-primary b { width: fit-content; margin-top: 8px; padding: 9px 12px; border-radius: 8px; background: var(--accent); color: #041a21; }
.commercial-entry-secondary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.commercial-entry-secondary span, .commercial-entry-secondary small, .commercial-entry-primary span, .commercial-entry-primary small { color: var(--text-muted); }
```

在 `styles/responsive.css` 的 mobile media query 加：

```css
.commercial-entry-secondary-grid { grid-template-columns: 1fr; }
```

- [ ] **Step 5: 執行首頁與 HTTP smoke**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_static_history_filters.py::test_home_commercial_tab_prioritizes_today_decisions \
  tests/test_frontend_http_e2e.py::test_frontend_shell_static_assets_and_report_history_flow \
  -q
```

Expected: `2 passed`。

- [ ] **Step 6: 提交首頁入口**

```bash
git add backend/static/index.html backend/static/styles/history_shell_commercial.css backend/static/styles/responsive.css tests/test_static_history_filters.py
git commit -m "feat: prioritize daily decisions in commercial entry"
```

---

### Task 6: 收緊互動、無障礙與 static asset 契約

**Files:**
- Modify: `backend/static/commercial/shared/shell.js`
- Modify: `backend/static/commercial/styles/components.css`
- Modify: `tests/test_commercial_layout_pages.py`
- Modify: `tests/test_frontend_http_e2e.py`

- [ ] **Step 1: 新增三頁共同驗收失敗測試**

```python
def test_three_pages_share_navigation_and_do_not_load_legacy_bundle():
    pages = {
        "research-workbench.html": "decision_page.js",
        "stock-detail.html": "stock_page.js",
        "portfolio-dashboard.html": "portfolio_page.js",
    }
    for filename, module in pages.items():
        html = read(filename)
        assert html.count('class="commercial-primary-action') == 1
        assert 'href="/static/commercial/research-workbench.html"' in html
        assert 'href="/static/commercial/stock-detail.html"' in html
        assert 'href="/static/commercial/portfolio-dashboard.html"' in html
        assert f"/static/commercial/pages/{module}" in html
        assert "commercial_pages.js" not in html
        assert "commercial_pages.css" not in html
        assert '<a class="commercial-brand" href="/"' in html


def test_metrics_are_not_buttons_and_tabs_have_keyboard_contract():
    components = read("styles/components.css")
    shell = read("shared/shell.js")
    for filename in ("research-workbench.html", "stock-detail.html", "portfolio-dashboard.html"):
        html = read(filename)
        assert 'class="commercial-metric" role="button"' not in html
    assert "ArrowLeft" in shell and "ArrowRight" in shell
    assert "focusPageHeading" in shell
    assert ":focus-visible" in components
    assert "min-height: 44px" in components
```

- [ ] **Step 2: 更新 HTTP smoke 新資產清單**

在 `test_frontend_shell_static_assets_and_report_history_flow` 的 asset loop 增加：

```python
for asset in (
    "/static/commercial/styles/tokens.css",
    "/static/commercial/styles/shell.css",
    "/static/commercial/styles/components.css",
    "/static/commercial/styles/responsive.css",
    "/static/commercial/shared/api.js",
    "/static/commercial/shared/async_state.js",
    "/static/commercial/shared/shell.js",
    "/static/commercial/shared/source_status.js",
    "/static/commercial/pages/decision_page.js",
    "/static/commercial/pages/stock_page.js",
    "/static/commercial/pages/portfolio_page.js",
):
    response = client.get(asset)
    assert response.status_code == 200, asset
    assert response.text.strip(), asset
```

- [ ] **Step 3: 執行共同契約並修正任何遺漏的 href、aria-current 或 asset path**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_frontend_http_e2e.py::test_frontend_shell_static_assets_and_report_history_flow \
  -q
```

Expected: 全部 PASS。若有失敗，只修改對應 HTML attribute 或 asset URL，不把舊 bundle 加回來。

- [ ] **Step 4: 用 Node 檢查所有新 JS 語法**

Run:

```bash
node --check backend/static/commercial/shared/api.js
node --check backend/static/commercial/shared/async_state.js
node --check backend/static/commercial/shared/shell.js
node --check backend/static/commercial/shared/source_status.js
node --check backend/static/commercial/pages/decision_page.js
node --check backend/static/commercial/pages/stock_page.js
node --check backend/static/commercial/pages/portfolio_page.js
```

Expected: 每個 command exit 0，沒有輸出。

- [ ] **Step 5: 提交共同互動契約**

```bash
git add \
  backend/static/commercial/shared/shell.js \
  backend/static/commercial/styles/components.css \
  tests/test_commercial_layout_pages.py \
  tests/test_frontend_http_e2e.py
git commit -m "test: enforce simple commercial interactions"
```

---

### Task 7: 移除舊 bundle 與未標示 fallback 行為

**Files:**
- Delete: `backend/static/commercial/commercial_pages.js`
- Delete: `backend/static/commercial/commercial_pages.css`
- Modify: `tests/test_commercial_layout_pages.py`
- Modify: `tests/test_frontend_http_e2e.py`

- [ ] **Step 1: 新增 legacy asset 不可再存在的失敗測試**

```python
def test_legacy_commercial_bundle_is_removed_after_page_modules_take_over():
    assert not (COMMERCIAL_DIR / "commercial_pages.js").exists()
    assert not (COMMERCIAL_DIR / "commercial_pages.css").exists()
```

- [ ] **Step 2: 執行測試並確認兩個舊檔仍存在**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_commercial_layout_pages.py::test_legacy_commercial_bundle_is_removed_after_page_modules_take_over -q
```

Expected: FAIL，指出 `commercial_pages.js` 存在。

- [ ] **Step 3: 搜尋所有引用後刪除舊 bundle**

Run:

```bash
rg -n "commercial_pages\.(js|css)" backend tests docs
```

Expected: 只剩待刪檔本身、舊測試或歷史文件引用；目前三個 HTML 不可出現在結果中。

刪除兩個舊檔，並從當前 HTTP asset smoke 移除對它們的任何 active assertion。歷史規格中的文字引用不修改。

- [ ] **Step 4: 執行商業版與首頁 focused tests**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_static_history_filters.py::test_home_commercial_tab_prioritizes_today_decisions \
  tests/test_frontend_http_e2e.py::test_frontend_shell_static_assets_and_report_history_flow \
  -q
```

Expected: 全部 PASS。

- [ ] **Step 5: 提交 legacy removal**

```bash
git add -u \
  backend/static/commercial/commercial_pages.js \
  backend/static/commercial/commercial_pages.css
git add tests/test_commercial_layout_pages.py tests/test_frontend_http_e2e.py
git commit -m "refactor: remove legacy commercial bundles"
```

---

### Task 8: 加入 live Playwright 密度與核心流程驗證

**Files:**
- Create: `tests/test_commercial_visual_optional.py`
- Replace: `backend/static/commercial/research-workbench.png`
- Replace: `backend/static/commercial/stock-detail.png`
- Replace: `backend/static/commercial/portfolio-dashboard.png`
- Replace: `backend/static/commercial/home-commercial-entry.png`

- [ ] **Step 1: 寫 optional live browser 失敗測試**

建立 `tests/test_commercial_visual_optional.py`：

```python
import os
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("COMMERCIAL_BASE_URL", "http://127.0.0.1:8080")
PAGES = (
    ("research-workbench.html", "今日決策"),
    ("stock-detail.html", "單股研究"),
    ("portfolio-dashboard.html", "組合健檢"),
)


def live_browser():
    required = os.getenv("VISUAL_REGRESSION_REQUIRED") == "1"
    try:
        urlopen(f"{BASE_URL}/static/commercial/research-workbench.html", timeout=2).close()
        import playwright.sync_api as sync_api
    except (ImportError, URLError, OSError) as exc:
        if required:
            pytest.fail(f"Live commercial browser is required: {exc}")
        pytest.skip(f"Live commercial browser is unavailable: {exc}")
    return sync_api


@pytest.mark.parametrize("width,height", ((375, 812), (768, 900), (1280, 720)))
def test_commercial_pages_keep_answer_and_primary_action_in_first_viewport(width, height):
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        for filename, heading in PAGES:
            page.goto(f"{BASE_URL}/static/commercial/{filename}", wait_until="networkidle")
            assert page.get_by_role("heading", name=heading, level=1).is_visible()
            assert page.locator(".commercial-primary-action:visible").count() == 1
            assert page.locator("button:visible").count() <= 12
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            answer_box = page.locator(".commercial-answer").bounding_box()
            assert answer_box and answer_box["y"] < height
        browser.close()


def test_decision_empty_and_api_error_states_never_render_sample_stocks():
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.route("**/api/decision-tracking", lambda route: route.fulfill(status=200, content_type="application/json", body='{"items": []}'))
        page.goto(f"{BASE_URL}/static/commercial/research-workbench.html", wait_until="networkidle")
        assert page.get_by_role("heading", name="尚無追蹤股票", level=2).is_visible()
        assert page.get_by_role("link", name="設定追蹤股票").is_visible()
        assert "2330" not in page.locator("#decision-task-list").inner_text()

        page.unroute("**/api/decision-tracking")
        page.route("**/api/decision-tracking", lambda route: route.fulfill(status=502, content_type="application/json", body='{"detail": "tracking unavailable"}'))
        page.reload(wait_until="networkidle")
        assert page.locator("#decision-source-status[data-state=error]").is_visible()
        assert "2330" not in page.locator("#decision-task-list").inner_text()
        browser.close()


def test_stock_and_portfolio_api_errors_show_recovery_state_without_fallbacks():
    sync_api = live_browser()
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        page.route("**/api/stocks/*/snapshot", lambda route: route.fulfill(status=502, content_type="application/json", body='{"detail": "stock unavailable"}'))
        page.goto(f"{BASE_URL}/static/commercial/stock-detail.html?ticker=2330.TW", wait_until="networkidle")
        assert page.locator("#stock-source-status[data-state=error]").is_visible()
        assert "stock unavailable" in page.locator("#stock-source-status").inner_text()

        page.route("**/api/watchlist/portfolio/risk", lambda route: route.fulfill(status=502, content_type="application/json", body='{"detail": "portfolio unavailable"}'))
        page.goto(f"{BASE_URL}/static/commercial/portfolio-dashboard.html", wait_until="networkidle")
        page.get_by_role("button", name="產生調整建議").click()
        page.locator("#portfolio-source-status[data-state=error]").wait_for()
        assert "portfolio unavailable" in page.locator("#portfolio-source-status").inner_text()
        assert page.locator("#portfolio-recommendations li").count() == 0
        browser.close()
```

- [ ] **Step 2: 先用正式 gate 執行，確認 Playwright 或 runtime 問題會被看見**

Run:

```bash
VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 \
  $(scripts/project_python.sh) -m pytest tests/test_commercial_visual_optional.py -q
```

Expected: 若 runtime 尚未重載新資產則 FAIL；重載後應 PASS。Playwright 缺少時必須安裝專案既有 optional dependency，不能把正式 gate 改成 skip。

- [ ] **Step 3: 以瀏覽器實際驗證三個主要流程**

在 1280 × 720 與 375 × 812 各執行一次：

1. 今日決策載入後，點主要 CTA，確認 URL 含正確 `ticker` 與 `from=decision`；再使用 browser back，確認回到原本今日決策清單。
2. 單股頁輸入 `2330.TW`，點更新，確認按鈕 loading/disabled，完成後來源狀態為成功。
3. 組合頁先輸入破損 CSV，確認不送 request 且 focus 回到 textarea；再輸入有效 CSV，確認只送一次 POST 並顯示健康度與最多三項建議。
4. 逐一 tab 鍵盤左右切換，確認 `aria-selected` 與內容同步。
5. 讀取 console errors，結果必須為空。

Expected: 每個可見動作都有導覽、網路或可見狀態證據；沒有「按了像沒作用」的控制。

- [ ] **Step 4: 覆寫四張 runtime 截圖**

使用 1280 × 720 截圖覆寫三頁 PNG；首頁以 1440 × 900、商業版 tab active 截圖覆寫 `home-commercial-entry.png`。截圖前等待 API 成功或明確錯誤狀態，不能保存骨架畫面。

- [ ] **Step 5: 提交 live browser gate 與新截圖**

```bash
git add tests/test_commercial_visual_optional.py backend/static/commercial/*.png
git commit -m "test: verify simplified commercial pages live"
```

---

### Task 9: 更新操作文件並執行完整驗收

**Files:**
- Modify: `docs/operator-guide.md`
- Verify: `docs/superpowers/specs/2026-07-11-commercial-pages-simplification-design.md`

- [ ] **Step 1: 在 operator guide 加入三個使用流程**

新增「商業版三頁」章節，內容必須明確寫出：

```markdown
## 商業版三頁

- 今日決策：先看依風險與資料時效排序的待辦，點第一項進入單股研究。
- 單股研究：輸入 ticker 後更新快照，先讀結論，再切換基本面、事件與技術證據。
- 組合健檢：貼上含 ticker 與 weight/market_value 的 CSV，取得健康度與最多三項調整建議。

正式頁面不會在 API 失敗時改用未標示的範例資料。若看到錯誤狀態，依畫面重試或先檢查 runtime；示範資料只能在明確 Demo 模式使用。
```

- [ ] **Step 2: 執行設計規格要求的 focused suite**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_commercial_layout_pages.py \
  tests/test_frontend_http_e2e.py \
  tests/test_stock_snapshot.py \
  tests/test_portfolio_risk.py \
  tests/test_decision_tracking_workflow.py \
  -q
```

Expected: 全部 PASS；不得以刪除 API 回歸 assertion 取得綠燈。

- [ ] **Step 3: 執行首頁商業版入口測試與 live browser gate**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_static_history_filters.py::test_home_commercial_tab_prioritizes_today_decisions \
  -q
VISUAL_REGRESSION_REQUIRED=1 COMMERCIAL_BASE_URL=http://127.0.0.1:8080 \
  $(scripts/project_python.sh) -m pytest tests/test_commercial_visual_optional.py -q
```

Expected: 全部 PASS。

- [ ] **Step 4: 執行 runtime 與變更完整性檢查**

Run:

```bash
$(scripts/project_python.sh) scripts/doctor_runtime.py
git diff --check
rg -n "commercial_pages\.(js|css)|fallbackTickers|fallbackPortfolio" backend/static/commercial
```

Expected:

- doctor 顯示 canonical report index 與 operational DB。
- `git diff --check` exit 0。
- `rg` 對 active commercial frontend 無結果。

- [ ] **Step 5: 依規格逐條完成驗收 audit**

記錄下列證據：

- 三頁各一個 `.commercial-primary-action`。
- 1280 × 720 的答案與主要 CTA 在首屏。
- 三頁初始可見 `button` 不超過 12。
- API error 不顯示 sample data。
- ticker deep link、browser back、mutation token 皆由 live browser 或 HTTP test 證明。
- 375 與 1280 無水平捲動，tab keyboard 與 focus ring 可見。

任何一項缺證據都回到對應 Task 修正，不得以「測試沒有失敗」代替驗收。

- [ ] **Step 6: 提交文件與最後修正**

```bash
git add docs/operator-guide.md
git commit -m "docs: document simplified commercial workflows"
```

提交前先用 `git diff --cached --stat` 確認沒有把工作樹原本不相關變更納入；若有，取消 staging 並只加入本計畫列出的檔案。
