"""Peer discovery and peer metric source helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager

import yfinance as yf

from .common import _run_named_fetches
from .identity import is_taiwan_ticker
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
        candidates, audit = resolve_legacy_peer_candidates(ticker, identity, load_peer_stock_master(), today=today)
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

    def fetch_peer(candidate: dict) -> dict:
        symbol = candidate["ticker"]
        yf_status = "success"
        try:
            info = yf.Ticker(symbol).info
            info = info if isinstance(info, dict) else {}
        except Exception as exc:
            info = {}
            yf_status = "download_failed:" + type(exc).__name__
        if info.get("symbol") and str(info["symbol"]).upper() != symbol:
            info, yf_status = {}, "identity_mismatch"
        if info.get("quoteType") and str(info["quoteType"]).upper() != "EQUITY":
            info, yf_status = {}, "not_equity"
        record = {**candidate, "source": "peer identity with per-field metric provenance"}
        if candidate["comparison_status"] == "industry_candidate_only":
            record["comparison_status"] = industry_comparability(industry, info.get("industry", ""))
            record["reported_industry"] = info.get("industry")
        mappings = {"gross_margin_pct": "grossMargins", "operating_margin_pct": "operatingMargins",
                    "profit_margin_pct": "profitMargins", "roe_pct": "returnOnEquity",
                    "pe_ttm": "trailingPE", "pb": "priceToBook", "ps_ttm": "priceToSalesTrailing12Months"}
        for field, key in mappings.items():
            number = finite_number(info.get(key))
            record[field] = round(number * (100 if field.endswith("_pct") else 1), 2) if number is not None else None
        revenue, assets = finite_number(info.get("totalRevenue")), finite_number(info.get("totalAssets"), positive=True)
        record["asset_turnover"] = round(revenue / assets, 4) if revenue is not None and assets is not None else None
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
        if (record["comparison_status"] != "business_industry_mismatch"
                and symbol.endswith((".TW", ".TWO")) and (record["pe_ttm"] is None or record["pb"] is None)):
            try:
                fallback = fetch_peer_valuation_fallback(symbol, today=today)
            except Exception as exc:
                fallback = {"metrics": {}, "status": "download_failed", "error_kind": type(exc).__name__}
            for field, number in fallback.get("metrics", {}).items():
                if field in ("pe_ttm", "pb") and record.get(field) is None:
                    record[field] = number
                    provenance[field] = {"provider": fallback.get("source", "FinMind TaiwanStockPER"),
                                         "observed_at": fallback.get("observed_at"),
                                         "basis": fallback.get("metric_basis", {}).get(field),
                                         "cache_hit": bool(fallback.get("cache_hit"))}
        available = [field for field in PEER_METRIC_FIELDS if record.get(field) is not None]
        missing = [field for field in PEER_METRIC_FIELDS if record.get(field) is None and field not in inapplicable]
        record.update(metric_sources=provenance, missing_metrics=missing,
                      metrics_status="complete" if not missing else "partial" if available else "unavailable",
                      acquisition_attempts=[{"provider": "yfinance", "status": yf_status if yf_status != "success" else "success" if info else "empty_response"},
                                            {"provider": "FinMind TaiwanStockPER", **{k: v for k, v in fallback.items() if k != "metrics"}}])
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
    eligible_records = [r for r in records if r["comparison_status"] != "business_industry_mismatch"]
    selected_records = sorted(eligible_records, key=lambda r: r["metrics_status"] == "unavailable")[:5]
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
