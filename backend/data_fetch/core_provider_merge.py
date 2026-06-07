"""Merge source-specific provider results into the legacy stock-data payload."""

from __future__ import annotations

from .types import ProviderResult


def merge_core_provider_result(data: dict, result: ProviderResult) -> None:
    value = result.value
    if result.source == "financial_statements" and isinstance(value, dict) and value:
        for key in (
            "years",
            "revenue_history",
            "net_income_history",
            "gross_profit_history",
            "operating_income_history",
            "fcf_history",
            "total_assets_history",
            "total_equity_history",
        ):
            if not data.get(key) and value.get(key):
                data[key] = value.get(key)
    elif result.source == "monthly_revenue" and isinstance(value, list):
        if not data.get("recent_monthly_revenue"):
            data["recent_monthly_revenue"] = value
    elif result.source == "institutional_trading" and isinstance(value, dict):
        if not data.get("institutional_trading"):
            data["institutional_trading"] = value
    elif result.source == "dynamic_peer_metrics" and isinstance(value, list):
        if not data.get("dynamic_peer_metrics"):
            data["dynamic_peer_metrics"] = value
    elif result.source == "pe_river_chart" and isinstance(value, dict):
        if not data.get("pe_river_chart") or data.get("pe_river_chart", {}).get("source") == "unavailable":
            data["pe_river_chart"] = value
