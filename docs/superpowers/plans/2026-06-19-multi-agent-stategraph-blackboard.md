# Multi-Agent StateGraph Blackboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace summary-chained agent context with a typed shared `AgentState`, add blocking data-validation circuit breakers, improve peer selection, and make structured outputs/tool calls provider-aware.

**Architecture:** Keep the existing `AnalysisPipelineRunner` and DAG groups, but add `AgentState` as a typed blackboard stored at `context["agent_state"]`. Agents receive role-specific `state_view` slices instead of depending on `{prev}`, while compatibility shims continue writing existing `context["analyses"]` and `context["structured_outputs"]` for renderers.

**Tech Stack:** Python 3.13, Pydantic, pytest, Google GenAI response schemas, optional OpenAI Responses/Chat Completions adapters, existing FastAPI/report pipeline.

---

## File Structure

- Create `backend/agent_state.py`: Pydantic models for shared state, provider values, validation issues, risk flags, and agent reports.
- Create `backend/state_memory.py`: state initialization, compatibility sync, immutable-ish merge helpers, and role-specific state view extraction.
- Modify `backend/pipeline_async.py`: initialize `AgentState`, run data validation before quant/agent execution, and keep compatibility context updated.
- Modify `backend/agent_runtime/prompting.py`: add `{state_view}` prompt payloads and reduce reliance on `{prev}` for state-aware agents.
- Modify `backend/data_financial_metric_validator.py`: upgrade warning-only metric validation into reusable circuit-breaker logic.
- Create `backend/data_reconciliation.py`: build retry and MOPS reconciliation plans for open circuit breakers.
- Modify `backend/financial_tools.py`: add implied revenue growth and margin sensitivity tools.
- Modify `backend/agent_runtime/routing.py`: register new financial tools for valuation agents.
- Modify `backend/data_fetch/market_sources/peers.py`: replace thin heuristic peer ranking with GICS/market-cap/revenue/business-overlap scoring.
- Modify `backend/structured_output_models.py`: keep provider-neutral Pydantic models and expose provider-specific schema helpers.
- Create `backend/openai_structured_outputs.py`: OpenAI-specific JSON Schema / parse helper functions that do not disturb Google GenAI schemas.
- Modify `backend/prompts/agents.json` and `backend/prompts/runtime_rules.json`: introduce State path discipline and tool-use rules.
- Test in `tests/test_agent_state_memory.py`, `tests/test_data_cross_validator.py`, `tests/test_audit_rules.py`, `tests/test_prompt_data_trust.py`, and `tests/test_provider_workflow.py`.

---

### Task 1: Typed AgentState Blackboard

**Files:**
- Create: `backend/agent_state.py`
- Create: `backend/state_memory.py`
- Test: `tests/test_agent_state_memory.py`

- [x] **Step 1: Write failing tests for state initialization and compatibility sync**

Add `tests/test_agent_state_memory.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from agent_state import AgentReport, RiskFlag, Severity
from state_memory import initialize_agent_state, merge_agent_report, sync_context_from_state, state_view_for


def test_initialize_agent_state_preserves_raw_data_and_identity():
    data = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "company_identity": {"stock_id": "2308", "official_name": "台達電子工業股份有限公司"},
        "revenue_history": [100, 120],
    }

    state = initialize_agent_state(data, run_id="run-1")

    assert state.run_id == "run-1"
    assert state.ticker == "2308.TW"
    assert state.company_name == "台達電"
    assert state.company_identity["stock_id"] == "2308"
    assert state.raw_financial_data["input"]["revenue_history"] == [100, 120]


def test_merge_agent_report_updates_reports_risk_flags_and_legacy_context():
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="run-2")
    flag = RiskFlag(
        id="accounting:fcf_conversion",
        severity=Severity.high,
        category="accounting",
        title="FCF conversion deteriorated",
        evidence_refs=["normalized_financials.cash_flow.free_cash_flow"],
        source_agents=["forensic_accounting"],
        impact="Lower confidence in DCF base case.",
        confidence=0.82,
    )
    report = AgentReport(
        agent_id="forensic_accounting",
        role="財務排雷專家",
        markdown="## 財務排雷\nFCF 轉換率惡化。",
        extracted_facts={"fcf_quality": "weak"},
        risk_flags=[flag],
    )

    state = merge_agent_report(state, report)
    context = {"analyses": {}, "structured_outputs": {}}
    sync_context_from_state(context, state)

    assert state.agent_reports["forensic_accounting"].extracted_facts["fcf_quality"] == "weak"
    assert state.risk_flags[0].id == "accounting:fcf_conversion"
    assert context["analyses"]["forensic_accounting"].startswith("## 財務排雷")
    assert context["agent_state"].ticker == "2330.TW"


def test_state_view_for_valuation_uses_whitelisted_paths_only():
    state = initialize_agent_state({"ticker": "2317.TW", "company_name": "鴻海"}, run_id="run-3")
    state.normalized_financials = {"revenue_history": [100, 110], "secret_debug": "do-not-include"}
    state.quant_metrics = {"calculations": {"dcf_scenarios_default": {"base": {"price_per_share_twd": 100}}}}
    state.peer_context = {"selected_peers": [{"ticker": "4938.TW", "score": 0.74}]}

    view = state_view_for("valuation", state)

    assert view["normalized_financials"]["revenue_history"] == [100, 110]
    assert "secret_debug" not in view["normalized_financials"]
    assert view["peer_context"]["selected_peers"][0]["ticker"] == "4938.TW"
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_agent_state_memory.py -q
```

