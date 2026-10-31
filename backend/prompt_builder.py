"""Prompt data builders for analysis agents."""

from __future__ import annotations

import json
import os
import re
import warnings
from functools import lru_cache

from jinja2 import ChainableUndefined, Environment

from config import CATALYST_LOOKBACK_DAYS
from financial_cross_checks import build_financial_cross_checks
from dividend_yield_units import dividend_yield_pct
from financial_tools import build_financial_tool_context, raw_twd_to_billion_twd, safe_float
from prompt_builder_helpers import (
    _agent_context,
    _compact_list,
    _compact_pe_river,
    _prompt_company_identity,
    _prompt_data_trust,
    _prompt_history_rows,
    _prompt_financial_history_basis,
    _prompt_financial_institution_history,
    _prompt_number,
    _prompt_ratio_to_pct,
    _prompt_source_audit_summary,
    _safe_iterable_prefix,
)
from prompt_context_sections import prompt_global_market_context, prompt_international_news_context
from prompt_peer_projection import comparable_peer_rows
from prompt_evidence import prompt_evidence_copy
from prompt_role_payload import project_role_payload
from prompt_record_tables import TABLE_RULE, pack_record_tables
from short_term_market_data import build_short_term_market_context

PROMPT_DATA_SCHEMA_VERSION = int(os.getenv("PROMPT_DATA_SCHEMA_VERSION", "3"))
PROMPT_ENV = Environment(
    autoescape=False,
    undefined=ChainableUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
LEGACY_PROMPT_FIELDS = {"ticker", "name", "fin_data", "prev"}


def _prompt_latest_quarter_financials(data: dict, *, compact: bool) -> dict:
    snapshot = dict.get(data, "latest_quarter_financials")
    if not isinstance(snapshot, dict) or snapshot.get("schema") != "mops_latest_quarter_financials.v1":
        return {}
    result = {key: snapshot.get(key) for key in (
        "coverage_status", "issuer_code", "issuer_name", "period", "income_period_basis",
        "balance_period_basis", "currency", "filed_unit", "scope", "cash_flow_statement_available",
    )}
    aliases = {
        "balance_sheet": (
            "資產總計", "資產總額", "負債總計", "負債總額", "權益總計", "權益總額",
            "歸屬於母公司業主之權益合計", "歸屬於母公司業主權益合計", "歸屬於母公司業主之權益",
        ),
        "income_statement_ytd": (
            "營業收入", "營業收入合計", "淨收益", "收益", "收入", "保險服務結果",
            "營業毛利（毛損）淨額", "營業利益（損失）", "淨利（淨損）歸屬於母公司業主",
            "淨利（損）歸屬於母公司業主", "本期淨利（淨損）", "本期稅後淨利（淨損）",
        ),
    }
    tables = snapshot.get("tables")
    result["statements"] = {}
    if isinstance(tables, dict):
        for name, aliases_for_table in aliases.items():
            table = tables.get(name)
            if not isinstance(table, dict) or not isinstance(table.get("row"), dict):
                continue
            row = table["row"]
            items = ({key: row[key] for key in aliases_for_table if key in row}
                     if compact else dict(row))
            result["statements"][name] = {
                "source_url": table.get("source_url"),
                "response_sha256": table.get("response_sha256"),
                "reported_period": table.get("period"),
                "reported_items": items,
            }
    return result


def _prompt_latest_quarter_financial_summary(data: dict) -> dict:
    snapshot=dict.get(data,"latest_quarter_financial_summary")
    ticker=dict.get(data,"ticker")
    if not isinstance(snapshot,dict)or not isinstance(ticker,str):
        return {}
    from data_fetch.market_sources.tpex_historical_quarterly_summary import project_summary
    projected=project_summary(snapshot,ticker)
    if projected is None:
        return {}
    # Keep the raw response receipts out of prompts; only verified fields and
    # a compact source identity are needed for analysis and attribution.
    return {key:projected.get(key)for key in (
        "schema","coverage_status","ticker","issuer_code","issuer_name","market_scope",
        "period","currency","amount_unit","per_share_unit","ratio_unit","scope",
        "cash_flow_statement_available","metrics","comparison","field_status",
        "source_url","response_sha256",
    )}
LEGACY_PLACEHOLDER_RE = re.compile(r"\{(" + "|".join(sorted(LEGACY_PROMPT_FIELDS)) + r")\}")


def render_prompt_template(template: str, variables: dict) -> str:
    """Render agent prompts with Jinja2 while accepting legacy {ticker} placeholders."""
    if not template:
        return ""

    jinja_template, has_legacy_placeholders = _get_compiled_prompt_template(template)
    if has_legacy_placeholders:
        warnings.warn("legacy prompt placeholder syntax is deprecated; use Jinja2 placeholders like {{ ticker }} instead", DeprecationWarning, stacklevel=2)
    return jinja_template.render(**variables)


@lru_cache(maxsize=256)
def _get_compiled_prompt_template(template: str):
    has_legacy_placeholders = bool(LEGACY_PLACEHOLDER_RE.search(template))
    normalized = LEGACY_PLACEHOLDER_RE.sub(r"{{ \1 }}", template)
    return PROMPT_ENV.from_string(normalized), has_legacy_placeholders


def _prompt_revenue_cagr(data: dict, tool_context: dict) -> dict:
    """Bind a calculated CAGR to aligned annual rows, never to a legacy name."""
    basis = {
        "period_status": "unverified", "start_year": None, "end_year": None,
        "periods": None, "source_period_verified": False,
        "source_paths": ["years", "revenue_history"],
        "calculation_path": "deterministic_financial_tool_results.calculations.revenue_cagr",
        "limit": "年度標籤僅綁定本次歷史序列，不另認證原始財報期間、口徑或首次可用日。",
    }
    result = {
        "revenue_cagr_pct": None,
        "revenue_cagr_basis": basis,
        "revenue_cagr_legacy_pct": _prompt_number(dict.get(data, "revenue_cagr_5yr")),
        "revenue_cagr_5yr_pct": None,
    }
    years = dict.get(data, "years")
    revenues = dict.get(data, "revenue_history")
    calculation = tool_context.get("calculations", {}).get("revenue_cagr")
    if isinstance(calculation, dict):
        # The tool's periods counts positive observations; attach the actual
        # annual binding so filtered or irregular rows cannot imply a duration.
        calculation["period_basis"] = basis
    if (not isinstance(years, (list, tuple)) or not isinstance(revenues, (list, tuple))
            or len(years) < 2 or len(years) != len(revenues)
            or not isinstance(calculation, dict)):
        return result
    if any(type(year) not in (str, int) or re.fullmatch(r"[1-9][0-9]{3}", str(year)) is None
           for year in years):
        return result
    annual_years = [int(year) for year in years]
    if any(end != start + 1 for start, end in zip(annual_years, annual_years[1:])):
        return result
    amounts = [None if isinstance(value, bool) else safe_float(value) for value in revenues]
    if any(value is None or value <= 0 for value in amounts):
        return result
    periods = annual_years[-1] - annual_years[0]
    cagr = _prompt_number(calculation.get("cagr_pct"))
    if (calculation.get("periods") != periods or cagr is None
            or calculation.get("start_value") != round(amounts[0], 4)
            or calculation.get("end_value") != round(amounts[-1], 4)):
        return result
    basis.update(period_status="bound_to_history_rows", start_year=str(annual_years[0]),
                 end_year=str(annual_years[-1]), periods=periods)
    result["revenue_cagr_pct"] = cagr
    if periods == 5:
        result["revenue_cagr_5yr_pct"] = cagr
    return result


def format_data_for_prompt(data: dict, *, compact: bool = False, dense: bool = False, role_scoped: bool = False, compact_json: bool = False) -> str:
    """Format financial data as clean JSON to avoid unit drift and prompt overload."""
    total_debt_b = raw_twd_to_billion_twd(dict.get(data, "total_debt_raw"))
    total_cash_b = raw_twd_to_billion_twd(dict.get(data, "total_cash_raw"))
    net_debt_b = None
    if total_debt_b is not None or total_cash_b is not None:
        net_debt_b = round((total_debt_b or 0) - (total_cash_b or 0), 4)

    history_basis = _prompt_financial_history_basis(data)
    from financial_fact_binding import debt_ratio_basis, financial_basis
    scalar_basis = financial_basis(data)['facts']
    tool_context = build_financial_tool_context(data)
    revenue_cagr = _prompt_revenue_cagr(data, tool_context)
    payload = {
        "schema_version": dict.get(data, "data_schema_version", PROMPT_DATA_SCHEMA_VERSION),
        "unit_contract": {
            "money": "billion_twd",
            "money_display_zh": "十億新臺幣（1 billion_twd = 10 億元）",
            "money_to_yi_twd": 10,
            "price": "twd_per_share",
            "percent": "percentage_points",
            "ratios": "plain_multiple_unless_key_ends_with_pct",
        },
        "company": {
            "identity": _prompt_company_identity(data),
            "sector": dict.get(data, "sector"),
            "industry": dict.get(data, "industry"),
            "country": dict.get(data, "country"),
            "employees": dict.get(data, "employees"),
            "fetch_date": dict.get(data, "fetch_date"),
        },
        "data_freshness": raw_data_freshness if isinstance(raw_data_freshness := dict.get(data, "data_freshness"), dict) else {},
        "source_freshness": raw_source_freshness if isinstance(raw_source_freshness := dict.get(data, "source_freshness"), dict) else {},
        "data_trust": _prompt_data_trust(data),
        "source_audit_summary": _prompt_source_audit_summary(data),
        "agent_context": _agent_context(data),
        "market_data": {
            "current_price_twd": _prompt_number(dict.get(data, "current_price")),
            "market_cap_billion_twd": raw_twd_to_billion_twd(dict.get(data, "market_cap_raw")),
            "week_52_high_twd": _prompt_number(dict.get(data, "week_52_high")),
            "week_52_low_twd": _prompt_number(dict.get(data, "week_52_low")),
        },
        "valuation_metrics": {
            "pe_ttm": _prompt_number(dict.get(data, "pe_ratio_raw")),
            "forward_pe": _prompt_number(dict.get(data, "forward_pe_raw")),
            "pb": _prompt_number(dict.get(data, "pb_ratio")),
            "ps": _prompt_number(dict.get(data, "ps_ratio")),
            "ev_ebitda": _prompt_number(dict.get(data, "ev_ebitda")),
            "shares_outstanding": _prompt_number(dict.get(data, "shares_raw"), 0),
            "trailing_eps_twd": _prompt_number(dict.get(data, "trailing_eps")),
            "forward_eps_twd": _prompt_number(dict.get(data, "forward_eps")),
            "dividend_yield_pct": dividend_yield_pct(data),
            "dividend_per_share_twd": _prompt_number(dict.get(data, "dividend_rate_raw")),
            "payout_ratio_pct": _prompt_ratio_to_pct(dict.get(data, "payout_ratio_raw")),
        },
        "ttm_financials": {
            "revenue_billion_twd": raw_twd_to_billion_twd(dict.get(data, "revenue_ttm_raw")),
            "net_income_billion_twd": raw_twd_to_billion_twd(dict.get(data, "net_income_ttm_raw")),
            "net_income_source": dict.get(data, "net_income_ttm_source"),
            "net_income_basis": scalar_basis['net_income_ttm_raw'],
            "ebitda_billion_twd": raw_twd_to_billion_twd(dict.get(data, "ebitda_raw")),
            "gross_margin_pct": _prompt_ratio_to_pct(dict.get(data, "gross_margin_raw")),
            "operating_margin_pct": _prompt_ratio_to_pct(dict.get(data, "operating_margin_raw")),
            "profit_margin_pct_calibrated": _prompt_ratio_to_pct(dict.get(data, "profit_margin_raw")),
            "profit_margin_pct_provider": _prompt_ratio_to_pct(dict.get(data, "profit_margin_provider_raw")),
        },
        "cash_flow": {
            "free_cash_flow_billion_twd": raw_twd_to_billion_twd(dict.get(data, "free_cash_flow_raw")),
            "free_cash_flow_basis": scalar_basis['free_cash_flow_raw'],
            "operating_cash_flow_billion_twd": raw_twd_to_billion_twd(dict.get(data, "operating_cash_flow_raw")),
        },
        "balance_sheet": {
            "total_debt_billion_twd": total_debt_b,
            "total_cash_billion_twd": total_cash_b,
            "net_debt_billion_twd": net_debt_b,
            "debt_to_equity_pct": _prompt_number(dict.get(data, "debt_to_equity")),
            "debt_to_equity_basis": debt_ratio_basis(data),
            "current_ratio": _prompt_number(dict.get(data, "current_ratio")),
            "equity_multiplier": dict.get(data, "equity_multiplier"),
        },
        "growth": {
            "latest_annual_revenue_growth_pct": _prompt_number(dict.get(data, "latest_annual_revenue_growth")),
            "latest_annual_net_income_growth_pct": _prompt_number(dict.get(data, "latest_annual_net_income_growth")),
            "ttm_vs_latest_annual_revenue_change_pct": _prompt_number(dict.get(data, "ttm_vs_latest_annual_revenue_change")),
            "yahoo_recent_revenue_growth_pct": _prompt_number(dict.get(data, "yahoo_revenue_growth")),
            "yahoo_recent_earnings_growth_pct": _prompt_number(dict.get(data, "yahoo_earnings_growth")),
            **revenue_cagr,
        },
        "history": {
            "unit": "billion_twd",
            **({"basis": history_basis} if history_basis else {}),
            "rows": _prompt_history_rows(data),
            "financial_institution": _prompt_financial_institution_history(data),
        },
        "latest_quarter_financials": _prompt_latest_quarter_financials(data, compact=compact),
        "latest_quarter_financial_summary": _prompt_latest_quarter_financial_summary(data),
        "market_catalysts": {
            "lookback_days": CATALYST_LOOKBACK_DAYS,
            "selection_summary": dict.get(data, "news_selection", {}),
            "items": prompt_evidence_copy(_compact_list(dict.get(data, "recent_catalysts", []), 3) if compact else _safe_iterable_prefix(dict.get(data, "recent_catalysts", []))),
        },
        "global_market_context": prompt_global_market_context(data, compact=compact),
        "international_news_context": prompt_international_news_context(data, compact=compact),
        "institutional_trading": raw_institutional_trading if isinstance(raw_institutional_trading := dict.get(data, "institutional_trading"), dict) else {},
        "peer_context": {
            "dynamic_peer_metrics": (
                comparable_peer_rows(_safe_iterable_prefix(dict.get(data, "dynamic_peer_metrics", [])))[:5]
                if compact else comparable_peer_rows(_safe_iterable_prefix(dict.get(data, "dynamic_peer_metrics", [])))
            ),
            "search_discovery_results": [] if compact else prompt_evidence_copy(
                _safe_iterable_prefix(dict.get(data, "peer_discovery_results", []))),
        },
        "local_valuation_context": {
            "pe_river_chart": _compact_pe_river(raw_pe_river_chart := dict.get(data, "pe_river_chart")) if compact else (raw_pe_river_chart if isinstance(raw_pe_river_chart := dict.get(data, "pe_river_chart"), dict) else {}),
        },
        "cross_checks": build_financial_cross_checks(data),
        "data_quality_notes": _compact_list(dict.get(data, "data_source_notes", []), 5) if compact else _safe_iterable_prefix(dict.get(data, "data_source_notes", [])),
        "recent_monthly_revenue_text": _compact_list(dict.get(data, "recent_monthly_revenue", []), 4) if compact else _safe_iterable_prefix(dict.get(data, "recent_monthly_revenue", [])),
        "deterministic_financial_tool_results": tool_context,
    }

    if dict.get(data, "_prompt_agent_num") in {15, 16, 22, 24}:
        payload["short_term_market_context"] = build_short_term_market_context(data, compact=compact)

    from official_financial_projection import read_official_financial_projection
    official = read_official_financial_projection(data)
    if official is not None:
        facts = official['facts']
        payload['cash_flow']['official_reference'] = {key: facts[key] for key in (
            'period_start', 'period_end', 'report_scope', 'currency', 'source_url',
            'acquired_at', 'cashflows', 'ttm_formula', 'free_cash_flow_definition')}
        payload['cash_flow']['official_reference']['historical_pit_verified'] = False
        from official_income_prompt import official_income_prompt_facts, official_income_reference_text
        income_facts = official_income_prompt_facts(data)
        if income_facts is not None:
            payload['cash_flow']['official_income_facts'] = income_facts
            reference_text = official_income_reference_text(income_facts, official['facts'])
            if reference_text is not None:
                payload['cash_flow']['official_income_reference_text'] = reference_text
    if official is not None:
        from official_cashflow_components import read_official_cashflow_components
        from evidence_cashflow_components import component_reference_text
        effects = read_official_cashflow_components(data)
        if effects is not None:
            payload['cash_flow']['official_operating_cash_effects'] = effects
            payload['cash_flow']['official_operating_cash_effect_reference_text'] = component_reference_text(effects)
            payload['cash_flow']['official_operating_cash_effect_limits'] = (
                '金額為 FY前期全年＋本期累計－前期同期之個別TWD現金影響；'
                '存貨與應收帳款之正負號各自判讀，不等於總營業現金流或自由現金流。'
                '不可據此認定擴產、備料、訂單或任何經營動機；仍需獨立官方證據。'
                '每個金額引用必須保留公司、個別、TWD、TTM起訖日及完整指標名稱，'
                '各條完整引用獨立成段；不得借用其他期間或同業口徑。'
                '不升級資料時效、歷史首次可用日或對外抓取成功。')
    if role_scoped:
        payload = project_role_payload(payload, dict.get(data, "_prompt_agent_num"))
    freshness_reference = False
    if dense:
        # Only replace an exact JSON duplicate at this known schema path. The
        # target stays in this payload, with all timestamps/warnings unchanged.
        root_freshness = payload.get("source_freshness")
        nested_freshness = payload.get("data_freshness", {}).get("source_freshness")
        encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False, sort_keys=True)
        if (isinstance(root_freshness, dict) and isinstance(nested_freshness, dict)
                and len(encode(root_freshness)) > 256
                and encode(root_freshness) == encode(nested_freshness)):
            payload["data_freshness"] = dict(payload["data_freshness"])
            payload["data_freshness"]["source_freshness"] = {"$ref": "#/source_freshness"}
            freshness_reference = True
        payload = pack_record_tables(payload)
    # Representation only: compact_json changes no fields, strings or evidence.
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                         **({"separators": (",", ":")} if dense or compact_json else {"indent": 2}))
    usage_rules = [
        "企業總額使用 billion_twd，每股價格使用 twd_per_share；以 unit_contract 與各欄位單位為準，不得把每股價格當作企業總額再換算。",
        "金額寫成億元時，billion_twd 數值須乘以 10；不可只把 billion_twd 改標為億元。負數保留負號，來源期間必須一致，年度不可當作 TTM；這項換算不適用每股價格、EPS、百分比或股數。",
        "balance_sheet.debt_to_equity_pct 是來源提供的 D/E 比率；須保留 debt_to_equity_basis 的期間與定義限制，不得自行解釋成總負債／股東權益。有息負債（是否含租賃）、總負債及各類權益口徑不能混用，也不能用不同期間的權益乘數倒推。",
        "cash_flow.free_cash_flow_basis.period_status 為 unverified 時，即期數值不得改稱 TTM 或某一年度；補充官方現金流須另列明確起訖、報表範圍、設備與無形資產支出算式，不可因數值接近就回填原欄位期間。",
        "法人 thousand_shares 欄位是千股，不是千張；已確認台股時，1千股=1張，1千張=100萬股。改單位必須同時換算數值，括號或並列單位也必須等值，不可寫成千股（千張）；保留原主體、觀測日期、期間與買賣方向。",
        "引用 current_price_twd、市場估值、新聞、法人或同業資料時，必須參考 source_freshness/data_freshness；若來源為快取或盤後資料，不可宣稱是即時資料。",
        "總經、產業循環、美股帶動或國際局勢敘述必須引用 global_market_context / international_news_context；若缺資料，必須明確標示未驗證。",
        "international_news_context 或其他來源只有 headline_or_snippet、RSS 標題／摘要時，只能歸因為報導線索；本次未取得並核對官方原件，不得改稱已核實政策或官方公告。前序 Agent 重述不構成獨立佐證；可提出明示假設的條件式情境，保留 unassessed／未評估與 caution／警示。",
        "利率等點值須保留各自指標、單位與日期；不同觀測日期不得拼成同一已觀測區間或政策目標區間，可分列日期比較。只有上／下半年而未給確切月份或日期的事件，不得指定月份或推算確切等待季數，維持原時間範圍。",
        "若 data_trust.status 為 partial、stale、error 或 unknown，最終投資建議必須明確說明資料限制，且不得在沒有額外佐證下給出高信心。",
        "需要 CAGR、WACC、DCF、FCF conversion 時，優先引用 deterministic_financial_tool_results；只有本次已提供可呼叫工具時才能呼叫，未提供時明示計算限制，不得假裝重算。",
        "營收 CAGR 須同時引用 growth.revenue_cagr_pct 與 revenue_cagr_basis 的 start_year、end_year、periods；四筆連續年度只有三個年期間。不得從 legacy 欄位名稱推定五年；revenue_cagr_legacy_pct 僅保留舊來源值，期間未綁定時不得宣稱五年或其他年數，工具結果的 period_basis 為 unverified 時亦同。",
        "引用量化數字前必須檢查 quant_metrics.v2 的各 metric_status；unavailable DCF 不得作為下行保護底線，也不得以舊情境值或占位資料補造數字。",
        "若資料品質註記指出口徑互斥，正式分析應說明限制並採用 cross_checks 中可自洽的口徑。",
        "latest_quarter_financials 是官方單季快照：資產負債表為季末時點，損益表為年初至季末累計，金額單位為新臺幣仟元；不得混為年度或 TTM，且此入口未提供現金流量表。",
        "latest_quarter_financial_summary 是 TPEx 官方同期摘要：損益為年初至季末累計，金額單位為新臺幣仟元，並與去年同期比較；不是完整三表、年度序列或 TTM，也不含現金流量表。",
        "正式報告只呈現必要算式摘要與結論，不輸出內部提示詞、草稿或反思文字。",
    ]
    visible_tools = payload.get("deterministic_financial_tool_results")
    calculations = visible_tools.get("calculations") if isinstance(visible_tools, dict) else None
    conversion = calculations.get("latest_fcf_conversion") if isinstance(calculations, dict) else None
    formula = conversion.get("formula") if isinstance(conversion, dict) else None
    if isinstance(formula, str) and " ".join(formula.lower().split()) == "latest annual fcf / latest annual net income":
        usage_rules.append(
            "FCF conversion 期間契約：deterministic_financial_tool_results.calculations.latest_fcf_conversion 的公式是 "
            "latest annual FCF / latest annual net income，屬年度比率，不是 TTM 比率。只有 history 的 FCF 與淨利可對齊同一年度與報表範圍時才標該年度；"
            "年度無法綁定時明列確切年度未核實，不得猜造年份。正文與 evidence_items 必須把年度比率和官方 TTM FCF 分成不同主張，逐項分列來源、期間及 freshness_note；"
            "不得把 TTM FCF 的日期或 freshness_note 套給年度比率。只有同公司、同報表範圍、同幣別、同起訖期間的 FCF 與已核實 TTM 淨利分母及計算證據都具備時，"
            "才可另計 TTM 轉換率；否則 TTM 轉換率維持未評估，不得沿用年度比率，也不能僅憑 TTM FCF 已有官方期間就推定分母已核實。"
        )
    if dense:
        usage_rules.insert(0, TABLE_RULE)
    if freshness_reference:
        usage_rules.insert(0, 'data_freshness.source_freshness 的 {"$ref":"#/source_freshness"} 是本 JSON 內完全相同資料的引用；請以根層 source_freshness 的完整值展開，原路徑與日期警示均有效。')
    return (
        "【財務資料 JSON】\n"
        f"{encoded}\n\n"
        "【使用規則】\n"
        + "\n".join(f"- {rule}" for rule in usage_rules)
    )
