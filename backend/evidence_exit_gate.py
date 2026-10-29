"""Deterministic sampled evidence checks for rendered reports."""
from __future__ import annotations

import math
import re
from collections import Counter
from random import Random
from typing import Any
from evidence_technical_claims import CANONICAL_TECHNICAL_FIELDS, technical_snapshot_values, valid_technical_date
from evidence_technical_assignments import explicit_atr14_policy
from evidence_claim_types import public_metadata_claim
from evidence_trade_plan_claims import COVER_STOP_PATH, saved_cover_stop_number
from evidence_position_policy_claims import verified_position_policy_claim

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

_EXCLUDED_SNAPSHOT_PATH = re.compile("|".join(re.escape(marker) for marker in
    (*_NORMALIZED_SNAPSHOT_METADATA_PATH_MARKERS, *_NORMALIZED_CONFIDENCE_METADATA_PATH_MARKERS)))


_SNAPSHOT_DATE_PATH = re.compile(r'(?:^|\.)(?:checked_at|retrieved_at|fetched_at|generated_at|updated_at|as_of|date|year|years|timestamp)(?:$|\.|\[)')


class _InvocationValues(list):
    """Path matches reused only during one evaluation, never across snapshots."""
    def __init__(self):
        super().__init__()
        self.path_matches = {}


from evidence_claim_boundaries import with_match_normalization_cache


