import asyncio
import logging
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_cross_validator import validate_financial_metrics  # noqa: E402
import pytest  # noqa: E402

from agent_state import ProviderValue, Severity, ValidationIssue  # noqa: E402
from config import API_KEY_SETUP_MESSAGE  # noqa: E402
from data_financial_metric_validator import (  # noqa: E402
    CircuitBreakerOpen,
    load_provider_values_from_payload,
    validate_state_provider_values,
)
from data_reconciliation import build_reconciliation_plan, reconcile_with_official_filing  # noqa: E402
from pipeline_async import run_analysis_pipeline_async  # noqa: E402
from state_memory import initialize_agent_state  # noqa: E402
from workflow_graph import (
    create_default_workflow_services,
    initialize_graph_state,
    legacy_context_from_graph,
    repair_graph_state,
    run_analysis_workflow,
)  # noqa: E402


def test_taiwan_small_cap_cross_validation_uses_wider_dynamic_thresholds():
    from data_cross_validator import cross_validate_sources

    result = cross_validate_sources(
        {"ticker": "1234.TW", "market_cap_raw": 5_000_000_000, "current_price": 100},
        {"twse": {"market_cap_raw": 4_000_000_000, "current_price": 70}},
    )

    assert result["thresholds"] == {"divergence_pct": 12.0, "conflict_pct": 40.0}
    assert result["overall_verdict"] == "divergent"
    assert result["fields"]["current_price"]["verdict"] == "divergent"
    assert result["conflict_fields"] == []


def test_validate_financial_metrics_marks_high_discrepancy_and_reduces_trust(caplog):
    payload = {
        "ticker": "2330.TW",
        "financial_metrics": {
            "eps": {"value": 10.0, "trust_score": 92, "flags": []},
        },
    }

    with caplog.at_level(logging.WARNING):
        validated = validate_financial_metrics(
            payload,
            {"eps": 10.0, "monthly_revenue": 100.0},
            {"eps": 10.8, "monthly_revenue": 103.0},
            source_a_name="TWSE",
            source_b_name="Yahoo",
        )

    eps = validated["financial_metrics"]["eps"]
    revenue = validated["financial_metrics"]["monthly_revenue"]

    assert eps["trust_score"] <= 50
    assert "High_Discrepancy" in eps["flags"]
    assert eps["discrepancy"]["source_a"] == "TWSE"
    assert eps["discrepancy"]["source_b"] == "Yahoo"
    assert revenue["trust_score"] > eps["trust_score"]
    assert "High_Discrepancy" not in revenue["flags"]
    assert any("eps" in record.message and "TWSE" in record.message for record in caplog.records)


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


def test_open_breaker_fetches_mops_and_resolves_matching_debt(monkeypatch):
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="reconcile-mops")
    state.provider_values["total_debt"] = [
        ProviderValue(provider="yfinance", field="total_debt", value=900.0, unit="thousand_twd", period="2025Q4"),
        ProviderValue(provider="finmind", field="total_debt", value=920.0, unit="thousand_twd", period="2025Q4"),
    ]
    validate_state_provider_values(state, fields=("total_debt",), threshold_pct=1.0)
    monkeypatch.setattr(
        "data_reconciliation.fetch_mops_balance_sheet",
        lambda *_args, **_kwargs: {
            "source": "MOPS",
            "unit": "thousand_twd",
            "statement_scope": "consolidated",
            "year": 2025,
            "season": 4,
            "total_liabilities": 910.0,
        },
    )

    result = reconcile_with_official_filing(state, year=2025, season=4, tolerance_pct=2.0)

    assert result["status"] == "resolved"
    assert state.provider_values["total_debt"][-1].provider == "MOPS"
    assert state.raw_financial_data["official_filings"][0]["source"] == "MOPS"
    assert state.circuit_breaker.status == "closed"
    assert state.validation_issues == []


