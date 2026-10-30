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
    from FinMind.data import DataLoader as _FinMindDataLoader
    from finmind_transport_receipts import observed_loader_class
    DataLoader = observed_loader_class(_FinMindDataLoader)
except ImportError:
    DataLoader = None


def fetch_finmind_news_catalysts(ticker: str) -> list[dict]:
    from .finmind_news import fetch_finmind_news_result
    from ..types import FetchRequest
    return fetch_finmind_news_result(FetchRequest.from_ticker(ticker)).value


def fetch_monthly_revenue_records(ticker: str, data_loader_cls=DataLoader, *, force_refresh=False) -> tuple[list, dict | None]:
    from source_audit import audited_fetch

    recent_monthly_revenue = []
    monthly_revenue_audit = None
    if not is_taiwan_ticker(ticker) or data_loader_cls is None:
        return recent_monthly_revenue, monthly_revenue_audit

    from .finmind_monthly_revenue import fetch_monthly_records
    monthly_revenue_result = fetch_monthly_records(
        ticker, data_loader_cls, audit_fetch=audited_fetch, force_refresh=force_refresh)
    return monthly_revenue_result.get("value") or [], monthly_revenue_result.get("audit")


def fetch_institutional_trading_trend(ticker: str) -> dict:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}
    import math
    import time
    from zoneinfo import ZoneInfo
    from source_observation_freshness import parse_observation_date

    stock_id = _stock_id_from_ticker(ticker)
    now_epoch = time.time()
    moment = datetime.fromtimestamp(now_epoch, ZoneInfo("Asia/Taipei"))
    today = moment.date()
    start_day = today - timedelta(days=max(INSTITUTIONAL_LOOKBACK_DAYS + 15, 45))
    # Holidays can make 45 calendar days shorter than the requested 30
    # exchange sessions. Keep the conservative fallback when the calendar is
    # unknown; never manufacture a missing observation or a zero trade.
    from official_institutional_source import expected_sessions
    sessions = expected_sessions(ticker, now_epoch, INSTITUTIONAL_LOOKBACK_DAYS, include_provisional=True)
    if sessions:
        start_day = min(start_day, datetime.fromisoformat(sessions[-1]).date())
        end_day = datetime.fromisoformat(sessions[0]).date()
    else:
        # No known session is not authorization to manufacture a query bound.
        return {}
    start_date = start_day.isoformat()
    end_date = end_day.isoformat()
    # The typed acquisition boundary records raised failures separately from empty data.
    loader=DataLoader()
    df = loader.taiwan_stock_institutional_investors(
        stock_id=stock_id, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return {}

    from official_response_evidence import archive_response
    acquired=datetime.fromtimestamp(time.time(),ZoneInfo("UTC")).isoformat()
    source_url=loader._dispatcher_url("TaiwanStockInstitutionalInvestorsBuySell") if hasattr(loader,"_dispatcher_url") else None
    sdk_evidence=archive_response(df.to_json(orient="records",force_ascii=False,date_format="iso").encode(),source_url=source_url,retrieved_at=acquired,evidence_kind="sdk_dataframe_json_not_raw_http",http_status=None)
    sdk_evidence["query"]={"dataset":"TaiwanStockInstitutionalInvestorsBuySell","data_id":stock_id,
                           "start_date":start_date,"end_date":end_date}
    df = df.copy()
    if not {"stock_id", "date", "name", "buy", "sell"}.issubset(df.columns):
        raise ValueError("Institutional response lacks required identity or observation fields")
    original_count = len(df)
    dates_parsed = df["date"].map(lambda value: parse_observation_date(str(value)))
    exact_stock = df["stock_id"].astype(str).str.strip() == stock_id
    beyond_end_date = exact_stock & dates_parsed.map(lambda day: day is not None and day > end_day)
    valid_dates = dates_parsed.map(lambda day: day is not None and start_day <= day <= end_day)
    df = df.loc[exact_stock & valid_dates].copy()
    df["date"] = dates_parsed.loc[df.index].map(lambda day: day.isoformat())
    # Keep booleans distinct before pandas converts them to numeric 0/1.
    valid_numbers = ~df["buy"].map(pd.api.types.is_bool) & ~df["sell"].map(pd.api.types.is_bool)
    for column in ("buy", "sell"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
        valid_numbers &= df[column].map(lambda value: math.isfinite(value) and value >= 0 and int(value) == value)
    df = df.loc[valid_numbers].copy()
    if df.empty:
        raise ValueError("Institutional response has no valid exact-stock dated observations")
    provisional_excluded_count = int(beyond_end_date.sum())
    rejected_count = original_count - len(df) - provisional_excluded_count
    df["net_buy"] = df["buy"] - df["sell"]
    df["category"] = df["name"].map(lambda name: (
        "foreign" if "Foreign" in str(name)
        else "investment_trust" if "Investment_Trust" in str(name)
        else "dealer"
    ))
    by_day = df.groupby(["date", "category"], as_index=False)["net_buy"].sum()
    dates = sorted(by_day["date"].unique())[-INSTITUTIONAL_LOOKBACK_DAYS:]
    recent = by_day[by_day["date"].isin(dates)]
    from institutional_observations import summarize_observations
    records = [
        {"date": str(row.date), "category": str(row.category), "net_buy_shares": int(row.net_buy),
         "source": "FinMind TaiwanStockInstitutionalInvestorsBuySell", "unit": "shares"}
        for row in recent.itertuples(index=False)
    ]
    summary = summarize_observations(records, ticker, limit=INSTITUTIONAL_LOOKBACK_DAYS,
                                     rejected_count=rejected_count)
    sdk_evidence["response_row_count"] = original_count
    sdk_evidence["excluded_after_end_date_row_count"] = provisional_excluded_count
    from market_evidence_policy import publication_observation
    return {"source_provenance": sdk_evidence, **summary,
            "publication_observation": publication_observation(
                summary.get('latest_date'), moment=moment,
                provider='FinMind TaiwanStockInstitutionalInvestorsBuySell', retrieved_at=acquired, ticker=ticker)}


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
    def __init__(self, value: dict, components: dict, cache_metadata: dict | None = None):
        super().__init__(value)
        self.components = components
        self.cache_metadata = cache_metadata or {}


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
    cache_metadata = (getattr(captured_error, "cache_metadata", {}) if captured_error is not None
                      else getattr(result.get("value"), "cache_metadata", {}))
    if cache_metadata.get("cache_hit") and not cache_metadata.get("stale"):
        # Retained source values help the radar evaluate its condition, but
        # are not a new provider acquisition in the SLA denominator.
        original_status = result["audit"].get("status")
        result["audit"].update(status="skipped_fresh_cache" if original_status == "success" else original_status,
                               cache_hit=True,
                               event_kind="cache_hit", stale=False,
                               fetched_at_epoch=cache_metadata.get("fetched_at_epoch"),
                               message=("沿用先前抓取失敗時保留的部分年度資料；原始錯誤仍見 component_statuses。"
                                        if captured_error is not None else
                                        "沿用仍在有效期內的 FinMind 年度財報觀測。"))
    return result


def fetch_finmind_financial_statement_fallback(ticker: str, *, use_cache: bool = False) -> dict:
    if DataLoader is None or not is_taiwan_ticker(ticker):
        return {}

    def acquire() -> dict:
        from .finmind_financial_transport import fetch_statement_tables

        stock_id = _stock_id_from_ticker(ticker)
        start_date = (datetime.now() - timedelta(days=365 * 6 + 30)).strftime("%Y-%m-%d")
        outcome = fetch_statement_tables(stock_id, start_date)
        frames = {name: pd.DataFrame(rows) for name, rows in outcome["tables"].items()}
        return {"value": _assemble_finmind_financial_statements(frames),
                "components": outcome["components"], "error": outcome["error"]}

    metadata = {}
    if use_cache:
        from shared_provider_cache import shared_fetch

        # Financial statement rows are slow moving. Cache the compact parsed
        # result, not multi-megabyte raw transport frames. An incomplete HTTP
        # operation has only a short retry interval; forced report refreshes
        # still bypass this radar-only cache.
        acquired, metadata = shared_fetch(
            f"finmind_financial_radar:v1:{ticker}:{datetime.now():%Y-%m-%d}",
            acquire, freshness_seconds=4 * 60 * 60,
            result_ttl=lambda row: 60 if row.get("error") else 4 * 60 * 60,
            lock_wait_seconds=21,
        )
        if not isinstance(acquired, dict):
            from .finmind_financial_transport import FinMindFinancialFetchError
            error = FinMindFinancialFetchError(str(metadata.get("error_kind") or "cache_unavailable"))
            error.cache_metadata = metadata
            raise error
    else:
        acquired = acquire()

    from .finmind_financial_transport import FinMindFinancialFetchError
    result = acquired["value"]
    if acquired["error"]:
        error = FinMindFinancialFetchError(
            acquired["error"]["reason"], status_code=acquired["error"].get("status_code"),
            partial_value=result, component_statuses=acquired["components"],
        )
        error.cache_metadata = metadata
        raise error
    return _FinMindStatementValue(result, acquired["components"], metadata)


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