Expected: FAIL because `agent_state` and `state_memory` modules do not exist.

- [x] **Step 3: Implement Pydantic models**

Create `backend/agent_state.py`:

```python
"""Typed shared state for the multi-agent analysis blackboard."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    high = "high"
    critical = "critical"


class ProviderValue(BaseModel):
    provider: str
    field: str
    value: float | str | None
    unit: str = ""
    period: str | None = None
    statement_type: Literal["consolidated", "parent_only", "unknown"] = "unknown"
    fetched_at: datetime | None = None
    source_url: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)


class ValidationIssue(BaseModel):
    field: str
    severity: Severity
    providers: list[str]
    values: list[ProviderValue] = Field(default_factory=list)
    diff_pct: float = 0.0
    threshold_pct: float = 0.0
    likely_cause: str | None = None
    resolution: str | None = None


class RiskFlag(BaseModel):
    id: str
    severity: Severity
    category: Literal[
        "data_quality",
        "accounting",
        "liquidity",
        "valuation",
        "moat",
        "growth",
        "sentiment",
        "peer_selection",
    ]
    title: str
    evidence_refs: list[str] = Field(default_factory=list)
    source_agents: list[str] = Field(default_factory=list)
    impact: str
    confidence: float = Field(ge=0, le=1)


class AgentReport(BaseModel):
    agent_id: str
    role: str
    markdown: str
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    structured_output: dict[str, Any] | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)


class CircuitBreakerState(BaseModel):
    status: Literal["closed", "open", "half_open"] = "closed"
    blocking_fields: list[str] = Field(default_factory=list)
    attempts: int = 0
    reason: str | None = None


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    run_id: str
    ticker: str
    company_name: str
    company_identity: dict[str, Any] = Field(default_factory=dict)
    raw_financial_data: dict[str, dict[str, Any]] = Field(default_factory=dict)
    provider_values: dict[str, list[ProviderValue]] = Field(default_factory=dict)
    normalized_financials: dict[str, Any] = Field(default_factory=dict)
    source_audit: list[dict[str, Any]] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    circuit_breaker: CircuitBreakerState = Field(default_factory=CircuitBreakerState)
    peer_context: dict[str, Any] = Field(default_factory=dict)
    quant_metrics: dict[str, Any] = Field(default_factory=dict)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    agent_reports: dict[str, AgentReport] = Field(default_factory=dict)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
```

- [x] **Step 4: Implement state helpers and view policies**

Create `backend/state_memory.py`:

```python
"""Shared AgentState initialization, merge, and view helpers."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from agent_state import AgentReport, AgentState


STATE_VIEW_POLICY: dict[str, dict[str, list[str] | dict[str, list[str]]]] = {
    "valuation": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "peer_context": ["selected_peers", "selection_policy", "dynamic_peer_metrics"],
        "root": ["risk_flags", "validation_issues", "tool_results"],
    },
    "final_risk_memo": {
        "normalized_financials": ["revenue_history", "net_income_history", "fcf_history", "cash_flow"],
        "quant_metrics": ["calculations", "unit_contract"],
        "peer_context": ["selected_peers", "selection_policy"],
        "root": ["risk_flags", "validation_issues", "tool_results", "agent_reports"],
    },
}


def initialize_agent_state(data: dict[str, Any], *, run_id: str | None = None) -> AgentState:
    return AgentState(
        run_id=run_id or str(uuid.uuid4()),
        ticker=str(data.get("ticker") or ""),
        company_name=str(data.get("company_name") or data.get("name") or data.get("ticker") or ""),
        company_identity=dict(data.get("company_identity") or {}),
        raw_financial_data={"input": copy.deepcopy(data)},
        normalized_financials=copy.deepcopy(data),
        source_audit=list(data.get("source_audit") or []),
        peer_context={"dynamic_peer_metrics": list(data.get("dynamic_peer_metrics") or [])},
        quant_metrics=dict(data.get("deterministic_financial_tool_results") or {}),
    )


def merge_agent_report(state: AgentState, report: AgentReport) -> AgentState:
    state.agent_reports[report.agent_id] = report
    state.risk_flags.extend(report.risk_flags)
    return state


def sync_context_from_state(context: dict[str, Any], state: AgentState) -> dict[str, Any]:
    context["agent_state"] = state
    analyses = context.setdefault("analyses", {})
    structured_outputs = context.setdefault("structured_outputs", {})
    for agent_id, report in state.agent_reports.items():
        analyses[agent_id] = report.markdown
        if report.structured_output is not None:
            structured_outputs[agent_id] = report.structured_output
    return context


def _pick(mapping: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: copy.deepcopy(mapping[key]) for key in keys if key in mapping}


def state_view_for(role: str | int, state: AgentState) -> dict[str, Any]:
    role_key = str(role)
    if role_key in {"4", "14"}:
        role_key = "valuation"
    if role_key in {"7", "16", "19"}:
        role_key = "final_risk_memo"

    policy = STATE_VIEW_POLICY.get(role_key, {"root": ["validation_issues", "risk_flags"]})
    view: dict[str, Any] = {
        "run_id": state.run_id,
        "ticker": state.ticker,
        "company_name": state.company_name,
        "circuit_breaker": state.circuit_breaker.model_dump(mode="json"),
    }
    for section, keys in policy.items():
        if section == "root":
            for key in keys:
                value = getattr(state, key)
                view[key] = _jsonable(value)
            continue
        value = getattr(state, section)
        if isinstance(value, dict):
            view[section] = _pick(value, list(keys))
    return view


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return copy.deepcopy(value)
```

