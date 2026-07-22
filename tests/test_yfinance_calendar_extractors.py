from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd


def test_calendar_value_reads_dict_series_and_dataframe_labels():
    from data_fetch.yfinance_calendar_extractors import calendar_value

    assert calendar_value({"Earnings-Date": "2026-07-01"}, ("Earnings Date",)) == "2026-07-01"

    series = pd.Series({"Ex Dividend Date": "2026-08-02"})
    assert calendar_value(series, ("Ex-Dividend Date",)) == "2026-08-02"

    frame = pd.DataFrame({"Value": ["2026-09-03"]}, index=["Earnings Date Start"])
    assert calendar_value(frame, ("Earnings Date Start",)) == "2026-09-03"

    column_frame = pd.DataFrame({"Fiscal-Year-End": ["2026-12-31", None]})
    assert calendar_value(column_frame, ("Fiscal Year End",)) == "2026-12-31"


def test_calendar_date_helpers_parse_ranges_and_timestamps():
    from data_fetch.yfinance_calendar_extractors import date_range, date_value

    assert date_value(pd.Timestamp("2026-07-01")) == "2026-07-01"
    assert date_value(datetime(2026, 7, 2, 12, 30)) == "2026-07-02"
    assert date_value(date(2026, 7, 3)) == "2026-07-03"
    assert date_value(1_798_761_600_000) == "2027-01-01"
    assert date_value("not a date") == ""
    assert date_range(["2026-07-05", "2026-07-01"], pd.Index(["2026-07-03"])) == (
        "2026-07-01",
        "2026-07-05",
    )


def test_calendar_event_append_dedupes_and_preserves_end_date():
    from data_fetch.yfinance_calendar_extractors import append_calendar_event

    events = []
    append_calendar_event(
        events,
        event_type="earnings_date",
        label="財報日",
        date_value="2026-07-01",
        end_date="2026-07-03",
        source="yfinance calendar",
    )
    append_calendar_event(
        events,
        event_type="earnings_date",
        label="財報日",
        date_value="2026-07-01",
        end_date="2026-07-04",
        source="yfinance info",
    )

    assert events == [
        {
            "type": "earnings_date",
            "label": "財報日",
            "date": "2026-07-01",
            "source": "yfinance calendar",
            "end_date": "2026-07-03",
        }
    ]


def test_read_stock_calendar_accepts_attribute_or_callable_and_swallows_errors():
    from data_fetch.yfinance_calendar_extractors import read_stock_calendar

    assert read_stock_calendar(SimpleNamespace(calendar={"Earnings Date": "2026-07-01"})) == {
        "Earnings Date": "2026-07-01"
    }
    assert read_stock_calendar(SimpleNamespace(calendar=lambda: {"Earnings Date": "2026-07-02"})) == {
        "Earnings Date": "2026-07-02"
    }

    def broken_calendar():
        raise RuntimeError("calendar unavailable")

    assert read_stock_calendar(SimpleNamespace(calendar=broken_calendar)) is None
