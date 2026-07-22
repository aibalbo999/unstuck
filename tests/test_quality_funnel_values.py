import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


from quality_funnel_values import first_number, format_metric_value  # noqa: E402


def test_first_number_reads_aliases_case_insensitively_and_skips_invalid_values():
    metrics = {
        "roe_avg_pct": None,
        "ROE_PCT": "N/A",
        "return_on_equity_pct": "22.4%",
    }

    assert first_number(metrics, ["roe_avg_pct", "roe_pct", "return_on_equity_pct"]) == 22.4


def test_first_number_handles_negative_parentheses_and_rejects_booleans():
    metrics = {
        "free_cash_flow_5y_sum": True,
        "fcf_5y_sum": "(1,250)",
    }

    assert first_number(metrics, ["free_cash_flow_5y_sum", "fcf_5y_sum"]) == -1250.0


def test_format_metric_value_preserves_quality_funnel_units():
    assert format_metric_value(1_250_000_000, "") == "1,250,000,000"
    assert format_metric_value(8.0, "%") == "8%"
    assert format_metric_value(1.25, "x") == "1.25x"
