"""Canary regression: moving-average periods are not execution prices."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from reporting.content_credibility_inputs import price_candidates
from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment


def _alignment(stop):
    return evaluate_trade_setup_alignment(
        trade_setup={"trade_direction": "Long", "entry_zone": "32.00 至 33.50",
                     "target_price": "35.25 至 38.00", "stop_loss": stop},
        current_price=33.5,
    )


@pytest.mark.parametrize("label", ["SMA5 均線支撐失效點", "EMA20", "ema60"])
def test_indicator_period_does_not_create_ambiguous_stop(label):
    stop = f"30.45 ({label})"
    assert price_candidates(stop) == [30.45]
    result = _alignment(stop)
    assert result["warnings"] == []
    assert result["blocking_issues"] == []


def test_real_alternative_stop_remains_ambiguous_alongside_indicator():
    stop = "30.45 (EMA20)，另一情境停損 29.00"
    assert price_candidates(stop) == [30.45, 29.0]
    assert "ambiguous_trade_setup_price_inputs" in {
        issue["id"] for issue in _alignment(stop)["warnings"]
    }


@pytest.mark.parametrize("text, expected", [
    ("30.45 (SMA30.25)", [30.45, 30.25]),
    ("30.45 (EMA20元)", [20.0]),
    ("30.45 (SMA5=29.0)", [30.45, 29.0]),
])
def test_indicator_cleanup_preserves_actual_value_tokens(text, expected):
    assert price_candidates(text) == expected


def test_indicator_period_alone_does_not_supply_missing_stop():
    assert price_candidates("EMA20") == []
    assert "missing_trade_setup_price_inputs" in {
        issue["id"] for issue in _alignment("EMA20")["warnings"]
    }
