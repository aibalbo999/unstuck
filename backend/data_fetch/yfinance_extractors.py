"""Small yfinance/FinMind extraction helpers for legacy payload assembly."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import math
import os
import time
from uuid import uuid4

import pandas as pd

from .yfinance_enrichment_extractors import extract_dividend_history, extract_event_calendar, extract_price_history_ranges
from runtime_events import emit_log
from .market_sources.taiwan import (
    DataLoader,
    _align_finmind_history,
    _history_has_values,
    fetch_finmind_financial_statement_fallback,
    audited_finmind_financial_statement_fallback,
)
from source_audit import audited_fetch
from provider_correlation import current_correlation
from .financial_statement_observation import observe_financial_statements
from .market_sources.official_xbrl_financial import PROVIDER as OFFICIAL_XBRL_PROVIDER, fetch_official_annual_histories
from .market_sources.financial_institution_xbrl import (
    PROVIDER as FINANCIAL_INSTITUTION_XBRL_PROVIDER,
    fetch_financial_institution_histories,
)


def _financial_period_key(value):
    """Require a real statement end date; a year label alone cannot join tables."""
    if isinstance(value, (date, datetime)) and not pd.isna(value):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str) and len(value) >= 10 and value[4] == value[7] == "-":
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            pass
    return None


def _financial_number(value):
    if value is None or pd.api.types.is_bool(value) or pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _financial_billions(value):
    number = _financial_number(value)
    return round(number / 1e9, 2) if number is not None else None


def _reported_free_cash_flow(cashflow, column):
    """Use one finite numeric reported total; do not infer missing components."""
    if list(cashflow.index).count("Free Cash Flow") != 1:
        return None
    value = cashflow.loc["Free Cash Flow", column]
    if not pd.api.types.is_number(value) or pd.api.types.is_bool(value):
        return None
    try:
        return _financial_billions(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _store_financial_period(mapping, period, value):
    if period is not None:
        # Two representations of the same date are ambiguous, never last-wins.
        mapping[period] = None if period in mapping else value


def _reproject_retained_history(original_years, periods, original_values, final_years, final_periods, fallback_values):
    if not _history_has_values(original_values):
        return fallback_values
    if len(original_values) != len(periods) or len(periods) != len(original_years):
        return [None] * len(final_years)
    original_counts, final_counts = Counter(map(str, original_years)), Counter(map(str, final_years))
    by_period = {(str(year), period): value for year, period, value in zip(original_years, periods, original_values)
               if period and str(year) == period[:4] and original_counts[str(year)] == 1}
    return [by_period.get((str(year), period)) if period and final_counts[str(year)] == 1 else None
            for year, period in zip(final_years, final_periods)]


def _fill_finmind_missing_cells(primary, years, periods, rows_by_year, field):
    """Fill only a missing cell whose full statement date was already verified."""
    if len(primary) != len(years) or len(periods) != len(years):
        return primary
    filled = []
    for value, year, period in zip(primary, years, periods):
        candidate = rows_by_year.get(str(year), {}).get(field) if period else None
        if (value is None and isinstance(candidate, (int, float)) and not isinstance(candidate, bool)
                and math.isfinite(candidate)):
            filled.append(candidate)
        else:
            filled.append(value)
    return filled


def extract_price_history(stock) -> dict:
    price_history = {}
    try:
        hist = stock.history(period="1y")
        if not hist.empty:
            # Use the last real trading day in each month; avoid future month-end labels.
            monthly = hist.groupby(pd.Grouper(freq="ME")).tail(1)
            today = datetime.now().date()
            monthly = monthly[[d.date() <= today for d in monthly.index]]
            price_history = {
                "dates": [str(d.date()) for d in monthly.index[-12:]],
                "prices": [round(p, 2) for p in monthly["Close"].tolist()[-12:]],
            }
    except Exception:
        pass
    return price_history


def _is_financial_industry(industry_context: str) -> bool:
    return any(term in industry_context.casefold() for term in (
        "financial services", "bank", "insurance", "金融保險"))


def extract_financial_histories(stock, ticker: str, data_source_notes: list, data_loader_cls=DataLoader, *, quote_type: str = "", finmind_use_cache: bool = False, industry_context: str = "", force_refresh: bool = False) -> dict:
    if (not finmind_use_cache and not force_refresh) or str(quote_type).upper() in {"ETF", "MUTUALFUND"}:
        return _extract_financial_histories_uncached(
            stock, ticker, data_source_notes, data_loader_cls,
            quote_type=quote_type, finmind_use_cache=finmind_use_cache, industry_context=industry_context,
        )

    from shared_provider_cache import shared_fetch

    def acquire():
        notes = []
        histories = _extract_financial_histories_uncached(
            stock, ticker, notes, data_loader_cls, finmind_use_cache=not force_refresh,
            industry_context=industry_context,
        )
        return {"histories": histories, "notes": notes}

    def retention_seconds(row):
        histories = row.get("histories") or {}
        primary = (histories.get("official_financial_audit")
                   or histories.get("sector_specific_financial_audit")
                   or histories.get("primary_financial_audit") or {})
        if primary.get("status") == "success":
            return 4 * 60 * 60
        return 60 * 60 if histories.get("years") else 5 * 60

    # Only financial-institution histories need a new cache namespace. Existing
    # general-industry radar observations keep their original cache lifetime.
    profile_suffix = ":financial-institution-v4" if _is_financial_industry(industry_context) else ""
    key = f"radar_annual_histories:v3:{ticker}:{datetime.now():%Y-%m-%d}{profile_suffix}"
    stored, metadata = shared_fetch(
        key,
        acquire, freshness_seconds=4 * 60 * 60,
        result_ttl=retention_seconds, lock_wait_seconds=25, force_refresh=force_refresh,
    )
    if metadata.get('stale') or metadata.get('error_kind'):
        raise RuntimeError("背景雷達年度財報快取與供應商暫時不可用")
    from .annual_history_cache_freshness import valid_cached_histories
    if not valid_cached_histories(stored):
        if not metadata.get('cache_hit'):
            raise RuntimeError('年度財報來源資料格式不完整')
        stored, metadata = shared_fetch(key,acquire,freshness_seconds=4*60*60,
            result_ttl=retention_seconds,lock_wait_seconds=25,force_refresh=True)
        if metadata.get('stale') or metadata.get('error_kind'):
            raise RuntimeError('年度財報來源暫時不可用')
        if not valid_cached_histories(stored):
            # An adapter returning an unusable cache must not discard a quote.
            # Retire only this corrupt key and use the existing provider path.
            from cache_store import set_cache_json
            try:set_cache_json('shared_provider:v1:'+sha256(key.encode()).hexdigest(),None,1)
            except Exception:pass  # Cache cleanup cannot discard provider values.
            return _extract_financial_histories_uncached(stock,ticker,data_source_notes,data_loader_cls,
                quote_type=quote_type,finmind_use_cache=finmind_use_cache,industry_context=industry_context)
    data_source_notes.extend(stored.get("notes") or [])
    result = deepcopy(stored["histories"])
    if metadata.get("cache_hit"):
        from provider_correlation import current_correlation

        correlation = current_correlation()
        for key in ("official_financial_audit", "sector_specific_financial_audit",
                    "primary_financial_audit", "finmind_financial_fallback_audit"):
            audit = result.get(key)
            if not isinstance(audit, dict):
                continue
            original_status = str(audit.get("status") or "unknown")
            original_stale = audit.get('stale') is True
            for identity in ("job_id", "fetch_id", "operation_id", "attempt_id",
                             "provider_attempts", "provider_attempt_count"):
                audit.pop(identity, None)
            audit.update({name: correlation[name] for name in ("job_id", "fetch_id", "ticker")
                          if correlation.get(name)})
            audit.update(status=("degraded_enrichment" if original_stale else "skipped_fresh_cache")
                         if original_status == "success" else original_status,
                         cache_hit=True, stale=original_stale,
                         event_kind="cache_hit", original_status=original_status,
                         http_request_sent=False, http_request_count=0,
                         provider_attempts=[], provider_attempt_count=0,
                         message=f"沿用年度財報來源觀測；原始狀態：{original_status}。")
    return result


def _extract_financial_histories_uncached(stock, ticker: str, data_source_notes: list, data_loader_cls=DataLoader, *, quote_type: str = "", finmind_use_cache: bool = False, industry_context: str = "") -> dict:
    if str(quote_type).upper() in {"ETF", "MUTUALFUND"}:
        return {**{key: [] for key in ("years", "revenue_history", "net_income_history", "gross_profit_history",
                                      "operating_income_history", "fcf_history", "total_assets_history", "total_equity_history")},
                "finmind_financial_fallback_audit": None, "primary_financial_audit": None,
                "official_financial_audit": None}
    official_financial_audit = None
    sector_specific_financial_audit = None
    sector_specific_financials = None
    financial_industry = _is_financial_industry(industry_context)
    if (ticker.endswith((".TW", ".TWO")) and financial_industry
            and os.getenv("STOCK_AGENT_TEST_NO_NETWORK") != "1"):
        from .market_sources.mops_public_holding import supports_public_holding, fetch_public_holding_result
        from .market_sources.tcfhc_annual_financial import supports_annual, fetch_annual_result, SCHEMA as AUDITED_HOLDING_SCHEMA, origin_note as audited_holding_note
        if supports_annual(ticker):
            sector_result = fetch_annual_result(ticker)
        elif supports_public_holding(ticker):
            sector_result = fetch_public_holding_result(ticker)
        else:
            sector_result = audited_fetch(
                "financial_statements", FINANCIAL_INSTITUTION_XBRL_PROVIDER,
                lambda: fetch_financial_institution_histories(ticker), default=None,
                record_counter=lambda value: len(value.get("years", [])) if isinstance(value, dict) else 0,
                unavailable_message="MOPS 未回傳五年完整金融業合併年報或保險業個體／個別年報科目。",
            )
        sector_specific_financial_audit = sector_result.get("audit")
        sector_specific_financials = sector_result.get("value")
        statement_projection = None
        if (sector_specific_financial_audit and sector_specific_financial_audit.get("status") == "success"
                and isinstance(sector_specific_financials, dict)
                and sector_specific_financials.get("schema") in {"broker_consolidated.v1", "financial_institution_consolidated.v1", "financial_holding_consolidated.v2", "financial_holding_public_annual.v1", "financial_holding_audited_annual.v1", "bank_consolidated.v1", "insurer_standalone.v1"}):
            from .financial_history_basis import project_broker_histories, project_financial_institution_histories, project_insurer_standalone_histories
            broker = sector_specific_financials["schema"] == "broker_consolidated.v1"
            projector = (project_broker_histories if broker else project_insurer_standalone_histories
                         if sector_specific_financials["schema"] == "insurer_standalone.v1"
                         else project_financial_institution_histories)
            statement_projection = projector(sector_specific_financials, ticker)
            if statement_projection is None:
                sector_specific_financial_audit.update(
                    status="degraded_enrichment", record_count=0, coverage_status="unverified_receipt",
                    error_kind="invalid_broker_history_receipt" if broker else "invalid_financial_institution_history_receipt",
                    message="金融業年度收據的公司、範圍、科目或文件憑據不完整；保留既有年度備援。")
                sector_specific_financials = None
        if (sector_specific_financial_audit and sector_specific_financial_audit.get("status") == "success"
                and sector_specific_financials):
            manifest = sector_specific_financials["documents"]
            broker_statement = sector_specific_financials["schema"] == "broker_consolidated.v1"
            insurer_individual = sector_specific_financials["schema"] == "insurer_individual.v1"
            insurer_standalone = sector_specific_financials["schema"] == "insurer_standalone.v1"
            bank_fcf_unknown = (
                sector_specific_financials["schema"] == "bank_consolidated.v1"
                and any(isinstance(row, dict) and row.get("intangible_purchase") is None
                        for row in (sector_specific_financials.get("raw_twd_by_year") or {}).values())
            )
            sector_specific_financial_audit.update(
                coverage_status=("sector_specific_individual_complete" if insurer_individual else
                                 "sector_specific_standalone_complete" if insurer_standalone else
                                 "sector_specific_partial_optional_cashflow" if bank_fcf_unknown else
                                 "sector_specific_complete"),
                report_scope="standalone" if insurer_standalone else "individual" if insurer_individual else "consolidated",
                statement_schema=sector_specific_financials["schema"],
                source_url=sector_specific_financials["source_url"],
                documents=manifest,
                comparative_revisions=sector_specific_financials["comparative_revisions"],
                response_sha256=sha256(";".join(f"{item['year']}:{item['sha256']}" for item in manifest).encode()).hexdigest(),
                component_statuses=(sector_specific_financial_audit.get("component_statuses", {})
                    if sector_specific_financials["schema"] in {"financial_holding_public_annual.v1", AUDITED_HOLDING_SCHEMA} else {f"filing_{item['year']}": {
                    "status": "complete", "as_of": f"{item['year']}-12-31",
                    "provider": FINANCIAL_INSTITUTION_XBRL_PROVIDER,
                    "response_sha256": item["sha256"],
                } for item in manifest}),
                message=("五年保險業個別年報已取得，逐年無子公司註記已核對；營業收入、本期損益及現金流保留個別範圍。"
                         if insurer_standalone else
                         "五年保險業個體年報專用科目已取得；保險業營業收入、營業淨利及本期損益保留原科目，不補入一般產業欄位。"
                         if insurer_individual else
                         "五年證券商合併年報專用科目已取得；申報營收、經紀及承銷收入保留原科目，不補入一般產業欄位。"
                         if broker_statement else
                         "五年銀行合併年報已取得官方 XBRL 專用科目；無形資產購置未明列，該年度 FCF 保持未知，不以零補值。"
                         if bank_fcf_unknown else
                         "五年金融業專用科目已取得；未補入一般產業的營收、毛利或營業利益欄位。"),
            )
            data_source_notes.append(
                "五年保險業個別年報已取得官方 XBRL 專用科目；各年原件明示無子公司，保留個別範圍及原科目。"
                if insurer_standalone else
                "五年保險業個體年報已取得官方 XBRL 專用科目；其數值不代表合併集團，且未代填一般產業欄位。"
                if insurer_individual else
                "五年證券商合併年報已取得官方 XBRL 專用科目；申報營收與經紀、承銷收入逐項保留，毛利未由此來源代填。"
                if broker_statement else
                "銀行合併年報的無形資產購置支出未明列，FCF 保持未知；淨收益仍保留為銀行專用科目。"
                if bank_fcf_unknown else
                audited_holding_note(sector_specific_financials)
                if sector_specific_financials["schema"] == AUDITED_HOLDING_SCHEMA else
                "五年金融業合併年報已取得官方 XBRL 專用科目；淨收益與一般產業營收不同，毛利及營業利益未由此來源代填。")
            if statement_projection is not None:
                sector_specific_financial_audit.update(
                    history_projection_schema="financial_history_basis.v1",
                    message=("五年保險業個別年報已按原申報科目對齊年度序列；逐年無子公司依據已核對，毛利及一般業營業利益維持未提供。"
                             if insurer_standalone else
                             "五年證券商合併年報已按原申報科目對齊年度序列；保留來源、合併範圍及科目標籤，毛利及營業利益維持未提供。"
                             if broker_statement else
                             "五年銀行合併年報已按原申報科目對齊年度序列；無形資產購置未明列，該年度 FCF 保持未知，不以零補值。"
                             if bank_fcf_unknown else
                             "五年金融業合併年報已按原申報科目對齊年度序列；淨收益為獨立欄位，一般產業營收、毛利及營業利益維持未提供。"))
                data_source_notes.append(
                    "年度序列採保險業官方個別年報明列營業收入、本期損益、資產、權益及現金流；沒有子公司，不另讀通用年度 SDK／FinMind 備援。"
                    if insurer_standalone else
                    "年度序列採證券商官方合併年報明列營業收入、母公司淨利、資產、母公司權益及現金流；未另讀通用年度 SDK／FinMind 備援。"
                    if broker_statement else
                    "年度序列採銀行官方合併年報明列淨收益、利息收入、手續費收入、母公司淨利、資產、權益及營業現金流；未明列的無形資產購置與 FCF 保持未知。"
                    if bank_fcf_unknown else
                    "年度序列採金融業官方合併年報明列淨收益、母公司淨利、資產、母公司權益及現金流；淨收益保持獨立欄位，未另讀通用年度 SDK／FinMind 備援。")
                return {**statement_projection, "sector_specific_financials": sector_specific_financials,
                        "sector_specific_financial_audit": sector_specific_financial_audit,
                        "official_financial_audit": None, "primary_financial_audit": None,
                        "finmind_financial_fallback_audit": None}
    if (ticker.endswith((".TW", ".TWO")) and not financial_industry
            and os.getenv("STOCK_AGENT_TEST_NO_NETWORK") != "1"):
        from .official_financial_gap_cache import fetch_official_financial_result
        from .market_sources.syntec_annual_bridge import supports_bridge,fetch_bridge_result,PROVIDER as BRIDGE_PROVIDER,bridge_origin_note
        from .market_sources.cal_annual_bridge import supports_bridge as supports_cal_bridge,fetch_bridge_result as fetch_cal_bridge_result,PROVIDER as CAL_PROVIDER,bridge_origin_note as cal_origin_note
        from .market_sources.ordinary_individual_annual import supports_annual as supports_individual,fetch_annual_result as fetch_individual,SCHEMA as INDIVIDUAL_SCHEMA,NOTE as INDIVIDUAL_NOTE,PROVIDER as INDIVIDUAL_PROVIDER
        official_result = (fetch_individual(ticker) if supports_individual(ticker) else fetch_cal_bridge_result(ticker) if supports_cal_bridge(ticker) else
                           fetch_bridge_result(ticker) if supports_bridge(ticker) else fetch_official_financial_result(ticker))
        official_financial_audit = official_result.get("audit")
        official = official_result.get("value")
        if official_financial_audit and official_financial_audit.get("status") == "success" and official and official.get('schema')==INDIVIDUAL_SCHEMA:
            from .annual_financial_source_provider import project_source_value
            projection=project_source_value(official,ticker)
            if projection is None:
                official_financial_audit.update(status='degraded_enrichment',record_count=0,coverage_status='unverified_receipt')
            else:
                official_financial_audit.update(coverage_status='ordinary_individual_complete',statement_schema=INDIVIDUAL_SCHEMA,report_scope='individual',source_url=official['source_url'],response_sha256=sha256(';'.join(f"{d['year']}:{d['sha256']}"for d in official['documents']).encode()).hexdigest(),raw_twd_by_year=deepcopy(official['raw_twd_by_year']),documents=deepcopy(official['documents']),comparative_revisions=deepcopy(official['comparative_revisions']))
                data_source_notes.append(INDIVIDUAL_NOTE)
                return {**projection,'official_financial_audit':official_financial_audit,'primary_financial_audit':None,'finmind_financial_fallback_audit':None}
        if official_financial_audit and official_financial_audit.get("status") == "success" and official:
            manifest = official["documents"]
            official_financial_audit.update(
                coverage_status="complete", source_url=official["source_url"],
                documents=manifest, raw_twd_by_year=official["raw_twd_by_year"],
                comparative_revisions=official["comparative_revisions"],
                recovered_documents=official.get("recovered_documents", []),
                response_sha256=sha256(";".join(f"{item['year']}:{item['sha256']}" for item in manifest).encode()).hexdigest(),
                component_statuses=(official_financial_audit.get('component_statuses', {})
                    if (official_financial_audit.get('provider') in (BRIDGE_PROVIDER,CAL_PROVIDER,INDIVIDUAL_PROVIDER)
                        or str(official_financial_audit.get('source_mix') or '').startswith('official_xbrl_after_public_json_transport_failure')) else {f"filing_{item['year']}": {
                    "status": "complete", "as_of": f"{item['year']}-12-31",
                    "provider": item.get("provider", OFFICIAL_XBRL_PROVIDER),
                    "response_sha256": item["sha256"],
                } for item in manifest}),
            )
            if official.get("recovered_documents"):
                recovered_years = "、".join(str(item["year"]) for item in official["recovered_documents"])
                json_transport_failed = str(official_financial_audit.get('source_mix') or '').startswith('official_xbrl_after_public_json_transport_failure')
                official_financial_audit.update(
                    source_mix=("official_xbrl_after_public_json_transport_failure_with_official_comparison_recovery"
                                if json_transport_failed else "xbrl_with_official_comparison_recovery"),
                    message=f"{recovered_years} 年 iXBRL 原件暫時無法讀取；已用官方財務比較站恢復並保留逐年來源與比較列修訂。"
                            + ("；年度 JSON 也發生暫時傳輸錯誤。" if json_transport_failed else ""),
                )
                data_source_notes.append(
                    f"五年合併年報中的 {recovered_years} 年原始 XBRL 暫時無法讀取；"
                    "該年度使用證交所財務比較站明列數值，較早年度均以次年 XBRL 完整比較列核對。"
                    "自由現金流只按同年度明列現金流與設備、無形資產支出計算。"
                    + ("年度 JSON 傳輸失敗已由官方 iXBRL 備援接手。" if json_transport_failed else "")
                )
            elif official_financial_audit.get('provider') in (BRIDGE_PROVIDER,CAL_PROVIDER):
                official_financial_audit['source_mix'] = official['source_basis']
                origin_note=cal_origin_note(official)or bridge_origin_note(official)
                if origin_note:data_source_notes.insert(0,origin_note)
            elif official_financial_audit.get('source_mix') == 'official_xbrl_after_public_json_transport_failure':
                data_source_notes.append("公開資訊觀測站年度 JSON 文件發生暫時傳輸錯誤；已改讀官方合併 iXBRL 原件，重新核對五年期間、發行人、幣別、必要科目及比較列，並保留逐年來源。")
            elif official_financial_audit.get('provider') == 'TWSE MOPS public annual JSON':
                official_financial_audit['source_mix'] = 'public_json_with_verified_available_comparatives'
                official_financial_audit['comparative_coverage'] = deepcopy(official['comparative_coverage'])
                data_source_notes.append("五年合併年報採公開資訊觀測站公開 JSON 三表；金額單位依各表官方顯示模板的『新台幣仟元』契約核對，並保留完整原件。必要科目只採明示值，原年度缺列僅由較新明示比較值補齊；無衝突的不完整比較期保留已明示原年度值，另列比較期覆蓋。自由現金流只由同年明列營業現金流、設備及無形資產支出計算。")
                from .market_sources.mops_public_annual import first_comparative_origin_note
                origin_note=first_comparative_origin_note(official)
                if origin_note:data_source_notes.insert(0,origin_note)
            else:
                data_source_notes.append("五年合併年報已採用證交所公開資訊觀測站原始 XBRL；自由現金流按同年度營業現金流及明列設備、無形資產支出計算。")
            return {
                **{key: official[key] for key in ("years", "revenue_history", "net_income_history",
                    "gross_profit_history", "operating_income_history", "fcf_history",
                    "total_assets_history", "total_equity_history")},
                "official_financial_audit": official_financial_audit,
                "primary_financial_audit": None, "finmind_financial_fallback_audit": None,
            }
    revenue_history = []
    net_income_history = []
    gross_profit_history = []
    operating_income_history = []
    fcf_history = []
    total_assets_history = []
    total_equity_history = []
    years = []
    income_periods = []
    reported_fcf_periods = set()
    finmind_financial_fallback_audit = None
    primary_started_at = time.time()
    primary_metadata = {**current_correlation(), "ticker": ticker, "operation_id": uuid4().hex}
    primary_metadata.pop("attempt_id", None)
    primary_tables = {}
    primary_errors = {}
    primary_balance_snapshot = None

    try:
        financials = stock.financials
        primary_tables["financials"] = financials
        if financials is not None and not financials.empty:
            for col in financials.columns[:5]:
                year = col.year if hasattr(col, "year") else str(col)[:4]
                years.append(str(year))
                income_periods.append(_financial_period_key(col))
                rev = financials.loc["Total Revenue", col] if "Total Revenue" in financials.index else None
                ni = financials.loc["Net Income", col] if "Net Income" in financials.index else None
                gp = financials.loc["Gross Profit", col] if "Gross Profit" in financials.index else None
                oi = financials.loc["Operating Income", col] if "Operating Income" in financials.index else None
                revenue_history.append(_financial_billions(rev))
                net_income_history.append(_financial_billions(ni))
                gross_profit_history.append(_financial_billions(gp))
                operating_income_history.append(_financial_billions(oi))
            years = list(reversed(years))
            income_periods = list(reversed(income_periods))
            revenue_history = list(reversed(revenue_history))
            net_income_history = list(reversed(net_income_history))
            gross_profit_history = list(reversed(gross_profit_history))
            operating_income_history = list(reversed(operating_income_history))
    except Exception as e:
        primary_errors["financials"] = type(e).__name__
        emit_log(f"    ⚠️  財務報表獲取失敗：{e}")

    fcf_history = [None] * len(income_periods)
    total_assets_history = [None] * len(income_periods)
    total_equity_history = [None] * len(income_periods)
    try:
        cashflow = stock.cashflow
        primary_tables["cashflow"] = cashflow
        if cashflow is not None and not cashflow.empty:
            fcf_by_period = {}
            for col in cashflow.columns:
                period = _financial_period_key(col)
                ocf = cashflow.loc["Operating Cash Flow", col] if "Operating Cash Flow" in cashflow.index else None
                capex_val = cashflow.loc["Capital Expenditure", col] if "Capital Expenditure" in cashflow.index else None
                ocf_val, capex_val_f = _financial_number(ocf), _financial_number(capex_val)
                fcf = round(ocf_val / 1e9 + capex_val_f / 1e9, 2) if ocf_val is not None and capex_val_f is not None else None
                if fcf is None and period is not None:
                    fcf = _reported_free_cash_flow(cashflow, col)
                    if fcf is not None:
                        reported_fcf_periods.add(period)
                _store_financial_period(fcf_by_period, period, fcf)
            fcf_history = [fcf_by_period.get(period) for period in income_periods]
    except Exception as e:
        primary_errors["cashflow"] = type(e).__name__
        emit_log(f"    ⚠️  現金流數據獲取失敗：{e}")

    # A candidate rejected by period ambiguity or a table error was not used.
    reported_fcf_periods.intersection_update(
        period for period, value in zip(income_periods, fcf_history) if value is not None
    )

    try:
        balance = stock.balance_sheet
        primary_tables["balance_sheet"] = balance
        if balance is not None and not balance.empty:
            equity_by_period = {}
            assets_by_period = {}
            for col in balance.columns[:5]:
                period = _financial_period_key(col)
                eq = balance.loc["Stockholders Equity", col] if "Stockholders Equity" in balance.index else (
                    balance.loc["Total Equity Gross Minority Interest", col] if "Total Equity Gross Minority Interest" in balance.index else None)
                ta = balance.loc["Total Assets", col] if "Total Assets" in balance.index else None
                _store_financial_period(equity_by_period, period, _financial_billions(eq))
                _store_financial_period(assets_by_period, period, _financial_billions(ta))
            total_equity_history = [equity_by_period.get(period) for period in income_periods]
            total_assets_history = [assets_by_period.get(period) for period in income_periods]
            # Capital notes need the original unrounded latest balance values.
            # Retain just those two SDK inputs, rather than reading the same
            # annual statement again when a quote refresh reuses this history.
            period = _financial_period_key(balance.columns[0])
            assets = _financial_number(balance.loc['Total Assets',balance.columns[0]]) if 'Total Assets' in balance.index else None
            equity_field = 'Stockholders Equity' if 'Stockholders Equity' in balance.index else 'Total Equity Gross Minority Interest'
            equity = _financial_number(balance.loc[equity_field,balance.columns[0]]) if equity_field in balance.index else None
            if period and assets is not None and equity is not None and assets > 0 and equity > 0:
                primary_balance_snapshot = {'ticker':ticker,'period':period,'assets':assets,'equity':equity,
                                            'schema':'yahoo-annual-balance-inputs.v1'}
    except Exception as e:
        primary_errors["balance_sheet"] = type(e).__name__
        emit_log(f"    ⚠️  資產負債表獲取失敗：{e}")

    primary_histories = {
        "years": years, "revenue_history": revenue_history, "net_income_history": net_income_history,
        "gross_profit_history": gross_profit_history, "operating_income_history": operating_income_history,
        "fcf_history": fcf_history, "total_assets_history": total_assets_history,
        "total_equity_history": total_equity_history,
    }
    primary_financial_audit = observe_financial_statements(
        tables=primary_tables, errors=primary_errors, metadata=primary_metadata,
        started_at=primary_started_at, finished_at=time.time(),
        histories=primary_histories,
    )
    if primary_balance_snapshot is not None:
        primary_balance_snapshot['data_fingerprint'] = primary_financial_audit['data_fingerprint']
        from .annual_history_cache_freshness import balance_inputs_digest
        primary_financial_audit['balance_inputs_sha256'] = balance_inputs_digest(primary_balance_snapshot)

    fallback_reanchored = False
    final_periods = income_periods
    if data_loader_cls is not None and (ticker.endswith(".TW") or ticker.endswith(".TWO")):
        needs_finmind_fallback = (
            not _history_has_values(revenue_history)
            or not _history_has_values(net_income_history)
            or not _history_has_values(total_assets_history)
            or not _history_has_values(total_equity_history)
            or not _history_has_values(fcf_history)
            or any(len(history) == len(years) and any(value is None for value in history)
                   for history in (revenue_history, net_income_history,
                                   total_assets_history, total_equity_history))
        )
        if needs_finmind_fallback:
            finmind_fallback_result = audited_finmind_financial_statement_fallback(
                ticker,
                fetcher=(lambda symbol: fetch_finmind_financial_statement_fallback(symbol, use_cache=True))
                if finmind_use_cache else fetch_finmind_financial_statement_fallback,
                audit_fetch=audited_fetch,
            )
            finmind_fallback = finmind_fallback_result.get("value") or {}
            finmind_financial_fallback_audit = finmind_fallback_result.get("audit")

            if finmind_fallback:
                fallback_years = finmind_fallback.get("years", []) or []
                rows_by_year = finmind_fallback.get("rows_by_year", {}) or {}
                if not years or not _history_has_values(revenue_history) or not _history_has_values(net_income_history):
                    years = fallback_years
                    final_periods = [_financial_period_key(rows_by_year.get(str(year), {}).get("statement_date"))
                                     for year in years]
                    fallback_reanchored = True
                final_counts = Counter(map(str, years))
                rows_by_year = {str(year): rows_by_year[str(year)] for year, period in zip(years, final_periods)
                                if period and period[:4] == str(year) and final_counts[str(year)] == 1
                                and _financial_period_key(rows_by_year.get(str(year), {}).get("statement_date")) == period}
                before_fill = (revenue_history, net_income_history, gross_profit_history,
                               operating_income_history, fcf_history, total_assets_history, total_equity_history)
                if not _history_has_values(revenue_history):
                    revenue_history = _align_finmind_history(years, rows_by_year, "revenue")
                else:
                    revenue_history = _fill_finmind_missing_cells(revenue_history, years, final_periods, rows_by_year, "revenue")
                if not _history_has_values(net_income_history):
                    net_income_history = _align_finmind_history(years, rows_by_year, "net_income")
                else:
                    net_income_history = _fill_finmind_missing_cells(net_income_history, years, final_periods, rows_by_year, "net_income")
                if not _history_has_values(gross_profit_history):
                    gross_profit_history = _align_finmind_history(years, rows_by_year, "gross_profit")
                else:
                    gross_profit_history = _fill_finmind_missing_cells(gross_profit_history, years, final_periods, rows_by_year, "gross_profit")
                if not _history_has_values(operating_income_history):
                    operating_income_history = _align_finmind_history(years, rows_by_year, "operating_income")
                else:
                    operating_income_history = _fill_finmind_missing_cells(operating_income_history, years, final_periods, rows_by_year, "operating_income")
                if not _history_has_values(fcf_history):
                    fcf_history = _align_finmind_history(years, rows_by_year, "free_cash_flow")
                else:
                    fcf_history = _fill_finmind_missing_cells(fcf_history, years, final_periods, rows_by_year, "free_cash_flow")
                if not _history_has_values(total_assets_history):
                    total_assets_history = _align_finmind_history(years, rows_by_year, "total_assets")
                else:
                    total_assets_history = _fill_finmind_missing_cells(total_assets_history, years, final_periods, rows_by_year, "total_assets")
                if not _history_has_values(total_equity_history):
                    total_equity_history = _align_finmind_history(years, rows_by_year, "total_equity")
                else:
                    total_equity_history = _fill_finmind_missing_cells(total_equity_history, years, final_periods, rows_by_year, "total_equity")
                after_fill = (revenue_history, net_income_history, gross_profit_history,
                              operating_income_history, fcf_history, total_assets_history, total_equity_history)
                if any(before != after for before, after in zip(before_fill, after_fill)):
                    data_source_notes.append(
                        "yfinance 年度財報欄位缺漏時，已使用 FinMind 相同報表截止日的可用欄位補值。"
                    )

    if fallback_reanchored:
        # Keep the existing fallback fill policy. Only reindex primary values
        # that it retained; new/ambiguous years stay missing, without refetching.
        aligned = {key: _reproject_retained_history(primary_histories["years"], income_periods,
                   primary_histories[key], years, final_periods, values) for key, values in {
            "revenue_history": revenue_history, "net_income_history": net_income_history,
            "gross_profit_history": gross_profit_history, "operating_income_history": operating_income_history,
            "fcf_history": fcf_history, "total_assets_history": total_assets_history,
            "total_equity_history": total_equity_history,
        }.items()}
        revenue_history, net_income_history = aligned["revenue_history"], aligned["net_income_history"]
        gross_profit_history, operating_income_history = aligned["gross_profit_history"], aligned["operating_income_history"]
        fcf_history = aligned["fcf_history"]
        total_assets_history, total_equity_history = aligned["total_assets_history"], aligned["total_equity_history"]

    used_reported_periods = sorted({period for period, value in zip(final_periods, fcf_history)
                                    if period in reported_fcf_periods and value is not None})
    if used_reported_periods:
        data_source_notes.append(
            "yfinance 現金流分項仍不足；" + "、".join(used_reported_periods)
            + " 已採用同一現金流報表、相同截止日的原始 Free Cash Flow 欄位，未補推營業現金流或資本支出。"
        )

    return {
        "years": years,
        "revenue_history": revenue_history,
        "net_income_history": net_income_history,
        "gross_profit_history": gross_profit_history,
        "operating_income_history": operating_income_history,
        "fcf_history": fcf_history,
        "total_assets_history": total_assets_history,
        "total_equity_history": total_equity_history,
        "finmind_financial_fallback_audit": finmind_financial_fallback_audit,
        "primary_financial_audit": primary_financial_audit,
        "primary_balance_snapshot": primary_balance_snapshot,
        "official_financial_audit": official_financial_audit,
        "sector_specific_financial_audit": sector_specific_financial_audit,
        "sector_specific_financials": sector_specific_financials,
    }


def fetch_monthly_revenue_records(ticker: str, data_loader_cls=DataLoader, *, force_refresh=False) -> tuple[list, dict | None]:
    recent_monthly_revenue = []
    monthly_revenue_audit = None
    if not (ticker.endswith(".TW") or ticker.endswith(".TWO")) or data_loader_cls is None:
        return recent_monthly_revenue, monthly_revenue_audit

    from .market_sources.finmind_monthly_revenue import fetch_monthly_records
    monthly_revenue_result = fetch_monthly_records(
        ticker, data_loader_cls, audit_fetch=audited_fetch, force_refresh=force_refresh)
    return monthly_revenue_result.get("value") or [], monthly_revenue_result.get("audit")
