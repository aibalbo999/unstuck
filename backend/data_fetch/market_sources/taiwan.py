"""FinMind-backed Taiwan market source helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
import math

import pandas as pd

from config import CATALYST_LOOKBACK_DAYS, INSTITUTIONAL_LOOKBACK_DAYS
from financial_tools import safe_float

from .common import _run_named_fetches
from .identity import _stock_id_from_ticker, is_taiwan_ticker

try:
    from FinMind.data import DataLoader
except ImportError:
    DataLoader = None


def fetch_finmind_news_catalysts(ticker: str) -> list[dict]:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return []
    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=CATALYST_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    try:
        df = DataLoader().taiwan_stock_news(stock_id=stock_id, start_date=start_date)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    records = []
    for _, row in df.tail(20).iloc[::-1].iterrows():
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "date": str(row.get("date", ""))[:19],
            "title": title,
            "summary": str(row.get("description", "") or "")[:280],
            "source": str(row.get("source", "FinMind")).strip() or "FinMind",
            "link": str(row.get("link", "")).strip(),
            "source_type": "finmind_news",
        })
    return records


def fetch_monthly_revenue_records(ticker: str, data_loader_cls=DataLoader) -> tuple[list, dict | None]:
    from source_audit import audited_fetch

    recent_monthly_revenue = []
    monthly_revenue_audit = None
    if not is_taiwan_ticker(ticker) or data_loader_cls is None:
        return recent_monthly_revenue, monthly_revenue_audit

    def fetch_records():
        fm_dl = data_loader_cls()
        stock_id = _stock_id_from_ticker(ticker)
        start_date = (datetime.now() - timedelta(days=240)).strftime("%Y-%m-%d")
        df_rev = fm_dl.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date)
        records = []
        if df_rev is not None and not df_rev.empty:
            for _, row in df_rev.tail(6).iterrows():
                year = row.get("revenue_year")
                month = row.get("revenue_month")
                value = row.get("revenue")
                if year and month and value:
                    records.append(f"{year}年{month}月: NT${float(value) / 1e8:.2f}億")
        return records

    monthly_revenue_result = audited_fetch(
        "monthly_revenue",
        "FinMind TaiwanStockMonthRevenue",
        fetch_records,
        default=[],
        unavailable_message="FinMind 月營收未回傳可用資料。",
    )
    return monthly_revenue_result.get("value") or [], monthly_revenue_result.get("audit")


def fetch_institutional_trading_trend(ticker: str) -> dict:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}
    import math
    import time
    from zoneinfo import ZoneInfo
    from source_observation_freshness import parse_observation_date

    stock_id = _stock_id_from_ticker(ticker)
    today = datetime.fromtimestamp(time.time(), ZoneInfo("Asia/Taipei")).date()
    start_day = today - timedelta(days=max(INSTITUTIONAL_LOOKBACK_DAYS + 15, 45))
    start_date = start_day.isoformat()
    # The typed acquisition boundary records raised failures separately from empty data.
    df = DataLoader().taiwan_stock_institutional_investors(stock_id=stock_id, start_date=start_date)
    if df is None or df.empty:
        return {}

    df = df.copy()
    if not {"stock_id", "date", "name", "buy", "sell"}.issubset(df.columns):
        raise ValueError("Institutional response lacks required identity or observation fields")
    original_count = len(df)
    dates_parsed = df["date"].map(lambda value: parse_observation_date(str(value)))
    valid_dates = dates_parsed.map(lambda day: day is not None and start_day <= day <= today)
    df = df.loc[(df["stock_id"].astype(str).str.strip() == stock_id) & valid_dates].copy()
    df["date"] = dates_parsed.loc[df.index].map(lambda day: day.isoformat())
    for column in ("buy", "sell"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    valid_numbers = df["buy"].map(lambda value: math.isfinite(value) and value >= 0) & df["sell"].map(lambda value: math.isfinite(value) and value >= 0)
    df = df.loc[valid_numbers].copy()
    if df.empty:
        raise ValueError("Institutional response has no valid exact-stock dated observations")
    rejected_count = original_count - len(df)
    df["net_buy"] = df["buy"] - df["sell"]
    df["category"] = df["name"].map(lambda name: (
        "foreign" if "Foreign" in str(name)
        else "investment_trust" if "Investment_Trust" in str(name)
        else "dealer"
    ))
    by_day = df.groupby(["date", "category"], as_index=False)["net_buy"].sum()
    dates = sorted(by_day["date"].unique())[-INSTITUTIONAL_LOOKBACK_DAYS:]
    recent = by_day[by_day["date"].isin(dates)]
    totals = recent.groupby("category")["net_buy"].sum().to_dict()
    daily_total = recent.groupby("date")["net_buy"].sum().tail(10)
    total_net = sum(totals.values())
    last_5_net = recent[recent["date"].isin(dates[-5:])]["net_buy"].sum() if dates else 0
    from ..institutional_provider import institutional_window_status
    last_5_window_status = institutional_window_status(list(dates), ticker, 5)
    if total_net > 0 and last_5_net > 0:
        trend = "accumulation"
    elif total_net < 0 and last_5_net < 0:
        trend = "distribution"
    else:
        trend = "mixed"

    return {
        "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell",
        "lookback_trading_days": len(dates),
        "observed_date_count": len(dates),
        "observation_dates": [str(day) for day in dates],
        "window_basis": "available_observations; not proof of complete exchange sessions",
        "window_coverage_status": institutional_window_status(list(dates), ticker, INSTITUTIONAL_LOOKBACK_DAYS),
        "last_5_window_status": last_5_window_status,
        "rejected_record_count": rejected_count,
        "daily_category_observations": [
            {"date": str(row.date), "category": str(row.category), "net_buy_shares": int(row.net_buy),
             "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell", "unit": "shares"}
            for row in recent.itertuples(index=False)
        ],
        "latest_date": str(dates[-1]) if dates else "",
        "net_buy_shares_by_category": {key: int(value) for key, value in totals.items()},
        "net_buy_thousand_shares_by_category": {key: round(value / 1000, 2) for key, value in totals.items()},
        "total_net_buy_shares": int(total_net),
        "total_net_buy_thousand_shares": round(total_net / 1000, 2),
        "last_5_trading_days_net_buy_thousand_shares": round(last_5_net / 1000, 2) if last_5_window_status == "complete" else None,
        "trend": trend,
        "daily_total_net_buy_last_10": [
            {"date": str(date), "net_buy_thousand_shares": round(value / 1000, 2)}
            for date, value in daily_total.items()
        ],
    }


def _history_has_values(values: list) -> bool:
    return bool(values) and any(value is not None for value in values)


def _finmind_number(value) -> Optional[float]:
    if not pd.api.types.is_number(value) or pd.api.types.is_bool(value) or pd.api.types.is_complex(value):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _raw_twd_to_billion(value) -> Optional[float]:
    number = _finmind_number(value)
    return round(number / 1e9, 2) if number is not None else None


def _finmind_raw_value(df: pd.DataFrame, statement_date: str, type_candidates: list[str],
                       *, prefer_first: bool = False, origin_name: str | None = None) -> Optional[float]:
    """Require unique rows; aliases agree, or explicitly prioritize a present type."""
    if df is None or df.empty or not {"date", "type", "value"}.issubset(df.columns):
        return None
    values = []
    for field in type_candidates:
        rows = df[(df["date"] == statement_date) & (df["type"] == field)]
        if rows.empty:
            continue
        if len(rows) != 1:
            return None
        row = rows.iloc[0]
        if origin_name is not None:
            label = row.get("origin_name")
            normalized = "".join(label.split()).replace("（", "(").replace("）", ")") if isinstance(label, str) else ""
            if normalized != origin_name:
                return None
        value = _finmind_number(row.get("value"))
        if value is None:
            return None
        if prefer_first:
            return value
        values.append(value)
    return values[0] if values and all(value == values[0] for value in values) else None


def _finmind_annual_income(df: pd.DataFrame, statement_date: str, field: str,
                           *, parent_profit: bool = False) -> Optional[float]:
    # FinancialStatements contains individual quarters, including the December row.
    label = "淨利(淨損)歸屬於母公司業主" if parent_profit else None
    values = [_finmind_raw_value(df, statement_date[:4] + suffix, [field], origin_name=label)
              for suffix in ("-03-31", "-06-30", "-09-30", "-12-31")]
    if any(value is None for value in values):
        return None
    try:
        return _raw_twd_to_billion(math.fsum(values))
    except OverflowError:
        return None


def _finmind_statement_dates(*frames: pd.DataFrame) -> list[str]:
    dates = set()
    for df in frames:
        if df is not None and not df.empty and "date" in df.columns:
            for value in df["date"]:
                if not isinstance(value, str) or len(value) != 10 or not value.endswith("-12-31"):
                    continue
                try:
                    if datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value:
                        dates.add(value)
                except ValueError:
                    continue
    return sorted(dates)[-5:]


class _FinMindStatementValue(dict):
    """Keep the legacy value keys, with transport coverage owned by the audit."""
    def __init__(self, value: dict, components: dict):
        super().__init__(value)
        self.components = components


def _finmind_selected_fields_present(value: dict) -> bool:
    import math
    years = value.get("years") or []
    fields = ("revenue_history", "net_income_history", "gross_profit_history", "operating_income_history",
              "fcf_history", "total_assets_history", "total_equity_history")
    return bool(years) and all(
        len(value.get(field) or []) == len(years)
        and all(isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number)
                for number in value[field]) for field in fields
    )


def audited_finmind_financial_statement_fallback(ticker: str, *, fetcher=None, audit_fetch=None) -> dict:
    """Keep the existing guard/failure audit while retaining completed table values."""
    from source_audit import audited_fetch
    from .finmind_financial_transport import FinMindFinancialFetchError

    captured_error = None

    def fetch():
        nonlocal captured_error
        try:
            return (fetcher or fetch_finmind_financial_statement_fallback)(ticker)
        except FinMindFinancialFetchError as exc:
            captured_error = exc
            raise
        except Exception:
            # Even an unexpected adapter/parser failure must not replay the
            # entire three-request operation through the generic retry layer.
            captured_error = FinMindFinancialFetchError("unexpected_financial_failure")
            raise captured_error from None

    result = (audit_fetch or audited_fetch)(
        "financial_statements", "FinMind financial statement fallback", fetch,
        default={}, unavailable_message="FinMind 財報備援未回傳可用年度資料。",
    )
    if captured_error is not None:
        # audited_fetch already recorded the failure/cooldown. Do not clear it or
        # turn a nonempty partial dict into a successful provider operation.
        result["value"] = captured_error.partial_value
        result["audit"] = {**result["audit"], "component_statuses": captured_error.component_statuses}
    elif isinstance(result.get("value"), _FinMindStatementValue):
        value = result["value"]
        result["audit"] = {**result["audit"], "component_statuses": value.components,
                           "quality_status": "not_assessed"}
        complete = (all(value.components.get(name, {}).get("status") == "success"
                        for name in ("financials", "balance", "cashflow"))
                    and _finmind_selected_fields_present(value))
        if value and result["audit"]["status"] == "success" and not complete:
            result["audit"].update(status="degraded_enrichment", coverage_status="partial",
                                   message="FinMind 已取得部分財報；空表或必要欄位缺值仍保留。")
        else:
            result["audit"]["coverage_status"] = "selected_fields_present" if complete else "empty"
    return result


def fetch_finmind_financial_statement_fallback(ticker: str) -> dict:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}

    stock_id = _stock_id_from_ticker(ticker)
    start_date = (datetime.now() - timedelta(days=365 * 6 + 30)).strftime("%Y-%m-%d")

    from .finmind_financial_transport import fetch_statement_tables, FinMindFinancialFetchError

    outcome = fetch_statement_tables(stock_id, start_date)
    frames = {name: pd.DataFrame(rows) for name, rows in outcome["tables"].items()}
    result = _assemble_finmind_financial_statements(frames)
    if outcome["error"]:
        raise FinMindFinancialFetchError(
            outcome["error"]["reason"], status_code=outcome["error"].get("status_code"),
            partial_value=result, component_statuses=outcome["components"],
        )
    return _FinMindStatementValue(result, outcome["components"])


def _assemble_finmind_financial_statements(frames: dict) -> dict:
    """Annual quarter sums, year-end balances, and incomplete CF components."""
    financials = frames.get("financials")
    balance = frames.get("balance")
    cashflow = frames.get("cashflow")

    statement_dates = _finmind_statement_dates(financials, balance, cashflow)
    if not statement_dates:
        return {}

    rows_by_year = {}
    for statement_date in statement_dates:
        year = statement_date[:4]
        operating_cash_flow = _finmind_raw_value(
            cashflow, statement_date,
            ["NetCashInflowFromOperatingActivities", "CashFlowsFromOperatingActivities"],
        )
        ppe_cash_flow = _finmind_raw_value(cashflow, statement_date, ["PropertyAndPlantAndEquipment"])
        rows_by_year[year] = {
            "statement_date": statement_date,
            "revenue": _finmind_annual_income(financials, statement_date, "Revenue"),
            "net_income": _finmind_annual_income(financials, statement_date, "EquityAttributableToOwnersOfParent", parent_profit=True),
            "gross_profit": _finmind_annual_income(financials, statement_date, "GrossProfit"),
            "operating_income": _finmind_annual_income(financials, statement_date, "OperatingIncome"),
            # This dataset lacks verified intangible acquisition outflows. PPE
            # alone cannot stand in for the complete capital-expenditure scope.
            "free_cash_flow": None,
            "operating_cash_flow": operating_cash_flow,
            "property_and_equipment_cash_flow": ppe_cash_flow,
            "cash_flow_value_unit": "TWD",
            "free_cash_flow_status": "capex_scope_unverified" if operating_cash_flow is not None and ppe_cash_flow is not None else "missing_components",
            "total_assets": _raw_twd_to_billion(_finmind_raw_value(balance, statement_date, ["TotalAssets"])),
            "total_equity": _raw_twd_to_billion(_finmind_raw_value(
                balance, statement_date, ["EquityAttributableToOwnersOfParent", "Equity"], prefer_first=True)),
        }

    years = sorted(rows_by_year.keys())[-5:]
    return {
        "source": "FinMind TaiwanStockFinancialStatements/BalanceSheet/CashFlowsStatement",
        "years": years,
        "rows_by_year": rows_by_year,
        "revenue_history": [rows_by_year[year]["revenue"] for year in years],
        "net_income_history": [rows_by_year[year]["net_income"] for year in years],
        "gross_profit_history": [rows_by_year[year]["gross_profit"] for year in years],
        "operating_income_history": [rows_by_year[year]["operating_income"] for year in years],
        "fcf_history": [rows_by_year[year]["free_cash_flow"] for year in years],
        "total_assets_history": [rows_by_year[year]["total_assets"] for year in years],
        "total_equity_history": [rows_by_year[year]["total_equity"] for year in years],
    }


def _align_finmind_history(years: list[str], rows_by_year: dict, key: str) -> list:
    return [rows_by_year.get(str(year), {}).get(key) for year in years]
