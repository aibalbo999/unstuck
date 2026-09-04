# 四模式報告完整適配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓四種 pipeline 的分析輸出、專屬模板、品質閘門與實際產物完整一致。

**Architecture:** 保留單一 renderer 與共用 evidence boundary，在 structured schema、parsed context 與 mode focus context 增加模式專屬資料。模板 profile 同時宣告專屬 focus template 與段落 manifest，讓版面依決策週期選擇內容。

**Tech Stack:** Python 3.13、Pydantic、Jinja2、pytest、FastAPI、本機 RQ runtime。

---

### Task 1: 鎖定 structured output 契約

**Files:**
- Modify: `tests/test_structured_output_models.py`
- Modify: `tests/test_structured_output_parser.py`
- Modify: `tests/test_quality_gate_structured_outputs.py`
- Modify: `backend/structured_output_recommendation_outputs.py`
- Modify: `backend/structured_output_risk_models.py`
- Modify: `backend/structured_output_models.py`
- Modify: `backend/structured_output_validation.py`
- Modify: `backend/structured_output_normalizer_payloads.py`
- Modify: `backend/structured_output_normalize_dispatch.py`
- Modify: `backend/structured_output_parser.py`

- [x] 先新增 Agent 16 `position_plan`、Agent 19 `short_setup`、Agent 24 支撐/壓力的失敗測試。
- [x] 執行 focused pytest，確認因欄位或 schema 尚不存在而失敗。
- [x] 實作 Pydantic schema、normalizer 與 parsed context persistence。
- [x] 重跑 focused pytest，確認 structured data 從 response schema 流到 renderer context。

### Task 2: 鎖定 final audit 與文字輸出

**Files:**
- Modify: `tests/test_final_audit.py`
- Modify: `tests/test_structured_output_parser.py`
- Modify: `backend/final_audit.py`
- Modify: `backend/final_audit_mode_contracts.py`
- Modify: `backend/structured_output_rendering.py`
- Modify: `backend/structured_output_report_text.py`

- [x] 新增 B/C 缺少專屬計畫與 D 目標價混入多個非區間價位的失敗測試。
- [x] 確認測試先失敗，再實作 repair issue 與模式專屬 Markdown block。
- [x] 確認舊 payload fallback 仍可讀，且不把資料不足改成虛構價位。

### Task 3: 完成 HTML/Markdown 專屬模板

**Files:**
- Create: `backend/reporting/mode_focus_context.py`
- Modify: `backend/reporting/html_renderer.py`
- Modify: `backend/reporting/markdown_renderer.py`
- Modify: `backend/reporting/mode_templates.py`
- Modify: `backend/reporting/tear_sheet_summary.py`
- Modify: `backend/templates/includes/report_main.html.j2`
- Modify: `backend/templates/includes/mode_focus/*.html.j2`
- Modify: `backend/templates/includes/report_styles_mode_focus.html.j2`
- Modify: `tests/test_report_mode_templates.py`

- [x] 新增每個模式的動態 focus rows 與 section manifest 失敗測試。
- [x] 實作 mode focus context，讓 HTML/Markdown 共用同一組安全顯示值。
- [x] 讓模式 D 隱藏長期圖表與 overlay，A/B/C 顯示各自的歷史資料標題。
- [x] 驗證四種 HTML marker、Markdown 欄位、agent section 與無錯誤 horizon 文案。

### Task 4: 同步 prompt 與文件契約

**Files:**
- Modify: `backend/prompts/agents.json`
- Modify: `backend/prompts/runtime_rules.json`
- Modify: `docs/pipeline-mode-contract.md`
- Modify: `docs/system-architecture-map.md`
- Modify: `tests/test_prompt_context_routing.py`
- Modify: `tests/test_docs_contract.py`
- Modify: `tests/fixtures/golden_reports/2330_v1_markdown.json`

- [x] 新增 prompt schema 與文件同步的失敗測試。
- [x] 更新 Agent 16/19/24 的輸出指示與 runtime rules。
- [x] 更新模式契約與 golden digest，再跑 prompt/docs/golden lanes。

### Task 5: 完整驗證與 runtime 產物

**Files:**
- Verify only: source tree、runtime processes、report artifacts、API responses。

- [x] 執行 focused mode/structured/final-audit/conformance/style tests。
- [x] 執行 `git diff --check`、Python compile 與完整 pytest。
- [x] 以 `./start_mac.command` 正式重載 runtime，確認 doctor、health、ready 與 queue。
- [x] 新產生或重跑 v1-v4 各一份報告，核對 template marker、mode fields、agent sections、conformance、content credibility 與 evidence gate。
- [x] 僅在四模式證據都成立且沒有未處理契約缺口時，將目標標記 complete。
