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
)
_NUMBER_IN_STRING_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_DATE_PREFIX_RE = re.compile(r"^\s*(?:[（(]|[/.-]\s*\d{1,2}\s*[/.-]\s*\d{1,2}\b)"); _SHORT_DATE_SUFFIX_RE = re.compile(r"^[/.-]\s*\d{1,2}\b(?=\s*(?:[A-Za-z\u4e00-\u9fff，,；;。]))")
_RANGE_PREFIX_RE = re.compile(r"^\s*-\s*\d")
_HORIZON_PREFIX_RE = re.compile(r"^\s*\d+(?:\s*[-–—~～至到]\s*\d+)?\s*(?:週|周|weeks?|個月|月|年|years?|天|日|days?)", re.IGNORECASE)
_EPS_VALUE_RE = re.compile(
    rf"(?:EPS|每股盈餘)[^\d\n]{{0,24}}?(?P<num>-?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{_NUMERIC_UNIT_PATTERN})?(?![\dA-Za-z.])",
    re.IGNORECASE,
)
_NON_CLAIM_SUFFIX_RE = re.compile(r"^\s*(?:[A-Za-z\u4e00-\u9fff]|週|周|個月|月|年|天|日)")
_NON_CLAIM_LABEL_MARKERS = ("code", "duration", "error", "hash", "pipeline", "prompt", "provider", "recordcount", "twse", "tradingview", "交易計畫健康度", "抓取", "資料日期", "時間", "程式碼", "版本", "錯誤", "耗時", "雜湊")
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
    (("大戶", "major holders", "major_holders"), ("major_holders", "major_holders_gt_1000_lots_pct")), (("散戶", "retail holders", "retail_holders"), ("retail_holders", "retail_holders_lt_50_lots_pct")), (("融資餘額", "margin balance", "margin_balance"), ("margin_balance", "margin_previous_balance")), (("融券餘額", "short balance", "short_balance"), ("short_balance", "short_previous_balance")), (("融資買進", "margin purchase", "margin_purchase"), ("margin_purchase",)), (("融資賣出", "margin sale", "margin_sale"), ("margin_sale",)), (("融券買進", "short purchase", "short_purchase"), ("short_purchase",)), (("融券賣出", "short sale", "short_sale"), ("short_sale",)), (("借券賣出餘額", "borrowed short sale balance", "borrowed_short_sale_balance"), ("borrowed_short_sale_balance",)), (("杜邦", "dupont"), ("dupont_identity_note",)),
    (("股價", "現價", "當前價格", "currentprice", "current_price"), ("current_price", "regularmarketprice", "stock_price", "share_price")),
    (("forwardpe", "forward pe"), ("forward_pe", "forwardpe", "forward_eps")),
    (("epsimpliedrevenuegrowth", "impliedrevenuegrowth"), ("forward_eps_implied_revenue_growth_pct", "implied_revenue_growth_pct")),
    (("淨利率", "profitmargin", "profit_margin"), ("profit_margin", "profit_margin_raw")),
    (("熊市", "基本", "牛市", "情境"), ("price_target", "price_targets", "target_price", "scenario", "scenarios")),
    (("風險", "支撐", "壓力", "關卡"), ("risk_price",)),
    (("p/e", "pe", "本益比"), ("pe_ratio", "trailingpe", "forwardpe", "price_earnings")), (("p/b", "pb", "本益比淨值比", "pricebook", "price_to_book"), ("pb_ratio", "pb", "price_to_book")), (("roe", "股東權益報酬率", "權益報酬率"), ("roe", "roe_pct", "return_on_equity")), (("beta", "貝他"), ("beta",)),
    (("毛利率", "grossmargin", "gross_margin"), ("gross_margin", "gross_margin_raw")), (("殖利率", "dividendyield", "dividend_yield"), ("dividend_yield", "dividend_yield_raw")), (("營收", "收入", "revenue", "sales"), ("revenue", "monthly_revenue", "sales")),
    (("淨利", "netincome", "net_income"), ("net_income", "netincome")),
    (("fcf", "自由現金流", "freecashflow", "free_cash_flow"), ("fcf", "free_cash_flow", "freecashflow")),
    (("市值", "marketcap", "market_cap"), ("market_cap", "marketcap")),
    (("eps", "每股盈餘"), ("eps", "earnings_per_share")),
    (("護城河", "moat"), ("moat", "moat_score", "moat_scores")),
    (("營業利益率", "operatingmargin", "operating_margin"), ("operating_margin", "operatingincome", "operating_income")),
    (("下行", "downside"), ("downside", "downside_pct")),
    (("情境", "scenario", "目標價", "targetprice"), ("price_target", "price_targets", "target_price", "scenario", "scenarios", "valuation", "dcf")),
)
def extract_numeric_claims(markdown: str) -> list[dict[str, Any]]:
    """Extract labelled numeric claims from rendered Markdown."""
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, float, int]] = set()
    in_code = False
    for line_number, raw_line in enumerate(str(markdown or "").splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith("#"):
            continue
        for match in list(_KV_RE.finditer(line)) + list(_TABLE_CELL_RE.finditer(line)):
            if _is_non_claim_match(line, match):
                continue
            label = _clean_label(match.group("label"))
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
            })
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
    claims = extract_numeric_claims(markdown)
    sample = sample_numeric_claims(claims, sample_ratio=sample_ratio, min_sample=min_sample, max_sample=max_sample, seed=seed)
    snapshot_values = [
        item for item in flatten_snapshot_numbers(snapshot)
        if _is_eligible_snapshot_value(item)
    ]
    checked = [_check_claim(claim, snapshot_values, tolerance_pct=tolerance_pct) for claim in sample]
    failed_count = sum(1 for item in checked if item["status"] == "mismatch")
    unverifiable_count = sum(1 for item in checked if item["status"] == "unverifiable")
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
        "unverifiable_count": unverifiable_count,
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
                values.extend({"path": f"{path}[{str(date)[:10]}].prices[{index}]", "value": float(price)} for index, (date, price) in enumerate(zip(value["dates"], value["prices"])) if isinstance(price, (int, float)) and not isinstance(price, bool))
                return
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                if path.endswith("global_market_context.items") and isinstance(item, dict) and (symbol := _normalize_match_text(item.get("symbol") or item.get("label"))):
                    for key, child in item.items(): walk(child, f"{path}[{symbol}].{key}")
                    continue
                walk(item, f"{path}[{index}]")
    walk(snapshot, "")
    return values