def test_unknown_mops_unit_keeps_breaker_open(monkeypatch):
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="reconcile-open")
    state.provider_values["total_debt"] = [
        ProviderValue(provider="yfinance", field="total_debt", value=100.0, unit="thousand_twd", period="2025Q4"),
        ProviderValue(provider="finmind", field="total_debt", value=130.0, unit="thousand_twd", period="2025Q4"),
    ]
    validate_state_provider_values(state, fields=("total_debt",), threshold_pct=5.0)
    monkeypatch.setattr(
        "data_reconciliation.fetch_mops_balance_sheet",
        lambda *_args, **_kwargs: {"source": "MOPS", "unit": "unknown", "total_liabilities": 115.0},
    )

    result = reconcile_with_official_filing(state, year=2025, season=4)

    assert result["status"] == "unresolved"
    assert state.circuit_breaker.status == "open"
    assert "official_filings" not in state.raw_financial_data


def test_mops_value_without_provider_alignment_keeps_breaker_open(monkeypatch):
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="reconcile-mismatch")
    state.provider_values["total_debt"] = [
        ProviderValue(provider="yfinance", field="total_debt", value=100.0, unit="thousand_twd", period="2025Q4"),
        ProviderValue(provider="finmind", field="total_debt", value=130.0, unit="thousand_twd", period="2025Q4"),
    ]
    validate_state_provider_values(state, fields=("total_debt",), threshold_pct=5.0)
    monkeypatch.setattr(
        "data_reconciliation.fetch_mops_balance_sheet",
        lambda *_args, **_kwargs: {
            "source": "MOPS",
            "unit": "thousand_twd",
            "statement_scope": "consolidated",
            "year": 2025,
            "season": 4,
            "total_liabilities": 500.0,
        },
    )

    result = reconcile_with_official_filing(state, year=2025, season=4, tolerance_pct=2.0)

    assert result["status"] == "unresolved"
    assert result["reason"] == "no_provider_aligned_with_official"
    assert state.circuit_breaker.status == "open"
    assert "official_filings" not in state.raw_financial_data


def test_mops_alignment_requires_unit_period_and_statement_scope(monkeypatch):
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="reconcile-metadata")
    state.provider_values["total_debt"] = [
        ProviderValue(
            provider="yfinance",
            field="total_debt",
            value=900.0,
            unit="billion_twd",
            period="2024Q4",
            statement_type="parent_only",
        ),
        ProviderValue(provider="finmind", field="total_debt", value=1300.0, unit="billion_twd", period="2024Q4"),
    ]
    validate_state_provider_values(state, fields=("total_debt",), threshold_pct=5.0)
    monkeypatch.setattr(
        "data_reconciliation.fetch_mops_balance_sheet",
        lambda *_args, **_kwargs: {
            "source": "MOPS",
            "unit": "thousand_twd",
            "statement_scope": "consolidated",
            "year": 2025,
            "season": 4,
            "total_liabilities": 900.0,
        },
    )

    result = reconcile_with_official_filing(state, year=2025, season=4, tolerance_pct=2.0)

    assert result["status"] == "unresolved"
    assert state.circuit_breaker.status == "open"
    assert "official_filings" not in state.raw_financial_data


def test_mixed_blocking_fields_remain_fail_closed(monkeypatch):
    state = initialize_agent_state({"ticker": "2330.TW", "company_name": "台積電"}, run_id="reconcile-mixed")
    state.provider_values["total_debt"] = [
        ProviderValue(provider="yfinance", field="total_debt", value=900.0, unit="thousand_twd", period="2025Q4"),
        ProviderValue(provider="finmind", field="total_debt", value=1000.0, unit="thousand_twd", period="2025Q4"),
    ]
    state.provider_values["revenue"] = [
        ProviderValue(provider="yfinance", field="revenue", value=100.0),
        ProviderValue(provider="finmind", field="revenue", value=80.0),
    ]
    validate_state_provider_values(state, fields=("total_debt", "revenue"), threshold_pct=5.0)
    monkeypatch.setattr(
        "data_reconciliation.fetch_mops_balance_sheet",
        lambda *_args, **_kwargs: {
            "source": "MOPS",
            "unit": "thousand_twd",
            "statement_scope": "consolidated",
            "year": 2025,
            "season": 4,
            "total_liabilities": 900.0,
        },
    )

    result = reconcile_with_official_filing(state, year=2025, season=4)

    assert result["status"] == "unsupported"
    assert set(result["blocking_fields"]) == {"total_debt", "revenue"}
    assert state.circuit_breaker.status == "open"


