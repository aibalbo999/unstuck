# Decision Learning Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立到期回測、跨期反思與事件驅動 Watchlist 的完整後端與前端閉環。

**Architecture:** 純計算模組負責回測與 trigger 判斷，SQLite store 負責冪等結果與事件，scheduler 只做編排。分析資料中的 `temporal_memory` 由 Prompt 路由限制給最終決策 Agent。

**Tech Stack:** Python 3.13、FastAPI、SQLite、asyncio、yfinance、原生 JavaScript/CSS、pytest。

---

### Task 1: 到期回測資料模型與純計算

**Files:**
- Create: `backend/decision_backtest.py`
- Create: `backend/market_price_history.py`
- Modify: `backend/decision_tracking_store.py`
- Test: `tests/test_decision_backtest.py`

- [ ] 先測試曆月到期日、方向 ROI、目標價 Hit/Miss 與 SQLite 唯一鍵。
- [ ] 執行 `pytest -q tests/test_decision_backtest.py`，確認因 API 尚未存在而失敗。
- [ ] 實作純函式、yfinance 歷史收盤價 provider 與 `decision_backtest_results` table。
- [ ] 重跑測試，確認通過。

### Task 2: 回測 scheduler、統計 API 與績效前端

**Files:**
- Modify: `backend/decision_tracking_service.py`
- Modify: `backend/decision_tracking_scheduler.py`
- Modify: `backend/api_routes/performance.py`
- Create: `backend/static/performance_panel.js`
- Create: `backend/static/styles/performance.css`
- Modify: `backend/static/api_client_extensions.js`
- Modify: `backend/static/ops_workspace.js`
- Modify: `backend/static/index.html`
- Test: `tests/test_decision_tracking_workflow.py`
- Test: `tests/test_static_history_filters.py`

- [ ] 先測試 due report 掃描、冪等 price fetch、統計聚合與 API payload。
- [ ] 實作 `run_due_backtests()` 並讓 scheduler 每日刷新後執行。
- [ ] 新增績效面板，顯示 Hit Rate、平均 ROI、各期與最近結果。
- [ ] 跑 focused tests 與 JavaScript syntax checks。

### Task 3: 上一期報告記憶與最終 Agent 反思

**Files:**
- Create: `backend/temporal_memory_service.py`
- Modify: `backend/report_history_service.py`
- Modify: `backend/analysis_jobs.py`
- Modify: `backend/agent_runtime/prompting.py`
- Modify: `backend/prompt_builder.py`
- Modify: `backend/report_index_rows.py`
- Modify: `backend/analysis_types.py`
- Test: `tests/test_temporal_memory.py`
- Test: `tests/test_prompt_context_routing.py`

- [ ] 先測試上一份報告提取、Miss 反思文字與僅路由至 Agent 7/16/19。
- [ ] 將 temporal memory 注入新分析 data，保存於 snapshot。
- [ ] 在最終 Agent Prompt 加入 `【Agent 歷史反思】`，其他 Agent 移除該欄位。
- [ ] 讓 report list 從 snapshot 回傳 temporal memory 給預覽。

### Task 4: Watchlist trigger store 與純判斷

**Files:**
- Create: `backend/watchlist_triggers.py`
- Modify: `backend/watchlist_store.py`
- Modify: `backend/watchlist_service.py`
- Test: `tests/test_watchlist_triggers.py`
- Test: `tests/test_watchlist_service.py`

- [ ] 先測試四種 trigger、V2/V3 路由、schema migration 與事件冪等性。
- [ ] 增加 `triggers_json` 與 `watchlist_trigger_events` table。
- [ ] 實作 price/SMA、外資連賣、VIX、營收創高純判斷。
- [ ] 回傳最近 trigger event 與摘要。

### Task 5: 盤後 trigger monitor 與任務派送

**Files:**
- Modify: `backend/watchlist_scheduler.py`
- Modify: `backend/watchlist_service.py`
- Modify: `backend/api.py`
- Test: `tests/test_watchlist_service.py`

- [ ] 先測試只在盤後每日監控一次、資料不足不 enqueue、active job 去重。
- [ ] scheduler 使用 `StockDataService.fetch_async()` 取得同一份可信資料 payload。
- [ ] 記錄 evaluation，依 trigger 決定 Pipeline 後 enqueue。
- [ ] 將 queued/skipped/error 數量寫入 runtime log。

### Task 6: Trigger 與反思前端

**Files:**
- Create: `backend/static/watchlist_trigger_form.js`
- Create: `backend/static/temporal_memory_panel.js`
- Modify: `backend/static/watchlist_panel.js`
- Modify: `backend/static/report_preview_panel.js`
- Modify: `backend/static/ops_workspace.js`
- Modify: `backend/static/app.js`
- Modify: `backend/static/index.html`
- Modify: `backend/static/styles/watchlist.css`
- Modify: `backend/static/styles/preview_panel.css`
- Test: `tests/test_static_history_filters.py`

- [ ] 先測試 DOM wiring、payload keys、trigger/event/反思文字與靜態模組尺寸。
- [ ] 實作 trigger controls、最近事件 chip 與 temporal memory preview。
- [ ] 更新 cache-busting 版本並執行瀏覽器桌面/手機 QA。

### Task 7: 完整驗證與文件

**Files:**
- Modify: `docs/operator-guide.md`
- Modify: `docs/architecture.md`

- [ ] 執行所有 focused tests。
- [ ] 執行 `./scripts/ci_gate.sh`。
- [ ] 以 live local app 驗證績效面板、trigger 設定、反思預覽及無 console error。
- [ ] 更新 operator guide 的排程、門檻與失敗重試說明。
