from __future__ import annotations

from typing import Any

from .utils import (
    _label,
    _metric,
    _number,
    _number_from_label,
    _percent_change,
    _percent_of,
    _signed_percent_label,
    _text,
)


def _dividends(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "yield": _number(data.get("dividend_yield_raw")),
        "yield_label": _label(data.get("dividend_yield"), data.get("dividend_yield_raw")),
        "annual_dividend": _number(data.get("dividend_rate_raw")),
        "annual_dividend_label": _label(data.get("dividend_rate"), data.get("dividend_rate_raw")),
        "payout_ratio": _number(data.get("payout_ratio_raw")),
        "payout_ratio_label": _label(data.get("payout_ratio"), data.get("payout_ratio_raw")),
        "ex_dividend_date": _text(data.get("ex_dividend_date")),
    }

def _dividend_profile(data: dict[str, Any]) -> dict[str, Any]:
    annual_dividend = _metric(data.get("dividend_rate_raw"), data.get("dividend_rate"))
    yield_metric = _metric(data.get("dividend_yield_raw"), data.get("dividend_yield"))
    payout_ratio = _metric(data.get("payout_ratio_raw"), data.get("payout_ratio"))
    history = _dividend_history(data)
    coverage = _dividend_coverage(data, annual_dividend.get("value"))
    has_data = any(
        value not in (None, "")
        for value in (
            annual_dividend.get("value"),
            yield_metric.get("value"),
            payout_ratio.get("value"),
            history.get("year_count"),
            coverage.get("fcf_coverage_ratio"),
        )
    )
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "股利資料不足",
            "annual_dividend": {},
            "yield": {},
            "payout_ratio": {},
            "history": {},
            "coverage": {},
            "signals": [],
        }
    return {
        "status": "available",
        "label": _dividend_label(history, payout_ratio.get("value"), coverage.get("fcf_coverage_ratio")),
        "annual_dividend": annual_dividend,
        "yield": yield_metric,
        "payout_ratio": payout_ratio,
        "history": history,
        "coverage": coverage,
        "signals": _dividend_signals(history, coverage),
    }

