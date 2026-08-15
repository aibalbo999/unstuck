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


def test_trade_setup_alignment_warns_when_prices_cannot_be_parsed():
    from reporting.content_credibility_trade_setup import evaluate_trade_setup_alignment

    result = evaluate_trade_setup_alignment(
        trade_setup=_trade_setup(target_price="等待突破確認", stop_loss="依收盤價判定"),
        current_price=170.0,
    )

    assert result["blocking_issues"] == []
    assert result["warnings"][0]["id"] == "missing_trade_setup_price_inputs"
    assert result["checks"][0]["status"] == "warning"