@with_match_normalization_cache
def evaluate_report_evidence(
    markdown: str,
    snapshot: dict[str, Any],
    *,
    sample_ratio: float = 1.0,
    min_sample: int = 3,
    max_sample: int | None = None,
    tolerance_pct: float = 1.0,
    seed: int = 17,
) -> dict[str, Any]:
    """Verify every extracted numeric claim by default; explicit sampling is diagnostic."""
    markdown = re.sub(r"<!-- evidence-ledger:start -->.*?<!-- evidence-ledger:end -->", "", markdown, flags=re.S)
    snapshot_values = _InvocationValues()
    normalized_snapshot_paths = []
    path_normalizations = {}
    path_eligibility = {}
    for item in flatten_snapshot_numbers(snapshot, eligible_only=True, _normalized_paths=path_normalizations, _eligible_paths=path_eligibility):
        path = item.get("path")
        normalized_path = path_normalizations.get(path)
        if normalized_path is None:
            normalized_path = _normalize_match_text(path)
            path_normalizations[path] = normalized_path
        eligible = path_eligibility.get(path)
        if eligible is None:
            eligible = _is_eligible_snapshot_value(item, normalized_path=normalized_path)
            path_eligibility[path] = eligible
        if eligible:
            snapshot_values.append(item)
            normalized_snapshot_paths.append(normalized_path)
    price_history_months = tuple(sorted({match.group(1) for item in snapshot_values if (match := re.search(r"price_history\[(20\d{2}-\d{2})-\d{2}\]", str(item.get("path") or "")))}))
    claims = [{**claim, "_price_history_months": price_history_months, "_legacy_conclusion_context_missing": isinstance(snapshot.get("rerun_context"), dict) and not snapshot["rerun_context"].get("parsed") and not snapshot["rerun_context"].get("structured_outputs") and (any(_normalize_match_text(marker) in _normalize_match_text(claim.get("label")) for marker in ("短期目標", "中期目標", "長期目標", "個月目標", "長期潛力")) or re.search(r"(?:(?:買入|持有|避免|放空|觀望)?(?:3|6|12)個月|(?:nt|twd|元)\d+(?:3|6|12)個月)", _normalize_match_text(claim.get("label"))) and "最終投資建議" in _normalize_match_text(claim.get("raw_text")))} for claim in extract_numeric_claims(markdown)]
    data = snapshot.get("data")
    technical = data.get("technical_indicators") if isinstance(data, dict) else None
    technical = technical if isinstance(technical, dict) else {}
    claims = [{**claim, "_technical_as_of": valid_technical_date(technical.get("as_of")), "_technical_default_atr14": explicit_atr14_policy(technical)} for claim in claims]
    from evidence_operational_time_claims import operational_time_claim
    timestamp_claims = []
    retained = []
    for claim in claims:
        temporal = operational_time_claim(claim, snapshot)
        if temporal is None:retained.append(claim)
        else:timestamp_claims.append(temporal)
    claims = retained
    policy_claims = []
    financial_and_score_claims = []
    for claim in claims:
        policy = verified_position_policy_claim(claim, snapshot, markdown)
        if policy is not None:
            policy_claims.append(public_metadata_claim(policy))
        else:
            financial_and_score_claims.append(claim)
    claims = financial_and_score_claims
    metadata_claims = [public_metadata_claim(claim) for claim in claims if claim.get("claim_type") == "analysis_score"]
    claims = [claim for claim in claims if claim.get("claim_type") != "analysis_score"]
    sample = sample_numeric_claims(claims, sample_ratio=sample_ratio, min_sample=min_sample, max_sample=len(claims) if max_sample is None else max_sample, seed=seed)
    from evidence_financial_amounts import financial_comparison_snapshot
    financial_snapshot = financial_comparison_snapshot(snapshot)
    checked = [
        _check_financial_or_other_claim(claim, financial_snapshot, snapshot_values,
                                       tolerance_pct=tolerance_pct, normalized_paths=normalized_snapshot_paths)
        for claim in sample
    ]
    from evidence_bound_technical_claims import prepare_bound_technical, check_bound_technical_claim
    if any(item.get('verification_reason_code') == 'missing_semantic_path' for item in checked):
        original_technical = prepare_bound_technical(snapshot)
        if original_technical is not None:
            checked = [(check_bound_technical_claim(claim, original_technical, tolerance_pct=tolerance_pct) or item)
                       if item.get('status') == 'unverifiable' and item.get('verification_reason_code') == 'missing_semantic_path'
                       else item for claim, item in zip(sample, checked)]
    from evidence_derived_claims import derived_pe_claims
    derived = derived_pe_claims(markdown, snapshot)
    from evidence_official_financial_claims import official_debt_component_claims
    derived.extend(official_debt_component_claims(markdown, snapshot, tolerance_pct))
    derived = [{"id": len(claims) + index + 1, **item} for index, item in enumerate(derived)]
    claims.extend(derived)
    checked.extend(derived)
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
            if failed_count:
                verdict = "rejected"
                summary = "至少一項可比對抽樣數字與資料快照矛盾，須修正後發布。"
            else:
                verdict = "caution"
                summary = "部分抽樣數字無法對上資料快照，需人工確認。"
            if unverifiable_count:
                summary += "另有數字缺少同語意資料路徑。"
    coverage_complete = len(checked) == len(claims)
    if not coverage_complete:
        if verdict == "approved":
            verdict = "caution"
        summary += "未逐項核對全部可抽取主張，不得視為完整通過。"
    summary += f"逐項核對 {len(checked)}/{len(claims)} 筆可抽取數字；僅核對保存快照一致性，不代表來源獨立真實性或預測有效。"
    metadata_invalid = sum(item["status"] == "invalid" for item in metadata_claims)
    metadata_unverifiable = sum(item["status"] == "unverifiable" for item in metadata_claims)
    if metadata_invalid or metadata_unverifiable:
        if verdict == "approved":
            verdict = "caution"
    if metadata_claims:
        summary += (f"財務抽查 {len(checked)}/{len(claims)} 筆；分析評分 {len(metadata_claims)} 筆"
                    f"（有效 {len(metadata_claims) - metadata_invalid - metadata_unverifiable}、無效 {metadata_invalid}、"
                    f"量尺未明 {metadata_unverifiable}），評分不計入財務證據。")
        reason_labels = {"score_not_finite": "評分不是有限數值", "score_scale_invalid": "評分量尺無效或互相衝突",
                         "score_out_of_range": "評分超出合法範圍", "score_scale_unspecified": "評分量尺未明示"}
        reasons = sorted({reason_labels.get(item["verification_reason_code"], item["verification_reason_code"])
                          for item in metadata_claims if item["status"] != "valid"})
        if reasons:
            summary += "需確認：" + "、".join(reasons) + "。"
    if policy_claims:
        summary += f"另核對 {len(policy_claims)} 筆研究等待政策值，不計入財務證據，也不代表實際持倉。"
    timestamp_invalid = sum(item['status']=='invalid' for item in timestamp_claims)
    timestamp_unknown = sum(item['status']=='unverifiable' for item in timestamp_claims)
    if timestamp_claims:
        summary += (f"另逐項核對 {len(timestamp_claims)} 筆時間中繼資料（矛盾 {timestamp_invalid}、依據不足 {timestamp_unknown}）；"
                    "僅核對保存標示，不計入財務證據，也不代表重新抓取或來源採用通過。")
    if timestamp_invalid:
        verdict='rejected'
    elif timestamp_unknown and verdict=='approved':
        verdict='caution'
    source_admission=None
    context=snapshot.get("rerun_context") or {}
    context=context if isinstance(context,dict) else {}
    parsed=context.get("parsed") or {}
    parsed=parsed if isinstance(parsed,dict) else {}
    oos=snapshot.get("oos_evaluation_inputs")
    oos=oos if isinstance(oos,dict) else {}
    setup=parsed.get("trade_setup") or oos.get("trade_setup")
    applicable=isinstance(data,dict) and str(data.get("ticker") or "").endswith((".TW",".TWO"))
    if isinstance(data,dict) and (applicable or isinstance(setup,dict)):
        setup=setup if isinstance(setup,dict) else {}
        from report_source_admission import report_source_admission,admission_reason_label
        source_admission=report_source_admission(data,setup)
        from trade_price_reference import snapshot_price_reference_checks
        price_checks = snapshot_price_reference_checks(snapshot)
        source_admission["price_reference_checks"] = price_checks
        source_admission["blockers"].extend(reason for check in price_checks if check["status"] == "mismatch" for reason in check["reason_codes"] if reason.endswith("_mismatch"))
        unknown_price_reasons = [reason for check in price_checks if check["status"] == "unverifiable" for reason in check["reason_codes"]]
        if unknown_price_reasons:
            source_admission["source_warnings"].extend(unknown_price_reasons)
            source_admission["source_eligible"] = False
            source_admission["eligible"] = False
        if source_admission["blockers"]:
            source_admission["eligible"] = False
            verdict="rejected"
            summary += " 來源／可執行價位門檻未通過：" + "；".join(admission_reason_label(reason) for reason in source_admission["blockers"]) + "；保留原分析，不可當作已查驗候選。"
        elif applicable and source_admission["source_eligible"] is False:
            if verdict=="approved":verdict="caution"
            summary += " 來源尚未核驗：" + "；".join(admission_reason_label(reason) for reason in source_admission["source_warnings"]) + "；數字一致不代表來源已驗證，不是下單許可。"
    from technical_reasoning import technical_reasoning_checks, histogram_data_from_snapshot
    reasoning_checks = technical_reasoning_checks(markdown, histogram_data_from_snapshot(snapshot))
    if any(item["status"] == "mismatch" for item in reasoning_checks):
        verdict = "rejected"
        summary += " 技術敘述與同一分析輸入窗的指標關係矛盾，詳見逐項檢核。"
    elif any(item["status"] == "unverifiable" for item in reasoning_checks):
        if verdict == "approved":
            verdict = "caution"
        summary += " MACD柱變化缺少可比的兩日計算依據，查核尚未完成。"
    return {
        "technical_reasoning_checks": reasoning_checks,
        "technical_reasoning_coverage": "explicit current histogram magnitude and named SMA relations;not all prose reasoning",
        "source_admission":source_admission,
        "schema_version": 2,
        "coverage_policy": "all_extracted_numeric_claims" if coverage_complete else "diagnostic_sample",
        "coverage_complete": coverage_complete,
        "unchecked_count": len(claims) - len(checked),
        "timestamp_claim_count": len(timestamp_claims),
        "timestamp_checked_count": len(timestamp_claims),
        "timestamp_invalid_count": timestamp_invalid,
        "timestamp_unverifiable_count": timestamp_unknown,
        "timestamp_claims": timestamp_claims,
        "all_numeric_claim_count": len(claims)+len(metadata_claims)+len(policy_claims)+len(timestamp_claims),
        "all_numeric_checked_count": len(checked)+len(metadata_claims)+len(policy_claims)+len(timestamp_claims),
        "policy_claim_count": len(policy_claims),
        "policy_checked_count": len(policy_claims),
        "policy_claims": policy_claims,
        "metadata_claim_count": len(metadata_claims),
        "metadata_checked_count": len(metadata_claims),
        "metadata_invalid_count": metadata_invalid,
        "metadata_unverifiable_count": metadata_unverifiable,
        "metadata_claims": metadata_claims,
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
def flatten_snapshot_numbers(snapshot: Any, *, eligible_only: bool = False, _normalized_paths: dict | None = None, _eligible_paths: dict | None = None) -> list[dict[str, Any]]:
    """Collect numeric values from a sanitized snapshot."""
    values: list[dict[str, Any]] = []
    path_normalizations = _normalized_paths if _normalized_paths is not None else {}
    path_eligibility = _eligible_paths if _eligible_paths is not None else {}
    def normalized(path):
        if path not in path_normalizations:
            path_normalizations[path] = _normalize_match_text(path)
        return path_normalizations[path]
    date_components = {"checked_at", "retrieved_at", "fetched_at", "generated_at", "updated_at", "as_of", "date", "year", "years", "timestamp"}
    marker_tail = max(map(len, (*_NORMALIZED_SNAPSHOT_METADATA_PATH_MARKERS, *_NORMALIZED_CONFIDENCE_METADATA_PATH_MARKERS)), default=1) - 1
    component_info = {}
    suffix_eligibility = {}
    normalized_components = {}
    def plain_component(component):
        if component not in component_info:
            component_info[component] = bool(re.fullmatch(r"[0-9A-Za-z_\u4e00-\u9fff]+", component))
        return component_info[component]
    def walk(value: Any, path: str, parent_path=None, component=None, indexed=False) -> None:
        if (value is None or isinstance(value, bool)) and path != COVER_STOP_PATH:
            return
        # These excluded metadata prefixes stay excluded for every descendant.
        # The public default still returns the complete legacy flattened list.
        if eligible_only and path:
            eligible = path_eligibility.get(path)
            if eligible is None:
                # An admitted parent has no excluded marker in its prefix.
                # For a plain child, only a boundary-spanning suffix can add
                # one. Complex keys retain the original full-path predicate.
                if (parent_path is not None and parent_path in path_normalizations
                        and component is not None and plain_component(component)):
                    if component not in normalized_components:
                        normalized_components[component] = _normalize_match_text(component)
                    child_normalized = normalized_components[component]
                    parent_normalized = path_normalizations[parent_path]
                    path_normalizations[path] = parent_normalized + child_normalized
                    date_eligible = indexed or component not in date_components
                    suffix = parent_normalized[-marker_tail:] + child_normalized
                    key = (suffix, date_eligible)
                    if key not in suffix_eligibility:
                        suffix_eligibility[key] = _is_eligible_snapshot_value(
                            {"path": path}, normalized_path=suffix, _date_component_eligible=date_eligible)
                    eligible = suffix_eligibility[key]
                else:
                    eligible = _is_eligible_snapshot_value({"path": path}, normalized_path=normalized(path))
                path_eligibility[path] = eligible
            if not eligible:
                return
        if path == COVER_STOP_PATH:
            number = saved_cover_stop_number(value, snapshot)
            if number is not None:
                values.append({"path": path, "value": number})
            return
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            if _valid_claim_number(float(value)):
                values.append({"path": path, "value": float(value)})
            return
        if isinstance(value, str):
            matches = list(_NUMBER_IN_STRING_RE.finditer(value))
            path_text = normalized(path)
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
            if path == "data.technical_indicators":
                values.extend(technical_snapshot_values(value))
                for key, item in value.items():
                    if not re.fullmatch(r"sma_\d+", key) and key not in CANONICAL_TECHNICAL_FIELDS:
                        walk(item, f"{path}.{key}")
                return
            if path.endswith("price_history") and {"dates", "prices"} <= value.keys():
                points = [(index, str(date)[:10], float(price)) for index, (date, price) in enumerate(zip(value["dates"], value["prices"])) if isinstance(price, (int, float)) and not isinstance(price, bool)]
                values.extend({"path": f"{path}[{date}].prices[{index}]", "value": price} for index, date, price in points)
                values.extend({"path": f"{path}[month-end={month}]", "value": next(price for _, date, price in reversed(points) if date[:7] == month)} for month in {date[:7] for _, date, _ in points})
                values.extend({"path": f"{path}[month={month}].{kind}", "value": (min if kind == "low" else max)(price for _, date, price in points if date[:7] == month)} for month in {date[:7] for _, date, _ in points} for kind in ("low", "high"))
                return
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key), path, str(key))
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
                if path.endswith("daily_total_net_buy_last_10") and isinstance(item, dict) and item.get("date"):
                    walk(item, f"{path}[{item.get('date')}]")
                else:
                    walk(item, f"{path}[{index}]", path, str(index), True)
    walk(snapshot, "")
    return values
