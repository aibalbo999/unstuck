"""Deterministic sampled evidence checks for rendered reports."""
from __future__ import annotations

import math
import re
from collections import Counter
from random import Random
from typing import Any

from evidence_exit_gate_claims import (
    _HORIZON_PREFIX_RE,
    _NORMALIZED_CANONICAL_STRING_PATH_MARKERS,
    _NORMALIZED_CONFIDENCE_METADATA_PATH_MARKERS,
    _NORMALIZED_SNAPSHOT_METADATA_PATH_MARKERS,
    _NUMBER_IN_STRING_RE,
    _SCENARIO_TARGET_LABELS,
    _TECHNICAL_LEVEL_LABELS,
    _clean_number,
    _normalize_match_text,
    _path_markers_for_claim,
    _valid_claim_number,
    best_match as _best_match,
    extract_numeric_claims,
)

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
    claims = [{**claim, "_price_history_months": price_history_months, "_legacy_conclusion_context_missing": isinstance(snapshot.get("rerun_context"), dict) and not snapshot["rerun_context"].get("parsed") and not snapshot["rerun_context"].get("structured_outputs") and (any(_normalize_match_text(marker) in _normalize_match_text(claim.get("label")) for marker in ("短期目標", "中期目標", "長期目標", "個月目標", "長期潛力")) or re.search(r"(?:(?:買入|持有|避免|放空|觀望)?(?:3|6|12)個月|(?:nt|twd|元)\d+(?:3|6|12)個月)", _normalize_match_text(claim.get("label"))) and "最終投資建議" in _normalize_match_text(claim.get("raw_text")))} for claim in extract_numeric_claims(markdown)]
    sample = sample_numeric_claims(claims, sample_ratio=sample_ratio, min_sample=min_sample, max_sample=max_sample, seed=seed)
    checked = [_check_claim(claim, snapshot_values, tolerance_pct=tolerance_pct) for claim in sample]
    failed_count = sum(1 for item in checked if item["status"] == "mismatch")
    verified_count = sum(1 for item in checked if item["status"] == "verified"); unverifiable_count = sum(1 for item in checked if item["status"] == "unverifiable"); unverifiable_reason_counts = {reason: sum(1 for item in checked if item["status"] == "unverifiable" and item["verification_reason_code"] == reason) for reason in {item["verification_reason_code"] for item in checked if item["status"] == "unverifiable"}}
    if not checked:
        verdict = "caution"; summary = "報告中未抽取到足夠可核驗數字。"
    else:
        comparable = [item for item in checked if item["status"] in {"verified", "mismatch"}]
        if not comparable:
            verdict = "caution"; summary = "抽樣數字缺少可對應的資料快照路徑，需人工確認。"
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
            if path == "data.daily_market_data.bars":
                date_counts = Counter(bar["date"] for bar in value if isinstance(bar, dict) and isinstance(bar.get("date"), str))
                for bar in value:
                    if not isinstance(bar, dict) or not isinstance(bar.get("date"), str) or date_counts[bar["date"]] != 1:
                        continue
                    for kind in ("high", "low"):
                        number = bar.get(kind)
                        if isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number) and number > 0:
                            values.append({"path": f"{path}[{bar['date']}].{kind}", "value": float(number)})
            for index, item in enumerate(value):
                if path.endswith("global_market_context.items") and isinstance(item, dict) and (symbol := _normalize_match_text(item.get("symbol") or item.get("label"))):
                    for key, child in item.items(): walk(child, f"{path}[{symbol}].{key}")
                    continue
                walk(item, f"{path}[{item.get('date')}]" if path.endswith("daily_total_net_buy_last_10") and isinstance(item, dict) and item.get("date") else f"{path}[{index}]")
    walk(snapshot, "")
    return values
