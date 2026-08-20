import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _trade_setup(**overrides):
    setup = {
        "trade_direction": "Long",
        "entry_zone": "NT$168-172",
        "target_price": "NT$182",
        "stop_loss": "NT$162",
        "core_catalyst": "下週法說會可能釋出新產品出貨上修訊號。",
        "risk_level": "Medium",
    }
    setup.update(overrides)
    return setup


def test_trade_setup_alignment_passes_and_records_directional_evidence():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment

    result = evaluate_trade_setup_alignment(
        trade_setup=_trade_setup(),
        current_price=170.0,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["id"] == "trade_setup_alignment"
    assert result["checks"][0]["status"] == "passed"
    assert result["checks"][0]["details"] == {
        "trade_direction": "Long",
        "current_price": 170.0,
        "target_price": 182.0,
        "stop_loss": 162.0,
    }


def test_trade_setup_alignment_blocks_long_target_or_stop_in_wrong_direction():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment

    result = evaluate_trade_setup_alignment(
        trade_setup=_trade_setup(target_price="NT$160", stop_loss="NT$175"),
        current_price=170.0,
    )

    assert {issue["id"] for issue in result["blocking_issues"]} == {
        "long_target_not_above_current_price",
        "long_stop_not_below_current_price",
    }
    assert all(check["status"] == "blocked" for check in result["checks"])


def test_trade_setup_alignment_uses_price_after_calendar_date_for_stop_loss():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment

    result = evaluate_trade_setup_alignment(
        trade_setup=_trade_setup(
            target_price="NT$230",
            stop_loss="跌破 2026 年 7 月 31 日價格點 204.0 TWD",
        ),
        current_price=210.0,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["details"]["stop_loss"] == 204.0


def test_trade_setup_alignment_ignores_period_range_before_target_price():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment

    result = evaluate_trade_setup_alignment(
        trade_setup=_trade_setup(
            target_price="1-2週目標價看近期高點壓力位1950.0 TWD",
            stop_loss="有效跌破支撐位1640.0 TWD",
            trade_direction="Neutral",
        ),
        current_price=1745.0,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"] == []
    assert result["checks"][0]["details"]["target_price"] == 1950.0


def test_trade_setup_alignment_warns_when_prices_cannot_be_parsed():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment

    result = evaluate_trade_setup_alignment(
        trade_setup=_trade_setup(target_price="等待突破確認", stop_loss="依收盤價判定"),
        current_price=170.0,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "missing_trade_setup_price_inputs"
    assert result["checks"][0]["status"] == "warning"
