"""Valuation helper sources such as P/E river chart data."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from financial_tools import safe_float

from .identity import _stock_id_from_ticker, is_taiwan_ticker
from .taiwan import DataLoader


def build_pe_river_chart_data(ticker: str, years: list[str], net_income_history: list, shares_outstanding) -> dict:
    shares = safe_float(shares_outstanding)
    eps = []
    for value in net_income_history or []:
        number = safe_float(value)
        eps.append(round(number * 1e9 / shares, 2) if number is not None and shares else None)

    multiples = [10, 12, 15, 18]
    source = "default multiples"
    sample_count = 0
    fallback_reason = "historical_provider_unavailable"
    loader = df = None
    if DataLoader is not None and is_taiwan_ticker(ticker):
        start_date = (datetime.now() - timedelta(days=365 * 5 + 30)).strftime("%Y-%m-%d")
        try:
            loader = DataLoader()
            from finmind_per_lineage import bounded_per_frame
            df = bounded_per_frame(loader, stock_id=_stock_id_from_ticker(ticker), start_date=start_date)
            per_values = [float(v) for v in df.get("PER", []) if isinstance(v, (int, float)) and 0 < float(v) < 100]
            sample_count = len(per_values)
            fallback_reason = "insufficient_historical_samples"
            if len(per_values) >= 20:
                series = pd.Series(per_values)
                multiples = sorted({round(float(series.quantile(q)), 1) for q in [0.25, 0.5, 0.75, 0.9]})
                source = "FinMind 5-year PER quantiles"
                fallback_reason = None
        except Exception:
            pass

    bands = {
        f"{multiple:g}x": [round(e * multiple, 2) if e is not None else None for e in eps]
        for multiple in multiples
    }
    result = {
        "years": years or [],
        "eps_twd": eps,
        "multiples": multiples,
        "bands": bands,
        "source": source,
        "valuation_basis": "historical_quantiles" if fallback_reason is None else "scenario_assumption",
        "historical_quantiles_available": fallback_reason is None,
        "historical_sample_count": sample_count,
        "fallback_reason": fallback_reason,
        "coverage_notes": [] if fallback_reason is None else ["預設本益比僅為情境假設，非歷史分位數或獨立市場證據。"],
    }

    if fallback_reason is None and loader is not None:
        try:
            from finmind_per_lineage import bind_per_quantiles, PerResult
            lineage = bind_per_quantiles(loader, df, result, ticker)
            if lineage is not None:
                return PerResult(result, lineage)
        except Exception:
            pass
    return result
