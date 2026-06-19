import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_cross_validator import validate_financial_metrics  # noqa: E402


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
