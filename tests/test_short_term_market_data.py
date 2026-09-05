"""Offline contracts for daily market evidence and the mode-D prompt boundary."""

from datetime import date, timedelta
import json

import pandas as pd
import pytest

from agent_runtime.prompting import build_prompt
from data_fetch import yfinance_enrichment_extractors as extractors
from prompt_builder import format_data_for_prompt
from state_memory import initialize_agent_state


AS_OF = date(2026, 9, 5)  # Saturday: the final completed session is Friday.


def _frame(count=80, *, flat=False):
    closes = [100.0 if flat else 100.0 + i for i in range(count)]
    return pd.DataFrame(
        {"Open": closes, "High": [v + 2 for v in closes],
         "Low": [v - 2 for v in closes], "Close": closes, "Volume": [1000.0] * count},
        index=pd.bdate_range(end="2026-09-04", periods=count),
    )


class HistoryStock:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def history(self, period):
        self.calls.append(period)
        return self.frame


def _bundle(frame):
    extractor = getattr(extractors, "extract_market_history_bundle", None)
    assert callable(extractor), "The existing 5y fetch must supply bounded daily evidence"
    return extractor(HistoryStock(frame), as_of=AS_OF)


def _data(**extra):
    return {"ticker": "TEST.TW", "company_name": "Fixture", "current_price": 100,
            "fetch_date": AS_OF.isoformat(), "data_trust": {"status": "fresh"}, **extra}


def _prompt_json(data):
    return json.loads(format_data_for_prompt(data).split("\n", 1)[1].split("\n\n【使用規則】", 1)[0])


def test_mode_d_prompt_receives_future_calendar_evidence_and_excludes_old_events():
    calendar = {"events": [
        {"date": (date.today() + timedelta(days=5)).isoformat(), "label": "FUTURE_EVENT_765", "source": "official calendar"},
        {"date": (date.today() - timedelta(days=30)).isoformat(), "label": "EXPIRED_EVENT_765", "source": "official calendar"},
    ]}
    data = _data(event_calendar=calendar, _prompt_agent_num=24)
    prompt = build_prompt(24, data, {"pipeline_id": "v4", "agent_state": initialize_agent_state(data)})
    assert "FUTURE_EVENT_765" in prompt
    assert "EXPIRED_EVENT_765" not in prompt


def test_same_5y_fetch_supplies_bounded_daily_history_and_keeps_legacy_ranges():
    stock = HistoryStock(_frame(150))
    extractor = getattr(extractors, "extract_market_history_bundle", None)
    assert callable(extractor), "Daily OHLCV must share the existing history request"
    bundle = extractor(stock, as_of=AS_OF)
    assert stock.calls == ["5y"]
    assert set(bundle["price_history_ranges"]["ranges"]) == {"1m", "3m", "6m", "1y", "3y", "5y"}
    daily = bundle["daily_market_data"]
    assert daily["sample_count"] == len(daily["bars"]) == 120
    assert daily["as_of"] == "2026-09-04"
    assert daily["bars"][-1] == {"date": "2026-09-04", "open": 249.0, "high": 251.0,
                                 "low": 247.0, "close": 249.0, "volume": 1000.0}
    assert daily["availability"] == "available"


def test_indicator_values_use_daily_samples_and_explicit_warmup():
    indicators = _bundle(_frame(60))["technical_indicators"]
    assert indicators["sample_count"] == 60
    assert indicators["sma_5"] == pytest.approx(157)
    assert indicators["sma_10"] == pytest.approx(154.5)
    assert indicators["sma_20"] == pytest.approx(149.5)
    assert indicators["sma_60"] == pytest.approx(129.5)
    assert indicators["rsi_14"] == pytest.approx(100)
    assert indicators["macd"] == pytest.approx(7)
    assert indicators["macd_signal"] == pytest.approx(7)
    assert indicators["macd_histogram"] == pytest.approx(0)
    assert indicators["atr_14"] == pytest.approx(4)
    assert indicators["volume_sma_20"] == pytest.approx(1000)
    assert indicators["volume_ratio_20"] == pytest.approx(1)
    insufficient = _bundle(_frame(20))["technical_indicators"]
    assert insufficient["sma_20"] is not None
    assert insufficient["sma_60"] is None
    assert insufficient["macd"] is None
    assert insufficient["availability"] == "partial"
    assert "sma_60" in insufficient["missing_indicators"]


def test_flat_prices_have_neutral_rsi_zero_macd_and_no_infinite_volume_ratio():
    frame = _frame(60, flat=True)
    frame["Volume"] = 0.0
    indicators = _bundle(frame)["technical_indicators"]
    assert indicators["rsi_14"] == pytest.approx(50)
    assert indicators["macd"] == pytest.approx(0)
    assert indicators["macd_signal"] == pytest.approx(0)
    assert indicators["macd_histogram"] == pytest.approx(0)
    assert indicators["volume_ratio_20"] is None
    json.dumps(indicators, allow_nan=False)


