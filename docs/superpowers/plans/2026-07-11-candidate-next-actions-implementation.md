# Candidate Next Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven development and execute this plan task-by-task with regression checkpoints.

**Goal:** Turn a daily screener candidate into three concrete, safe next actions: inspect a stock snapshot, add it to watchlist, or preselect an analysis mode without starting analysis automatically.

**Architecture:** Keep candidate data shaping in `daily_decision_queue.py`, map the queue item into a candidate-specific action model in `operator_dashboard_actions.js`, and render the three buttons in `operator_summary_panel.js`. `app_panels.js` owns the integration callbacks so existing `StockSnapshotPanel` methods remain the only snapshot/watchlist implementation and `app.js` remains the owner of view switching and pipeline selection.

**Tech Stack:** Python pytest, browser static contract tests, vanilla JavaScript, Playwright optional browser QA.

---

### Task 1: Preserve candidate context in the daily queue

**Files:**
- Modify: `backend/daily_decision_queue.py:183-194`
- Test: `tests/test_daily_decision_queue.py`

- [x] **Step 1: Write the failing test**

Add a candidate queue assertion that passes `ticker`, `company_name`, `reason`, and `score`, then requires the queue item to preserve `company_name`, expose `candidate_reason`, and keep `score` as a non-display data field.

- [x] **Step 2: Run the focused test and verify it fails**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_daily_decision_queue.py -k candidate -q
```

Expected: FAIL because `_candidate_items()` currently creates a score-only detail and drops company name/reason.

- [x] **Step 3: Write the minimal implementation**

Change `_candidate_items()` to return:

```python
{
    "source": "screener",
    "type": "review_candidate",
    "priority_score": 420,
    "title": f"{ticker} 進入候選清單",
    "detail": reason or "市場掃描候選",
    "candidate_reason": reason or "市場掃描候選",
    "company_name": company_name,
    "score": candidate_score,
    "ticker": ticker,
}
```

Use the existing safe field helper and empty-value fallbacks; do not change screener ranking or add another API.

- [x] **Step 4: Run the test and verify it passes**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_daily_decision_queue.py -k candidate -q
```

Expected: PASS.

### Task 2: Add candidate action mapping and rendering

**Files:**
- Modify: `backend/static/operator_dashboard_actions.js:28-48`
- Modify: `backend/static/operator_summary_panel.js:6-57`
- Test: `tests/test_static_history_filters.py`

- [x] **Step 1: Write the failing static contract test**

Require candidate actions to expose `candidateActionModel`, three labels, `candidate_reason`, `company_name`, and a `data-candidate-action` attribute. Require the renderer to delegate candidate actions to a callback rather than routing them to the market screener panel.

- [x] **Step 2: Run the test and verify it fails**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py -k candidate -q
```

Expected: FAIL because current `review_candidate` maps to `open-ops` and renders one generic button.

- [x] **Step 3: Write the minimal implementation**

Add a candidate action model with these labels:

```javascript
{
  snapshot: '查看股票快照',
  watchlist: '加入追蹤',
  analysis: '選擇分析模式'
}
```

Render one primary snapshot button and two secondary buttons, carrying the candidate ticker and action type in data attributes. Keep the generic renderer unchanged for all other action types.

- [x] **Step 4: Run the test and verify it passes**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py -k candidate -q
```

Expected: PASS.

### Task 3: Connect candidate actions to existing workflows

**Files:**
- Modify: `backend/static/app_panels.js:6-101`
- Modify: `backend/static/app.js:18-54`
- Test: `tests/test_static_history_filters.py`
- Test: `tests/test_frontend_http_e2e.py` or the existing optional browser test module

- [x] **Step 1: Write the failing integration test**

Require candidate callbacks to:

```javascript
onCandidateSnapshot(ticker)
onCandidateWatchlist(ticker)
onCandidateAnalysis(ticker)
```

The snapshot callback must activate the analysis tab, set the existing ticker input, and call `stockSnapshotPanel.load(ticker)`. The watchlist callback must call `stockSnapshotPanel.addToWatchlist(ticker)`. The analysis callback must activate analysis, set/focus the ticker input, call `selectPipelineMode(getSelectedPipeline())`, and must not click the analysis submit button.

- [x] **Step 2: Run the test and verify it fails**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py -k 'candidate or app_panels' -q
```

Expected: FAIL because `app_panels.js` does not provide candidate callbacks and `app.js` does not expose an analysis-view helper.

- [x] **Step 3: Write the minimal implementation**

Pass `switchView` and candidate callbacks from `app.js` into `app_panels.js`. Create the operator summary after the snapshot panel exists, and route each candidate action to the existing panel method. Use `switchView('home-view')`, click `#home-tab-analysis` when available, and focus the ticker input after setting it. Do not call `analyzeBtn.click()`.

- [x] **Step 4: Run the integration test and verify it passes**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py -k 'candidate or app_panels' -q
```

Expected: PASS.

### Task 4: Verify browser behavior and record D578

**Files:**
- Modify: `tests/test_commercial_visual_optional.py` or the existing consumer browser test module
- Modify: `README.md`, `docs/operator-guide.md`, `tests/test_docs_contract.py`
- Modify: `docs/hcs-plus-optimization-state.md`
- Modify: `docs/superpowers/specs/2026-07-08-system-optimization-next-round.md`

- [x] **Step 1: Add browser assertions**

At desktop and 390px mobile, mock the daily decision payload with one candidate and assert the three buttons, the candidate reason, no horizontal overflow, snapshot loading after the snapshot action, watchlist API call after the watchlist action, and analysis input focus without automatic analysis.

- [x] **Step 2: Run the browser and static lanes**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_static_history_filters.py tests/test_frontend_http_e2e.py tests/test_commercial_visual_optional.py -q
node --check backend/static/operator_dashboard_actions.js
node --check backend/static/operator_summary_panel.js
node --check backend/static/app_panels.js
node --check backend/static/app.js
```

Expected: PASS with no warning summary.

- [x] **Step 3: Update the decision record**

Record D578 as `Candidate Next Actions`, including the preserved reason/company context, the three callbacks, the no-auto-analysis safety boundary, focused results, and the full-suite result.

- [x] **Step 4: Run final verification**

Run:

```bash
$(scripts/project_python.sh) -m pytest tests/test_daily_decision_queue.py tests/test_static_history_filters.py tests/test_frontend_http_e2e.py -q -W error::DeprecationWarning
git diff --check
$(scripts/project_python.sh) scripts/doctor_runtime.py
$(scripts/project_python.sh) -m pytest -q
```

Expected: all focused tests and the complete suite pass; runtime doctor reports canonical report index and operational database paths.