def _check_financial_or_other_claim(claim, snapshot, snapshot_values, **kwargs):
    if claim.get('river_value_path') == 'pe_river_chart.eps_twd':
        return _check_year_bound_river_eps(claim, snapshot, tolerance_pct=kwargs['tolerance_pct'])
    from evidence_financial_amounts import check_financial_amount
    from evidence_official_financial_claims import official_ratio_claim
    official = official_ratio_claim(claim, snapshot, kwargs['tolerance_pct'])
    if official is not None:
        return official
    financial = check_financial_amount(claim, snapshot, kwargs['tolerance_pct'])
    return financial if financial is not None else _check_claim(claim, snapshot_values, **kwargs)



def _check_year_bound_river_eps(claim: dict[str, Any], snapshot: dict[str, Any], *, tolerance_pct: float) -> dict[str, Any]:
    """Compare only the EPS slot belonging to the claim's explicit annual basis."""
    data = snapshot.get('data')
    river = data.get('pe_river_chart') if isinstance(data, dict) else None
    years = river.get('years') if isinstance(river, dict) else None
    values = river.get('eps_twd') if isinstance(river, dict) else None
    year = claim.get('river_reference_year')
    valid = (type(year) is str and re.fullmatch(r'20\d{2}', year)
             and type(years) is list and type(values) is list and len(years) == len(values)
             and all(type(item) is str and re.fullmatch(r'20\d{2}', item) for item in years)
             and len(set(years)) == len(years) and year in years)
    index = years.index(year) if valid else None
    value = values[index] if index is not None else None
    if type(value) not in (int, float) or not math.isfinite(value):
        checked = _check_claim({**claim, 'eps_river_binding_unverified': True}, [], tolerance_pct=tolerance_pct)
        return {**checked, 'verification_reason_code': 'river_eps_year_unbound'}
    # Supply a single exact same-year slot; never choose another year by value.
    return _check_claim(claim, [{'path': f'data.pe_river_chart.eps_twd[{index}]', 'value': float(value)}],
                        tolerance_pct=tolerance_pct)