- [x] **Step 5: Run focused tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_agent_state_memory.py -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/agent_state.py backend/state_memory.py tests/test_agent_state_memory.py
git commit -m "feat: add shared agent state blackboard"
```

---

### Task 2: Data Validation Circuit Breaker

**Files:**
- Modify: `backend/data_financial_metric_validator.py`
- Modify: `backend/pipeline_async.py`
- Test: `tests/test_data_cross_validator.py`

- [x] **Step 1: Add failing circuit-breaker tests**

Append to `tests/test_data_cross_validator.py`:

```python
import pytest

from agent_state import ProviderValue
from data_financial_metric_validator import CircuitBreakerOpen, validate_state_provider_values
from state_memory import initialize_agent_state


def test_validate_state_provider_values_opens_circuit_on_critical_field_conflict():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="validation-1")
    state.provider_values["total_debt"] = [
        ProviderValue(provider="yfinance", field="total_debt", value=100.0, unit="billion_twd", period="2025Q4"),
        ProviderValue(provider="finmind", field="total_debt", value=125.0, unit="billion_twd", period="2025Q4"),
    ]

    state = validate_state_provider_values(state, fields=("total_debt",), threshold_pct=5.0)

    assert state.circuit_breaker.status == "open"
    assert state.circuit_breaker.blocking_fields == ["total_debt"]
    assert state.validation_issues[0].diff_pct == 20.0
    assert state.risk_flags[0].category == "data_quality"


def test_validate_state_provider_values_can_raise_for_hard_stop():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="validation-2")
    state.provider_values["revenue"] = [
        ProviderValue(provider="yfinance", field="revenue", value=100.0, unit="billion_twd", period="2025"),
        ProviderValue(provider="finmind", field="revenue", value=80.0, unit="billion_twd", period="2025"),
    ]

    with pytest.raises(CircuitBreakerOpen):
        validate_state_provider_values(state, fields=("revenue",), threshold_pct=5.0, raise_on_open=True)
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_data_cross_validator.py -q
```

Expected: FAIL because `validate_state_provider_values` is not implemented.

- [x] **Step 3: Implement circuit-breaker helpers**

Add to `backend/data_financial_metric_validator.py` without removing the existing `validate_financial_metrics` API:

```python
from decimal import Decimal

from agent_state import AgentState, ProviderValue, RiskFlag, Severity, ValidationIssue


CRITICAL_FINANCIAL_FIELDS = ("revenue", "net_income", "total_debt", "free_cash_flow")


class CircuitBreakerOpen(Exception):
    def __init__(self, issues: list[ValidationIssue]):
        super().__init__("Critical financial data conflict")
        self.issues = issues


def relative_difference_pct(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0) * 100


def validate_state_provider_values(
    state: AgentState,
    *,
    fields: tuple[str, ...] = CRITICAL_FINANCIAL_FIELDS,
    threshold_pct: float = DIVERGENCE_THRESHOLD_PCT,
    raise_on_open: bool = False,
) -> AgentState:
    blocking: list[ValidationIssue] = []
    for field in fields:
        numeric_values = [
            (item, float(item.value))
            for item in state.provider_values.get(field, [])
            if isinstance(item.value, (int, float, Decimal))
        ]
        if len(numeric_values) < 2:
            continue
        left, right, diff_pct = max(
            (
                (a, b, relative_difference_pct(a_value, b_value))
                for a, a_value in numeric_values
                for b, b_value in numeric_values
                if a.provider < b.provider
            ),
            key=lambda item: item[2],
        )
        if diff_pct <= threshold_pct:
            continue
        issue = ValidationIssue(
            field=field,
            severity=Severity.critical,
            providers=[left.provider, right.provider],
            values=[left, right],
            diff_pct=round(diff_pct, 2),
            threshold_pct=float(threshold_pct),
            likely_cause=_infer_conflict_cause(left, right),
        )
        state.validation_issues.append(issue)
        state.risk_flags.append(RiskFlag(
            id=f"data_conflict:{field}",
            severity=Severity.critical,
            category="data_quality",
            title=f"{field} provider conflict {diff_pct:.2f}%",
            evidence_refs=[f"provider_values.{field}"],
            source_agents=["data_validation"],
            impact="Block valuation and final decision until reconciled.",
            confidence=0.95,
        ))
        blocking.append(issue)

    if blocking:
        state.circuit_breaker.status = "open"
        state.circuit_breaker.blocking_fields = [issue.field for issue in blocking]
        state.circuit_breaker.reason = "critical_provider_conflict"
        if raise_on_open:
            raise CircuitBreakerOpen(blocking)
    else:
        state.circuit_breaker.status = "closed"
        state.circuit_breaker.blocking_fields = []
        state.circuit_breaker.reason = None
    return state


