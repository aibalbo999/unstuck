# AI Berkshire Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold ai-berkshire's investment discipline into stock-agent without replacing the existing LangGraph/RQ/data-trust architecture.

**Architecture:** Add four deep modules behind small interfaces: `investment_thesis`, `evidence_exit_gate`, `research_playbooks`, and `quality_funnel`. Each module is deterministic, testable without live network calls, and exposes structured payloads that existing report rendering, review, and watchlist flows can reuse.

**Tech Stack:** Python 3.13, pytest, existing FastAPI/LangGraph report pipeline, local SQLite-backed stores, Jinja/Markdown renderers.

---

### Task 1: Investment Thesis Module

**Files:**
- Create: `backend/investment_thesis.py`
- Modify: `backend/workflow_chief_editor.py`
- Modify: `backend/workflow_services.py`
- Modify: `backend/reporting/markdown_renderer.py`
- Test: `tests/test_investment_thesis.py`

- [ ] Write a failing test showing a recommendation context produces mirror-test lines, assumptions, red lines, information-richness grade, and a health score.
- [ ] Run `PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_investment_thesis.py -q` and verify it fails because the module does not exist.
- [ ] Implement `build_investment_thesis(context)` as a deterministic structured payload.
- [ ] Store `investment_thesis` in the workflow context and render a concise Markdown section.
- [ ] Run the targeted test and the existing report rendering tests.

### Task 2: Evidence Exit Gate Module

**Files:**
- Create: `backend/evidence_exit_gate.py`
- Modify: `backend/report_review_gate.py`
- Modify: `backend/report_persistence.py`
- Test: `tests/test_evidence_exit_gate.py`

- [ ] Write a failing test that extracts numeric report claims, samples them deterministically, and returns `approved/caution/rejected` from source-backed verification.
- [ ] Run `PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_evidence_exit_gate.py -q` and verify it fails because the module does not exist.
- [ ] Implement extraction, sample selection, snapshot numeric flattening, tolerance matching, and verdict rendering.
- [ ] Add evidence gate fields to review records without breaking existing review JSON.
- [ ] Run targeted tests plus `tests/test_report_data_trust.py`.

### Task 3: Research Playbook Registry

**Files:**
- Create: `backend/research_playbooks.py`
- Modify: `backend/pipeline_modes.py`
- Test: `tests/test_research_playbooks.py`

- [ ] Write a failing test proving pipeline modes can be mirrored as playbooks and non-pipeline playbooks exist for checklist/thesis/portfolio workflows.
- [ ] Run `PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_research_playbooks.py -q` and verify it fails because the module does not exist.
- [ ] Implement a small registry with canonical ids, labels, category, agent roles, gates, and source notes.
- [ ] Add helper functions that pipeline code can use without changing pipeline behavior.
- [ ] Run targeted tests plus `tests/test_v4_pipeline_mode.py`.

### Task 4: Quality Funnel Module

**Files:**
- Create: `backend/quality_funnel.py`
- Modify: `backend/market_screener.py`
- Test: `tests/test_quality_funnel.py`

- [ ] Write a failing test for pass/gray/reject outcomes using ROE, FCF, gross margin, OCF/net income, net margin, dilution, and debt risk.
- [ ] Run `PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_quality_funnel.py -q` and verify it fails because the module does not exist.
- [ ] Implement deterministic scoring and red-line reasons with Taiwan-friendly optional missing-data handling.
- [ ] Attach quality funnel metadata to market screener candidates before watchlist import.
- [ ] Run targeted tests plus `tests/test_market_screener.py`.

### Task 5: Verification And Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `README.md`

- [ ] Document the four new modules and their relationship to ai-berkshire.
- [ ] Run `PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_investment_thesis.py tests/test_evidence_exit_gate.py tests/test_research_playbooks.py tests/test_quality_funnel.py -q`.
- [ ] Run focused regression tests for audit, report, and screener paths.
