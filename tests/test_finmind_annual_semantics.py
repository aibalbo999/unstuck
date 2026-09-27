"""FinMind annual IS/point-in-time BS/partial CF contracts, entirely offline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from data_fetch.market_sources import taiwan

FIXTURE = Path(__file__).parent / "fixtures/finmind_annual_semantics/5314_statements.json"
PERIODS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
PARENT_NI = "淨利（淨損）歸屬於母公司業主"


def row(kind, value, date="2025-12-31", origin=None):
    return {"date": date, "stock_id": "5314", "type": kind, "value": value, "origin_name": origin or kind}


def synthetic_tables():
    return {"financials": [row(kind, value, date, PARENT_NI if kind == "EquityAttributableToOwnersOfParent" else kind)
                           for date in PERIODS for kind, value in {"Revenue": 6e6, "GrossProfit": 2e6, "OperatingIncome": -1e6, "EquityAttributableToOwnersOfParent": 1e6}.items()],
            "balance": [row("TotalAssets", 3e9), row("Equity", 2e9), row("EquityAttributableToOwnersOfParent", 1e9)],
            "cashflow": [row("CashFlowsFromOperatingActivities", 1e9), row("PropertyAndPlantAndEquipment", -1e8)]}


def assemble(tables):
    return taiwan._assemble_finmind_financial_statements({name: pd.DataFrame(rows) for name, rows in tables.items()})


def test_captured_quarters_equal_official_annual_is_and_preserve_cf_components():
    fixture = json.loads(FIXTURE.read_text())
    assert fixture["source_table_sha256"]["financials"] == "066e67dcfec9dd2a7fb796282765192c1e84df93b943c3a9419c8586a5ea2670"
    original = deepcopy(fixture["tables"])
    result = assemble(fixture["tables"])
    assert result["years"] == ["2021", "2022", "2023", "2024", "2025"]
    fields = {"revenue": "revenue", "gross_profit": "gross_profit", "operating_income": "operating_income", "net_income": "net_income_parent"}
    for year in result["years"]:
        for output, source in fields.items():
            expected = fixture["official_annual_is_TWD"][year][source]["value"]
            assert result["rows_by_year"][year][output] == round(expected / 1e9, 2)
    assert result["rows_by_year"]["2021"]["operating_cash_flow"] == -16037000
    assert result["rows_by_year"]["2024"]["property_and_equipment_cash_flow"] == -9409000
    assert result["fcf_history"] == [None] * 5
    assert result["rows_by_year"]["2024"]["free_cash_flow_status"] == "capex_scope_unverified"
    assert result["rows_by_year"]["2024"]["cash_flow_value_unit"] == "TWD"
    assert fixture["tables"] == original


def test_sum_raw_quarters_before_rounding_and_parent_precedes_consolidated():
    tables = synthetic_tables()
    tables["financials"] += [row("IncomeAfterTaxes", 9e9, date) for date in PERIODS]
    result = assemble(tables)
    assert result["revenue_history"] == [0.02]  # round(sum .006*4), not sum(round .006).
    assert result["net_income_history"] == [0.0]
    assert result["gross_profit_history"] == [0.01]
    assert result["operating_income_history"] == [-0.0]


@pytest.mark.parametrize("case", ["missing_quarter", "duplicate_same", "duplicate_conflict", "wrong_end", "nan", "inf", "bool", "numeric_string"])
def test_revenue_requires_four_unique_exact_finite_numeric_quarters(case):
    tables = synthetic_tables(); target = next(r for r in tables["financials"] if r["type"] == "Revenue" and r["date"] == PERIODS[1])
    if case == "missing_quarter":tables["financials"].remove(target)
    elif case.startswith("duplicate"):
        duplicate = dict(target)
        if case == "duplicate_conflict":duplicate["value"] += 1
        tables["financials"].append(duplicate)
    elif case == "wrong_end":target["date"] = "2025-06-29"
    else:target["value"] = {"nan": float("nan"), "inf": float("inf"), "bool": True, "numeric_string": "6000000"}[case]
    result = assemble(tables)
    assert result["revenue_history"] == [None]
    assert result["gross_profit_history"] == [0.01]


@pytest.mark.parametrize("origin", ["歸屬於母公司業主之權益合計", "綜合損益總額歸屬於母公司業主", "本期淨利（淨損）", "", None])
def test_net_income_requires_explicit_parent_profit_label_without_consolidated_fallback(origin):
    tables = synthetic_tables()
    for r in tables["financials"]:
        if r["type"] == "EquityAttributableToOwnersOfParent":r["origin_name"] = origin
    tables["financials"] += [row("IncomeAfterTaxes", 7e9, date) for date in PERIODS]
    assert assemble(tables)["net_income_history"] == [None]


def test_net_income_absent_parent_is_not_group_profit():
    tables = synthetic_tables();tables["financials"] = [r for r in tables["financials"] if r["type"] != "EquityAttributableToOwnersOfParent"]
    tables["financials"] += [row("IncomeAfterTaxes", 7e9, date) for date in PERIODS]
    assert assemble(tables)["net_income_history"] == [None]


def test_income_explicit_zero_and_negative_values_are_preserved():
    tables = synthetic_tables()
    for r in tables["financials"]:r["value"] = -1e8 if r["type"] == "OperatingIncome" else 0
    result = assemble(tables)
    assert result["revenue_history"] == result["net_income_history"] == result["gross_profit_history"] == [0.0]
    assert result["operating_income_history"] == [-0.4]


@pytest.mark.parametrize("date", ["2025-09-30", "2025-12-30", "2025-12-31garbage", "0000-12-31", "not-a-date-12-31"])
def test_no_valid_year_end_means_no_annual_result(date):
    tables = {"financials": [row("Revenue", 1e9, date)], "balance": [], "cashflow": []}
    assert assemble(tables) == {}


def test_parent_equity_priority_is_independent_of_row_order():
    tables = synthetic_tables()
    assert assemble(tables)["total_equity_history"] == [1.0]
    tables["balance"].reverse()
    assert assemble(tables)["total_equity_history"] == [1.0]
    tables["balance"] = [r for r in tables["balance"] if r["type"] != "EquityAttributableToOwnersOfParent"]
    assert assemble(tables)["total_equity_history"] == [2.0]


@pytest.mark.parametrize("case", ["duplicate", "nan", "inf", "bool"])
def test_present_invalid_parent_equity_does_not_fallback_to_group(case):
    tables = synthetic_tables(); target = next(r for r in tables["balance"] if r["type"] == "EquityAttributableToOwnersOfParent")
    if case == "duplicate":tables["balance"].append(dict(target))
    else:target["value"] = {"nan": float("nan"), "inf": float("inf"), "bool": True}[case]
    assert assemble(tables)["total_equity_history"] == [None]


@pytest.mark.parametrize("case, expected", [("single", 1e9), ("equal_aliases", 1e9), ("conflict", None), ("duplicate", None), ("zero", 0), ("invalid", None)])
def test_cashflow_components_preserved_without_inventing_complete_capex(case, expected):
    tables = synthetic_tables()
    if case == "equal_aliases":tables["cashflow"].append(row("NetCashInflowFromOperatingActivities", 1e9))
    elif case == "conflict":tables["cashflow"].append(row("NetCashInflowFromOperatingActivities", 2e9))
    elif case == "duplicate":tables["cashflow"].append(dict(tables["cashflow"][0]))
    elif case == "zero":tables["cashflow"][0]["value"] = 0
    elif case == "invalid":tables["cashflow"][0]["value"] = True
    result = assemble(tables); annual = result["rows_by_year"]["2025"]
    assert annual["operating_cash_flow"] == expected
    assert annual["property_and_equipment_cash_flow"] == -1e8
    assert annual["cash_flow_value_unit"] == "TWD" and result["fcf_history"] == [None]
    assert annual["free_cash_flow_status"] == ("missing_components" if expected is None else "capex_scope_unverified")


def test_no_ppe_is_missing_components_and_zero_ppe_still_unknown_full_capex():
    tables = synthetic_tables();tables["cashflow"] = tables["cashflow"][:1]
    result = assemble(tables)
    assert result["rows_by_year"]["2025"]["free_cash_flow_status"] == "missing_components"
    tables["cashflow"].append(row("PropertyAndPlantAndEquipment", 0))
    result = assemble(tables)
    assert result["rows_by_year"]["2025"]["property_and_equipment_cash_flow"] == 0
    assert result["rows_by_year"]["2025"]["free_cash_flow_status"] == "capex_scope_unverified"
    assert result["fcf_history"] == [None]


def test_balance_and_cumulative_cashflow_remain_year_end_not_quarter_sums():
    tables = synthetic_tables()
    for date in PERIODS[:-1]:
        tables["balance"].extend([row("TotalAssets", 99e9, date), row("EquityAttributableToOwnersOfParent", 88e9, date)])
        tables["cashflow"].extend([row("CashFlowsFromOperatingActivities", 77e9, date), row("PropertyAndPlantAndEquipment", -66e9, date)])
    result = assemble(tables)
    assert result["revenue_history"] == [0.02]
    assert result["total_assets_history"] == [3.0] and result["total_equity_history"] == [1.0]
    assert result["rows_by_year"]["2025"]["operating_cash_flow"] == 1e9
    assert result["rows_by_year"]["2025"]["property_and_equipment_cash_flow"] == -1e8


@pytest.mark.parametrize("numpy_scalar", [False, True])
def test_complex_quarter_values_are_not_coerced_to_real(numpy_scalar):
    import numpy as np
    tables = synthetic_tables()
    target = next(r for r in tables["financials"] if r["type"] == "Revenue" and r["date"] == PERIODS[1])
    target["value"] = np.complex128(6e6 + 1j) if numpy_scalar else complex(6e6, 1)
    frames = {name: pd.DataFrame(rows, dtype=object) for name, rows in tables.items()}
    result = taiwan._assemble_finmind_financial_statements(frames)
    assert result["revenue_history"] == [None]
    assert result["gross_profit_history"] == [0.01]