def test_load_provider_values_from_payload_bridges_existing_comparisons_to_circuit_breaker():
    payload = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "financial_metric_validation": {
            "comparisons": {
                "total_debt": {
                    "field": "total_debt",
                    "source_a": "yfinance",
                    "source_b": "finmind",
                    "source_a_value": 100.0,
                    "source_b_value": 125.0,
                    "threshold_pct": 5.0,
                },
            },
        },
    }
    state = initialize_agent_state(payload, run_id="validation-bridge")

    state = load_provider_values_from_payload(state, payload)
    state = validate_state_provider_values(state, fields=("total_debt",), threshold_pct=5.0)

    assert [value.provider for value in state.provider_values["total_debt"]] == ["yfinance", "finmind"]
    assert state.circuit_breaker.status == "open"
    assert state.circuit_breaker.blocking_fields == ["total_debt"]


def test_validate_state_provider_values_is_idempotent_for_same_conflict():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="validation-idempotent")
    state.provider_values["revenue"] = [
        ProviderValue(provider="yfinance", field="revenue", value=100.0),
        ProviderValue(provider="finmind", field="revenue", value=80.0),
    ]

    validate_state_provider_values(state, fields=("revenue",), threshold_pct=5.0)
    validate_state_provider_values(state, fields=("revenue",), threshold_pct=5.0)

    assert len(state.validation_issues) == 1
    assert len(state.risk_flags) == 1
    assert state.circuit_breaker.blocking_fields == ["revenue"]


def test_validate_state_provider_values_clears_stale_conflict_when_values_align():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="validation-clear")
    state.provider_values["free_cash_flow"] = [
        ProviderValue(provider="yfinance", field="free_cash_flow", value=100.0),
        ProviderValue(provider="finmind", field="free_cash_flow", value=80.0),
    ]
    validate_state_provider_values(state, fields=("free_cash_flow",), threshold_pct=5.0)

    state.provider_values["free_cash_flow"] = [
        ProviderValue(provider="yfinance", field="free_cash_flow", value=100.0),
        ProviderValue(provider="finmind", field="free_cash_flow", value=99.0),
    ]
    validate_state_provider_values(state, fields=("free_cash_flow",), threshold_pct=5.0)

    assert state.validation_issues == []
    assert state.risk_flags == []
    assert state.circuit_breaker.status == "closed"
    assert state.circuit_breaker.blocking_fields == []
    assert state.circuit_breaker.reason is None


def test_validate_state_provider_values_preserves_external_same_field_issue():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="validation-preserve")
    state.validation_issues.append(
        ValidationIssue(
            field="revenue",
            severity=Severity.warning,
            providers=["manual"],
            likely_cause="manual_review",
        )
    )
    state.provider_values["revenue"] = [
        ProviderValue(provider="yfinance", field="revenue", value=100.0),
        ProviderValue(provider="finmind", field="revenue", value=99.0),
    ]

    validate_state_provider_values(state, fields=("revenue",), threshold_pct=5.0)

    assert len(state.validation_issues) == 1
    assert state.validation_issues[0].likely_cause == "manual_review"
    assert state.circuit_breaker.status == "closed"


def test_validate_state_provider_values_attempts_ignore_blocking_field_order():
    state = initialize_agent_state({"ticker": "2308.TW", "company_name": "台達電"}, run_id="validation-attempts")
    state.provider_values["revenue"] = [
        ProviderValue(provider="yfinance", field="revenue", value=100.0),
        ProviderValue(provider="finmind", field="revenue", value=80.0),
    ]
    state.provider_values["total_debt"] = [
        ProviderValue(provider="yfinance", field="total_debt", value=100.0),
        ProviderValue(provider="finmind", field="total_debt", value=125.0),
    ]

    validate_state_provider_values(state, fields=("revenue", "total_debt"), threshold_pct=5.0)
    attempts = state.circuit_breaker.attempts
    validate_state_provider_values(state, fields=("total_debt", "revenue"), threshold_pct=5.0)

    assert state.circuit_breaker.attempts == attempts
    assert set(state.circuit_breaker.blocking_fields) == {"revenue", "total_debt"}


