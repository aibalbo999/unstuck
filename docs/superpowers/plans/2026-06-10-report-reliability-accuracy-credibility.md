# Report Reliability Accuracy Credibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the three report-quality phases: hard reliability gates, evidence-backed precision, and confidence calibration/regression coverage.

**Architecture:** Keep the existing data-trust, source-audit, final-audit, and report-rendering boundaries. Add narrow deterministic gates where model/prompt contracts are currently advisory, and expose evidence and calibration metadata through existing snapshots and report artifacts.

**Tech Stack:** Python 3.13, FastAPI services, Pydantic structured-output models, pytest, Jinja/reporting helpers.

---

### Task 1: Phase 1 Reliability Gates

**Files:**
- Modify: `backend/structured_output_normalizer.py`
- Modify: `backend/final_audit.py`
- Modify: `backend/report_rerun_service.py`
- Modify: `backend/reporting/evidence.py`
- Test: `tests/test_audit_rules.py`
- Test: `tests/test_report_data_trust.py`
- Test: `tests/test_report_preview.py`

- [x] Write failing tests that reject incomplete structured JSON.
- [x] Write failing tests that aggregate source evidence by usable data, not last provider event.
- [x] Write failing tests that block final-only reruns after material data refresh.
- [x] Implement minimal gates and rerun eligibility checks.
- [x] Run focused tests.

### Task 2: Phase 2 Evidence Matrix

**Files:**
- Create: `backend/reporting/evidence_matrix.py`
- Modify: `backend/reporting/audit_trust.py`
- Modify: `backend/data_trust_snapshot.py`
- Test: `tests/test_report_data_trust.py`

- [x] Write failing tests for report-visible evidence rows covering valuation, moat, recommendation, and source freshness.
- [x] Implement evidence matrix builder with cited source, status, fetched time, and limitation text.
- [x] Add matrix to HTML, Markdown, and data snapshots.
- [x] Run focused report tests.

### Task 3: Phase 3 Calibration And Regression

**Files:**
- Create: `backend/confidence_calibration.py`
- Modify: `backend/final_audit.py`
- Modify: `backend/decision_tracking.py`
- Test: `tests/test_prompt_data_trust.py`
- Test: `tests/test_report_preview.py`

- [x] Write failing tests for high-confidence low-trust downgrade guidance.
- [x] Add deterministic confidence calibration metadata.
- [x] Preserve tracking/report APIs while surfacing calibration warnings.
- [x] Run full pytest.
