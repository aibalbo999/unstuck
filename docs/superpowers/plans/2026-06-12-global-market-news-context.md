# Global Market News Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional global market and international news context to report data, prompts, source audit, and operator-facing source labels.

**Architecture:** Add two optional provider sources, merge their payloads through the existing provider workflow, and expose them through prompt JSON without changing core data trust semantics. Source health reuses Provider SLA and static UI labels.

**Tech Stack:** Python 3.13, FastAPI data services, pytest, yfinance, httpx, existing static JavaScript.

---

### Task 1: Provider Workflow And Audit Shape

**Files:**
- Modify: `tests/test_provider_workflow.py`
- Modify: `backend/data_fetch/workflow.py`
- Modify: `backend/data_fetch/enrichment_merge.py`
- Modify: `backend/data_fetch/constants.py`
- Modify: `backend/data_freshness_policy.py`
- Modify: `backend/data_trust_constants.py`
- Modify: `backend/data_trust_audit.py`

- [x] Write a failing test showing `global_market_context` and `international_news_context` providers are executed, merged, audited, and do not make core trust stale.
- [x] Run `PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_provider_workflow.py::test_stock_data_service_merges_global_market_and_international_news_context -q` and verify it fails because the fields are missing.
- [x] Implement workflow refresh gates and merge logic for both optional sources.
- [x] Add source constants, source labels, and record counting for the new sources.
- [x] Run the focused provider workflow test and verify it passes.

### Task 2: External Fetchers And Default Providers

**Files:**
- Create: `backend/data_fetch/market_sources/global_context.py`
- Modify: `backend/data_fetch/enrichment_providers.py`
- Modify: `backend/data_fetch/provider_registry.py`
- Modify: `backend/data_fetch/__init__.py`
- Modify: `backend/external_data_parsers.py`
- Create: `backend/external_data_gdelt.py`
- Modify: `tests/test_data_fetch_fixtures.py`

- [x] Write failing parser/fetcher tests for market proxy output and GDELT article parsing.
- [x] Run the focused tests and verify failure on missing modules/functions.
- [x] Implement deterministic yfinance market proxy summarization and GDELT parser/client wrappers.
- [x] Register `GlobalMarketContextProvider` and `InternationalNewsContextProvider`.
- [x] Run focused tests and verify they pass.

### Task 3: Prompt Contract And Runtime Rules

**Files:**
- Modify: `tests/test_prompt_data_trust.py`
- Modify: `tests/test_audit_rules.py`
- Modify: `backend/prompt_builder.py`
- Modify: `backend/prompts/runtime_rules.json`

- [x] Write failing tests that prompt JSON includes `global_market_context` and `international_news_context` in normal and compact modes.
- [x] Write failing tests that Agent 11, 15, and 16 rules require citing or disclosing global context.
- [x] Run focused tests and verify failure.
- [x] Add compact helpers and prompt payload sections.
- [x] Update runtime rules for Agents 11, 15, and 16.
- [x] Run focused prompt tests and verify they pass.

### Task 4: Operator UX Labels

**Files:**
- Modify: `tests/test_static_history_filters.py`
- Modify: `backend/static/provider_sla_panel.js`

- [x] Write a failing static frontend test for `全球市場脈絡` and `國際新聞脈絡` labels and non-alarmist impact text.
- [x] Run focused static test and verify failure.
- [x] Add source labels and impact text to Provider SLA panel.
- [x] Run focused static test and JS syntax checks.

### Task 5: Verification And Commit

**Files:**
- All touched files.

- [x] Run `scripts/ci_gate.sh`.
- [x] Run `for f in backend/static/*.js; do node --check "$f" || exit 1; done`.
- [x] Run `scripts/visual_regression.sh`.
- [x] Run `PYTHON_BIN=$(../scripts/project_python.sh); "$PYTHON_BIN" -m snapshot_maintenance verify-snapshots` from `backend/`.
- [x] Inspect `git diff` and commit implementation.