def _infer_conflict_cause(left: ProviderValue, right: ProviderValue) -> str:
    if left.period != right.period:
        return "period_mismatch"
    if left.unit != right.unit:
        return "unit_mismatch"
    if left.statement_type != right.statement_type:
        return "statement_scope_mismatch"
    return "provider_value_mismatch"
```

- [x] **Step 4: Wire validation into `pipeline_async.py`**

After `context` initialization in `run_analysis_pipeline_async`, initialize and validate state:

```python
from data_financial_metric_validator import validate_state_provider_values
from state_memory import initialize_agent_state, sync_context_from_state

context["agent_state"] = initialize_agent_state(data, run_id=context["pipeline_id"])
validate_state_provider_values(context["agent_state"])
sync_context_from_state(context, context["agent_state"])
```

If existing data payload does not yet populate `provider_values`, this call is a no-op. Later provider tasks will populate it.

- [x] **Step 5: Run focused tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_data_cross_validator.py tests/test_agent_state_memory.py -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/data_financial_metric_validator.py backend/pipeline_async.py tests/test_data_cross_validator.py
git commit -m "feat: add financial data circuit breaker"
```

---

### Task 3: Reconciliation Fallback Plan

**Files:**
- Create: `backend/data_reconciliation.py`
- Modify: `backend/pipeline_async.py`
- Test: `tests/test_data_cross_validator.py`

- [x] **Step 1: Add failing reconciliation-plan tests**

Append to `tests/test_data_cross_validator.py`:

```python
from data_reconciliation import build_reconciliation_plan


def test_build_reconciliation_plan_requests_fresh_retry_and_mops_for_blocking_fields():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="reconcile-1")
    state.circuit_breaker.status = "open"
    state.circuit_breaker.blocking_fields = ["revenue", "total_debt"]
    state.circuit_breaker.reason = "critical_provider_conflict"

    plan = build_reconciliation_plan(state)

    assert plan["status"] == "required"
    assert plan["blocking_fields"] == ["revenue", "total_debt"]
    assert plan["steps"][0]["action"] == "fresh_provider_retry"
    assert plan["steps"][1]["action"] == "mops_statement_lookup"
    assert "公開資訊觀測站" in plan["steps"][1]["description"]
    assert plan["resume_condition"]["max_diff_pct"] == 2.0
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_data_cross_validator.py::test_build_reconciliation_plan_requests_fresh_retry_and_mops_for_blocking_fields -q
```

Expected: FAIL because `data_reconciliation` is missing.

- [x] **Step 3: Implement reconciliation plan builder**

Create `backend/data_reconciliation.py`:

```python
"""Fallback planning for financial data conflicts."""

from __future__ import annotations

from typing import Any

from agent_state import AgentState


def build_reconciliation_plan(state: AgentState) -> dict[str, Any]:
    blocking_fields = list(state.circuit_breaker.blocking_fields or [])
    if state.circuit_breaker.status != "open" or not blocking_fields:
        return {
            "status": "not_required",
            "blocking_fields": [],
            "steps": [],
            "resume_condition": {"max_diff_pct": 2.0, "preferred_source": "official_filing"},
        }

    return {
        "status": "required",
        "reason": state.circuit_breaker.reason or "critical_provider_conflict",
        "ticker": state.ticker,
        "company_name": state.company_name,
        "blocking_fields": blocking_fields,
        "steps": [
            {
                "action": "fresh_provider_retry",
                "providers": ["yfinance", "FinMind"],
                "fields": blocking_fields,
                "description": "Bypass cache and refetch conflicting provider fields with unit, period, and statement-scope checks.",
            },
            {
                "action": "mops_statement_lookup",
                "provider": "MOPS",
                "fields": blocking_fields,
                "description": "Search 公開資訊觀測站 for the latest quarterly or annual filing and extract matching consolidated statement values.",
            },
            {
                "action": "source_ranking",
                "description": "Prefer official filings, matching period, matching currency/unit, and consolidated statements over stale third-party API values.",
            },
        ],
        "resume_condition": {
            "max_diff_pct": 2.0,
            "preferred_source": "official_filing",
            "required_resolution": "At least one provider aligns with MOPS or official filing within tolerance.",
        },
        "fail_closed_action": "Render Data Conflict Report and skip valuation/final target prices.",
    }
```

- [x] **Step 4: Store reconciliation plan when pipeline opens the breaker**

Modify `backend/pipeline_async.py` after `validate_state_provider_values(...)`:

