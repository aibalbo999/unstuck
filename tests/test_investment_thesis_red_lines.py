import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from investment_thesis_red_lines import (  # noqa: E402
    contrarian_red_lines,
    position_red_lines,
    red_lines,
    trade_red_lines,
)


def test_position_red_lines_add_partial_data_trust_and_buy_chasing_warnings():
    lines = position_red_lines({"data_trust": {"status": "partial"}}, "買進")

    conditions = [item["condition"] for item in lines]
    assert any("partial" in condition for condition in conditions)
    assert any("牛市情境上方" in condition for condition in conditions)


def test_core_red_lines_add_partial_data_trust_warning_without_buy_chasing_warning():
    lines = red_lines({"data_trust": {"status": "partial"}}, "觀望")

    conditions = [item["condition"] for item in lines]
    assert any("partial data trust" in condition for condition in conditions)
    assert not any("股價超過牛市情境" in condition for condition in conditions)


def test_trade_and_contrarian_red_lines_keep_mode_specific_actions():
    trade_lines = trade_red_lines({"stop_loss": "跌破月線"})
    contrarian_lines = contrarian_red_lines()

    assert trade_lines[0]["condition"] == "價格觸發停損：跌破月線"
    assert any("回補" in item["action"] for item in contrarian_lines)