def _check_claim(claim: dict[str, Any], snapshot_values: list[dict[str, Any]], *, tolerance_pct: float) -> dict[str, Any]:
    reported = float(claim.get("reported_value") or 0)
    path_markers = _path_markers_for_claim(claim)
    raw_claim_text = str(claim.get("raw_text") or "")
    normalized_label = _normalize_match_text(claim.get("label"))
    news_boundary = bool(re.search(r"(?:market[_ ]?catalysts?|recent[_ ]?catalysts?|新聞|催化劑|盤中速報|news)", raw_claim_text, re.IGNORECASE) and any(_normalize_match_text(marker) in normalized_label for marker in ("支撐", "壓力", "關卡", "風險")))
    research_boundary = any(marker in path_markers for marker in ("factset", "broker_research"))
    unavailable_boundary = "short_balance" in path_markers and bool(re.search(r"\b(?:null|n/?a|not\s+provided|unavailable)\b|未提供|無資料|不可用", raw_claim_text, re.IGNORECASE))
    legacy_conclusion_boundary = bool(claim.get("_legacy_conclusion_context_missing"))
    scenario_projection_boundary = bool(re.search(r"\|\s*[*_`]*\s*(?:保守|悲觀|中性|基準|樂觀)\s*[*_`]*\s*\|", raw_claim_text) and (claim.get("unit") == "億" or re.search(r"(?:情境預測|年營收|CAGR)", f"{claim.get('context_text') or ''}\n{raw_claim_text}", re.IGNORECASE)))
    candidate_values = _relevant_snapshot_values(claim, snapshot_values)
    if path_markers and path_markers[0].startswith("rerun_context.parsed.recommendation.") and not candidate_values:
        path_markers = ()
    best = _best_match(reported, candidate_values)
    if not path_markers or not candidate_values: status = "unverifiable"
    elif best and best["diff_pct"] <= tolerance_pct:
        status = "verified"
    else:
        status = "mismatch"
    if news_boundary and not path_markers:
        verification_reason_code = "news_source_not_canonical"
    elif research_boundary and not candidate_values:
        verification_reason_code = "research_source_not_canonical"
    elif legacy_conclusion_boundary and not path_markers:
        verification_reason_code = "legacy_conclusion_without_snapshot_path"
    elif not candidate_values and any(_normalize_match_text(marker) in normalized_label for marker in ("信心", "confidence")):
        verification_reason_code = "confidence_metadata_not_evidence"
    elif not candidate_values and (any(_normalize_match_text(marker) in normalized_label for marker in ("券資比", "margin short ratio", "short margin ratio")) or normalized_label in {"潛在下行空間", "potentialdownside"}):
        verification_reason_code = "derived_metric_not_canonical"
    elif not candidate_values and normalized_label in {"防軋空停損點stoplosslevel", "價格停損條件"}:
        verification_reason_code = "risk_control_not_canonical"
    elif not candidate_values and (normalized_label in _SCENARIO_TARGET_LABELS or re.search(r"\|\s*[*_`]*\s*(?:熊市|基本|牛市)\s*[*_`]*\s*\|", raw_claim_text)):
        verification_reason_code = "scenario_target_not_canonical"
    elif not candidate_values and normalized_label in _TECHNICAL_LEVEL_LABELS:
        verification_reason_code = "technical_level_not_canonical"
    elif not candidate_values and (scenario_projection_boundary or normalized_label in {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "fomo評分", "fomo過熱評分", "fomoscore", "聰明錢派發評分", "情緒評分", "score", "評分"} or any(_normalize_match_text(marker) in normalized_label or _normalize_match_text(marker) in _normalize_match_text(raw_claim_text) for marker in ("Agent 3 評分", "Agent 3 score"))):
        verification_reason_code = "analysis_metadata_not_evidence"
    elif unavailable_boundary and not candidate_values:
        verification_reason_code = "snapshot_field_unavailable"
    elif not path_markers:
        verification_reason_code = "missing_semantic_path"
    elif not candidate_values:
        verification_reason_code = "no_matching_snapshot_path"
    elif best and best["diff_pct"] <= tolerance_pct:
        verification_reason_code = "matched_snapshot_value"
    else:
        verification_reason_code = "snapshot_value_mismatch"
    return {
        **{key: value for key, value in claim.items() if key not in {"context_text", "series_context_text", "_price_history_months", "_legacy_conclusion_context_missing"}},
        "status": status, "verification_reason_code": verification_reason_code, "candidate_count": len(candidate_values),
        "matched_path": best.get("path") if best else "",
        "matched_value": best.get("value") if best else None,
        "diff_pct": round(best.get("diff_pct", 0.0), 4) if best else None,
    }
def _convert_snapshot_value_for_claim(claim: dict[str, Any], item: dict[str, Any], path_markers: tuple[str, ...]) -> dict[str, Any]:
    unit = _normalize_match_text(claim.get("unit"))
    path = _normalize_match_text(item.get("path"))
    if "shares_to_lots" in path_markers and unit == "張" and "borrowed_short_return_today" in path:
        return {**item, "value": float(item["value"]) / 1000}
    if "shares_to_thousands" in path_markers and unit == "k" and "borrowed_short_sale_today" in path:
        return {**item, "value": float(item["value"]) / 1000}
    if "shares_to_millions" in path_markers and unit in {"m", "million"} and ("borrowed_short_sale_today" in path or "borrowed_short_return_today" in path):
        return {**item, "value": float(item["value"]) / 1_000_000}
    return item


def _relevant_snapshot_values(claim: dict[str, Any], snapshot_values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path_markers = _path_markers_for_claim(claim)
    if not path_markers: return []
    if path_markers[0].startswith("data.daily_market_data.bars["):
        return [item for item in snapshot_values if item.get("path") == path_markers[0]]
    return [
        _convert_snapshot_value_for_claim(claim, item, path_markers)
        for item in snapshot_values
        if any(_normalize_match_text(marker) in _normalize_match_text(item.get("path")) for marker in path_markers)
    ]
def _is_eligible_snapshot_value(item: dict[str, Any]) -> bool:
    path = _normalize_match_text(item.get("path"))
    return not any(marker in path for marker in _NORMALIZED_SNAPSHOT_METADATA_PATH_MARKERS) and not any(marker in path for marker in _NORMALIZED_CONFIDENCE_METADATA_PATH_MARKERS)
