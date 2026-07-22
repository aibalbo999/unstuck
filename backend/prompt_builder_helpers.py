"""Data-shaping helpers for prompt JSON payloads."""

from __future__ import annotations

import pandas as pd

from financial_tools import safe_float
from mapping_fields import safe_mapping_dict
from prompt_source_audit import prompt_source_audit_summary


def _prompt_number(value, decimals=4):
    number = safe_float(value)
    if number is None:
        return None
    try:
        if pd.isna(number):
            return None
    except Exception:
        pass
    return round(number, decimals)


def _prompt_ratio_to_pct(value, decimals=4):
    number = _prompt_number(value, decimals + 2)
    if number is None:
        return None
    return round(number * 100, decimals)


def _prompt_history_rows(data: dict) -> list[dict]:
    years = _safe_iterable_prefix(dict.get(data, "years", []))
    rows = []
    for idx, year in enumerate(years):
        rows.append({
            "year": str(year),
            "revenue_billion_twd": _prompt_number(_history_value_at(data, "revenue_history", idx)),
            "net_income_billion_twd": _prompt_number(_history_value_at(data, "net_income_history", idx)),
            "gross_profit_billion_twd": _prompt_number(_history_value_at(data, "gross_profit_history", idx)),
            "operating_income_billion_twd": _prompt_number(_history_value_at(data, "operating_income_history", idx)),
            "free_cash_flow_billion_twd": _prompt_number(_history_value_at(data, "fcf_history", idx)),
            "gross_margin_pct": _prompt_number(_history_value_at(data, "gross_margin_history", idx)),
            "operating_margin_pct": _prompt_number(_history_value_at(data, "op_margin_history", idx)),
            "net_margin_pct": _prompt_number(_history_value_at(data, "net_margin_history", idx)),
            "roe_pct": _prompt_number(_history_value_at(data, "roe_history", idx)),
            "total_assets_billion_twd": _prompt_number(_history_value_at(data, "total_assets_history", idx)),
            "total_equity_billion_twd": _prompt_number(_history_value_at(data, "total_equity_history", idx)),
        })
    return _limit_history_rows(rows, dict.get(data, "_prompt_history_year_limit"))


def _history_value_at(data: dict, key: str, idx: int):
    values = _safe_iterable_prefix(dict.get(data, key, []), idx + 1)
    return values[idx] if idx < len(values) else None


def _limit_history_rows(rows: list[dict], raw_limit) -> list[dict]:
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return rows
    if limit <= 0 or len(rows) <= limit:
        return rows

    indexed_years = []
    for index, row in enumerate(rows):
        try:
            year_value = int(str(row.get("year") or "").strip())
        except ValueError:
            year_value = None
        indexed_years.append((index, year_value))

    if all(year_value is not None for _, year_value in indexed_years):
        selected_indices = {
            index
            for index, _year in sorted(indexed_years, key=lambda item: item[1] or 0)[-limit:]
        }
        return [row for index, row in enumerate(rows) if index in selected_indices]
    return rows[-limit:]


def _prompt_company_identity(data: dict) -> dict:
    identity = raw_identity if isinstance(raw_identity := dict.get(data, "company_identity"), dict) else {}
    return {
        "ticker": dict.get(data, "ticker"),
        "company_name": dict.get(data, "company_name"),
        "stock_id": dict.get(identity, "stock_id"),
        "official_name": dict.get(identity, "official_name"),
        "legal_name": dict.get(identity, "legal_name"),
        "allowed_aliases": dict.get(identity, "allowed_aliases", []),
        "forbidden_aliases": dict.get(identity, "forbidden_aliases", []),
        "industry_categories": dict.get(identity, "industry_categories", []),
        "same_industry_peers": dict.get(identity, "same_industry_peers", []),
    }


def _prompt_data_trust(data: dict) -> dict:
    trust = safe_mapping_dict(dict.get(data, "data_trust")) or {}
    return {
        "status": dict.get(trust, "status", "unknown"),
        "critical_failures": _safe_iterable_prefix(dict.get(trust, "critical_failures", [])),
        "stale_sources": _safe_iterable_prefix(dict.get(trust, "stale_sources", [])),
        "last_market_data_at": dict.get(trust, "last_market_data_at"),
        "notes": _safe_iterable_prefix(dict.get(trust, "notes", [])),
        "reason_codes": _safe_iterable_prefix(dict.get(trust, "reason_codes", [])),
    }


def _prompt_source_audit_summary(data: dict) -> list[dict]:
    return prompt_source_audit_summary(data)


def _has_prompt_value(value) -> bool:
    try:
        return value is not None and bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return value is not None


def _compact_list(items, limit: int) -> list:
    try:
        max_items = max(0, int(limit))
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return []
    return _safe_iterable_prefix(items, max_items)


def _safe_iterable_prefix(items, limit: int | None = None) -> list:
    if items is None or limit == 0:
        return []
    try:
        iterator = iter(items)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return []
    values = []
    while limit is None or len(values) < limit:
        try:
            values.append(next(iterator))
        except (StopIteration, TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
            return values
    return values


def _compact_pe_river(pe_river: dict) -> dict:
    if not isinstance(pe_river, dict):
        return {}
    bands = raw_bands if isinstance(raw_bands := dict.get(pe_river, "bands"), dict) else {}
    return {
        "source": dict.get(pe_river, "source"),
        "years": _safe_iterable_prefix(dict.get(pe_river, "years", []))[-5:],
        "multiples": _compact_list(dict.get(pe_river, "multiples", []), 5),
        "band_labels": list(bands.keys())[:5],
    }


def _agent_context(data: dict) -> dict:
    keys = (
        "macro_indicators",
        "chip_data",
        "alternative_data",
        "sentiment_context",
        "social_sentiment",
        "sec_edgar",
        "taiwan_open_data",
        "earnings_call",
    )
    return {key: value for key in keys if _has_prompt_value(value := dict.get(data, key))}
