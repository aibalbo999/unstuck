"""Data-shaping helpers for prompt JSON payloads."""

from __future__ import annotations

import pandas as pd

from financial_tools import raw_twd_to_billion_twd, safe_float
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
    from data_fetch.financial_history_basis import INSTITUTION_SCHEMAS
    years = _safe_iterable_prefix(dict.get(data, "years", []))
    typed_net_revenue = _prompt_financial_history_basis(data).get("statement_schema") in INSTITUTION_SCHEMAS
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
        if typed_net_revenue:
            rows[-1]["net_revenue_billion_twd"] = _prompt_number(_history_value_at(data, "net_revenue_history", idx))
    return _limit_history_rows(rows, dict.get(data, "_prompt_history_year_limit"))


def _prompt_financial_history_basis(data: dict) -> dict:
    from data_fetch.financial_history_basis import prompt_history_basis
    return prompt_history_basis(data)


def _prompt_financial_institution_history(data: dict) -> dict:
    from data_fetch.financial_history_basis import INSTITUTION_SCHEMAS, BANK_SCHEMA, HOLDING_SCHEMA, PUBLIC_HOLDING_SCHEMA, AUDITED_HOLDING_SCHEMA
    statement = safe_mapping_dict(dict.get(data, "sector_specific_financials"))
    if statement is None:
        return {}
    schema = dict.get(statement, "schema")
    if schema == 'ordinary_individual.v1':
        from data_fetch.market_sources.ordinary_individual_annual import project_individual_history, FIELDS, NOTE
        if project_individual_history(statement,dict.get(data,'ticker','')) is None:return {}
        fields=(*FIELDS.values(),'free_cash_flow')
        basis_note=NOTE
    elif schema == "broker_consolidated.v1":
        fields = ("reported_revenue", "brokerage_fee_income", "underwriting_revenue",
                  "net_income_attributable", "assets", "equity", "operating_cash_flow",
                  "ppe_purchase", "intangible_purchase", "free_cash_flow")
        basis_note = ("reported_revenue_is_securities_broker_statement_line_not_bank_net_revenue_or_general_industry_revenue; "
                      "brokerage_and_underwriting_are_components_not_total_revenue; gross_profit_not_supplied")
    elif schema in INSTITUTION_SCHEMAS:
        documents = dict.get(statement, "documents", [])
        bank_receipt = ("statement_taxonomy" in statement
                        or isinstance(documents, list) and any(isinstance(doc,dict)
                            and ("statement_taxonomy" in doc or "source_record_archive" in doc) for doc in documents))
        if schema in {BANK_SCHEMA, HOLDING_SCHEMA, PUBLIC_HOLDING_SCHEMA, AUDITED_HOLDING_SCHEMA} or bank_receipt:
            from data_fetch.financial_history_basis import project_financial_institution_histories
            if project_financial_institution_histories(statement, dict.get(data, "ticker", "")) is None:
                return {}
        fields = ("interest_income", "net_interest_revenue", "net_fee_revenue", "net_revenue",
                  "net_income_attributable", "assets", "equity", "operating_cash_flow",
                  "ppe_purchase", "intangible_purchase", "free_cash_flow")
        basis_note = "net_revenue_is_financial_institution_statement_line_not_general_industry_revenue; gross_profit_and_operating_income_not_supplied"
        if schema == AUDITED_HOLDING_SCHEMA:
            basis_note += "; issuer_published_audited_English_translation_Chinese_original_prevails; comparative_restatements_retained_not_original_PIT; selected_whole_native_pages_not_whole_book_images"
    elif ((schema == "insurer_individual.v1" and dict.get(statement, "report_scope") == "individual")
          or (schema == "insurer_standalone.v1" and dict.get(statement, "report_scope") == "standalone")):
        fields = ("insurance_operating_revenue", "net_operating_income", "profit_loss",
                  "assets", "equity", "operating_cash_flow", "ppe_purchase",
                  "intangible_purchase", "free_cash_flow")
        basis_note = ("individual_insurer_statement_not_consolidated_group; insurance_operating_revenue_"
                      "not_bank_net_revenue_or_general_industry_revenue; gross_profit_not_supplied")
        if schema == "insurer_standalone.v1":
            from data_fetch.financial_history_basis import project_insurer_standalone_histories
            if project_insurer_standalone_histories(statement, dict.get(data, "ticker", "")) is None:
                return {}
            basis_note = ("standalone_insurer_no_subsidiaries_in_each_filing; insurance_operating_revenue_"
                          "not_bank_net_revenue; profit_loss_not_parent_attributable_net_income; gross_profit_not_supplied")
    else:
        return {}
    by_year = safe_mapping_dict(dict.get(statement, "raw_twd_by_year")) or {}
    years = dict.get(statement, "years")
    if not isinstance(years, list) or not years or len(years) > 5:
        return {}
    bank_unknown_fields = {"intangible_purchase", "free_cash_flow"} if schema == BANK_SCHEMA else set()
    if bank_unknown_fields and any(
            isinstance(row, dict) and row.get("intangible_purchase") is None
            for row in by_year.values()):
        basis_note += "; bank filing omits an intangible-purchase fact for affected years, so free cash flow remains unknown and is not zero"
    rows = []
    for year in years:
        if not isinstance(year, str) or len(year) != 4 or not year.isdigit():
            return {}
        facts = safe_mapping_dict(dict.get(by_year, year))
        if facts is None or any(
                type(dict.get(facts, field)) is not int
                and not (field in bank_unknown_fields and dict.get(facts, field) is None)
                for field in fields):
            return {}
        rows.append({"year": year, **{field + "_billion_twd": raw_twd_to_billion_twd(dict.get(facts, field))
                                       for field in fields}})
    return {"schema": schema, "report_scope": dict.get(statement, "report_scope", "consolidated"),
            "unit": "billion_twd",
            "basis_note": basis_note,
            "rows": _limit_history_rows(rows, dict.get(data, "_prompt_history_year_limit"))}


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
        "valuation_basis": dict.get(pe_river, "valuation_basis"),
        "historical_quantiles_available": dict.get(pe_river, "historical_quantiles_available"),
        "coverage_notes": dict.get(pe_river, "coverage_notes", []),
    }


def _agent_context(data: dict) -> dict:
    keys = (
        "macro_indicators",
        "chip_data",
        "alternative_data",
        "annual_workforce",
        "sentiment_context",
        "social_sentiment",
        "sec_edgar",
        "taiwan_open_data",
        "earnings_call",
        "conference_presentation",
    )
    context = {key: value for key in keys if _has_prompt_value(value := dict.get(data, key))}
    documents = dict.get(data, "official_disclosures")
    if isinstance(documents, dict) and documents:
        from source_document_prompt import document_prompt_context
        context["official_disclosures"] = document_prompt_context(documents)
    from prompt_evidence import prompt_evidence_copy
    return prompt_evidence_copy(context)