def _check_claim(claim: dict[str, Any], snapshot_values: list[dict[str, Any]], *,
                 tolerance_pct: float, normalized_paths: list[str] | None = None) -> dict[str, Any]:
    if claim.get('scenario_projection'):
        return {**claim, 'status': 'unverifiable', 'verification_reason_code': 'scenario_target_not_observed_fact',
                'verification_scope': 'model_scenario', 'candidate_count': 0}
    reported = float(claim.get("reported_value") or 0)
    path_markers = _path_markers_for_claim(claim)
    raw_claim_text = str(claim.get("raw_text") or "")
    normalized_label = _normalize_match_text(claim.get("label"))
    news_boundary = bool(re.search(r"(?:market[_ ]?catalysts?|recent[_ ]?catalysts?|新聞|催化劑|盤中速報|news)", raw_claim_text, re.IGNORECASE) and any(_normalize_match_text(marker) in normalized_label for marker in ("支撐", "壓力", "關卡", "風險")))
    research_boundary = any(marker in path_markers for marker in ("factset", "broker_research"))
    unavailable_boundary = "short_balance" in path_markers and bool(re.search(r"\b(?:null|n/?a|not\s+provided|unavailable)\b|未提供|無資料|不可用", raw_claim_text, re.IGNORECASE))
    legacy_conclusion_boundary = bool(claim.get("_legacy_conclusion_context_missing"))
    scenario_projection_boundary = bool(re.search(r"\|\s*[*_`]*\s*(?:保守|悲觀|中性|基準|樂觀)\s*[*_`]*\s*\|", raw_claim_text) and (claim.get("unit") == "億" or re.search(r"(?:情境預測|年營收|CAGR)", f"{claim.get('context_text') or ''}\n{raw_claim_text}", re.IGNORECASE)))
    candidate_values = _relevant_snapshot_values(claim, snapshot_values, normalized_paths=normalized_paths)
    if path_markers and path_markers[0].startswith("rerun_context.parsed.recommendation.") and not candidate_values:
        path_markers = ()
    # Agent plans are saved for reproducibility, not independent factual evidence.
    generated_candidates = [item for item in candidate_values if str(item.get("path") or "").startswith("rerun_context.")]
    candidate_values = [item for item in candidate_values if not str(item.get("path") or "").startswith("rerun_context.")]
    analysis_only = bool(generated_candidates) and not candidate_values
    best = _best_match(reported, candidate_values or generated_candidates)
    if analysis_only:
        status = "mismatch" if best and best["diff_pct"] > tolerance_pct else "unverifiable"
    elif not path_markers or not candidate_values: status = "unverifiable"
    elif best and best["diff_pct"] <= tolerance_pct:
        status = "verified"
    else:
        status = "mismatch"
    if analysis_only:
        verification_reason_code = "generated_analysis_value_mismatch" if status == "mismatch" else "generated_analysis_not_independent_evidence"
    elif news_boundary and not path_markers:
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
    elif not candidate_values and (scenario_projection_boundary or normalized_label in {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "fomo評分", "fomo過熱評分", "fomoscore", "聰明錢派發評分", "情緒評分", "情緒過熱評分", "過熱評分", "score", "評分"} or any(_normalize_match_text(marker) in normalized_label or _normalize_match_text(marker) in _normalize_match_text(raw_claim_text) for marker in ("Agent 3 評分", "Agent 3 score"))):
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
    # A provider D/E scalar has no same-period numerator/denominator receipt.
    # Matching its digits cannot certify a claim that it is total liabilities / equity.
    if ("debt_to_equity" in path_markers
            and re.search(r"總負債\s*[／/]\s*(?:股東)?權益", raw_claim_text)):
        status = "unverifiable"
        verification_reason_code = "financial_ratio_definition_unverified"
    return {
        **{key: value for key, value in claim.items() if key not in {"context_text", "series_context_text", "technical_context_text", "_price_history_months", "_legacy_conclusion_context_missing", "_technical_as_of", "_technical_default_atr14"}},
        "status": status, "verification_reason_code": verification_reason_code, "candidate_count": len(candidate_values),
        "verification_scope": "saved_analysis_consistency" if analysis_only else "snapshot_fact_consistency",
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


def _semantic_marker_matches(path, marker):
    # Revenue is a financial field, not any key containing the letters sales.
    if marker in {'revenue', 'monthly_revenue', 'sales'}:
        if any(token in path.lower() for token in ('chip_data', 'institutional_trading', 'borrowed_short', 'margin_short')):
            return False
        components = re.findall(r'[A-Za-z_][A-Za-z_0-9]*', path.lower())
        if marker == 'sales':
            return any(key in {'sales', 'net_sales', 'total_sales', 'sales_revenue'} for key in components)
        return any(key == marker or key.startswith(marker + '_') or key.endswith('_' + marker) for key in components)
    return _normalize_match_text(marker) in _normalize_match_text(path)


def _relevant_snapshot_values(claim: dict[str, Any], snapshot_values: list[dict[str, Any]], *,
                              normalized_paths: list[str] | None = None) -> list[dict[str, Any]]:
    path_markers = _path_markers_for_claim(claim)
    if not path_markers: return []
    if path_markers[0] == COVER_STOP_PATH or path_markers[0].startswith(("data.daily_market_data.bars[", "data.technical_indicators.", "rerun_context.parsed.recommendation.")):
        return [item for item in snapshot_values if item.get("path") == path_markers[0]]
    normalized_markers = tuple(_normalize_match_text(marker) for marker in path_markers)
    if normalized_paths is None:
        normalized_paths = [_normalize_match_text(item.get("path")) for item in snapshot_values]
    cache = getattr(snapshot_values, "path_matches", None)
    key = tuple(path_markers)
    matched = cache.get(key) if cache is not None else None
    if matched is None:
        pairs = tuple(zip(path_markers, normalized_markers))
        special = tuple((marker, normalized) for marker, normalized in pairs if marker in {'revenue', 'monthly_revenue', 'sales'})
        simple = tuple(normalized for marker, normalized in pairs if marker not in {'revenue', 'monthly_revenue', 'sales'})
        # Common marker sets contain only literal substrings. Avoid regex and
        # empty-generator dispatch millions of times, preserving item order.
        if not special and len(simple) == 1:
            marker = simple[0]
            matched = [item for item, path in zip(snapshot_values, normalized_paths) if marker in path]
        elif not special and len(simple) == 2:
            first, second = simple
            matched = [item for item, path in zip(snapshot_values, normalized_paths)
                       if first in path or second in path]
        elif not special and len(simple) == 3:
            first, second, third = simple
            matched = [item for item, path in zip(snapshot_values, normalized_paths)
                       if first in path or second in path or third in path]
        else:
            pattern = re.compile("|".join(re.escape(marker) for marker in simple)) if simple else None
            if special:
                matched = [item for item, normalized_path in zip(snapshot_values, normalized_paths)
                           if (pattern is not None and pattern.search(normalized_path)) or
                              any(normalized in normalized_path and _semantic_marker_matches(str(item.get('path') or ''), marker)
                                  for marker, normalized in special)]
            else:
                matched = [item for item, path in zip(snapshot_values, normalized_paths) if pattern.search(path)]
        if cache is not None:
            cache[key] = matched
    # Units and transformations remain claim-specific; only path selection is reused.
    return [_convert_snapshot_value_for_claim(claim, item, path_markers) for item in matched]
def _is_eligible_snapshot_value(item: dict[str, Any], *, normalized_path: str | None = None, _date_component_eligible: bool | None = None) -> bool:
    # Acquisition dates and financial period labels are context, never money
    # evidence just because their parent path includes a financial metric.
    if _date_component_eligible is False or (_date_component_eligible is None and _SNAPSHOT_DATE_PATH.search(str(item.get('path') or ''))):
        return False
    path = normalized_path if normalized_path is not None else _normalize_match_text(item.get("path"))
    return _EXCLUDED_SNAPSHOT_PATH.search(path) is None