```python
from data_reconciliation import build_reconciliation_plan

context["data_reconciliation_plan"] = build_reconciliation_plan(context["agent_state"])
if context["agent_state"].circuit_breaker.status == "open":
    context.setdefault("blocking_issues", []).append(
        "關鍵財務欄位跨來源衝突，已建立 MOPS reconciliation plan，暫停估值。"
    )
```

- [x] **Step 5: Run focused tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_data_cross_validator.py -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/data_reconciliation.py backend/pipeline_async.py tests/test_data_cross_validator.py
git commit -m "feat: add data reconciliation fallback plan"
```

---

### Task 4: State Views In Agent Prompts

**Files:**
- Modify: `backend/agent_runtime/prompting.py`
- Modify: `backend/prompts/agents.json`
- Modify: `backend/prompts/runtime_rules.json`
- Test: `tests/test_prompt_data_trust.py`
- Test: `tests/test_audit_rules.py`

- [x] **Step 1: Write failing prompt tests**

Add to `tests/test_prompt_data_trust.py`:

```python
from agent_runtime.prompting import build_prompt
from state_memory import initialize_agent_state


def test_valuation_prompt_includes_state_view_and_deemphasizes_previous_summary():
    data = {"ticker": "2308.TW", "company_name": "台達電", "revenue_history": [100, 120]}
    state = initialize_agent_state(data, run_id="prompt-1")
    state.quant_metrics = {"calculations": {"dcf_scenarios_default": {"base": {"price_per_share_twd": 100}}}}
    context = {
        "analyses": {1: "早期商業模式完整分析 " * 200},
        "structured_outputs": {},
        "agent_state": state,
    }

    prompt = build_prompt(4, data, context)

    assert "AgentState view" in prompt
    assert '"quant_metrics"' in prompt
    assert "你不再讀取前序摘要" in prompt
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_prompt_data_trust.py::test_valuation_prompt_includes_state_view_and_deemphasizes_previous_summary -q
```

Expected: FAIL because prompts do not include `state_view`.

- [x] **Step 3: Add state view rendering in prompt builder**

Modify `backend/agent_runtime/prompting.py`:

```python
import json
from state_memory import state_view_for


def build_state_view_section(agent_num: int, context: AnalysisContext) -> str:
    state = context.get("agent_state")
    if state is None:
        return ""
    view = state_view_for(agent_num, state)
    return (
        "【AgentState view】\n"
        "你不再讀取前序摘要作為主要資料來源；請直接引用下列 State path。\n"
        f"{json.dumps(view, ensure_ascii=False, indent=2, default=str)}"
    )
```

In `build_prompt()`, compute `state_view_section = build_state_view_section(agent_num, context)` and include it before `structured_instruction`:

```python
prompt_parts = [
    analysis_prompt,
    state_view_section,
    rag_context,
    ...
]
```

- [x] **Step 4: Update valuation prompt wording**

Modify Agent 4 and Agent 14 in `backend/prompts/agents.json` so each starts with:

```text
你會收到 AgentState view。請以 AgentState view 的 normalized_financials、quant_metrics、peer_context、risk_flags、validation_issues 為主要依據；前序分析只能作為 agent_reports 或 {prev} 的輔助交叉檢查，不得取代原始資料。
若 circuit_breaker.status 不是 closed，必須先列 data_quality_blockers，不得輸出目標股價。
```

- [x] **Step 5: Add runtime rule for State path citation**

In `backend/prompts/runtime_rules.json`, add a shared rule under valuation agents:

```json
"正式報告中的關鍵數字必須能追溯到 AgentState view 的 state path，例如 normalized_financials、quant_metrics、peer_context 或 tool_results；不可只引用前序摘要。"
```

- [x] **Step 6: Run prompt tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_prompt_data_trust.py tests/test_audit_rules.py::AuditRuleTests::test_previous_context_uses_relevant_slices_instead_of_full_context -q
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add backend/agent_runtime/prompting.py backend/prompts/agents.json backend/prompts/runtime_rules.json tests/test_prompt_data_trust.py
git commit -m "feat: add state views to agent prompts"
```

---

### Task 5: Peer Selection Ranking

**Files:**
- Modify: `backend/data_fetch/market_sources/peers.py`
- Test: `tests/test_provider_workflow.py`

- [x] **Step 1: Add failing peer-selection tests**

Append to `tests/test_provider_workflow.py`:

