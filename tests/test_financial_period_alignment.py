"""Annual statement alignment, replayed offline from a bounded SDK capture."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from data_fetch.yfinance_extractors import extract_financial_histories
from data_fetch.yfinance_derived import calculate_margin_histories


CAPTURE = Path(__file__).parent / "fixtures/financial_period_alignment/2254_annual_frames.json"
CAPTURE_SHA256 = "1b3c706390388140c807e510f8ac6f08f3c6685402e56662d4d5af3a37ea3a59"


def captured_frames():
    assert hashlib.sha256(CAPTURE.read_bytes()).hexdigest() == CAPTURE_SHA256
    payload = json.loads(CAPTURE.read_text())
    assert payload["original_capture_sha256"] == "bbdbab4075a71c4bb4039440502ff7ba5dee24cded2ffa1eafc1558268f622db"
    return {name: pd.DataFrame(item["data"], index=item["index"], columns=pd.to_datetime(item["columns"]))
            for name, item in payload["frames"].items()}


class StatementStock:
    def __init__(self, frames):
        self.frames = frames
        self.calls = Counter()

    def __getattr__(self, name):
        self.calls[name] += 1
        return self.frames[name]


def margins(histories):
    return calculate_margin_histories(*(histories[key] for key in (
        "revenue_history", "gross_profit_history", "operating_income_history", "net_income_history", "total_equity_history")))


def test_captured_2254_aligns_periods_and_roe_without_hiding_raw_gap():
    frames = captured_frames()
    originals = {name: frame.copy(deep=True) for name, frame in frames.items()}
    stock = StatementStock(frames)
    result = extract_financial_histories(stock, "2254.TW", [], data_loader_cls=None)
    assert result["years"] == ["2022", "2023", "2024", "2025"]
    assert result["revenue_history"] == [0.93, 0.55, 0.63, 0.48]
    assert result["net_income_history"] == [0.15, -0.05, -0.07, -0.05]
    assert result["total_assets_history"] == [2.09, 2.4, 2.42, 2.18]
    assert result["total_equity_history"] == [0.76, 0.99, 1.16, 1.1]
    assert result["fcf_history"] == [-0.27, -0.27, -0.11, 0.06]
    assert margins(result)["roe_history"] == [19.7, -5.1, -6.0, -4.5]
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 1}
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"
    assert result["primary_financial_audit"]["raw_count"] == 5
    for name in ("cashflow", "balance_sheet"):
        assert "missing_required_value" in result["primary_financial_audit"]["component_statuses"][name]["reason_code"]
    assert "source_period_order_or_range_mismatch" in result["primary_financial_audit"]["component_statuses"]["balance_sheet"]["reason_code"]
    for name, original in originals.items():
        pd.testing.assert_frame_equal(frames[name], original)


def test_reordered_balance_and_cashflow_follow_income_periods():
    frames = captured_frames()
    for name in ("cashflow", "balance_sheet"):
        frames[name] = frames[name].iloc[:, ::-1]
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    assert result["total_equity_history"] == [0.76, 0.99, 1.16, 1.1]
    assert result["fcf_history"] == [-0.27, -0.27, -0.11, 0.06]


def test_missing_middle_period_stays_none_without_shifting_neighbors():
    frames = captured_frames()
    frames["balance_sheet"] = frames["balance_sheet"].drop(columns=pd.Timestamp("2024-12-31"))
    frames["cashflow"] = frames["cashflow"].drop(columns=pd.Timestamp("2023-12-31"))
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    assert result["total_equity_history"] == [0.76, 0.99, None, 1.1]
    assert result["fcf_history"] == [-0.27, None, -0.11, 0.06]
    assert margins(result)["roe_history"] == [19.7, -5.1, None, -4.5]


@pytest.mark.parametrize("case", ["different_day", "invalid_anchor", "missing_tables"])
def test_unverified_periods_are_not_joined_by_year_or_position(case):
    frames = captured_frames()
    if case == "different_day":
        for name in ("cashflow", "balance_sheet"):
            frames[name] = frames[name].rename(columns={pd.Timestamp("2025-12-31"): pd.Timestamp("2025-06-30")})
    elif case == "invalid_anchor":
        frames["financials"] = frames["financials"].rename(columns={pd.Timestamp("2025-12-31"): "2025-unknown"})
    else:
        frames["cashflow"], frames["balance_sheet"] = pd.DataFrame(), pd.DataFrame()
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    for key in ("fcf_history", "total_assets_history", "total_equity_history"):
        assert len(result[key]) == len(result["years"]) == 4
        assert result[key][-1] is None
    assert margins(result)["roe_history"][-1] is None


def test_other_fiscal_end_in_same_year_does_not_override_exact_match():
    frames = captured_frames()
    frames["cashflow"][pd.Timestamp("2025-06-30")] = [9e9, -1e9]
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    assert result["fcf_history"][-1] == 0.06
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"


def test_duplicate_representations_of_exact_date_do_not_choose_a_value():
    frames = captured_frames()
    frame = frames["cashflow"]
    duplicate = pd.DataFrame([[9e9], [-1e9]], index=frame.index, columns=["2025-12-31"])
    frames["cashflow"] = pd.concat([frame, duplicate], axis=1)
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    assert result["fcf_history"][-1] is None
    assert result["fcf_history"][:-1] == [-0.27, -0.27, -0.11]


@pytest.mark.parametrize("capex", ["missing_row", "nan", "zero"])
def test_cashflow_requires_known_capex_but_accepts_explicit_zero(capex):
    frames = captured_frames()
    if capex == "missing_row":
        frames["cashflow"] = frames["cashflow"].drop("Capital Expenditure")
    else:
        frames["cashflow"].loc["Capital Expenditure", pd.Timestamp("2025-12-31")] = float("nan") if capex == "nan" else 0
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    ocf = frames["cashflow"].loc["Operating Cash Flow", pd.Timestamp("2025-12-31")]
    assert result["fcf_history"][-1] == (round(ocf / 1e9, 2) if capex == "zero" else None)


def test_zero_annual_values_are_preserved_and_do_not_trigger_empty_fallback(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    frames = captured_frames()
    for frame in frames.values():
        frame.iloc[:, :] = 0
    monkeypatch.setattr(extractors, "audited_fetch", lambda *_args, **_kwargs: pytest.fail("zero is available data"))
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=object)
    for key in ("revenue_history", "net_income_history", "gross_profit_history", "operating_income_history",
                "fcf_history", "total_assets_history", "total_equity_history"):
        assert result[key] == [0.0] * 4


def test_zero_numerators_produce_zero_ratios_with_existing_denominator_policy():
    result = calculate_margin_histories([1, 0, None], [0, 0, 0], [0, 0, 0], [0, 0, 0], [2, 0, -1])
    assert result == {key: [0.0, None, None] for key in (
        "gross_margin_history", "op_margin_history", "net_margin_history", "roe_history")}


@pytest.mark.parametrize("value", [False, True])
def test_boolean_is_not_a_financial_zero_or_one(value):
    frames = captured_frames()
    frames["financials"] = frames["financials"].astype(object)
    frames["financials"].loc["Total Revenue", pd.Timestamp("2025-12-31")] = value
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=None)
    assert result["revenue_history"][-1] is None


@pytest.mark.parametrize("duplicate_year", [False, True])
def test_fallback_year_change_reprojects_all_retained_primary_histories(monkeypatch, duplicate_year):
    import data_fetch.yfinance_extractors as extractors
    frames = captured_frames()
    frames["financials"] = frames["financials"].iloc[:, :2].copy()
    frames["financials"].loc["Net Income"] = float("nan")
    if duplicate_year:
        frames["financials"].columns = pd.to_datetime(["2025-12-31", "2025-06-30"])
    calls = []

    def fallback(*args, **kwargs):
        calls.append(args)
        return {"value": {"years": ["2023", "2024", "2025"], "rows_by_year": {
            year: {"statement_date": f"{year}-12-31", "net_income": 0.1, "revenue": 999, "gross_profit": 999, "operating_income": 999,
                   "free_cash_flow": 999, "total_assets": 999, "total_equity": 999}
            for year in ("2023", "2024", "2025")}},
            "audit": {"source": "financial_statements", "provider": "FinMind financial statement fallback",
                      "status": "success", "record_count": 3}}

    monkeypatch.setattr(extractors, "audited_fetch", fallback)
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=object)
    assert len(calls) == 1
    assert result["years"] == ["2023", "2024", "2025"]
    assert result["net_income_history"] == [0.1, 0.1, 0.1]
    expected = {
        "revenue_history": [None, 0.63, 0.48], "gross_profit_history": [None, 0.17, 0.11],
        "operating_income_history": [None, -0.05, -0.07], "fcf_history": [None, -0.11, 0.06],
        "total_assets_history": [None, 2.42, 2.18], "total_equity_history": [None, 1.16, 1.1],
    }
    for key, values in expected.items():
        assert result[key] == ([None] * 3 if duplicate_year else values)
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"


def install_finmind_frames(monkeypatch, capex, statement_date="2025-12-31"):
    from data_fetch.market_sources import taiwan, finmind_financial_transport
    def frame(values):
        return pd.DataFrame([{"date": statement_date, "type": key, "value": value} for key, value in values.items()])
    cash = {"NetCashInflowFromOperatingActivities": 5e8}
    if capex is not None:
        cash["PropertyAndPlantAndEquipment"] = capex
    frames = {"financials": frame({"Revenue": 2e9, "IncomeAfterTaxes": 4e8}),
              "balance": frame({"TotalAssets": 6e9, "Equity": 3e9}), "cashflow": frame(cash)}
    calls = []
    def fetches(stock_id, start_date):
        calls.append((stock_id, start_date))
        return {"tables": {name: frame.to_dict("records") for name, frame in frames.items()},
                "components": {name: {"status": "success"} for name in frames}, "error": None}
    monkeypatch.setattr(taiwan, "DataLoader", object)
    monkeypatch.setattr(finmind_financial_transport, "fetch_statement_tables", fetches)
    return taiwan, calls


@pytest.mark.parametrize("capex, expected", [(None, None), (0, 0.5), (-1e8, 0.4)])
def test_finmind_requires_known_capex_and_preserves_signed_formula(monkeypatch, capex, expected):
    taiwan, calls = install_finmind_frames(monkeypatch, capex)
    result = taiwan.fetch_finmind_financial_statement_fallback("2254.TW")
    assert result["fcf_history"] == [expected]
    assert result["rows_by_year"]["2025"]["statement_date"] == "2025-12-31"
    assert len(calls) == 1


@pytest.mark.parametrize("capex, statement_date", [(None, "2025-12-31"), (-1e8, "2025-06-30"),
                                                  (0, "2025-12-31"), (-1e8, "2025-12-31")])
def test_yahoo_to_finmind_fcf_fill_requires_both_capex_and_same_date(monkeypatch, capex, statement_date):
    _taiwan, calls = install_finmind_frames(monkeypatch, capex, statement_date)
    frames = captured_frames()
    frames["cashflow"] = frames["cashflow"].drop("Capital Expenditure")
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=object)
    expected = round(0.5 + capex / 1e9, 2) if capex is not None and statement_date == "2025-12-31" else None
    assert result["fcf_history"] == [None, None, None, expected]
    assert len(calls) == 1
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"


@pytest.mark.parametrize("case", ["different_day", "missing_date", "same_years_different_day"])
def test_fallback_reanchor_requires_matching_full_statement_date(monkeypatch, case):
    import data_fetch.yfinance_extractors as extractors
    frames = captured_frames()
    frames["financials"].loc["Net Income"] = float("nan")
    years = ["2022", "2023", "2024", "2025"] if case == "same_years_different_day" else ["2024", "2025"]
    rows = {year: {"statement_date": f"{year}-12-31", "net_income": 0.1} for year in years}
    rows["2025"]["statement_date"] = None if case == "missing_date" else "2025-06-30"
    monkeypatch.setattr(extractors, "audited_fetch", lambda *_args, **_kwargs: {
        "value": {"years": years, "rows_by_year": rows}, "audit": {"status": "success"}})
    result = extract_financial_histories(StatementStock(frames), "2254.TW", [], data_loader_cls=object)
    assert result["years"] == years
    for key in ("revenue_history", "gross_profit_history", "operating_income_history", "fcf_history",
                "total_assets_history", "total_equity_history"):
        assert result[key][-1] is None
    assert result["total_equity_history"][-2] == 1.16
    assert margins(result)["roe_history"][-1] is None