def _check_claim(claim: dict[str, Any], snapshot_values: list[dict[str, Any]], *, tolerance_pct: float) -> dict[str, Any]:
    reported = float(claim.get("reported_value") or 0)
    path_markers = _path_markers_for_claim(claim)
    candidate_values = _relevant_snapshot_values(claim, snapshot_values)
    best = _best_match(reported, candidate_values)
    if not path_markers or not candidate_values:
        status = "unverifiable"
    elif best and best["diff_pct"] <= tolerance_pct:
        status = "verified"
    else:
        status = "mismatch"
    return {
        **claim,
        "status": status,
        "matched_path": best.get("path") if best else "",
        "matched_value": best.get("value") if best else None,
        "diff_pct": round(best.get("diff_pct", 0.0), 4) if best else None,
    }
def _relevant_snapshot_values(claim: dict[str, Any], snapshot_values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path_markers = _path_markers_for_claim(claim)
    if not path_markers:
        return []
    relevant = [
        item for item in snapshot_values
        if any(_normalize_match_text(marker) in _normalize_match_text(item.get("path")) for marker in path_markers)
    ]
    return relevant
def _is_non_claim_match(line: str, match: re.Match[str]) -> bool:
    timestamp = re.search(r"\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}:\d{2}", line)
    if timestamp and timestamp.start() <= match.start("label") <= timestamp.end():
        return True

    label = _normalize_match_text(match.group("label"))
    if any(marker in label for marker in _NORMALIZED_NON_CLAIM_LABEL_MARKERS):
        return True

    number_start = match.start("num")
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
    claim_text = str(claim.get("raw_text") or ""); raw_label = str(claim.get("label") or "").lower()
    label = _normalize_match_text(raw_label)
    if not label:
        return ()
    raw_text = _normalize_match_text(claim.get("raw_text"))
    if "factset" in raw_text:
        return ("factset",)
    if any(marker in raw_text for marker in _NORMALIZED_RESEARCH_CONTEXT_MARKERS):
        return ("broker_research",)
    if (global_match := re.search(r"(?<![A-Za-z0-9])(\^?[A-Z][A-Z0-9^=.-]*)\s*[,：:]\s*change[_ ]?5d[_ ]?pct", claim_text, re.IGNORECASE)) and "change_5d_pct" in raw_text:
        return (f"global_market_context.items[{_normalize_match_text(global_match.group(1))}].change_5d_pct",)
    if ("1000lots" in raw_text and "concentration" in label) or ("50lots" in raw_text and "retail" in label): return ("major_holders_gt_1000_lots_pct",) if "concentration" in label else ("retail_holders_lt_50_lots_pct",)
    if label == "previous" and ("marginbalance" in raw_text or "shortbalance" in raw_text): return ("margin_previous_balance",) if "marginbalance" in raw_text else ("short_previous_balance",)
    history_date = re.search(r"(20\d{2})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})", claim_text); has_price_label = any(_normalize_match_text(marker) in label for marker in ("高點", "低點", "收盤", "支撐", "壓力", "股價", "價格", "close", "high", "low")); has_close_marker = any(_normalize_match_text(marker) in _normalize_match_text(claim_text) for marker in ("收盤", "close", "closing")); has_price_unit = bool(re.search(r"(?:NT\$|\$|TWD|元)", claim_text, re.IGNORECASE))
    if history_date and ("price_history" in raw_text or (has_price_label and has_close_marker and has_price_unit)):
        return (f"price_history[{history_date.group(1)}-{int(history_date.group(2)):02d}-{int(history_date.group(3)):02d}]",)
    if label == "totalnetbuythousandshares" and "total_net_buy_thousand_shares" in raw_text: return ("institutional_trading.total_net_buy_thousand_shares",)
    if "last_5_trading_days_net_buy_thousand_shares" in raw_text or label == "last5tradingdaysnetbuy": return ("institutional_trading.last_5_trading_days_net_buy_thousand_shares",)
    if label in ("週高點", "週低點", "壓力位", "支撐位") and str(claim.get("unit") or "").lower() in ("twd", "元") and (week_match := next((match for match in re.finditer(r"(?:(?:52\s*週|52週)\s*(?P<after>高|低)點\s*[:：為=]?\s*(?:NT\$|\$)?(?P<after_num>-?\d[\d,]*(?:\.\d+)?)|(?P<before_num>-?\d[\d,]*(?:\.\d+)?)\s*(?:TWD|元)?\s*[*_`]*\s*[（(]?\s*(?:52\s*週|52週)\s*(?P<before>高|低)點)", str(claim.get("raw_text") or ""), re.IGNORECASE) if _clean_number(match.group("after_num") or match.group("before_num")) == float(claim.get("reported_value") or 0)), None)): return ("week_52_high",) if (week_match.group("after") or week_match.group("before")) == "高" else ("week_52_low",)
    if (source_match := re.search(r"(-?\d[\d,]*(?:\.\d+)?)\s*(?:TWD|元)?\s*[（(]?\s*`?(?:data\.)?(market_data\.week_52_(?:high|low)_twd)", str(claim.get("raw_text") or ""), re.IGNORECASE)) and _clean_number(source_match.group(1)) == float(claim.get("reported_value") or 0): return ("week_52_high",) if "week_52_high_twd" in raw_text else ("week_52_low",)
    if any(marker in raw_text for marker in ("熊市", "牛市")):
        return ("stop_loss", "support", "resistance", "risk_price", "price_target", "price_targets", "target_price", "scenario", "scenarios")
    for label_markers, path_markers in _FIELD_HINTS:
        if any(_label_matches_marker(raw_label, label, marker) for marker in label_markers):
            return path_markers
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
