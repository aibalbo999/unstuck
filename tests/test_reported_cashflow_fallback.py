"""Captured Yahoo cashflow only; income/balance are explicit synthetic controls."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from data_fetch.yfinance_extractors import extract_financial_histories

FIXTURE = Path(__file__).parent / "fixtures/reported_cashflow_fallback/5314_cashflow.json"


class Stock:
    def __init__(self, cashflow, periods=None):
        self.calls = Counter()
        periods = periods if periods is not None else cashflow.columns
        self.frames = {"cashflow": cashflow,
                       "financials": pd.DataFrame([[1e9] * len(periods)] * 4, index=["Total Revenue", "Net Income", "Gross Profit", "Operating Income"], columns=periods),
                       "balance_sheet": pd.DataFrame([[2e9] * len(periods)] * 2, index=["Total Assets", "Stockholders Equity"], columns=periods)}

    def __getattr__(self, key):
        self.calls[key] += 1
        return self.frames[key]


def captured_cashflow():
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == "cc724eff1b670a8592e4fa2d47e9fbbb208f50969533d7bd51738bccb5e9ea13"
    payload = json.loads(FIXTURE.read_text())
    assert payload["original_frame_sha256"] == "a7df49c1bd33c0b56fd58e9c00c4ae6df080367d6ef7671a76b294604195d61c"
    assert payload["original_receipt_sha256"] == "983bcb0b447597e5054784348ad11e49c5590d54d7b1906255c1284d7e92810d"
    return pd.DataFrame([[float("nan") if v["kind"] == "nan" else v["value"] for v in row["values"]] for row in payload["rows"]],
                        index=[row["name"]["value"] for row in payload["rows"]], columns=pd.to_datetime(payload["columns"]), dtype=object)


def extract(cashflow, periods=None):
    stock, notes = Stock(cashflow, periods), []
    result = extract_financial_histories(stock, "5314.TWO", notes, data_loader_cls=None)
    return result, notes, stock


def cash(value=-1e8, *, date="2022-12-31", ocf=2e8, capex=None):
    return pd.DataFrame([[ocf], [capex], [value]], index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow"], columns=pd.to_datetime([date]), dtype=object)


def test_captured_reported_2022_fcf_fills_only_missing_output_and_retains_raw_partial():
    frame = captured_cashflow(); original = frame.copy(deep=True)
    result, notes, stock = extract(frame)
    assert result["years"] == ["2021", "2022", "2023", "2024", "2025"]
    assert result["fcf_history"] == [None, -0.01, -0.04, 0.31, 0.99]
    assert stock.calls == {"financials": 1, "cashflow": 1, "balance_sheet": 1}
    assert len(notes) == 1 and "2022-12-31" in notes[0] and "Free Cash Flow" in notes[0] and "分項仍不足" in notes[0]
    audit = result["primary_financial_audit"]
    assert audit["status"] == "degraded_enrichment" and audit["coverage_status"] == "partial" and audit["raw_count"] == 5
    assert "missing_required_value" in audit["component_statuses"]["cashflow"]["reason_code"]
    assert "missing_output_value" in audit["component_statuses"]["cashflow"]["reason_code"]
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("value, expected", [(0, 0.0), (-1e8, -0.1), (3e8, 0.3)])
def test_reported_finite_values_include_zero_and_negative(value, expected):
    result, notes, _ = extract(cash(value))
    assert result["fcf_history"] == [expected] and len(notes) == 1
    assert result["primary_financial_audit"]["status"] == "degraded_enrichment"


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -float("inf"), True, False, "100000000", complex(1, 2)])
def test_non_finite_boolean_or_non_numeric_reported_values_stay_missing(value):
    result, notes, _ = extract(cash(value))
    assert result["fcf_history"] == [None] and notes == []


def test_existing_computed_formula_wins_even_if_reported_value_disagrees():
    result, notes, _ = extract(cash(9e9, ocf=2e8, capex=-5e7))
    assert result["fcf_history"] == [0.15] and notes == []


@pytest.mark.parametrize("case", ["different_end", "invalid_period", "duplicate_date", "duplicate_representation", "duplicate_label"])
def test_ambiguous_or_unmatched_reported_values_are_never_used(case):
    frame = cash(); periods = pd.to_datetime(["2022-12-31"])
    if case == "different_end":
        frame.columns = pd.to_datetime(["2022-06-30"])
    elif case == "invalid_period":
        frame.columns = ["2022-unknown"]
    elif case == "duplicate_date":
        frame = pd.concat([frame, frame], axis=1)
    elif case == "duplicate_representation":
        duplicate = frame.copy(); duplicate.columns = ["2022-12-31"]
        frame = pd.concat([frame, duplicate], axis=1)
    else:
        frame = pd.concat([frame, frame.loc[["Free Cash Flow"]]])
    result, notes, _ = extract(frame, periods)
    assert result["fcf_history"] == [None] and notes == []


def test_duplicate_reported_label_does_not_change_existing_formula():
    frame = cash(9e9, ocf=2e8, capex=-5e7)
    frame = pd.concat([frame, frame.loc[["Free Cash Flow"]]])
    result, notes, _ = extract(frame)
    assert result["fcf_history"] == [0.15] and notes == []


@pytest.mark.parametrize("quote_type", ["ETF", "MUTUALFUND"])
def test_fund_skip_has_no_sdk_getters(quote_type):
    stock, notes = Stock(cash()), []
    result = extract_financial_histories(stock, "5314.TWO", notes, data_loader_cls=object, quote_type=quote_type)
    assert result["fcf_history"] == [] and stock.calls == {} and notes == []
    assert result["primary_financial_audit"] is None


def test_same_year_other_date_does_not_override_exact_reported_value():
    frame = pd.concat([cash(-1e8), cash(9e9, date="2022-06-30")], axis=1)
    result, notes, _ = extract(frame, pd.to_datetime(["2022-12-31"]))
    assert result["fcf_history"] == [-0.1]
    assert "2022-12-31" in notes[0] and "2022-06-30" not in notes[0]


def test_fallback_still_runs_for_missing_other_field_and_reanchors_notes(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    stock, notes, calls = Stock(cash()), [], []
    stock.frames["financials"].loc["Net Income"] = None
    def fallback(*args, **kwargs):
        calls.append(args)
        return {"value": {"years": ["2022"], "rows_by_year": {"2022": {"statement_date": "2022-06-30", "net_income": 0.2, "free_cash_flow": 9.9}}}, "audit": {"status": "degraded_enrichment"}}
    monkeypatch.setattr(extractors, "audited_finmind_financial_statement_fallback", fallback)
    result = extractors.extract_financial_histories(stock, "5314.TWO", notes, data_loader_cls=object)
    assert len(calls) == 1 and result["fcf_history"] == [None]
    assert not any("Free Cash Flow" in note for note in notes)


def test_ambiguous_reported_date_then_finmind_fill_is_not_attributed_to_yahoo(monkeypatch):
    import data_fetch.yfinance_extractors as extractors
    frame = cash(); duplicate = frame.copy(); duplicate.columns = ["2022-12-31"]
    stock, notes, calls = Stock(pd.concat([frame, duplicate], axis=1), pd.to_datetime(["2022-12-31"])), [], []
    def fallback(*args, **kwargs):
        calls.append(args)
        return {"value": {"years": ["2022"], "rows_by_year": {"2022": {"statement_date": "2022-12-31", "free_cash_flow": 0.5}}}, "audit": {"status": "degraded_enrichment"}}
    monkeypatch.setattr(extractors, "audited_finmind_financial_statement_fallback", fallback)
    result = extractors.extract_financial_histories(stock, "5314.TWO", notes, data_loader_cls=object)
    assert len(calls) == 1 and result["fcf_history"] == [0.5]
    assert not any("Free Cash Flow" in note for note in notes)


@pytest.mark.parametrize("missing", ["Operating Cash Flow", "Capital Expenditure"])
def test_missing_component_row_uses_reported_total_without_inventing_component(missing):
    frame = cash().drop(missing)
    result, notes, _ = extract(frame)
    assert result["fcf_history"] == [-0.1] and len(notes) == 1
    assert missing not in frame.index
    assert "missing_required_value" in result["primary_financial_audit"]["component_statuses"]["cashflow"]["reason_code"]