```python
from data_fetch.market_sources.peers import CompanyProfile, rank_peer_candidates, select_peer_profiles


def test_peer_selection_filters_market_cap_outliers_and_scores_business_overlap():
    target = CompanyProfile(
        ticker="2308.TW",
        name="台達電",
        gics_code="20104010",
        market="TW",
        market_cap_twd=5_000_000_000_000,
        revenue_twd=400_000_000_000,
        business_tags={"power", "thermal", "industrial_automation"},
        product_keywords={"power_supply", "cooling"},
        segment_revenue_tags={"datacenter_power"},
    )
    micro_cap = CompanyProfile("2429.TW", "銘旺科", "20104010", "TW", 4_000_000_000, 2_000_000_000, {"electronics"}, {"cable"}, set())
    global_peer = CompanyProfile("ETN", "Eaton", "20104010", "US", 4_500_000_000_000, 950_000_000_000, {"power", "industrial_automation"}, {"power_supply"}, {"datacenter_power"})

    ranked = rank_peer_candidates(target, [micro_cap, global_peer])

    assert [row["ticker"] for row in ranked] == ["ETN"]
    assert ranked[0]["market_cap_ratio"] == 0.9
    assert ranked[0]["score"] > 0.55


def test_select_peer_profiles_expands_globally_when_local_peers_are_insufficient():
    target = CompanyProfile("2308.TW", "台達電", "20104010", "TW", 5_000_000_000_000, 400_000_000_000, {"power"}, {"power_supply"}, set())
    local_bad = CompanyProfile("9999.TW", "微型同業", "20104010", "TW", 1_000_000_000, 1_000_000_000, {"power"}, {"power_supply"}, set())
    global_good = CompanyProfile("ETN", "Eaton", "20104010", "US", 4_500_000_000_000, 950_000_000_000, {"power"}, {"power_supply"}, set())

    result = select_peer_profiles(target, [local_bad, global_good], min_peers=1)

    assert result["expansion_used"] is True
    assert result["selected_peers"][0]["ticker"] == "ETN"
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_provider_workflow.py::test_peer_selection_filters_market_cap_outliers_and_scores_business_overlap tests/test_provider_workflow.py::test_select_peer_profiles_expands_globally_when_local_peers_are_insufficient -q
```

Expected: FAIL because `CompanyProfile`, `rank_peer_candidates`, and `select_peer_profiles` are missing.

- [x] **Step 3: Implement ranking primitives**

Add to `backend/data_fetch/market_sources/peers.py`:

```python
from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name: str
    gics_code: str | None
    market: str
    market_cap_twd: float | None
    revenue_twd: float | None
    business_tags: set[str]
    product_keywords: set[str]
    segment_revenue_tags: set[str]


def _gics_distance(left: str | None, right: str | None) -> int:
    if not left or not right:
        return 99
    if left == right:
        return 0
    if left[:6] == right[:6]:
        return 1
    if left[:4] == right[:4]:
        return 2
    if left[:2] == right[:2]:
        return 3
    return 99


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _ratio_in_band(value: float | None, target: float | None, low: float, high: float) -> bool:
    if not value or not target or target <= 0:
        return False
    ratio = value / target
    return low <= ratio <= high


def _peer_score(target: CompanyProfile, candidate: CompanyProfile) -> float:
    gics_distance = _gics_distance(target.gics_code, candidate.gics_code)
    if gics_distance > 2:
        return -1
    if not _ratio_in_band(candidate.market_cap_twd, target.market_cap_twd, 0.2, 5.0):
        return -1
    market_cap_ratio = candidate.market_cap_twd / target.market_cap_twd
    market_cap_score = 1 - min(abs(log(market_cap_ratio)), log(5)) / log(5)
    revenue_score = 0.0
    if _ratio_in_band(candidate.revenue_twd, target.revenue_twd, 0.2, 5.0):
        revenue_ratio = candidate.revenue_twd / target.revenue_twd
        revenue_score = 1 - min(abs(log(revenue_ratio)), log(5)) / log(5)
    business_score = max(
        _overlap_score(target.business_tags, candidate.business_tags),
        _overlap_score(target.product_keywords, candidate.product_keywords),
        _overlap_score(target.segment_revenue_tags, candidate.segment_revenue_tags),
    )
    gics_score = {0: 1.0, 1: 0.85, 2: 0.65}.get(gics_distance, 0.0)
    return round(0.30 * gics_score + 0.25 * market_cap_score + 0.20 * revenue_score + 0.25 * business_score, 4)


def rank_peer_candidates(target: CompanyProfile, candidates: list[CompanyProfile]) -> list[dict]:
    rows = []
    for candidate in candidates:
        score = _peer_score(target, candidate)
        if score < 0:
            continue
        rows.append({
            "ticker": candidate.ticker,
            "name": candidate.name,
            "market": candidate.market,
            "score": score,
            "market_cap_ratio": round(candidate.market_cap_twd / target.market_cap_twd, 3) if candidate.market_cap_twd and target.market_cap_twd else None,
            "business_overlap": round(_overlap_score(target.business_tags, candidate.business_tags), 4),
            "product_overlap": round(_overlap_score(target.product_keywords, candidate.product_keywords), 4),
        })
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def select_peer_profiles(target: CompanyProfile, universe: list[CompanyProfile], *, min_peers: int = 5) -> dict:
    local_ranked = rank_peer_candidates(target, [candidate for candidate in universe if candidate.market == target.market])
    selected = [row for row in local_ranked if row["score"] >= 0.55]
    expansion_used = False
    if len(selected) < min_peers:
        global_ranked = rank_peer_candidates(target, [candidate for candidate in universe if candidate.market != target.market])
        selected.extend(row for row in global_ranked if row["score"] >= 0.55)
        expansion_used = True
    return {
        "selected_peers": sorted(selected, key=lambda row: row["score"], reverse=True)[:min_peers],
        "expansion_used": expansion_used,
        "selection_policy": {
            "gics_distance_max": 2,
            "market_cap_band": "0.2x-5.0x",
            "revenue_band_preferred": "0.2x-5.0x",
            "minimum_score": 0.55,
        },
    }
```

