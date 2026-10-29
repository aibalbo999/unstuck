"""Peer discovery and peer metric source helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import date, datetime
import re

import pandas as pd
import yfinance as yf

from .common import _run_named_fetches
from .identity import is_taiwan_ticker
from .official_broker_cohort import get_official_broker_candidates
from .official_convenience_peer_cohort import get_official_convenience_candidates
from .official_steel_wire_peer_cohort import get_official_steel_wire_candidates
from .official_construction_peer_cohort import get_official_construction_candidates
from .official_food_processing_peer_cohort import get_official_food_processing_candidates
from .official_thermal_peer_cohort import get_official_thermal_candidates, verified_thermal_candidates
from .official_airline_peer_cohort import (get_official_airline_candidates, verified_airline_candidates,
                                          related_airline, IDENTITIES as AIRLINES, SCOPE as AIRLINE_SCOPE)
from .moneydj_numeric_candidates import get_published_food_biotech_candidates
from .moneydj_medical_peer_cohort import get_medical_cohort_candidates
from .official_underwriter_peer_cohort import documented_peer_candidates
from .peer_recovery import (_today, finite_number, fetch_peer_valuation_fallback,
                            industry_comparability, load_peer_stock_master, resolve_legacy_peer_candidates)
from .peer_selection import (
    CompanyProfile,
    rank_peer_candidates,
    ranked_profiles_from_identity,
    select_peer_profiles,
)


GLOBAL_PEER_HINTS = [
    (["半導體", "Semiconductor", "晶圓", "foundry"], [("Intel", "INTC"), ("Samsung Electronics", "005930.KS"), ("UMC", "2303.TW"), ("SMIC", "0981.HK")]),
    (["記憶體", "Memory", "DRAM", "NAND"], [("Micron", "MU"), ("SK hynix", "000660.KS"), ("Samsung Electronics", "005930.KS")]),
    (["面板", "Display", "LCD", "OLED"], [("AUO", "2409.TW"), ("Innolux", "3481.TW"), ("LG Display", "LPL"), ("BOE", "000725.SZ")]),
    (["航運", "Shipping", "Marine"], [("Evergreen Marine", "2603.TW"), ("Yang Ming", "2609.TW"), ("Wan Hai", "2615.TW"), ("Maersk", "MAERSK-B.CO")]),
]
# These annual-report links document a reinsurance business, not metric
# comparability. Current ticker, equity type and fine industry are checked
# again against the live quote before any metric row is admitted.
REINSURANCE_GLOBAL_PEERS = (
    ("RenaissanceRe", "RNR", "https://investor.renre.com/reports-filings/sec-filings/content/0001140361-26-010190/0001140361-26-010190.pdf"),
    ("Hannover Re", "HNR1.DE", "https://www.hannover-re.com/en/investors/results-and-reports/annual-report"),
    ("Munich Re", "MUV2.DE", "https://www.munichre.com/en/company/investors/reports-and-presentations/annual-report.item-25aee387f438d61e0e9115a79623698d.html"),
    ("Swiss Re", "SREN.SW", "https://www.swissre.com/investors/annual-report-2025.html"),
)
PEER_METRIC_FIELDS = (
    "gross_margin_pct",
    "operating_margin_pct",
    "profit_margin_pct",
    "roe_pct",
    "asset_turnover",
    "pe_ttm",
    "pb",
    "ps_ttm",
)


@contextmanager
def _suppress_yfinance_quote_noise():
    logger = logging.getLogger("yfinance")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


def infer_global_peer_tickers(ticker: str, company_name: str, sector: str, industry: str) -> list[tuple[str, str]]:
    signature = f"{company_name} {sector} {industry}"
    peers = []
    for keywords, candidates in GLOBAL_PEER_HINTS:
        if any(keyword.lower() in signature.lower() for keyword in keywords):
            peers.extend(candidates)
    return [(name, symbol) for name, symbol in peers if symbol.upper() != ticker.upper()][:5]


def _prioritize_legacy_candidates(ticker: str, candidates: list[dict]) -> list[dict]:
    """Spend the bounded download budget near the issuer before distant codes.

    Taiwan stock-code proximity only orders attempts. The existing current
    master and fine-industry checks still determine whether a row is usable.
    """
    target_id = int(ticker.split(".")[0])

    def priority(item):
        stock_id = str(item.get("ticker") or "").split(".")[0]
        return abs(int(stock_id) - target_id) if stock_id.isdigit() else float("inf")

    return sorted(candidates, key=priority)


def _annual_period(column) -> str | None:
    if isinstance(column, (date, datetime, pd.Timestamp)) and not pd.isna(column):
        return column.strftime("%Y-%m-%d")
    if isinstance(column, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", column):
        try:
            return date.fromisoformat(column).isoformat()
        except ValueError:
            pass
    return None


def _annual_asset_turnover(stock, *, today: date) -> dict | None:
    """Use one unambiguous common annual date, never TTM revenue with dated assets."""
    financials, balance = stock.financials, stock.balance_sheet
    if (not isinstance(financials, pd.DataFrame) or not isinstance(balance, pd.DataFrame)
            or financials.empty or balance.empty
            or list(financials.index).count("Total Revenue") != 1
            or list(balance.index).count("Total Assets") != 1):
        return None
    by_table = []
    for frame in (financials, balance):
        columns = {}
        for column in frame.columns:
            period = _annual_period(column)
            if period and period <= today.isoformat():
                columns.setdefault(period, []).append(column)
        by_table.append(columns)
    for period in sorted(set(by_table[0]) & set(by_table[1]), reverse=True):
        if len(by_table[0][period]) != 1 or len(by_table[1][period]) != 1:
            continue
        revenue = finite_number(financials.loc["Total Revenue", by_table[0][period][0]])
        assets = finite_number(balance.loc["Total Assets", by_table[1][period][0]], positive=True)
        if revenue is not None and assets is not None:
            return {"value": round(revenue / assets, 4), "observed_at": period}
    return None


def fetch_dynamic_peer_metrics_with_diagnostics(ticker: str, company_name: str, sector: str, industry: str, identity: dict) -> dict:
    """Keep verified identities even when every metric source is unavailable.

    At most ten candidate downloads (two batches) and five output rows. Industry
    membership alone is labeled as a candidate, never a ranked business match.
    """
    today = _today()
    ranked = ranked_profiles_from_identity(identity)
    selection_rows = {}
    selection_policy = None
    if ranked is not None:
        selected, selection_rows, selection_policy = ranked
        candidates = [{"name": name, "ticker": symbol.upper(), "identity_status": "profile_supplied",
                       "comparison_status": "profile_ranked"} for name, symbol in selected]
        audit = {"selection_status": "selected" if candidates else "profile_policy_rejected_all",
                 "selection_basis": "profile_ranked", "selection_rejected_reason_counts": {}}
    elif is_taiwan_ticker(ticker):
        master_rows = load_peer_stock_master()
        candidates, audit = resolve_legacy_peer_candidates(ticker, identity, master_rows, today=today)
        candidates = _prioritize_legacy_candidates(ticker, candidates)
        audit["candidate_order_policy"] = "stock_code_proximity_for_attempt_order_only"
        if ticker in AIRLINES and str(industry or "").strip().casefold() == "airlines":
            airline = get_official_airline_candidates(ticker, master_rows, today=today)
            audit["official_airline_candidate_status"] = airline["status"]
            audit["official_airline_candidate_details"] = {k: v for k, v in airline.items() if k != "candidates"}
            candidates = [c for c in candidates if not related_airline(ticker, c["ticker"])]
            if airline["candidates"]:
                candidates = airline["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "dated_caa_airlines_then_stock_code_proximity"
        if ticker == "3324.TWO":
            thermal = get_official_thermal_candidates(ticker, today=today)
            audit["official_thermal_candidate_status"] = thermal["status"]
            audit["official_thermal_candidate_details"] = {
                key: value for key, value in thermal.items() if key != "candidates"}
            if thermal["candidates"]:
                candidates = thermal["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "official_thermal_segment_then_stock_code_proximity"
        if ticker == "9103.TW" and str(industry or "").strip().casefold() == "medical instruments & supplies":
            medical=get_medical_cohort_candidates(ticker,identity,master_rows,today=today)
            audit['published_other_medical_status']=medical['status']
            audit['published_other_medical_details']=medical.get('details',{})
            if isinstance(medical.get('source_audit'),dict):
                audit.setdefault('related_entries',[]).append(medical['source_audit'])
            if medical['candidates']:
                candidates=medical['candidates']+candidates
                audit['legacy_selection_status']=audit['selection_status']
                audit['selection_status']='selected'
                audit['candidate_order_policy']='current_official_target_and_dated_medical_cohort_then_current_master'
        if ticker == "5314.TWO":
            published = get_published_food_biotech_candidates(ticker, master_rows, today=today)
            audit["published_food_biotech_candidate_status"] = published["status"]
            if isinstance(published.get("source_audit"),dict):
                audit["related_entries"]=[published["source_audit"]]
            if published["candidates"]:
                candidates = published["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "dated_publisher_leads_then_stock_code_proximity"
        documented = documented_peer_candidates(ticker, master_rows, today=today)
        audit["official_underwriter_candidate_count"] = len(documented)
        if documented:
            # Historical underwriter samples are leads with exact current
            # stock identities. Keep their dated provenance and do not assert
            # present whole-business comparability.
            candidates = documented + candidates
            audit["candidate_order_policy"] = "documented_underwriter_candidates_then_stock_code_proximity"
        if ticker == "2912.TW":
            try:
                convenience = get_official_convenience_candidates(ticker, master_rows, today=today)
            except Exception as exc:
                convenience = {"candidates": [], "status": "download_failed:" + type(exc).__name__}
            audit["official_convenience_candidate_status"] = convenience["status"]
            if convenience["candidates"]:
                candidates = convenience["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "official_convenience_lead_then_stock_code_proximity"
        if ticker == "1605.TW":
            try:
                steel_wire = get_official_steel_wire_candidates(ticker, master_rows, today=today)
            except Exception as exc:
                steel_wire = {"candidates": [], "status": "download_failed:" + type(exc).__name__}
            audit["official_steel_wire_candidate_status"] = steel_wire["status"]
            if steel_wire["candidates"]:
                candidates = steel_wire["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "official_steel_wire_leads_then_stock_code_proximity"
        if ticker == "9945.TW":
            construction = get_official_construction_candidates(ticker, master_rows, today=today)
            audit["official_construction_candidate_status"] = construction["status"]
            if construction["candidates"]:
                candidates = construction["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "official_construction_leads_then_stock_code_proximity"
        if ticker == "1229.TW":
            food = get_official_food_processing_candidates(ticker, master_rows, today=today)
            audit["official_food_processing_candidate_status"] = food["status"]
            if food["candidates"]:
                candidates = food["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "official_food_segment_leads_then_stock_code_proximity"
        if str(industry or "").strip().casefold() == "capital markets" and ticker.endswith(".TW"):
            try:
                official = get_official_broker_candidates(ticker, master_rows, today=today)
            except Exception as exc:
                official = {"candidates": [], "status": "download_failed:" + type(exc).__name__}
            audit["official_broker_candidate_status"] = official["status"]
            if official["candidates"]:
                candidates = official["candidates"] + candidates
                audit["selection_status"] = "selected"
                audit["candidate_order_policy"] = "official_broker_business_first_then_stock_code_proximity"
        if ticker == "2851.TW" and str(industry or "").strip().casefold() == "insurance - reinsurance":
            global_reinsurers = [
                {"name": name, "ticker": symbol, "identity_status": "documented_reinsurer_candidate",
                 "identity_source_url": source_url, "identity_report_year": 2025,
                 "comparison_status": "industry_candidate_only",
                 "comparison_scope": "cross_market_reinsurance",
                 "comparison_limitations": ["financial_period_unverified", "cross_market_accounting_and_currency"]}
                for name, symbol, source_url in REINSURANCE_GLOBAL_PEERS
            ]
            candidates = global_reinsurers + candidates
            audit["global_reinsurer_candidate_count"] = len(global_reinsurers)
            audit["candidate_order_policy"] = "documented_global_reinsurance_leads_then_current_master"
    else:
        candidates = [{"name": name, "ticker": symbol.upper(), "identity_status": "heuristic_candidate",
                       "comparison_status": "heuristic_unverified"}
                      for name, symbol in infer_global_peer_tickers(ticker, company_name, sector, industry)]
        audit = {"selection_status": "selected" if candidates else "no_candidates",
                 "selection_basis": "global_heuristic", "selection_rejected_reason_counts": {}}

    seen = {ticker.upper()}
    unique = []
    for candidate in candidates:
        if candidate["ticker"] in seen:
            continue
        seen.add(candidate["ticker"])
        unique.append(candidate)
    candidate_count = len(unique)
    unique = unique[:10]
    stocks_by_symbol = {}

    def fetch_peer(candidate: dict) -> dict:
        symbol = candidate["ticker"]
        yf_status = "success"
        try:
            from yfinance_transport_receipts import observe_peer_metrics
            with observe_peer_metrics(symbol):
                stock = yf.Ticker(symbol)
                stocks_by_symbol[symbol] = stock
                info = stock.info
            info = info if isinstance(info, dict) else {}
        except Exception as exc:
            info = {}
            yf_status = "download_failed:" + type(exc).__name__
        if info.get("symbol") and str(info["symbol"]).upper() != symbol:
            info, yf_status = {}, "identity_mismatch"
        if info.get("quoteType") and str(info["quoteType"]).upper() != "EQUITY":
            info, yf_status = {}, "not_equity"
        global_reinsurance = candidate.get("comparison_scope") == "cross_market_reinsurance"
        global_identity_valid = (
            str(info.get("symbol") or "").upper() == symbol
            and str(info.get("quoteType") or "").upper() == "EQUITY"
            and str(info.get("industry") or "").strip().casefold() == "insurance - reinsurance"
        ) if global_reinsurance else True
        if global_reinsurance and not global_identity_valid:
            info = {}
            if yf_status == "success":
                yf_status = "identity_or_industry_unverified"
        record = {**candidate, "source": "peer identity with per-field metric provenance"}
        thermal_scope = candidate.get("comparison_scope") == "thermal_management_segment"
        if ((candidate.get("comparison_status") == "published_segment_candidate" or thermal_scope)
                and (str(info.get("symbol") or "").upper() != symbol
                     or str(info.get("quoteType") or "").upper() != "EQUITY")):
            info, yf_status = {}, "identity_unverified"
            record["comparison_status"] = "identity_unverified"
        if candidate["comparison_status"] == "industry_candidate_only":
            record["comparison_status"] = industry_comparability(industry, info.get("industry", ""))
            record["reported_industry"] = info.get("industry")
        medical_scope=candidate.get('comparison_scope')=='publisher_other_medical_candidates'
        airline_scope=candidate.get('comparison_scope')==AIRLINE_SCOPE
        if medical_scope or airline_scope:
            if (str(info.get('symbol')or'').upper()!=symbol or str(info.get('quoteType')or'').upper()!='EQUITY'):
                info,yf_status={},'identity_unverified';record['comparison_status']='identity_unverified'
            elif record['comparison_status']!='business_industry_matched':
                record['comparison_status']='business_industry_mismatch'
        if global_reinsurance and not global_identity_valid:
            record["comparison_status"] = "identity_unverified"
        mappings = {"gross_margin_pct": "grossMargins", "operating_margin_pct": "operatingMargins",
                    "profit_margin_pct": "profitMargins", "roe_pct": "returnOnEquity",
                    "pe_ttm": "trailingPE", "pb": "priceToBook", "ps_ttm": "priceToSalesTrailing12Months"}
        for field, key in mappings.items():
            number = finite_number(info.get(key))
            record[field] = round(number * (100 if field.endswith("_pct") else 1), 2) if number is not None else None
        revenue, assets = finite_number(info.get("totalRevenue")), finite_number(info.get("totalAssets"), positive=True)
        record["asset_turnover"] = round(revenue / assets, 4) if revenue is not None and assets is not None else None
        if candidate.get("comparison_status") == "published_segment_candidate" or medical_scope or thermal_scope or airline_scope:
            # Undated quote aggregates cannot establish a common annual period.
            record["asset_turnover"] = None
        financial_signature = " ".join([industry, str(info.get("industry", "")), *candidate.get("industry_categories", [])]).casefold()
        financial_institution = any(word in financial_signature for word in ("bank", "insurance", "金融保險"))
        inapplicable = {"gross_margin_pct", "asset_turnover", "ps_ttm"} if financial_institution else set()
        for field in inapplicable:
            record[field] = None
        record["metric_applicability"] = {field: "not_applicable_financial_institution" if field in inapplicable else "applicable"
                                           for field in PEER_METRIC_FIELDS}
        provenance = {field: {"provider": "yfinance", "observed_at": None,
                              "observation_note": "provider field; report period not supplied"}
                      for field in PEER_METRIC_FIELDS if record.get(field) is not None}
        fallback = {"status": "not_needed", "metrics": {}}
        if (record["comparison_status"] not in {"business_industry_mismatch", "identity_unverified"}
                and symbol.endswith((".TW", ".TWO")) and (record["pe_ttm"] is None or record["pb"] is None)):
            try:
                fallback = fetch_peer_valuation_fallback(symbol, today=today)
            except Exception as exc:
                fallback = {"metrics": {}, "status": "download_failed", "error_kind": type(exc).__name__}
            for field, number in fallback.get("metrics", {}).items():
                if field in ("pe_ttm", "pb") and record.get(field) is None:
                    record[field] = number
                    field_source = (fallback.get("metric_sources") or {}).get(field)
                    provenance[field] = (field_source if isinstance(field_source, dict) else
                                         {"provider": fallback.get("source", "FinMind TaiwanStockPER"),
                                          "observed_at": fallback.get("observed_at"),
                                          "basis": fallback.get("metric_basis", {}).get(field),
                                          "cache_hit": bool(fallback.get("cache_hit"))})
        available = [field for field in PEER_METRIC_FIELDS if record.get(field) is not None]
        missing = [field for field in PEER_METRIC_FIELDS if record.get(field) is None and field not in inapplicable]
        record.update(metric_sources=provenance, missing_metrics=missing,
                      metrics_status="complete" if not missing else "partial" if available else "unavailable",
                      acquisition_attempts=[{"provider": "yfinance", "status": yf_status if yf_status != "success" else "success" if info else "empty_response"},
                                            *(fallback.get("attempts") or [{"provider": fallback.get("source", "FinMind TaiwanStockPER"),
                                                                              "status": fallback.get("status", "unavailable")}])])
        selection = selection_rows.get(symbol)
        if selection is not None and selection_policy is not None:
            record.update({key: selection[key] for key in ("market_cap_ratio", "revenue_ratio", "business_overlap", "product_overlap", "segment_overlap")})
            record.update(selection_score=selection["score"], selection_policy=selection_policy)
        return record

    records = []
    with _suppress_yfinance_quote_noise():
        for offset in range(0, len(unique), 5):
            batch = unique[offset:offset + 5]
            results = _run_named_fetches({c["ticker"]: (fetch_peer, (c,), None, "peer download failed") for c in batch}, max_workers=5)
            # Thread completion order must not change candidate selection order.
            records.extend(results[c["ticker"]] for c in batch if results.get(c["ticker"]))
            if sum(r["metrics_status"] != "unavailable" and r["comparison_status"] != "business_industry_mismatch" for r in records) >= 5:
                break
    eligible_records = [r for r in records if r["comparison_status"] not in {
        "business_industry_mismatch", "identity_unverified"}]
    selected_records = sorted(eligible_records, key=lambda r: r["metrics_status"] == "unavailable")[:5]
    for record in selected_records:
        if (record["asset_turnover"] is not None
                or record["metric_applicability"]["asset_turnover"] != "applicable"
                or record["comparison_status"] not in {"business_industry_matched", "official_convenience_candidate", "official_segment_candidate", "published_segment_candidate"}
                or not record["ticker"].endswith((".TW", ".TWO"))):
            continue
        try:
            annual = _annual_asset_turnover(stocks_by_symbol[record["ticker"]], today=today)
            outcome = "success" if annual is not None else "missing_matching_annual_values"
        except Exception as exc:
            annual, outcome = None, "download_failed:" + type(exc).__name__
        record["acquisition_attempts"].append({"provider": "Yahoo annual financial statements", "status": outcome})
        if annual is None:
            continue
        record["asset_turnover"] = annual["value"]
        record["metric_sources"]["asset_turnover"] = {
            "provider": "yfinance annual financials + balance sheet", "observed_at": annual["observed_at"],
            "basis": "annual_revenue / same_date_year_end_assets",
            "observation_note": "same-date SDK annual frames; HTTP cache status unknown",
        }
        record["missing_metrics"] = [field for field in record["missing_metrics"] if field != "asset_turnover"]
        record["metrics_status"] = "complete" if not record["missing_metrics"] else "partial"
    thermal_records = [r for r in selected_records if r.get("comparison_scope") == "thermal_management_segment"]
    if thermal_records and not verified_thermal_candidates(thermal_records, ticker, today=today):
        selected_records = [r for r in selected_records if r.get("comparison_scope") != "thermal_management_segment"]
        audit["official_thermal_candidate_status"] = "originals_expired_or_unverified_after_metrics"
    airline_records = [r for r in selected_records if r.get("comparison_scope") == AIRLINE_SCOPE]
    if airline_records and not verified_airline_candidates(airline_records, ticker, today=today):
        selected_records = [r for r in selected_records if r.get("comparison_scope") != AIRLINE_SCOPE]
        audit["official_airline_candidate_status"] = "originals_expired_or_unverified_after_metrics"
    usable_count = sum(r["metrics_status"] != "unavailable" for r in selected_records)
    partial = any(r["metrics_status"] != "complete" for r in selected_records)
    audit.update(candidate_count=candidate_count, candidate_attempt_count=len(records), identity_count=len(selected_records),
                 raw_count=len(records), usable_count=usable_count,
                 coverage_status="unavailable" if not usable_count else "partial" if partial else "success",
                 quality_status="metrics_missing" if not usable_count else "partial_metrics" if partial else "usable",
                 metric_observation_note="yfinance reporting periods are not supplied; inspect per-field provenance before period comparisons",
                 business_industry_rejected_count=len(records) - len(eligible_records),
                 candidate_diagnostics=[{"ticker": r["ticker"], "metrics_status": r["metrics_status"],
                                         "comparison_status": r["comparison_status"], "reported_industry": r.get("reported_industry"),
                                         "missing_metrics": r["missing_metrics"], "acquisition_attempts": r["acquisition_attempts"]} for r in records])
    return {"peers": selected_records, "audit": audit}


def fetch_dynamic_peer_metrics(ticker: str, company_name: str, sector: str, industry: str, identity: dict) -> list[dict]:
    """Compatibility list interface; provider callers should also use the audit."""
    return fetch_dynamic_peer_metrics_with_diagnostics(ticker, company_name, sector, industry, identity)["peers"]