def test_missing_high_low_are_null_not_fabricated_and_atr_is_unavailable():
    bundle = _bundle(_frame(70).drop(columns=["High", "Low"]))
    assert bundle["daily_market_data"]["bars"][-1]["high"] is None
    assert bundle["daily_market_data"]["bars"][-1]["low"] is None
    assert bundle["daily_market_data"]["availability"] == "partial"
    assert bundle["technical_indicators"]["sma_60"] is not None
    assert bundle["technical_indicators"]["atr_14"] is None


def test_nullable_dataframe_cells_preserve_close_evidence_without_inventing_ohlcv():
    frame = _frame(60).astype({"High": "Float64", "Low": "Float64", "Volume": "Float64"})
    frame["High"] = pd.array([pd.NA] * 60, dtype="Float64")
    frame["Low"] = pd.array([pd.NA] * 60, dtype="Float64")
    frame["Volume"] = pd.array([pd.NA] * 60, dtype="Float64")
    bundle = _bundle(frame)
    assert bundle["daily_market_data"]["sample_count"] == 60
    assert bundle["technical_indicators"]["sma_60"] == pytest.approx(129.5)
    assert bundle["technical_indicators"]["atr_14"] is None
    assert bundle["technical_indicators"]["volume_latest"] is None


def test_daily_boundary_drops_future_and_invalid_prices_or_negative_volume():
    frame = _frame(60)
    frame.loc[pd.Timestamp("2026-09-07")] = [999, 1000, 998, 999, 1000]
    frame.iloc[0, frame.columns.get_loc("Close")] = float("inf")
    frame.iloc[1, frame.columns.get_loc("High")] = 1
    frame.iloc[2, frame.columns.get_loc("Volume")] = -1
    daily = _bundle(frame)["daily_market_data"]
    assert daily["sample_count"] == 57
    assert daily["as_of"] == "2026-09-04"
    assert daily["excluded_row_count"] == 4
    json.dumps(daily, allow_nan=False)


def test_invalid_dataframe_date_is_excluded_without_losing_valid_history():
    frame = _frame(60)
    frame.loc[pd.NaT] = [100, 102, 98, 100, 1000]
    daily = _bundle(frame)["daily_market_data"]
    assert daily["sample_count"] == 60
    assert daily["excluded_row_count"] == 1


def test_atr_uses_previous_close_for_gap_risk():
    frame = _frame(15, flat=True)
    frame.iloc[-1] = [110, 112, 108, 110, 1000]
    indicators = _bundle(frame)["technical_indicators"]
    assert indicators["atr_14"] == pytest.approx((13 * 4 + 12) / 14)


def test_old_cache_without_daily_evidence_is_refetched_not_reused_as_mode_d_data():
    from data_fetch.constants import DATA_SCHEMA_VERSION, REQUIRED_DATA_SCHEMA_FIELDS
    from data_fetch.yfinance_cache_gate import build_fresh_cache_payload

    complete = {field: {} for field in REQUIRED_DATA_SCHEMA_FIELDS}
    complete.update(data_schema_version=DATA_SCHEMA_VERSION, ticker="TEST.TW")
    for missing in ("daily_market_data", "technical_indicators"):
        old = {key: value for key, value in complete.items() if key != missing}
        payload, _stale, schema_mismatch = build_fresh_cache_payload(
            "TEST.TW", old, assess_cached=lambda *_: (True, {}),
            append_cache_audit=lambda *_args, **_kwargs: None, now_epoch=0,
        )
        assert payload is None
        assert schema_mismatch is True


def test_events_preserve_date_precision_and_keep_unknown_dates_separate():
    from short_term_market_data import build_short_term_market_context
    calendar = {"events": [
        {"date": "2026-09-07", "label": "confirmed", "source": "issuer", "date_status": "confirmed"},
        {"date": "2026-09-08", "end_date": "2026-09-11", "label": "range", "source": "yfinance calendar"},
        {"label": "unscheduled", "source": "issuer"},
        {"date": "2026-10-01", "label": "outside", "source": "issuer"},
        {"date": "2026-08-01", "label": "expired", "source": "issuer"},
    ]}
    events = build_short_term_market_context(_data(event_calendar=calendar), as_of=AS_OF)["event_calendar"]
    assert [e["label"] for e in events["events"]] == ["confirmed", "range"]
    assert [e["date_status"] for e in events["events"]] == ["confirmed", "date_range"]
    assert events["events"][1]["end_date"] == "2026-09-11"
    assert events["undated_events"][0]["date_status"] == "date_unknown"
    assert events["horizon_calendar_days"] == 14


@pytest.mark.parametrize("agent", [17, 18, 19, 23, 7, None])
def test_daily_prompt_context_is_not_broadcast_to_other_roles(agent):
    payload = _prompt_json(_data(_prompt_agent_num=agent, event_calendar={"events": []}))
    assert "short_term_market_context" not in payload


def test_mode_d_prompt_context_has_bounded_daily_bars_and_technical_values():
    bundle = _bundle(_frame(120))
    payload = _prompt_json(_data(**bundle, _prompt_agent_num=22))
    context = payload["short_term_market_context"]
    assert len(context["daily_market_data"]["bars"]) == 20
    assert context["daily_market_data"]["sample_count"] == 120
    assert context["daily_market_data"]["displayed_sample_count"] == 20
    assert context["technical_indicators"]["sma_60"] == pytest.approx(189.5)