- [x] **Step 4: Integrate ranking into existing `fetch_dynamic_peer_metrics`**

Keep existing yfinance fetching, but add `selection_policy` metadata to returned records when profile data is available. Do not remove the old fallback path because many tickers lack GICS/revenue metadata.

- [x] **Step 5: Run focused tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_provider_workflow.py -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/data_fetch/market_sources/peers.py tests/test_provider_workflow.py
git commit -m "feat: improve peer selection ranking"
```

---

### Task 6: Structured Output Provider Adapters

**Files:**
- Modify: `backend/structured_output_models.py`
- Create: `backend/openai_structured_outputs.py`
- Test: `tests/test_audit_rules.py`

- [x] **Step 1: Add failing tests for Google/OpenAI schema split**

Append inside `AuditRuleTests` in `tests/test_audit_rules.py`:

```python
from openai_structured_outputs import openai_json_schema_response_format
from structured_output_models import PriceTargetStructuredOutput


def test_openai_structured_output_schema_is_strict_without_changing_genai_schema():
    genai_schema = PriceTargetStructuredOutput.model_json_schema(by_alias=True)
    openai_format = openai_json_schema_response_format("price_target", PriceTargetStructuredOutput)

    assert "additionalProperties" not in json.dumps(genai_schema, ensure_ascii=False)
    assert openai_format["type"] == "json_schema"
    assert openai_format["json_schema"]["strict"] is True
    assert '"additionalProperties": false' in json.dumps(openai_format, ensure_ascii=False)
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_audit_rules.py::AuditRuleTests::test_openai_structured_output_schema_is_strict_without_changing_genai_schema -q
```

Expected: FAIL because `openai_structured_outputs` is missing.

- [x] **Step 3: Implement OpenAI schema adapter**

Create `backend/openai_structured_outputs.py`:

```python
"""OpenAI-specific Structured Outputs helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def openai_json_schema_response_format(name: str, model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema(by_alias=True)
    _force_no_extra_properties(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": schema,
        },
    }


def _force_no_extra_properties(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
        for value in node.values():
            _force_no_extra_properties(value)
    elif isinstance(node, list):
        for value in node:
            _force_no_extra_properties(value)
```

- [x] **Step 4: Export helper through compatibility facade**

If callers prefer a single import path, add `openai_json_schema_response_format` to `backend/structured_outputs.py` imports and `__all__`.

- [x] **Step 5: Run focused structured output tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_audit_rules.py::AuditRuleTests::test_structured_agents_use_native_response_schema tests/test_audit_rules.py::AuditRuleTests::test_structured_schema_omits_additional_properties_for_genai tests/test_audit_rules.py::AuditRuleTests::test_openai_structured_output_schema_is_strict_without_changing_genai_schema -q
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/structured_output_models.py backend/openai_structured_outputs.py backend/structured_outputs.py tests/test_audit_rules.py
git commit -m "feat: add openai structured output adapter"
```

---

### Task 7: Financial Tool Calling Extensions

**Files:**
- Modify: `backend/financial_tools.py`
- Modify: `backend/agent_runtime/routing.py`
- Modify: `backend/prompts/runtime_rules.json`
- Test: `tests/test_audit_rules.py`

- [x] **Step 1: Add failing financial tool tests**

Append inside `AuditRuleTests` in `tests/test_audit_rules.py`:

```python
def test_implied_revenue_growth_tool_reverse_engineers_forward_eps():
    result = financial_tools.calculate_implied_revenue_growth(
        target_eps_twd=20,
        current_net_margin_pct=10,
        shares_outstanding=1_000_000_000,
        current_revenue_billion_twd=100,
        forecast_years=2,
    )

    assert result["required_revenue_billion_twd"] == 200.0
    assert round(result["implied_revenue_cagr_pct"], 2) == 41.42


def test_valuation_agents_register_implied_growth_tool():
    assert "calculate_implied_revenue_growth" in [tool.__name__ for tool in ar.get_agent_function_tools(4)]
    assert "calculate_implied_revenue_growth" in [tool.__name__ for tool in ar.get_agent_function_tools(14)]
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_audit_rules.py::AuditRuleTests::test_implied_revenue_growth_tool_reverse_engineers_forward_eps tests/test_audit_rules.py::AuditRuleTests::test_valuation_agents_register_implied_growth_tool -q
```

Expected: FAIL because the tool does not exist and is not registered.

- [x] **Step 3: Implement tools**

Add to `backend/financial_tools.py`:

```python
def calculate_implied_revenue_growth(
    target_eps_twd: float,
    current_net_margin_pct: float,
    shares_outstanding: float,
    current_revenue_billion_twd: float,
    forecast_years: int = 1,
) -> dict:
    if target_eps_twd <= 0:
        return {"error": "target_eps_twd must be positive"}
    if current_net_margin_pct <= 0:
        return {"error": "current_net_margin_pct must be positive"}
    if shares_outstanding <= 0:
        return {"error": "shares_outstanding must be positive"}
    if current_revenue_billion_twd <= 0:
        return {"error": "current_revenue_billion_twd must be positive"}
    if forecast_years <= 0:
        return {"error": "forecast_years must be positive"}

    required_net_income_billion_twd = target_eps_twd * shares_outstanding / 1e9
    required_revenue_billion_twd = required_net_income_billion_twd / (current_net_margin_pct / 100)
    implied_cagr_pct = ((required_revenue_billion_twd / current_revenue_billion_twd) ** (1 / forecast_years) - 1) * 100
    return {
        "target_eps_twd": round(target_eps_twd, 4),
        "current_net_margin_pct": round(current_net_margin_pct, 4),
        "shares_outstanding": round(shares_outstanding, 4),
        "current_revenue_billion_twd": round(current_revenue_billion_twd, 4),
        "forecast_years": forecast_years,
        "required_net_income_billion_twd": round(required_net_income_billion_twd, 4),
        "required_revenue_billion_twd": round(required_revenue_billion_twd, 4),
        "implied_revenue_cagr_pct": round(implied_cagr_pct, 4),
    }
```

- [x] **Step 4: Register tool for valuation agents**

Modify `backend/agent_runtime/routing.py`:

```python
from financial_tools import calculate_cagr, calculate_dcf, calculate_ddm, calculate_implied_revenue_growth, calculate_wacc

...
if agent_num in {4, 14}:
    return [calculate_cagr, calculate_wacc, calculate_dcf, calculate_ddm, calculate_implied_revenue_growth]
```

- [x] **Step 5: Update tool-use prompt rule**

In `backend/prompts/runtime_rules.json`, add:

```json
"若 Forward EPS 或市場共識 EPS 隱含極端成長，必須呼叫 calculate_implied_revenue_growth，並在正式輸出引用工具回傳的 implied_revenue_cagr_pct。"
```

- [x] **Step 6: Run focused tests**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_audit_rules.py::AuditRuleTests::test_implied_revenue_growth_tool_reverse_engineers_forward_eps tests/test_audit_rules.py::AuditRuleTests::test_valuation_agents_register_implied_growth_tool tests/test_audit_rules.py::AuditRuleTests::test_agent_function_tools_are_registered -q
```

Expected: PASS after updating the existing expected tool list in `test_agent_function_tools_are_registered`.

- [x] **Step 7: Commit**

```bash
git add backend/financial_tools.py backend/agent_runtime/routing.py backend/prompts/runtime_rules.json tests/test_audit_rules.py
git commit -m "feat: add implied growth valuation tool"
```

---

### Task 8: End-To-End Guardrails And Final Verification

**Files:**
- Modify: `tests/test_audit_rules.py`
- Modify: `tests/test_prompt_data_trust.py`
- Modify: `docs/architecture.md`
- All touched implementation files.

- [x] **Step 1: Add regression tests for blocked valuation**

Add a focused test that constructs a context with `agent_state.circuit_breaker.status == "open"` and asserts Agent 4 prompt includes the blocker and valuation output rules forbid target price generation.

- [x] **Step 2: Update architecture docs**

Append this section to `docs/architecture.md`:

```markdown
## Agent Blackboard

The analysis runtime keeps a typed `AgentState` at `context["agent_state"]`. It stores raw provider data, normalized financials, validation issues, risk flags, full agent reports, structured outputs, peer context, and deterministic tool results. Prompts receive role-specific `state_view` slices so downstream agents can cite raw or validated state paths instead of relying on compressed `{prev}` summaries.

Critical provider conflicts in Revenue, Net Income, Total Debt, or Free Cash Flow open a data circuit breaker. While open, valuation and final risk nodes must treat the run as blocked or reconciled before producing price targets.
```

- [x] **Step 3: Run focused test suite**

Run:

```bash
PYTHON_BIN=$(scripts/project_python.sh); "$PYTHON_BIN" -m pytest tests/test_agent_state_memory.py tests/test_data_cross_validator.py tests/test_prompt_data_trust.py tests/test_provider_workflow.py tests/test_audit_rules.py -q
```

Expected: PASS.

- [x] **Step 4: Run project CI gate**

Run:

```bash
scripts/ci_gate.sh
```

Expected: PASS. If this is too slow for the current machine, run the focused suite above and record the skipped CI reason in the final response.

- [x] **Step 5: Inspect diff**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` has no output; `git status --short` only lists intended files.

- [x] **Step 6: Commit final integration**

```bash
git add backend docs tests
git commit -m "feat: integrate stategraph guardrails"
```

---

## Self-Review Notes

- Spec coverage: Tasks 1 and 4 cover StateGraph/shared memory and prompt rewrites; Task 2 covers Data Validation Agent and circuit breaker; Task 3 covers retry/MOPS reconciliation fallback; Task 5 covers peer selection; Task 6 covers structured outputs; Task 7 covers function calling; Task 8 covers docs and verification.
- Scope control: The plan keeps the existing DAG runner and report renderer intact. Full LangGraph migration is intentionally deferred because the spec recommends a compatibility facade first.
- Provider split: Google GenAI schema behavior is preserved while OpenAI strict JSON schema is isolated in `openai_structured_outputs.py`.
