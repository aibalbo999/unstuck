"""Market and explicitly supplied instrument capabilities; never infer ETF from a code."""
from __future__ import annotations

from mapping_fields import safe_mapping_dict, safe_text
from data_freshness_market import is_taiwan_ticker

_TW_ONLY = {"monthly_revenue", "institutional_trading", "chip_data", "alternative_data",
            "social_sentiment", "taiwan_open_data", "official_disclosures", "company_ir", "twse_official", "twse_official_data"}
_COMPANY_ONLY = {"financial_statements", "monthly_revenue", "twse_official", "twse_official_data",
                 "pe_river_chart", "dynamic_peer_metrics", "peer_discovery", "earnings_call", "official_disclosures", "company_ir"}
_FUND_TYPES = {"ETF", "MUTUALFUND"}


def instrument_type(data: dict) -> str:
    data = safe_mapping_dict(data) or {}
    identity = safe_mapping_dict(data.get("company_identity")) or {}
    for value in (data.get("quote_type"), data.get("quoteType"), data.get("instrument_type"), identity.get("instrument_type")):
        value = safe_text(value).strip().upper()
        if value in {"ETF", "MUTUALFUND", "EQUITY", "INDEX", "CURRENCY", "CRYPTOCURRENCY", "FUTURE"}:
            return value
    return "unknown"


def source_applicability(source: str, data: dict, ticker: str | None = None) -> dict:
    data = safe_mapping_dict(data) or {}
    symbol = safe_text(ticker or data.get("ticker")).strip().upper()
    tw = is_taiwan_ticker(symbol)
    reason = None
    if symbol and source == "sec_edgar" and tw:
        reason = "market_outside_provider_coverage"
    elif symbol and source in _TW_ONLY and not tw:
        reason = "market_outside_provider_coverage"
    elif source in _COMPANY_ONLY and instrument_type(data) in _FUND_TYPES:
        reason = "company_financial_source_not_applicable_to_fund"
    return {"applicable": reason is None, "status": "not_applicable" if reason else "applicable",
            "reason_code": reason, "instrument_type": instrument_type(data)}


def source_is_applicable(source: str, data: dict, ticker: str | None = None) -> bool:
    return source_applicability(source, data, ticker)["applicable"]


def apply_source_applicability(data: dict) -> dict:
    """Annotate a newly fetched/copied payload without inventing unavailable fund analysis."""
    from data_trust_constants import SOURCE_AUDIT_SOURCES
    matrix = {source: source_applicability(source, data) for source in SOURCE_AUDIT_SOURCES}
    data["source_applicability"] = matrix
    freshness = dict(safe_mapping_dict(data.get('source_freshness')) or {})
    for source, capability in matrix.items():
        if not capability['applicable']:
            freshness[source] = {'source': source, 'status': 'not_applicable', 'stale': False,
                                 'is_fresh': None, 'fetched_at': None, 'cache_hit': False}
    data['source_freshness'] = freshness
    for entry in data.get("source_audit", []) or []:
        if isinstance(entry, dict) and not source_is_applicable(entry.get("source", ""), data):
            if entry.get("status") != "not_applicable":
                entry["observed_status"] = entry.get("status")
            entry.update(status="not_applicable", stale=False, record_count=0,
                         applicability_reason=matrix.get(entry.get("source"), {}).get("reason_code"))
    return data
