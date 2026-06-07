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
    if DataLoader is not None and is_taiwan_ticker(ticker):
        start_date = (datetime.now() - timedelta(days=365 * 5 + 30)).strftime("%Y-%m-%d")
        try:
            df = DataLoader().taiwan_stock_per_pbr(stock_id=_stock_id_from_ticker(ticker), start_date=start_date)
            per_values = [float(v) for v in df.get("PER", []) if isinstance(v, (int, float)) and 0 < float(v) < 100]
            if len(per_values) >= 20:
                series = pd.Series(per_values)
                multiples = sorted({round(float(series.quantile(q)), 1) for q in [0.25, 0.5, 0.75, 0.9]})
                source = "FinMind 5-year PER quantiles"
        except Exception:
            pass

    bands = {
        f"{multiple:g}x": [round(e * multiple, 2) if e is not None else None for e in eps]
        for multiple in multiples
    }
    return {
        "years": years or [],
        "eps_twd": eps,
        "multiples": multiples,
        "bands": bands,
        "source": source,
    }
