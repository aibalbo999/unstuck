from decimal import Decimal
import pytest
from reporting.trade_price_grid import equity_tick, grid_assessment, execution_rows


@pytest.mark.parametrize("value, expected", [(9.99, ".01"), (10, ".05"), (50, ".1"), (100, ".5"), (500, "1"), (1000, "5")])
def test_official_equity_tick_boundaries(value, expected):
    assert equity_tick(value) == Decimal(expected)


def test_reference_levels_are_not_silently_rounded_into_orders():
    setup = {"trade_direction": "Long", "entry_zone": "570-580", "target_price": "605.5", "stop_loss": "556.3"}
    before = dict(setup)
    result = grid_assessment({"ticker": "2327.TW", "quote_type": "EQUITY"}, setup)
    assert {item["field"] for item in result["invalid_levels"]} == {"target_price", "stop_loss"}
    assert setup == before and not result["actionable"]
    rows = execution_rows({"ticker": "2327.TW", "quote_type": "EQUITY"}, setup)
    assert "1.076" in rows[1]["value"]
    assert "不當作零成本" in rows[2]["value"]


def test_unknown_instrument_is_not_certified_with_equity_grid():
    assert grid_assessment({"ticker": "0050.TW", "quote_type": "ETF"}, {"entry_zone": "100.1"})["status"] == "unverified"
