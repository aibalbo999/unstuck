import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from data_cross_validation_thresholds import (  # noqa: E402
    dynamic_cross_validation_thresholds,
    is_taiwan_ticker_for_threshold,
)


def test_taiwan_ticker_detection_accepts_tw_twos_and_plain_ids():
    assert is_taiwan_ticker_for_threshold("1234.TW") is True
    assert is_taiwan_ticker_for_threshold("1234.TWO") is True
    assert is_taiwan_ticker_for_threshold("1234") is True
    assert is_taiwan_ticker_for_threshold("AAPL") is False
    assert is_taiwan_ticker_for_threshold("12345.TW") is False


def test_dynamic_cross_validation_thresholds_widen_for_small_and_mid_cap_taiwan_names():
    assert dynamic_cross_validation_thresholds(
        {"ticker": "1234.TW", "market_cap_raw": "NT$5,000,000,000"}
    ) == (12.0, 40.0)
    assert dynamic_cross_validation_thresholds(
        {"ticker": "1234.TW", "market_cap_raw": 20_000_000_000}
    ) == (8.0, 28.0)
    assert dynamic_cross_validation_thresholds(
        {"ticker": "1234.TW", "market_cap_raw": 100_000_000_000}
    ) == (5.0, 20.0)
    assert dynamic_cross_validation_thresholds(
        {"ticker": "AAPL", "market_cap_raw": 5_000_000_000}
    ) == (5.0, 20.0)
