"""Reusable stock-data payload factories for regression tests."""

from __future__ import annotations

from data_fetch.constants import DATA_SCHEMA_VERSION
from data_trust import build_data_trust, build_source_audit_entry


FRESH_AT = "2026-06-07T00:00:00+00:00"
FRESH_AT_EPOCH = 1780761600


def fresh_audited_payload(
    *,
    ticker: str = "FAKE",
    company_name: str = "Fake Semiconductor",
    provider: str = "fake-provider",
    include_financials: bool = True,
) -> dict:
    payload = {
        "data_schema_version": DATA_SCHEMA_VERSION,
        "ticker": ticker,
        "company_name": company_name,
        "current_price": 123.45,
        "current_price_fmt": "US$123.45",
        "market_cap_raw": 12_300_000_000,
        "market_cap_fmt": "US$12.3B",
        "pe_ratio": "18.2",
        "pe_ratio_raw": 18.2,
        "pb_ratio": "3.1",
        "gross_margin": "45.0%",
        "roe": "18.0%",
        "dividend_yield": "1.2%",
        "beta": "1.05",
        "industry": "Semiconductors",
        "fetch_date": "2026年06月07日",
        "price_history": {"2026-06-05": 121.0, "2026-06-06": 123.45},
        "recent_catalysts": [{"title": "Fake provider catalyst"}],
        "institutional_trading": {"trend": "neutral", "total_net_buy_thousand_shares": 0},
        "pe_river_chart": {"source": provider, "series": []},
        "source_freshness": {
            "market_data": {"stale": False, "fetched_at": FRESH_AT, "fetched_at_epoch": FRESH_AT_EPOCH},
            "financial_statements": {"stale": False, "fetched_at": FRESH_AT, "fetched_at_epoch": FRESH_AT_EPOCH},
        },
        "source_audit": [
            build_source_audit_entry("market_data", provider, "success", fetched_at=FRESH_AT, record_count=2),
        ],
    }
    if include_financials:
        payload.update(financial_history())
        payload["source_audit"].append(
            build_source_audit_entry("financial_statements", provider, "success", fetched_at=FRESH_AT, record_count=2)
        )
    payload["data_trust"] = build_data_trust(payload)
    return payload


def financial_history() -> dict:
    return {
        "years": ["2024", "2025"],
        "revenue_history": [10.0, 12.0],
        "net_income_history": [1.2, 1.8],
        "fcf_history": [0.8, 1.1],
        "gross_margin_history": [42.0, 45.0],
        "op_margin_history": [15.0, 18.0],
        "net_margin_history": [12.0, 15.0],
        "roe_history": [14.0, 18.0],
    }


def stale_audited_payload(*, source: str = "market_data") -> dict:
    payload = fresh_audited_payload()
    payload["source_freshness"][source] = {
        "stale": True,
        "fetched_at": "2026-06-01T00:00:00+00:00",
        "fetched_at_epoch": 1780243200,
    }
    payload["data_trust"] = build_data_trust(payload)
    return payload


def provider_sla_alert(
    *,
    source: str = "market_data",
    provider: str = "fake-provider",
    level: str = "warning",
    attempts: int = 3,
) -> dict:
    return {
        "source": source,
        "provider": provider,
        "alert_level": level,
        "alert_message": "success rate low",
        "success_rate": 0.4 if level == "critical" else 0.65,
        "attempts": attempts,
        "last_status": "error",
        "alert_basis": "last_24h",
        "windows": {
            "last_24h": {
                "attempts": attempts,
                "success_rate": 0.4 if level == "critical" else 0.65,
                "error_count": max(1, attempts - 1),
            }
        },
    }