def test_pipeline_state_initialization_surfaces_open_circuit_as_blocking_issue():
    payload = {
        "ticker": "2308.TW",
        "company_name": "台達電",
        "financial_metric_validation": {
            "comparisons": {
                "revenue": {
                    "field": "revenue",
                    "source_a": "yfinance",
                    "source_b": "finmind",
                    "source_a_value": 100.0,
                    "source_b_value": 80.0,
                },
            },
        },
    }
    graph_state = initialize_graph_state(payload, pipeline_id="v1")
    context = legacy_context_from_graph(
        graph_state,
        create_default_workflow_services(rotator=object(), progress_callback=None),
    )

    assert context["agent_state"].circuit_breaker.status == "open"
    assert graph_state["tool_results"]["data_reconciliation_plan"]["status"] == "required"
    assert graph_state["tool_results"]["data_reconciliation_plan"]["steps"][1]["action"] == "mops_statement_lookup"


def test_pipeline_state_initialization_resumes_when_mops_reconciles(monkeypatch):
    payload = {
        "ticker": "2330.TW",
        "company_name": "台積電",
        "financial_metric_validation": {
            "comparisons": {
                "total_debt": {
                    "field": "total_debt",
                    "source_a": "yfinance",
                    "source_b": "finmind",
                    "source_a_value": 900.0,
                    "source_b_value": 1000.0,
                },
            },
        },
    }
    monkeypatch.setattr(
        "data_reconciliation.fetch_mops_balance_sheet",
        lambda *_args, **_kwargs: {
            "source": "MOPS",
            "unit": "thousand_twd",
            "statement_scope": "consolidated",
            "year": 2025,
            "season": 4,
            "total_liabilities": 900.0,
        },
    )
    graph_state = initialize_graph_state(payload, pipeline_id="v1")
    repaired = repair_graph_state(graph_state)
    context = legacy_context_from_graph(
        repaired,
        create_default_workflow_services(rotator=object(), progress_callback=None),
    )

    assert context["agent_state"].circuit_breaker.status == "closed"
    assert repaired["tool_results"]["official_reconciliation"]["status"] == "resolved"
    assert context["blocking_issues"] == []


def test_graph_open_validation_blocks_agent_execution(monkeypatch):
    called = False

    async def fake_run_agent(*_args, **_kwargs):
        nonlocal called
        called = True
        return {}

    services = replace(
        create_default_workflow_services(rotator=object(), progress_callback=None),
        validate=lambda _state: {
            "circuit_breaker": {"status": "open", "blocking_fields": ["revenue"]},
            "validation_issues": [{"field": "revenue", "severity": "critical", "providers": ["a", "b"]}],
        },
        repair=lambda _state: {},
        run_agent=fake_run_agent,
    )

    result = asyncio.run(
        run_analysis_workflow(
            initial_state=initialize_graph_state({"ticker": "2308.TW", "company_name": "台達電"}, pipeline_id="v4"),
            pipeline_id="v4",
            services=services,
        )
    )

    assert called is False
    assert result["status"] == "blocked"


def test_run_analysis_pipeline_async_delegates_to_graph_runner(monkeypatch):
    from agent_runtime import AnalysisResult

    class FakeRunner:
        async def run_async(self, request):
            return AnalysisResult(
                context={
                    "ticker": request.data["ticker"],
                    "company_name": request.data["company_name"],
                    "pipeline_id": request.pipeline_id,
                    "blocking_issues": ["Critical financial provider conflict blocks analysis."],
                    "total_time": 0.1,
                },
                pipeline_id=request.pipeline_id,
    )

    monkeypatch.setattr("pipeline_async.AnalysisPipelineRunner", lambda: FakeRunner())
    monkeypatch.setattr("pipeline_async.has_api_keys", lambda: True)

    context = asyncio.run(
        run_analysis_pipeline_async({"ticker": "2308.TW", "company_name": "台達電"})
    )

    assert context["blocking_issues"] == ["Critical financial provider conflict blocks analysis."]
    assert "total_time" in context


def test_run_analysis_pipeline_requires_api_key_when_initial_data_is_not_blocked(monkeypatch):
    monkeypatch.setattr("pipeline_async.has_api_keys", lambda: False)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(run_analysis_pipeline_async({"ticker": "2308.TW", "company_name": "台達電"}))

    assert str(exc_info.value) == API_KEY_SETUP_MESSAGE
