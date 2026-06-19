import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_cross_validator import validate_financial_metrics  # noqa: E402
import pytest  # noqa: E402

from agent_state import ProviderValue  # noqa: E402
from data_financial_metric_validator import (  # noqa: E402
    CircuitBreakerOpen,
    load_provider_values_from_payload,
    validate_state_provider_values,
)
from state_memory import initialize_agent_state  # noqa: E402


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