def _dividend_history(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("dividend_history") if isinstance(data.get("dividend_history"), dict) else {}
    years = [str(year) for year in source.get("years") or []]
    dividends = [_number(value) for value in source.get("dividends") or []]
    pairs = [(year, value) for year, value in zip(years, dividends, strict=False) if value is not None]
    years = [year for year, _ in pairs][-5:]
    dividends = [value for _, value in pairs][-5:]
    latest = dividends[-1] if dividends else None
    previous = dividends[-2] if len(dividends) >= 2 else None
    return {
        "years": years,
        "dividends": dividends,
        "year_count": len(dividends),
        "latest_annual_dividend": latest,
        "latest_yoy_pct": _percent_change(latest, previous),
        "source": _text(source.get("source")),
    }

def _dividend_coverage(data: dict[str, Any], annual_dividend: float | None) -> dict[str, Any]:
    free_cash_flow = _number(data.get("free_cash_flow_raw"), data.get("free_cash_flow"))
    shares = _number(data.get("shares_outstanding_raw"), data.get("shares_raw"), data.get("shares_outstanding"))
    dividend_cash_required = annual_dividend * shares if annual_dividend is not None and shares is not None else None
    coverage_ratio = (
        round(free_cash_flow / dividend_cash_required, 2)
        if free_cash_flow is not None and dividend_cash_required is not None and dividend_cash_required > 0
        else None
    )
    return {
        "free_cash_flow": free_cash_flow,
        "shares_outstanding": shares,
        "dividend_cash_required": dividend_cash_required,
        "fcf_coverage_ratio": coverage_ratio,
    }

def _dividend_label(history: dict[str, Any], payout_ratio: float | None, coverage_ratio: float | None) -> str:
    year_count = _number(history.get("year_count")) or 0
    latest_yoy = _number(history.get("latest_yoy_pct"))
    if year_count >= 3 and (latest_yoy is None or latest_yoy >= 0) and (coverage_ratio is None or coverage_ratio >= 1):
        return "配息穩定"
    if payout_ratio is not None and payout_ratio > 0.8:
        return "配息壓力偏高"
    if latest_yoy is not None and latest_yoy < 0:
        return "配息下滑"
    return "股利摘要"

def _dividend_signals(history: dict[str, Any], coverage: dict[str, Any]) -> list[str]:
    signals = []
    year_count = _number(history.get("year_count"))
    if year_count:
        signals.append(f"連續 {int(year_count)} 年有配息")
    latest_yoy = _number(history.get("latest_yoy_pct"))
    if latest_yoy is not None:
        signals.append(f"近一年配息成長 {_signed_percent_label(latest_yoy)}")
    coverage_ratio = _number(coverage.get("fcf_coverage_ratio"))
    if coverage_ratio is not None:
        signals.append(f"FCF 覆蓋 {coverage_ratio:.1f}x")
    return signals[:3]

def _financial_health(data: dict[str, Any]) -> dict[str, Any]:
    cash = _number(data.get("total_cash_raw"), data.get("total_cash"))
    debt = _number(data.get("total_debt_raw"), data.get("total_debt"))
    debt_to_equity = _number(data.get("debt_to_equity_raw"), _number_from_label(data.get("debt_to_equity")))
    health = {
        "revenue_ttm": _metric(data.get("revenue_ttm_raw"), data.get("revenue_ttm")),
        "revenue_growth": _metric(data.get("latest_annual_revenue_growth_raw"), data.get("latest_annual_revenue_growth") or data.get("revenue_growth")),
        "gross_margin": _metric(data.get("gross_margin_raw"), data.get("gross_margin")),
        "operating_margin": _metric(data.get("operating_margin_raw"), data.get("operating_margin")),
        "profit_margin": _metric(data.get("profit_margin_raw"), data.get("profit_margin")),
        "free_cash_flow": _metric(data.get("free_cash_flow_raw"), data.get("free_cash_flow")),
        "balance_sheet": {
            "cash": cash,
            "cash_label": _label(data.get("total_cash"), cash),
            "debt": debt,
            "debt_label": _label(data.get("total_debt"), debt),
            "debt_to_equity": debt_to_equity,
            "debt_to_equity_label": _label(data.get("debt_to_equity"), debt_to_equity),
        },
    }
    health["highlights"] = _financial_highlights(health)
    return health

def _financial_trends(data: dict[str, Any]) -> dict[str, Any]:
    rows = _financial_trend_rows(data)[-5:]
    if not rows:
        return {
            "status": "insufficient_data",
            "label": "財報趨勢不足",
            "period_type": "annual",
            "rows": [],
            "signals": [],
            "source": "",
        }
    latest = rows[-1]
    return {
        "status": "available",
        "label": _financial_trend_label(latest),
        "period_type": _text(data.get("financial_period_type")) or "annual",
        "rows": rows,
        "signals": _financial_trend_signals(latest),
        "source": _text(data.get("financial_history_source")) or "financial_history",
    }

def _financial_trend_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    histories = {
        "revenue": data.get("revenue_history") or [],
        "net_income": data.get("net_income_history") or [],
        "free_cash_flow": data.get("fcf_history") or [],
        "gross_margin_pct": data.get("gross_margin_history") or [],
        "operating_margin_pct": data.get("op_margin_history") or [],
        "net_margin_pct": data.get("net_margin_history") or [],
        "roe_pct": data.get("roe_history") or [],
    }
    periods = [str(item) for item in data.get("years") or data.get("financial_periods") or []]
    length = max([len(periods), *(len(items) for items in histories.values() if isinstance(items, list))], default=0)
    if length <= 0:
        return []
    if not periods:
        periods = _fallback_periods(length)
    rows = []
    for index in range(length):
        row = {
            "period": periods[index] if index < len(periods) else _fallback_periods(length)[index],
            "revenue": _history_number(histories["revenue"], index),
            "revenue_yoy_pct": _history_yoy(histories["revenue"], index),
            "net_income": _history_number(histories["net_income"], index),
            "net_income_yoy_pct": _history_yoy(histories["net_income"], index),
            "free_cash_flow": _history_number(histories["free_cash_flow"], index),
            "free_cash_flow_yoy_pct": _history_yoy(histories["free_cash_flow"], index),
            "gross_margin_pct": _history_number(histories["gross_margin_pct"], index),
            "operating_margin_pct": _history_number(histories["operating_margin_pct"], index),
            "net_margin_pct": _history_number(histories["net_margin_pct"], index),
            "roe_pct": _history_number(histories["roe_pct"], index),
        }
        if any(row.get(key) is not None for key in row if key != "period"):
            rows.append(row)
    return rows

def _history_number(values: Any, index: int) -> float | None:
    return _number(values[index]) if isinstance(values, list) and index < len(values) else None

def _history_yoy(values: Any, index: int) -> float | None:
    if not isinstance(values, list) or index <= 0 or index >= len(values):
        return None
    return _percent_change(_history_number(values, index), _history_number(values, index - 1))

def _fallback_periods(length: int) -> list[str]:
    if length <= 1:
        return ["最新"]
    return [f"T-{length - index - 1}" for index in range(length - 1)] + ["最新"]

def _financial_trend_label(latest: dict[str, Any]) -> str:
    revenue_yoy = _number(latest.get("revenue_yoy_pct"))
    net_income_yoy = _number(latest.get("net_income_yoy_pct"))
    if revenue_yoy is not None and revenue_yoy < 0:
        return "營收下滑"
    if revenue_yoy is not None and revenue_yoy > 0 and net_income_yoy is not None and net_income_yoy > 0:
        return "營收與獲利成長"
    if revenue_yoy is not None and revenue_yoy > 0 and net_income_yoy is not None and net_income_yoy <= 0:
        return "營收成長但獲利承壓"
    return "財報趨勢"

def _financial_trend_signals(latest: dict[str, Any]) -> list[str]:
    signals = []
    for label, key in (
        ("營收 YoY", "revenue_yoy_pct"),
        ("淨利 YoY", "net_income_yoy_pct"),
        ("FCF YoY", "free_cash_flow_yoy_pct"),
    ):
        value = _number(latest.get(key))
        if value is not None:
            signals.append(f"{label} {_signed_percent_label(value)}")
    return signals[:3]

def _financial_highlights(health: dict[str, Any]) -> list[str]:
    highlights = []
    revenue_growth = _number(health.get("revenue_growth", {}).get("value"))
    free_cash_flow = _number(health.get("free_cash_flow", {}).get("value"))
    balance_sheet = health.get("balance_sheet", {})
    cash = _number(balance_sheet.get("cash"))
    debt = _number(balance_sheet.get("debt"))
    if revenue_growth is not None and revenue_growth > 0:
        highlights.append("營收成長")
    if free_cash_flow is not None and free_cash_flow > 0:
        highlights.append("FCF 為正")
    if cash is not None and debt is not None:
        highlights.append("現金高於負債" if cash >= debt else "負債高於現金")
    return highlights[:4]
