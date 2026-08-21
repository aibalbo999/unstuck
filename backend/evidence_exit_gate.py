"""Deterministic sampled evidence checks for rendered reports."""
from __future__ import annotations
import math
import re
from random import Random
from typing import Any
def _normalize_match_text(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z_\u4e00-\u9fff]+", "", str(value or "").lower())
_NUMERIC_UNIT_PATTERN = r"(?:TWD|%|x|X|倍|億|元|張|B|M|K|k|T)"
_KV_RE = re.compile(
    rf"(?P<label>[\u4e00-\u9fffA-Za-z][^:\n：|]{{0,30}})[:：]\s*[*_`]*\s*(?:[~約])?(?:NT\$|\$)?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{_NUMERIC_UNIT_PATTERN})?(?:[.．](?=\s*(?:[)）]|$)))?(?![\dA-Za-z.])"
)
_TABLE_CELL_RE = re.compile(
    rf"\|\s*(?P<label>[^|\n]{{1,30}})\s*\|\s*[*_`]*\s*(?:[~約])?(?:NT\$|\$)?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{_NUMERIC_UNIT_PATTERN})?(?:[.．](?=\s*\|))?(?![\dA-Za-z.])\s*\|"
); _TABLE_VALUE_LABEL_RE = re.compile(rf"^\s*(?:NT\$|\$)?\s*-?\d[\d,]*(?:\.\d+)?\s*(?:{_NUMERIC_UNIT_PATTERN}|billion[_ ]?twd|million[_ ]?twd|thousand[_ ]?twd)\s*$", re.IGNORECASE)
_SECONDARY_EVIDENCE_RE = re.compile(rf"(?:及|與|以及|,|，)\s*[*_`]*\s*(?:NT\$|\$)?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{_NUMERIC_UNIT_PATTERN})?\s*[^。\n]{{0,45}}(?:price_history|\d{{1,2}}\s*月份?\s*(?:收盤|收盤平台)|\d{{1,2}}\s*月\s*(?:底|末)(?:低點|高點))[^。\n]{{0,20}}", re.IGNORECASE)
_NUMBER_IN_STRING_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_DATE_PREFIX_RE = re.compile(r"^\s*(?:[（(]|[/.-]\s*\d{1,2}\s*[/.-]\s*\d{1,2}\b)"); _SHORT_DATE_SUFFIX_RE = re.compile(r"^[/.-]\s*\d{1,2}(?!\d)(?=\s*(?:[A-Za-z\u4e00-\u9fff，,；;。]|[-–—]|$))")
_RANGE_PREFIX_RE = re.compile(r"^\s*-\s*\d")
_HORIZON_PREFIX_RE = re.compile(r"^\s*(?:近\s*)?\d+(?:\s*[-–—~～至到]\s*\d+)?\s*(?:週|周|weeks?|個月|月|年|years?|天|日|days?)", re.IGNORECASE)
_EPS_VALUE_RE = re.compile(
    rf"(?:EPS|每股盈餘)[^\d\n]{{0,24}}?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{_NUMERIC_UNIT_PATTERN})?(?![\dA-Za-z.])",
    re.IGNORECASE,
)
_NON_CLAIM_SUFFIX_RE = re.compile(r"^\s*(?:[A-Za-z\u4e00-\u9fff]|週|周|個月|月|年|天|日)")
_NON_CLAIM_LABEL_MARKERS = ("code", "duration", "error", "hash", "pipeline", "prompt", "provider", "recordcount", "twse", "tradingview", "交易計畫健康度", "近 10 日每日趨勢", "daily trend", "Recent catalysts", "近期催化劑", "抓取", "資料日期", "時間", "程式碼", "版本", "錯誤", "耗時", "雜湊")
_SNAPSHOT_METADATA_PATH_MARKERS = ("cache_generated_at_epoch", "conclusion_generated_at", "conclusion_guardrails", "content_hash", "data_snapshot_hash", "duration_ms", "evidence_exit_gate", "fetched_at", "final_audit", "generated_at", "hash", "record_count", "reproducibility_packet", "report_conformance", "report_lint", "snapshot_hash", "snapshot_refreshed_at", "source_audit", "target_ticker")
_CONFIDENCE_METADATA_PATH_MARKERS = ("content_credibility", "data_confidence", "max_recommended_confidence", "min_data_confidence", "confidence_data_trust", "report_conformance")
_NORMALIZED_NON_CLAIM_LABEL_MARKERS = tuple(_normalize_match_text(marker) for marker in _NON_CLAIM_LABEL_MARKERS)
_NORMALIZED_SNAPSHOT_METADATA_PATH_MARKERS = tuple(_normalize_match_text(marker) for marker in _SNAPSHOT_METADATA_PATH_MARKERS)
_NORMALIZED_CONFIDENCE_METADATA_PATH_MARKERS = tuple(_normalize_match_text(marker) for marker in _CONFIDENCE_METADATA_PATH_MARKERS)
_NORMALIZED_CANONICAL_STRING_PATH_MARKERS = tuple(_normalize_match_text(marker) for marker in ("target_price", "analyst_target", "current_price", "forward_eps", "trailing_eps"))
_NORMALIZED_RESEARCH_CONTEXT_MARKERS = tuple(_normalize_match_text(marker) for marker in ("券商研究", "市場研究", "券商給予"))
_FIELD_HINTS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("信心", "confidence"), ("confidence", "confidence_score", "agent_confidence")),
    (("停損", "止損", "stoploss", "stop_loss"), ("stop_loss", "stoploss", "risk_price")),
    (("大戶", "major holders", "major_holders"), ("major_holders", "major_holders_gt_1000_lots_pct")), (("散戶", "retail holders", "retail_holders"), ("retail_holders", "retail_holders_lt_50_lots_pct")), (("融資餘額", "margin balance", "margin_balance"), ("margin_balance", "margin_previous_balance")), (("融券餘額", "short balance", "short_balance"), ("short_balance", "short_previous_balance")), (("融資買進", "margin purchase", "margin_purchase"), ("margin_purchase",)), (("融資賣出", "margin sale", "margin_sale"), ("margin_sale",)), (("融券買進", "short purchase", "short_purchase"), ("short_purchase",)), (("融券賣出", "short sale", "short_sale"), ("short_sale",)), (("借券賣出餘額", "borrowed short sale balance", "borrowed_short_sale_balance"), ("borrowed_short_sale_balance",)), (("當日借券還券", "borrowed short return today"), ("borrowed_short_return_today", "shares_to_lots")), (("Dealer", "自營商"), ("institutional_trading.net_buy_thousand_shares_by_category.dealer",)), (("Total Net Buy (30 days)", "totalnetbuy30days"), ("institutional_trading.total_net_buy_thousand_shares",)), (("Taiwan Weighted Index",), ("global_market_context.items[twii].latest",)), (("USD/TWD",), ("global_market_context.items[twdx].latest",)), (("WTI Crude Oil", "WTI Crude Oil Futures"), ("global_market_context.items[clf].latest",)), (("杜邦", "dupont"), ("dupont_identity_note",)),
    (("股價", "現價", "當前價格", "當前價位", "currentprice", "current_price"), ("current_price", "regularmarketprice", "stock_price", "share_price")),
    (("forwardpe", "forward pe"), ("forward_pe", "forwardpe", "forward_eps")),
    (("epsimpliedrevenuegrowth", "impliedrevenuegrowth"), ("forward_eps_implied_revenue_growth_pct", "implied_revenue_growth_pct")), (("incomegrowthlatestannual", "latest annual net income growth"), ("latest_annual_net_income_growth",)),
    (("淨利率", "profitmargin", "profit_margin"), ("profit_margin", "profit_margin_raw")),
    (("熊市", "基本", "牛市", "情境"), ("price_target", "price_targets", "target_price", "scenario", "scenarios")), (("週目標", "weektarget"), ("parsed.trade_setup.target_price", "structured_outputs.24.target_price")),
    (("風險", "支撐", "壓力", "關卡"), ("risk_price",)), (("river chart", "pe_river_chart"), ("pe_river_chart.multiples",)), (("weekhigh", "52 week high"), ("week_52_high",)), (("weeklow", "52 week low"), ("week_52_low",)),
    (("p/e", "pe", "本益比"), ("pe_ratio", "trailingpe", "forwardpe", "price_earnings")), (("p/b", "pb", "本益比淨值比", "pricebook", "price_to_book"), ("pb_ratio", "pb", "price_to_book")), (("roe", "股東權益報酬率", "權益報酬率"), ("roe", "roe_pct", "return_on_equity")), (("beta", "貝他"), ("beta",)),
    (("毛利率", "grossmargin", "gross_margin"), ("gross_margin", "gross_margin_raw")), (("殖利率", "dividendyield", "dividend_yield"), ("dividend_yield", "dividend_yield_raw")), (("營收", "收入", "revenue", "sales"), ("revenue", "monthly_revenue", "sales")),
    (("淨利", "netincome", "net_income"), ("net_income", "netincome")),
    (("operating cash flow", "operating_cash_flow", "營業現金流"), ("operating_cash_flow",)), (("fcf", "自由現金流", "freecashflow", "free_cash_flow"), ("fcf", "free_cash_flow", "freecashflow")),
    (("市值", "marketcap", "market_cap"), ("market_cap", "marketcap")),
    (("eps", "每股盈餘"), ("eps", "earnings_per_share")),
    (("護城河", "moat"), ("moat", "moat_score", "moat_scores")),
    (("營業利益率", "operatingmargin", "operating_margin"), ("operating_margin", "operatingincome", "operating_income")),
    (("下行", "downside"), ("downside", "downside_pct")),
    (("情境", "scenario", "目標價", "targetprice"), ("price_target", "price_targets", "target_price", "scenario", "scenarios", "valuation", "dcf")),
)
def extract_numeric_claims(markdown: str) -> list[dict[str, Any]]:
    """Extract labelled numeric claims from rendered Markdown."""
    claims: list[dict[str, Any]] = []; seen: set[tuple[str, float, int]] = set()
    in_code = False
    for line_number, raw_line in enumerate((lines := str(markdown or "").splitlines()), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith("#"):
            continue
        for match in list(_KV_RE.finditer(line)) + list(_TABLE_CELL_RE.finditer(line)):
            if _is_non_claim_match(line, match):
                continue
            label = _clean_label(match.group("label")); horizon_prefix = re.search(r"(?P<horizon>\d+)\s*[*_`]*$", line[:match.start("label")]); label = f"{horizon_prefix.group('horizon')}{label}" if horizon_prefix and label.startswith(("個月", "月")) else label
            number, unit = _claim_value(match, label, line)
            if not label or number is None or not _valid_claim_number(number):
                continue
            default_number = _clean_number(match.group("num"))
            if number == default_number and _NON_CLAIM_SUFFIX_RE.match(line[match.end():]):
                continue
            if number == default_number and _RANGE_PREFIX_RE.match(line[match.end():]):
                continue
            if number == default_number and _SHORT_DATE_SUFFIX_RE.match(line[match.end():]): continue
            if (
                number == default_number
                and not match.group("unit")
                and default_number is not None
                and 1900 <= default_number <= 2100
                and _DATE_PREFIX_RE.match(line[match.end():])
            ):
                continue
            key = (label, round(number, 6), line_number)
            if key in seen:
                continue
            seen.add(key)
            claims.append({
                "id": len(claims) + 1,
                "label": label,
                "reported_value": number,
                "unit": unit,
                "line_number": line_number,
                "raw_text": line[:160],
                **({"series_context_text": "\n".join(lines[max(0, line_number - 20):line_number - 1])} if re.fullmatch(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}", label, re.IGNORECASE) else {"context_text": "\n".join(lines[max(0, line_number - 3):line_number - 1])} if line_number > 1 else {}),
            })
            if any(_normalize_match_text(marker) in _normalize_match_text(label) for marker in ("支撐", "壓力", "高點", "低點")):
                for secondary in _SECONDARY_EVIDENCE_RE.finditer(line[match.end():]):
                    secondary_number = _clean_number(secondary.group("num")); secondary_label = f"{label}（次要價位）"
                    if secondary_number is None or not _valid_claim_number(secondary_number) or (secondary_key := (secondary_label, round(secondary_number, 6), line_number)) in seen:
                        continue
                    seen.add(secondary_key); secondary_text = secondary.group(0).strip()
                    claims.append({"id": len(claims) + 1, "label": secondary_label, "reported_value": secondary_number, "unit": (secondary.group("unit") or "").strip(), "line_number": line_number, "raw_text": f"{label}: {secondary_text}"[:160]})
    return claims
def _claim_value(match: re.Match[str], label: str, line: str) -> tuple[float | None, str]:
    """Prefer the value tied to an explicit EPS phrase over a leading date."""
    default_number = _clean_number(match.group("num"))
    default_unit = (match.group("unit") or "").strip()
    if not _label_has_eps_hint(label):
        return default_number, default_unit
    suffix = line[match.end("label") + 1 :]
    eps_match = _EPS_VALUE_RE.search(suffix)
    if not eps_match:
        return default_number, default_unit
    number = _clean_number(eps_match.group("num"))
    unit = (eps_match.group("unit") or "").strip()
    return (number if number is not None else default_number), (unit or default_unit)
def _label_has_eps_hint(label: str) -> bool:
    normalized = _normalize_match_text(label)
    return any(_normalize_match_text(marker) in normalized for marker in ("eps", "每股盈餘"))
def evaluate_report_evidence(
    markdown: str,
    snapshot: dict[str, Any],
    *,
    sample_ratio: float = 0.15,
    min_sample: int = 3,
    max_sample: int = 30,
    tolerance_pct: float = 1.0,
    seed: int = 17,
) -> dict[str, Any]:
    """Sample report numeric claims and verify them against snapshot values."""
    snapshot_values = [
        item for item in flatten_snapshot_numbers(snapshot)
        if _is_eligible_snapshot_value(item)
    ]
    price_history_months = tuple(sorted({match.group(1) for item in snapshot_values if (match := re.search(r"price_history\[(20\d{2}-\d{2})-\d{2}\]", str(item.get("path") or "")))}))
    claims = [{**claim, "_price_history_months": price_history_months, "_legacy_conclusion_context_missing": isinstance(snapshot.get("rerun_context"), dict) and not snapshot["rerun_context"].get("parsed") and not snapshot["rerun_context"].get("structured_outputs") and any(_normalize_match_text(marker) in _normalize_match_text(claim.get("label")) for marker in ("短期目標", "中期目標", "長期目標", "個月目標", "長期潛力"))} for claim in extract_numeric_claims(markdown)]
    sample = sample_numeric_claims(claims, sample_ratio=sample_ratio, min_sample=min_sample, max_sample=max_sample, seed=seed)
    checked = [_check_claim(claim, snapshot_values, tolerance_pct=tolerance_pct) for claim in sample]
    failed_count = sum(1 for item in checked if item["status"] == "mismatch")
    verified_count = sum(1 for item in checked if item["status"] == "verified"); unverifiable_count = sum(1 for item in checked if item["status"] == "unverifiable"); unverifiable_reason_counts = {reason: sum(1 for item in checked if item["status"] == "unverifiable" and item["verification_reason_code"] == reason) for reason in {item["verification_reason_code"] for item in checked if item["status"] == "unverifiable"}}
    if not checked:
        verdict = "caution"
        summary = "報告中未抽取到足夠可核驗數字。"
    else:
        comparable = [item for item in checked if item["status"] in {"verified", "mismatch"}]
        if not comparable:
            verdict = "caution"
            summary = "抽樣數字缺少可對應的資料快照路徑，需人工確認。"
        elif failed_count == 0 and unverifiable_count == 0:
            verdict = "approved"
            summary = "抽樣數字均可在資料快照中找到對應值。"
        else:
            failure_rate = failed_count / len(comparable)
            if failure_rate >= 0.5:
                verdict = "rejected"
                summary = "超過半數可比對抽樣數字無法對上資料快照。"
            else:
                verdict = "caution"
                summary = "部分抽樣數字無法對上資料快照，需人工確認。"
            if unverifiable_count:
                summary += "另有數字缺少同語意資料路徑。"
    return {
        "schema_version": 1,
        "verdict": verdict,
        "summary": summary,
        "claim_count": len(claims),
        "sampled_count": len(checked),
        "failed_count": failed_count,
        "unverifiable_count": unverifiable_count, "verified_count": verified_count, "unverifiable_reason_counts": unverifiable_reason_counts,
        "tolerance_pct": tolerance_pct,
        "sampled_claims": checked,
    }
def sample_numeric_claims(
    claims: list[dict[str, Any]],
    *,
    sample_ratio: float = 0.15,
    min_sample: int = 3,
    max_sample: int = 30,
    seed: int = 17,
) -> list[dict[str, Any]]:
    if not claims:
        return []
    sample_size = max(min_sample, math.ceil(len(claims) * max(sample_ratio, 0.0)))
    sample_size = min(max_sample, len(claims), sample_size)
    if sample_size >= len(claims):
        return list(claims)
    priority = [item for item in claims if re.search(r"`[A-Za-z_][A-Za-z0-9_.]*`", str(item.get("raw_text") or "")) or any(marker in _normalize_match_text(item.get("label")) for marker in ("pettm", "forwardpe", "本益比"))]
    if len(priority) >= sample_size:
        sampled = Random(seed).sample(priority, sample_size)
    else:
        others = [item for item in claims if item not in priority]
        sampled = priority + Random(seed).sample(others, sample_size - len(priority))
    return sorted(sampled, key=lambda item: int(item.get("line_number") or 0))
def flatten_snapshot_numbers(snapshot: Any) -> list[dict[str, Any]]:
    """Collect numeric values from a sanitized snapshot."""
    values: list[dict[str, Any]] = []
    def walk(value: Any, path: str) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            if _valid_claim_number(float(value)):
                values.append({"path": path, "value": float(value)})
            return
        if isinstance(value, str):
            matches = list(_NUMBER_IN_STRING_RE.finditer(value))
            path_text = _normalize_match_text(path)
            if any(marker in path_text for marker in _NORMALIZED_CANONICAL_STRING_PATH_MARKERS):
                if _normalize_match_text("target_price") in path_text:
                    value = _HORIZON_PREFIX_RE.sub(" ", value, count=1)
                    matches = list(_NUMBER_IN_STRING_RE.finditer(value))
                matches = matches[:1]
            for match in matches:
                number = _clean_number(match.group(0))
                if number is not None and _valid_claim_number(number):
                    values.append({"path": path, "value": number})
            return
        if isinstance(value, dict):
            if path.endswith("price_history") and {"dates", "prices"} <= value.keys():
                points = [(index, str(date)[:10], float(price)) for index, (date, price) in enumerate(zip(value["dates"], value["prices"])) if isinstance(price, (int, float)) and not isinstance(price, bool)]
                values.extend({"path": f"{path}[{date}].prices[{index}]", "value": price} for index, date, price in points)
                values.extend({"path": f"{path}[month-end={month}]", "value": next(price for _, date, price in reversed(points) if date[:7] == month)} for month in {date[:7] for _, date, _ in points})
                values.extend({"path": f"{path}[month={month}].{kind}", "value": (min if kind == "low" else max)(price for _, date, price in points if date[:7] == month)} for month in {date[:7] for _, date, _ in points} for kind in ("low", "high"))
                return
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                if path.endswith("global_market_context.items") and isinstance(item, dict) and (symbol := _normalize_match_text(item.get("symbol") or item.get("label"))):
                    for key, child in item.items(): walk(child, f"{path}[{symbol}].{key}")
                    continue
                walk(item, f"{path}[{item.get('date')}]" if path.endswith("daily_total_net_buy_last_10") and isinstance(item, dict) and item.get("date") else f"{path}[{index}]")
    walk(snapshot, "")
    return values
def _check_claim(claim: dict[str, Any], snapshot_values: list[dict[str, Any]], *, tolerance_pct: float) -> dict[str, Any]:
    reported = float(claim.get("reported_value") or 0)
    path_markers = _path_markers_for_claim(claim); raw_claim_text = str(claim.get("raw_text") or ""); news_boundary = bool(re.search(r"(?:market[_ ]?catalysts?|recent[_ ]?catalysts?|新聞|news)", raw_claim_text, re.IGNORECASE) and re.search(r"(?:NT\$|\$|TWD|元)", raw_claim_text, re.IGNORECASE) and any(_normalize_match_text(marker) in _normalize_match_text(claim.get("label")) for marker in ("支撐", "壓力", "關卡", "風險"))); legacy_conclusion_boundary = bool(claim.get("_legacy_conclusion_context_missing"))
    candidate_values = _relevant_snapshot_values(claim, snapshot_values)
    best = _best_match(reported, candidate_values)
    if not path_markers or not candidate_values:
        status = "unverifiable"
    elif best and best["diff_pct"] <= tolerance_pct:
        status = "verified"
    else:
        status = "mismatch"
    return {
        **{key: value for key, value in claim.items() if key not in {"context_text", "series_context_text", "_price_history_months", "_legacy_conclusion_context_missing"}},
        "status": status, "verification_reason_code": "news_source_not_canonical" if news_boundary and not path_markers else "legacy_conclusion_without_snapshot_path" if legacy_conclusion_boundary and not path_markers else "confidence_metadata_not_evidence" if not candidate_values and any(_normalize_match_text(marker) in _normalize_match_text(claim.get("label")) for marker in ("信心", "confidence")) else "missing_semantic_path" if not path_markers else "no_matching_snapshot_path" if not candidate_values else "matched_snapshot_value" if best and best["diff_pct"] <= tolerance_pct else "snapshot_value_mismatch", "candidate_count": len(candidate_values),
        "matched_path": best.get("path") if best else "",
        "matched_value": best.get("value") if best else None,
        "diff_pct": round(best.get("diff_pct", 0.0), 4) if best else None,
    }
def _relevant_snapshot_values(claim: dict[str, Any], snapshot_values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path_markers = _path_markers_for_claim(claim)
    if not path_markers: return []
    return [
        ({**item, "value": float(item["value"]) / 1000} if "shares_to_lots" in path_markers and _normalize_match_text(claim.get("unit")) == "張" and "borrowed_short_return_today" in _normalize_match_text(item.get("path")) else item)
        for item in snapshot_values
        if any(_normalize_match_text(marker) in _normalize_match_text(item.get("path")) for marker in path_markers)
    ]
def _is_non_claim_match(line: str, match: re.Match[str]) -> bool:
    timestamp = re.search(r"\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}", line)
    if (timestamp and timestamp.start() <= match.start("label") <= timestamp.end()) or re.search(r"`institutional_trading`\s*[:：]\s*\d+\s*-\s*day\s+lookback\b", line, re.IGNORECASE) or (match.re is _TABLE_CELL_RE and _TABLE_VALUE_LABEL_RE.fullmatch(match.group("label"))):
        return True
    label = _normalize_match_text(match.group("label")); number_start = match.start("num")
    if any(marker in label for marker in _NORMALIZED_NON_CLAIM_LABEL_MARKERS):
        return True
    if re.search(r"\d{1,2}:\s*$", line[:number_start]) and any(marker in label for marker in ("marketdata", "截至", "資料日期", "資料時間", "抓取時間")): return True
    if number_start <= 0 or line[number_start - 1] != "T":
        return False
    suffix = line[match.end("num") :]
    return bool(re.match(r":\d{2}(?::\d{2})?(?:[.,+\-Z]|$)", suffix))
def _is_eligible_snapshot_value(item: dict[str, Any]) -> bool:
    path = _normalize_match_text(item.get("path"))
    if any(marker in path for marker in _NORMALIZED_SNAPSHOT_METADATA_PATH_MARKERS):
        return False
    if any(marker in path for marker in _NORMALIZED_CONFIDENCE_METADATA_PATH_MARKERS):
        return False
    return True
def _path_markers_for_claim(claim: dict[str, Any]) -> tuple[str, ...]:
    claim_text = str(claim.get("raw_text") or ""); raw_label = str(claim.get("label") or "").lower(); series_context = str(claim.get("series_context_text") or "")
    label = _normalize_match_text(raw_label)
    if not label: return ()
    if (date_match := re.fullmatch(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})", raw_label.strip(), re.IGNORECASE)) and any(_normalize_match_text(marker) in _normalize_match_text(series_context) for marker in ("daily_total_net_buy_last_10", "Last 10 trading days daily total net buy")) and (year_match := re.search(r"(20\d{2})\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}", series_context)): return (f"institutional_trading.daily_total_net_buy_last_10[{year_match.group(1)}-{(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec').index(date_match.group(1).title()) + 1):02d}-{int(date_match.group(2)):02d}].net_buy_thousand_shares",)
    raw_text = _normalize_match_text(claim.get("raw_text"))
    if "factset" in raw_text:
        return ("factset",)
    if any(marker in raw_text for marker in _NORMALIZED_RESEARCH_CONTEXT_MARKERS):
        return ("broker_research",)
    if (global_match := re.search(r"(?<![A-Za-z0-9])(\^?[A-Z][A-Z0-9^=.-]*)\s*[,：:]\s*change[_ ]?5d[_ ]?pct", claim_text, re.IGNORECASE)) and "change_5d_pct" in raw_text:
        return (f"global_market_context.items[{_normalize_match_text(global_match.group(1))}].change_5d_pct",)
    if ("1000lots" in raw_text and "concentration" in label) or ("50lots" in raw_text and "retail" in label): return ("major_holders_gt_1000_lots_pct",) if "concentration" in label else ("retail_holders_lt_50_lots_pct",)
    if label == "previous" and ("marginbalance" in raw_text or "shortbalance" in raw_text): return ("margin_previous_balance",) if "marginbalance" in raw_text else ("short_previous_balance",)
    history_date = re.search(r"(20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})", claim_text); has_price_label = any(_normalize_match_text(marker) in label for marker in ("高點", "低點", "收盤", "支撐", "壓力", "股價", "價格", "close", "high", "low")); has_close_marker = any(_normalize_match_text(marker) in _normalize_match_text(claim_text) for marker in ("收盤", "close", "closing")); has_price_unit = bool(re.search(r"(?:NT\$|\$|TWD|元)", claim_text, re.IGNORECASE)); has_inline_extremum = bool(re.search(r"20\d{2}\s*[-/年.]\s*\d{1,2}\s*[-/月.]\s*\d{1,2}\s*(?:高點|低點|high|low)", claim_text, re.IGNORECASE)); has_dated_extremum = (any(_normalize_match_text(marker) in label for marker in ("高點", "低點")) or (has_price_label and has_inline_extremum)) and not any(_normalize_match_text(marker) in label for marker in ("52週", "52week")); has_news_source = any(marker in raw_text for marker in ("market_catalysts", "catalyst", "新聞", "news"))
    if history_date and ("price_history" in raw_text or (has_price_label and has_close_marker and has_price_unit) or (has_dated_extremum and not has_news_source)):
        return (f"price_history[{history_date.group(1)}-{int(history_date.group(2)):02d}-{int(history_date.group(3)):02d}]",)
    if (month_end := re.search(r"(?:(20\d{2})\s*(?:[-/年.]\s*)?)?(\d{1,2})\s*(?:(?:月份?|月)\s*收盤(?:平台|價)?|(?:月|月份)\s*(?:底|末)[^\n]{0,12}(?:低點|高點))", claim_text, re.IGNORECASE)) and any(_normalize_match_text(marker) in label for marker in ("支撐", "壓力", "高點", "低點")) and not has_news_source:
        month = int(month_end.group(2)); candidates = {month_name for month_name in claim.get("_price_history_months") or () if int(month_name[5:7]) == month}; year = month_end.group(1) or (next(iter({month_name[:4] for month_name in candidates})) if len({month_name[:4] for month_name in candidates}) == 1 else ""); previous_numbers = list(_NUMBER_IN_STRING_RE.finditer(claim_text[:month_end.start()]))
        if previous_numbers and _clean_number(previous_numbers[-1].group()) == float(claim.get("reported_value") or 0) and year and f"{year}-{month:02d}" in candidates: return (f"price_history[month-end={year}-{month:02d}]",)
    if (month_extremum := re.search(r"(20\d{2})\s*(?:[-/年.]\s*)?(\d{1,2})\s*(?:月|月份)?[^\n]{0,16}(低點|高點)", claim_text, re.IGNORECASE)) and any(_normalize_match_text(marker) in label for marker in ("支撐", "壓力", "高點", "低點")) and not has_news_source and (previous_numbers := list(_NUMBER_IN_STRING_RE.finditer(claim_text[:month_extremum.start()]))) and _clean_number(previous_numbers[-1].group()) == float(claim.get("reported_value") or 0): return (f"price_history[month={month_extremum.group(1)}-{int(month_extremum.group(2)):02d}].{'low' if month_extremum.group(3) == '低點' else 'high'}",)
    if label == "totalnetbuythousandshares" and "total_net_buy_thousand_shares" in raw_text: return ("institutional_trading.total_net_buy_thousand_shares",)
    if "last_5_trading_days_net_buy_thousand_shares" in raw_text or label == "last5tradingdaysnetbuy": return ("institutional_trading.last_5_trading_days_net_buy_thousand_shares",)
    if label in ("週高點", "週低點", "壓力位", "支撐位", "近期壓力", "關鍵壓力位") and str(claim.get("unit") or "").lower() in ("twd", "元") and (week_match := next((match for match in re.finditer(r"(?:(?:52\s*週|52週)\s*(?P<after>最高|最低|高|低)(?:點|價)?\s*[:：為=]?\s*(?:NT\$|\$)?(?P<after_num>-?\d[\d,]*(?:\.\d+)?)|(?P<before_num>-?\d[\d,]*(?:\.\d+)?)\s*(?:TWD|元)?\s*[*_`]*\s*[（(]?\s*[。．]?\s*(?:此為|為|是)?\s*(?:52\s*週|52週)\s*(?P<before>最高|最低|高|低)(?:點|價)?)", str(claim.get("raw_text") or ""), re.IGNORECASE) if _clean_number(match.group("after_num") or match.group("before_num")) == float(claim.get("reported_value") or 0)), None)): return ("week_52_high",) if (week_match.group("after") or week_match.group("before")) in ("高", "最高") else ("week_52_low",)
    if (source_match := re.search(r"(-?\d[\d,]*(?:\.\d+)?)\s*(?:TWD|元)?\s*[（(]?\s*`?(?:data\.)?(market_data\.week_52_(?:high|low)_twd)", str(claim.get("raw_text") or ""), re.IGNORECASE)) and _clean_number(source_match.group(1)) == float(claim.get("reported_value") or 0): return ("week_52_high",) if "week_52_high_twd" in raw_text else ("week_52_low",)
    if label == "low" and re.search(r"52\s*[- ]?week\s+high\s*[:：].*[/,]\s*low\s*[:：]", claim_text, re.IGNORECASE): return ("week_52_low",)
    if label == "最新餘額": return ("margin_balance",) if ("融資餘額" in raw_text or "marginbalance" in raw_text or "融資餘額" in _normalize_match_text(claim.get("context_text"))) else ("short_balance",) if ("融券餘額" in raw_text or "shortbalance" in raw_text or "融券餘額" in _normalize_match_text(claim.get("context_text"))) else ()
    if ((("riverchart" in raw_text or "河流圖" in raw_text) and str(claim.get("unit") or "").lower() in ("twd", "元") and re.search(r"\d[\d,]*(?:\.\d+)?\s*x\s*(?:區間|位階|band)", claim_text, re.IGNORECASE)) or (label == "x中高分位帶" and (band_match := re.search(r"(?P<multiple>\d[\d,]*(?:\.\d+)?)\s*x", str(claim.get("raw_text") or ""), re.IGNORECASE))) or (label in ("關鍵壓力", "關鍵壓力位") and str(claim.get("unit") or "").lower() in ("twd", "元") and any(marker in raw_text for marker in ("52週最高價", "week52high")))): return ("pe_river_chart.bands",) if ("riverchart" in raw_text or "河流圖" in raw_text) else (f"pe_river_chart.bands.{band_match.group('multiple')}x",) if label == "x中高分位帶" else ("week_52_high",)
    if (has_news_source and has_price_unit and any(_normalize_match_text(marker) in label for marker in ("支撐", "壓力", "關卡", "風險"))) or any(marker in raw_text for marker in ("熊市", "牛市")): return () if (has_news_source and has_price_unit and any(_normalize_match_text(marker) in label for marker in ("支撐", "壓力", "關卡", "風險"))) else ("stop_loss", "support", "resistance", "risk_price", "price_target", "price_targets", "target_price", "scenario", "scenarios")
    for label_markers, path_markers in _FIELD_HINTS:
        if any(_label_matches_marker(raw_label, label, marker) for marker in label_markers):
            return ("structured_outputs.24.target_price", "parsed.trade_setup.target_price") if any(_normalize_match_text(marker) in label for marker in ("目標價", "targetprice")) and label not in ("目標價", "targetprice") else ("price_target", "price_targets", "target_price", "scenario", "scenarios") if label in ("目標價", "targetprice") else path_markers
    return ()
def _label_matches_marker(raw_label: str, normalized_label: str, marker: str) -> bool:
    normalized_marker = _normalize_match_text(marker)
    if normalized_marker == "pe":
        return bool(re.search(r"(?<![a-z0-9])p\s*/?\s*e(?![a-z0-9])", raw_label))
    return normalized_marker in normalized_label
def _best_match(reported: float, snapshot_values: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for item in snapshot_values:
        candidate = float(item["value"])
        if reported == 0:
            diff_pct = 0.0 if candidate == 0 else 100.0
        else:
            diff_pct = abs(candidate - reported) / abs(reported) * 100
        if best is None or diff_pct < best["diff_pct"]:
            best = {"path": item["path"], "value": candidate, "diff_pct": diff_pct}
    return best
def _clean_label(value: str) -> str:
    label = re.sub(r"^[\-\*\s|]+", "", str(value or ""))
    label = re.sub(r"[\*_`]+", "", label).strip()
    if len(label) < 2:
        return ""
    if re.fullmatch(r"\d{4}|Q[1-4]|\d+", label):
        return ""
    if _normalize_match_text(label) in {"na", "none", "null", "unknown"}:
        return ""
    return label[:40]
def _clean_number(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
def _valid_claim_number(value: float) -> bool:
    return math.isfinite(value) and abs(value) < 1e15
