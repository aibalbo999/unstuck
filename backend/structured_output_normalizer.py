"""Normalize structured-agent JSON and convert it to report text."""

from __future__ import annotations

import math
import re
from typing import Any, Optional

from confidence_calibration import build_confidence_calibration, confidence_score, has_unresolved_cross_source_conflict
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text, safe_text_list
from recommendation_labels import normalize_recommendation_label
from structured_output_rendering import (
    ensure_agent19_required_sections,
    format_recommendation_block,
    normalize_escaped_newlines,
)
from structured_output_validation import validated_structured_payload


_NUMERIC_TOKEN_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_MANAGEMENT_GUIDANCE_TONES = {"樂觀", "中立", "保守", "資料不足"}
_TRADE_DIRECTIONS = {"Long", "Short", "Neutral"}
_TRADE_RISK_LEVELS = {"High", "Medium", "Low"}


def _number_text(value: str) -> str:
    tokens = [match.group(0) for match in _NUMERIC_TOKEN_RE.finditer(value.replace(",", ""))]
    return tokens[0] if len(tokens) == 1 else ""


def _coerce_number(value, minimum=None, maximum=None):
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = _number_text(value)
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        return None
    if not math.isfinite(number):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return round(number, 2)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n", ""}:
            return False
        return default
    number = _coerce_number(value)
    if number == 1:
        return True
    if number == 0:
        return False
    return default


def _pick_mapping_value(mapping: dict, *keys):
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


_MOAT_SCORE_ALIASES = {
    "品牌影響力": ("品牌影響力", "brand_influence"),
    "網路效應": ("網路效應", "network_effect"),
    "轉換成本": ("轉換成本", "switching_cost"),
    "成本優勢": ("成本優勢", "cost_advantage"),
    "專利技術": ("專利技術", "patent_technology"),
    "整體護城河": ("整體護城河", "overall_moat"),
}


_PRICE_TARGET_ALIASES = {
    "熊市情境": ("熊市情境", "bear_case", "bear"),
    "基本情境": ("基本情境", "base_case", "base"),
    "牛市情境": ("牛市情境", "bull_case", "bull"),
}

_SCENARIO_TRIGGER_FALLBACK = {
    "trigger_condition": "待後續資料確認觸發條件",
    "action": "重新檢查投資結論",
    "direction": "neutral_review",
}


def _display_text(value: Any, default: str = "") -> str:
    return safe_text(value).strip() or default


def _display_line(value: Any, default: str = "") -> str:
    text = _display_text(value, default)
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _display_price_target(value: Any) -> str:
    price = _coerce_number(value)
    return f"NT${price:,.0f}" if price is not None else "N/A"


def _report_body_text(analysis_markdown: Any, fallback_text: Any) -> str:
    return normalize_escaped_newlines(_display_text(analysis_markdown) or _display_text(fallback_text))


def _coerce_reasoning_steps(value: Any, minimum: int = 0) -> list[str]:
    if value is None:
        return ["待補推論步驟" for _ in range(minimum)]
    has_sequence_items = False
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = safe_sequence_items(value)
        has_sequence_items = True
    else:
        return ["待補推論步驟" for _ in range(minimum)]
    steps = []
    for item in candidates:
        text = _display_line(item)
        if text:
            steps.append(text)
    while has_sequence_items and len(steps) < minimum:
        steps.append("待補推論步驟")
    return steps


def _coerce_scenario_triggers(value: Any, minimum: int = 2, maximum: int = 5) -> list[dict[str, str]]:
    if value is None:
        return [dict(_SCENARIO_TRIGGER_FALLBACK) for _ in range(minimum)]
    if not isinstance(value, (list, tuple)):
        return [dict(_SCENARIO_TRIGGER_FALLBACK) for _ in range(minimum)]
    items = safe_sequence_items(value)
    if isinstance(value, (list, tuple)) and not items:
        return [dict(_SCENARIO_TRIGGER_FALLBACK) for _ in range(minimum)]
    triggers = []
    fallbacks = []
    for item in items:
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append(dict(_SCENARIO_TRIGGER_FALLBACK))
            continue
        condition = _display_line(row.get("trigger_condition"))
        action = _display_line(row.get("action"))
        direction = _display_line(row.get("direction"), "neutral_review")
        if direction not in {"bullish_upgrade", "bearish_downgrade", "neutral_review"}:
            direction = "neutral_review"
        if len(condition) < 10 or len(action) < 5:
            fallbacks.append({
                "trigger_condition": condition if len(condition) >= 10 else _SCENARIO_TRIGGER_FALLBACK["trigger_condition"],
                "action": action if len(action) >= 5 else _SCENARIO_TRIGGER_FALLBACK["action"],
                "direction": direction,
            })
            continue
        triggers.append({
            "trigger_condition": condition,
            "action": action,
            "direction": direction,
        })
    while len(items) >= minimum and len(triggers) < minimum and fallbacks:
        triggers.append(fallbacks.pop(0))
    return triggers[:maximum]


def _coerce_required_text_list(value: Any, minimum: int, fallback: str) -> list[str]:
    texts = safe_text_list(value)
    if not isinstance(value, (list, tuple)):
        return [fallback for _ in range(minimum)]
    while len(texts) < minimum:
        texts.append(fallback)
    return texts


def _coerce_confidence_basis(value: Any) -> Any:
    basis = safe_mapping_dict(value)
    if basis is None:
        return value
    return {
        **basis,
        "evidence_items": _coerce_required_text_list(basis.get("evidence_items"), 3, "待補具體佐證"),
        "key_risks_acknowledged": _coerce_required_text_list(basis.get("key_risks_acknowledged"), 2, "待補已納入風險"),
        "data_gaps": safe_text_list(basis.get("data_gaps")),
    }


def _coerce_next_catalysts(value: Any) -> list[dict[str, str]]:
    catalysts = []
    fallbacks = []
    for item in safe_sequence_items(value):
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append({
                "event_name": "待確認催化事件",
                "expected_timeframe": "待後續資料確認",
                "impact_direction": "volatile",
                "trigger_condition": "待後續資料確認",
            })
            continue
        impact_direction = _display_line(row.get("impact_direction"), "volatile")
        if impact_direction not in {"bullish", "bearish", "volatile"}:
            impact_direction = "volatile"
        event_name = _display_line(row.get("event_name"))
        expected_timeframe = _display_line(row.get("expected_timeframe"))
        trigger_condition = _display_line(row.get("trigger_condition"))
        catalyst = {
            "event_name": event_name or "待確認催化事件",
            "expected_timeframe": expected_timeframe or "待後續資料確認",
            "impact_direction": impact_direction,
            "trigger_condition": trigger_condition if len(trigger_condition) >= 5 else "待後續資料確認",
        }
        if event_name and expected_timeframe and len(trigger_condition) >= 5:
            catalysts.append(catalyst)
        else:
            fallbacks.append(catalyst)
    if not catalysts and fallbacks:
        catalysts.append(fallbacks[0])
    return catalysts


def _derive_next_catalysts_from_scenario_triggers(value: Any) -> list[dict[str, str]]:
    catalysts = []
    for idx, trigger in enumerate(safe_dict_list(value), start=1):
        condition = _display_line(trigger.get("trigger_condition"))
        if len(condition) < 5:
            continue
        direction = _display_line(trigger.get("direction"))
        if "bullish" in direction:
            impact = "bullish"
        elif "bearish" in direction:
            impact = "bearish"
        else:
            impact = "volatile"
        catalysts.append({
            "event_name": f"Scenario trigger {idx}",
            "expected_timeframe": "待後續資料確認",
            "impact_direction": impact,
            "trigger_condition": condition,
        })
    return catalysts


def _coerce_dcf_scenarios(value: Any) -> list[dict[str, float | str]]:
    scenarios = []
    for row in safe_dict_list(value):
        scenario = _display_line(row.get("scenario")).lower()
        if scenario not in {"bear", "base", "bull"}:
            continue
        revenue_growth_bias = _coerce_number(row.get("revenue_growth_bias_pct"))
        margin_bias = _coerce_number(row.get("margin_bias_pct"))
        wacc = _coerce_number(row.get("wacc_pct"), 0.01, None)
        intrinsic_value = _coerce_number(row.get("intrinsic_value"), 0, None)
        scenarios.append({
            "scenario": scenario,
            "revenue_growth_bias_pct": revenue_growth_bias if revenue_growth_bias is not None else 0.0,
            "margin_bias_pct": margin_bias if margin_bias is not None else 0.0,
            "wacc_pct": wacc if wacc is not None else 1.0,
            "intrinsic_value": intrinsic_value if intrinsic_value is not None else 0.0,
        })
        if len(scenarios) >= 3:
            break
    return scenarios


def _coerce_moat_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value
    scores = safe_mapping_dict(payload.get("moat_scores"))
    normalized = {
        **payload,
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }
    if scores is None:
        return normalized

    normalized_scores = dict(scores)
    for key, aliases in _MOAT_SCORE_ALIASES.items():
        score = _coerce_number(_pick_mapping_value(scores, *aliases), 1, 10)
        normalized_scores[key] = score if score is not None else 1.0
    return {
        **normalized,
        "moat_scores": normalized_scores,
    }


def _coerce_downside_risks(raw_value: Any, validated_value: Any) -> list[dict[str, Any]]:
    risks = []
    for idx, risk in enumerate(safe_dict_list(validated_value)[:5]):
        normalized = dict(risk)
        confidence = _coerce_number(normalized.get("confidence"), 0, 1)
        normalized["confidence"] = confidence if confidence is not None else 0.7
        risks.append(normalized)
    return risks


def _coerce_price_target_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value
    targets = safe_mapping_dict(payload.get("price_targets"))
    if targets is None:
        return payload
    summary = safe_mapping_dict(payload.get("valuation_summary"))
    if summary is not None:
        primary_method = _display_line(summary.get("primary_method"), "blended")
        if primary_method not in {"normalized_dcf", "relative_valuation", "blended"}:
            primary_method = "blended"
        summary = {
            **summary,
            "primary_method": primary_method,
            "uses_market_value_wacc": _coerce_bool(summary.get("uses_market_value_wacc")),
            "uses_normalized_fcf": _coerce_bool(summary.get("uses_normalized_fcf")),
            "double_counting_check": _display_text(summary.get("double_counting_check"), "資料不足"),
        }

    normalized_targets = {
        **targets,
        "dcf_reasoning": _display_text(
            _pick_mapping_value(targets, "dcf_reasoning", "DCF推論", "DCF 推論"),
            "資料不足",
        ),
        "peer_reasoning": _display_text(
            _pick_mapping_value(targets, "peer_reasoning", "同業推論", "同業比較推論"),
            "資料不足",
        ),
        "scenario_reasoning": _display_text(
            _pick_mapping_value(targets, "scenario_reasoning", "情境推論", "情境差異推論"),
            "資料不足",
        ),
    }
    for key, aliases in _PRICE_TARGET_ALIASES.items():
        price = _coerce_number(_pick_mapping_value(targets, *aliases), 0, None)
        normalized_targets[key] = price if price is not None else 0.0

    normalized = {
        **payload,
        "price_targets": normalized_targets,
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }
    if summary is not None:
        normalized["valuation_summary"] = summary
    if "dcf_scenarios" in payload:
        normalized["dcf_scenarios"] = _coerce_dcf_scenarios(payload.get("dcf_scenarios"))
    return normalized


def _coerce_downside_risk_rows(value: Any, minimum: int = 3, maximum: int = 5) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return [
            {
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            }
            for _ in range(minimum)
        ]
    risks = []
    fallbacks = []
    for item in safe_sequence_items(value):
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append({
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            })
            continue
        title = _display_line(row.get("title"))
        evidence = _display_line(row.get("evidence"))
        severity = _display_line(row.get("severity"), "warning")
        if severity not in {"warning", "high", "critical"}:
            severity = "warning"
        confidence = _coerce_number(row.get("confidence"), 0, 1)
        risk = {
            **row,
            "title": title or "下行風險",
            "evidence": evidence or "資料不足",
            "impact": _display_line(row.get("impact")),
            "severity": severity,
            "confidence": confidence if confidence is not None else 0.7,
        }
        if title and evidence:
            risks.append(risk)
        else:
            fallbacks.append(risk)
    while len(risks) < minimum and fallbacks:
        risks.append(fallbacks.pop(0))
    while len(risks) < minimum:
        risks.append({
            "title": "下行風險",
            "evidence": "資料不足",
            "impact": "",
            "severity": "warning",
            "confidence": 0.7,
        })
    return risks[:maximum]


def _coerce_bear_advocate_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value

    return {
        **payload,
        "thesis_summary": _display_text(payload.get("thesis_summary"), "資料不足"),
        "downside_risks": _coerce_downside_risk_rows(payload.get("downside_risks")),
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }


def _coerce_management_highlights(value: Any, required: int = 3) -> list[dict[str, str]]:
    if not isinstance(value, (list, tuple)):
        return [{"keyword": "亮點", "quote": "資料不足"} for _ in range(required)]
    highlights = []
    fallbacks = []
    for item in safe_sequence_items(value):
        row = safe_mapping_dict(item)
        if row is None:
            fallbacks.append({"keyword": "亮點", "quote": "資料不足"})
            continue
        keyword = _display_line(row.get("keyword"))
        quote = _display_line(row.get("quote"))
        highlight = {
            **row,
            "keyword": keyword or "亮點",
            "quote": quote or "資料不足",
        }
        if keyword and quote:
            highlights.append(highlight)
        else:
            fallbacks.append(highlight)
    while len(highlights) < required and fallbacks:
        highlights.append(fallbacks.pop(0))
    while len(highlights) < required:
        highlights.append({"keyword": "亮點", "quote": "資料不足"})
    return highlights[:required]


def _coerce_management_sentiment_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value

    guidance_tone = _display_line(payload.get("guidance_tone"), "資料不足")
    if guidance_tone not in _MANAGEMENT_GUIDANCE_TONES:
        guidance_tone = "資料不足"

    confidence = _coerce_number(payload.get("confidence"), 0, 1)

    return {
        **payload,
        "guidance_tone": guidance_tone,
        "confidence": confidence if confidence is not None else 0.0,
        "highlights": _coerce_management_highlights(payload.get("highlights")),
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }


def _coerce_trade_setup_payload(value: Any) -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value

    trade_direction = _display_line(payload.get("trade_direction"))
    risk_level = _display_line(payload.get("risk_level"))
    if trade_direction not in _TRADE_DIRECTIONS:
        trade_direction = "Neutral"
    if risk_level not in _TRADE_RISK_LEVELS:
        risk_level = "High"
    return {
        **payload,
        "trade_direction": trade_direction,
        "entry_zone": _display_line(payload.get("entry_zone"), "N/A"),
        "target_price": _display_line(payload.get("target_price"), "N/A"),
        "stop_loss": _display_line(payload.get("stop_loss"), "N/A"),
        "core_catalyst": _display_line(payload.get("core_catalyst"), "N/A"),
        "risk_level": risk_level,
    }


def _coerce_recommendation_payload(value: Any, default_label: str = "持有") -> Any:
    payload = safe_mapping_dict(value)
    if payload is None:
        return value
    recommendation = safe_mapping_dict(payload.get("recommendation"))
    if recommendation is None:
        return payload

    key_aliases = {
        "recommendation": "建議",
        "target_3m": "短期目標（3個月）",
        "target_6m": "中期目標（6個月）",
        "target_12m": "長期目標（12個月）",
        "long_term_potential_5y": "長期潛力（5年）",
        "confidence": "信心指數",
    }
    defaults = {
        "建議": default_label,
        "短期目標（3個月）": "N/A",
        "中期目標（6個月）": "N/A",
        "長期目標（12個月）": "N/A",
        "長期潛力（5年）": "N/A",
        "信心指數": "N/A",
    }
    normalized = {}
    for raw_key, raw_value in recommendation.items():
        key_text = _display_line(raw_key)
        key = key_aliases.get(key_text, key_text)
        if not key:
            continue
        if key == "建議":
            label = normalize_recommendation_label(raw_value)
            normalized[key] = label if label in {"買入", "持有", "避免", "放空"} else defaults[key]
        elif key in defaults:
            normalized[key] = _display_line(raw_value, defaults[key])
        else:
            normalized[key] = _display_text(raw_value)

    return {
        **payload,
        "recommendation": {**recommendation, **normalized},
        "analysis_markdown": _display_text(payload.get("analysis_markdown"), "資料不足"),
    }


def _coerce_text(value: Any) -> str:
    return safe_text(value).strip() if value is not None else ""


def _next_catalyst_field(value: Any, default: str) -> str:
    text = _display_line(value, default)
    return default if len(text) < 2 else text


def _next_catalyst_text(catalysts: Any) -> str:
    lines = []
    for item in safe_dict_list(catalysts):
        event_name = _next_catalyst_field(item.get("event_name"), "待確認催化事件")
        expected_timeframe = _next_catalyst_field(item.get("expected_timeframe"), "待後續資料確認")
        impact_direction = _display_line(item.get("impact_direction"), "volatile")
        if impact_direction not in {"bullish", "bearish", "volatile"}:
            impact_direction = "volatile"
        trigger_condition = _display_line(item.get("trigger_condition"), "待後續資料確認")
        if len(trigger_condition) < 5:
            trigger_condition = "待後續資料確認"
        lines.append(f"- **{event_name}**（{expected_timeframe}，{impact_direction}）：{trigger_condition}")
    if not lines:
        return ""
    return "\n\n### 下一步催化觀察\n" + "\n".join(lines)


def _valuation_reasoning_text(reasoning: Any) -> str:
    reasoning_map = safe_mapping_dict(reasoning) or {}
    rows = [
        ("DCF 推論", _pick_mapping_value(reasoning_map, "dcf_reasoning", "DCF推論", "DCF 推論")),
        ("同業推論", _pick_mapping_value(reasoning_map, "peer_reasoning", "同業推論", "同業比較推論")),
        ("情境推論", _pick_mapping_value(reasoning_map, "scenario_reasoning", "情境推論", "情境差異推論")),
    ]
    lines = [
        f"- {label}: {_display_line(value)}"
        for label, value in rows
        if _display_line(value)
    ]
    if not lines:
        return ""
    return "\n\n## 估值推論\n" + "\n".join(lines)


def _percent_text(value: Any) -> str:
    number = _coerce_number(value)
    return f"{number:g}%" if number is not None else "N/A"


def _dcf_scenarios_text(value: Any) -> str:
    scenario_labels = {
        "bear": "熊市",
        "base": "基本",
        "bull": "牛市",
    }
    lines = []
    for row in safe_dict_list(value):
        scenario_key = _display_line(row.get("scenario")).lower()
        label = scenario_labels.get(scenario_key)
        if not label:
            continue
        lines.append(
            f"- {label}："
            f"營收成長偏差 {_percent_text(row.get('revenue_growth_bias_pct'))}；"
            f"利潤率偏差 {_percent_text(row.get('margin_bias_pct'))}；"
            f"WACC {_percent_text(row.get('wacc_pct'))}；"
            f"內在價值 {_display_price_target(row.get('intrinsic_value'))}"
        )
    if not lines:
        return ""
    return "\n\n## DCF 情境假設\n" + "\n".join(lines)


def _reasoning_steps_text(value: Any, heading: str) -> str:
    lines = []
    for step in safe_text_list(value):
        text = _display_line(step)
        if len(text) >= 2:
            lines.append(f"- {text}")
    if not lines:
        return ""
    return f"\n\n{heading}\n" + "\n".join(lines)


def _moat_reasoning_steps_text(value: Any) -> str:
    return _reasoning_steps_text(value, "## 護城河推論步驟")


def _downside_risk_line(item: dict[str, Any]) -> str:
    title = _display_line(item.get("title"), "下行風險")
    if len(title) < 2:
        title = "下行風險"
    evidence = _display_line(item.get("evidence"), "資料不足")
    if len(evidence) < 2:
        evidence = "資料不足"
    severity = _display_line(item.get("severity"))
    if severity and severity not in {"warning", "high", "critical"}:
        severity = "warning"
    confidence = ""
    if item.get("confidence") is not None:
        confidence_number = _coerce_number(item.get("confidence"), 0, 1)
        if confidence_number is None:
            confidence_number = 0.7
        confidence = _display_line(confidence_number)
    impact = _display_line(item.get("impact"))
    if len(impact) < 2:
        impact = ""
    metadata = []
    if severity:
        metadata.append(f"嚴重度：{severity}")
    if confidence:
        metadata.append(f"信心：{confidence}")
    metadata_text = f"（{'；'.join(metadata)}）" if metadata else ""
    impact_separator = "" if evidence.endswith(("。", "！", "？", ".", "!", "?", "；", ";")) else "；"
    impact_text = f"{impact_separator}影響：{impact}" if impact else ""
    return f"- **{title}**{metadata_text}：{evidence}{impact_text}"


def _management_highlight_line(item: dict[str, Any]) -> str:
    keyword = _display_line(item.get("keyword"), "亮點")
    if len(keyword) < 2:
        keyword = "亮點"
    quote = _display_line(item.get("quote"), "資料不足")
    if len(quote) < 2:
        quote = "資料不足"
    return f"- **{keyword}**：{quote}"


def _trade_plan_field(value: Any, default: str = "N/A") -> str:
    text = _display_line(value, default)
    return default if len(text) < 2 else text


def _moat_score_line(key: Any, value: Any) -> str:
    label = _display_line(key, "護城河指標")
    if len(label) < 2:
        label = "護城河指標"
    return f"{label}: {_display_line(value, 'N/A')}"


def _valuation_summary_line(key: Any, value: Any) -> str:
    label = _display_line(key, "估值檢查項目")
    if len(label) < 2:
        label = "估值檢查項目"
    text = _display_line(value, "N/A")
    if len(text) < 2:
        text = "N/A"
    return f"- {label}: {text}"


def _plain_jsonish(value: Any) -> Any:
    mapping = safe_mapping_dict(value)
    if mapping is not None:
        return {key: _plain_jsonish(child) for key, child in mapping.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_jsonish(child) for child in safe_sequence_items(value)]
    return value


def normalize_structured_output(agent_num: int, payload: Any) -> Optional[dict]:
    """Validate and normalize JSON payloads from structured agents."""
    payload = _plain_jsonish(payload)
    raw_payload = payload if isinstance(payload, dict) else {}
    if isinstance(payload, dict):
        if "reasoning_steps" in payload:
            payload = {**payload, "reasoning_steps": _coerce_reasoning_steps(payload.get("reasoning_steps"), minimum=3)}
        if "scenario_triggers" in payload:
            payload = {**payload, "scenario_triggers": _coerce_scenario_triggers(payload.get("scenario_triggers"))}
        if "confidence_basis" in payload:
            payload = {**payload, "confidence_basis": _coerce_confidence_basis(payload.get("confidence_basis"))}
        if "next_catalysts" in payload:
            next_catalysts = _coerce_next_catalysts(payload.get("next_catalysts"))
            if not next_catalysts:
                scenario_triggers = payload.get("scenario_triggers")
                if not safe_dict_list(scenario_triggers):
                    scenario_triggers = _coerce_scenario_triggers([])
                    payload = {**payload, "scenario_triggers": scenario_triggers}
                next_catalysts = _derive_next_catalysts_from_scenario_triggers(scenario_triggers)
            payload = {**payload, "next_catalysts": next_catalysts}
        if agent_num in {3, 12}:
            payload = _coerce_moat_payload(payload)
        if agent_num in {4, 14}:
            payload = _coerce_price_target_payload(payload)
        if agent_num in {7, 16, 19}:
            payload = _coerce_recommendation_payload(payload, default_label="避免" if agent_num == 19 else "持有")
            payload = _normalize_recommendation_payload_aliases(payload)
        if agent_num == 20:
            payload = _coerce_management_sentiment_payload(payload)
        if agent_num == 21:
            payload = _coerce_bear_advocate_payload(payload)
        if agent_num == 24:
            payload = _coerce_trade_setup_payload(payload)
    payload = validated_structured_payload(agent_num, payload)
    if payload is None:
        return None

    if agent_num in {3, 12}:
        raw_scores = safe_mapping_dict(raw_payload.get("moat_scores")) or {}
        reasoning_steps = _coerce_reasoning_steps(payload.get("reasoning_steps"))
        scores = {}
        for key, aliases in _MOAT_SCORE_ALIASES.items():
            score = _coerce_number(_pick_mapping_value(raw_scores, *aliases), 1, 10)
            if score is not None:
                scores[key] = score
        if not scores:
            validated_scores = safe_mapping_dict(payload.get("moat_scores")) or {}
            for key, aliases in _MOAT_SCORE_ALIASES.items():
                score = _coerce_number(_pick_mapping_value(validated_scores, *aliases), 1, 10)
                if score is not None:
                    scores[key] = score
        if not scores:
            return None
        return {
            "reasoning_steps": reasoning_steps,
            "moat_scores": scores,
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num in {4, 14}:
        raw_targets = safe_mapping_dict(raw_payload.get("price_targets")) or {}
        validated_targets = safe_mapping_dict(payload.get("price_targets")) or {}
        valuation_reasoning = {
            "dcf_reasoning": _coerce_text(_pick_mapping_value(raw_targets, "dcf_reasoning", "DCF推論", "DCF 推論"))
            or _coerce_text(validated_targets.get("dcf_reasoning")),
            "peer_reasoning": _coerce_text(_pick_mapping_value(raw_targets, "peer_reasoning", "同業推論", "同業比較推論"))
            or _coerce_text(validated_targets.get("peer_reasoning")),
            "scenario_reasoning": _coerce_text(_pick_mapping_value(raw_targets, "scenario_reasoning", "情境推論", "情境差異推論"))
            or _coerce_text(validated_targets.get("scenario_reasoning")),
        }
        raw_root_reasoning = payload.get("valuation_reasoning")
        if isinstance(raw_root_reasoning, dict):
            for key in ("dcf_reasoning", "peer_reasoning", "scenario_reasoning"):
                if not valuation_reasoning.get(key):
                    valuation_reasoning[key] = _coerce_text(raw_root_reasoning.get(key))
        valuation_reasoning = {key: value for key, value in valuation_reasoning.items() if value}
        target_map = {
            "熊": "熊市情境",
            "bear": "熊市情境",
            "基本": "基本情境",
            "base": "基本情境",
            "Base": "基本情境",
            "牛": "牛市情境",
            "bull": "牛市情境",
        }
        targets = {}
        for raw_key, raw_value in raw_targets.items():
            key_text = _display_line(raw_key)
            if not key_text:
                continue
            canonical = None
            for marker, mapped in target_map.items():
                if marker in key_text:
                    canonical = mapped
                    break
            if not canonical:
                continue
            price = _coerce_number(raw_value, 0, None)
            if price is not None:
                targets[canonical] = price
        if not targets:
            for canonical, aliases in _PRICE_TARGET_ALIASES.items():
                price = _coerce_number(_pick_mapping_value(validated_targets, *aliases), 0, None)
                if price is not None:
                    targets[canonical] = price
        if not targets:
            return None
        return {
            "price_targets": targets,
            "valuation_reasoning": valuation_reasoning,
            "valuation_summary": payload.get("valuation_summary", {}) if isinstance(payload.get("valuation_summary"), dict) else {},
            "dcf_scenarios": payload.get("dcf_scenarios", []) if isinstance(payload.get("dcf_scenarios"), list) else [],
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 20:
        return {
            "guidance_tone": str(payload.get("guidance_tone") or "資料不足"),
            "confidence": _coerce_number(raw_payload.get("confidence"), 0, 1) or 0.0,
            "highlights": list(payload.get("highlights") or [])[:3],
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 21:
        return {
            "thesis_summary": str(payload.get("thesis_summary") or "").strip(),
            "downside_risks": _coerce_downside_risks(raw_payload.get("downside_risks"), payload.get("downside_risks")),
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    if agent_num == 24:
        analysis_markdown = _display_text(raw_payload.get("analysis_markdown")) or _display_text(payload.get("analysis_markdown"))
        return {
            "trade_direction": _coerce_text(payload.get("trade_direction")),
            "entry_zone": _coerce_text(payload.get("entry_zone")),
            "target_price": _coerce_text(payload.get("target_price")),
            "stop_loss": _coerce_text(payload.get("stop_loss")),
            "core_catalyst": _coerce_text(payload.get("core_catalyst")),
            "risk_level": _coerce_text(payload.get("risk_level")),
            "analysis_markdown": analysis_markdown,
        }

    if agent_num in {7, 16, 19}:
        raw_rec = payload.get("recommendation", {})
        reasoning_steps = _coerce_reasoning_steps(payload.get("reasoning_steps"))
        if not isinstance(raw_rec, dict) or not raw_rec:
            return None
        key_aliases = {
            "recommendation": "建議",
            "target_3m": "短期目標（3個月）",
            "target_6m": "中期目標（6個月）",
            "target_12m": "長期目標（12個月）",
            "long_term_potential_5y": "長期潛力（5年）",
            "confidence": "信心指數",
        }
        normalized_rec = {}
        for key, value in raw_rec.items():
            key_text = _display_line(key)
            normalized_key = key_aliases.get(key_text, key_text)
            normalized_value = (
                normalize_recommendation_label(value) if normalized_key == "建議" else _display_text(value)
            )
            normalized_rec[normalized_key] = normalized_value

        confidence_basis = payload.get("confidence_basis")
        if isinstance(confidence_basis, dict):
            normalized_rec["confidence_basis"] = confidence_basis

        return {
            "reasoning_steps": reasoning_steps,
            "recommendation": normalized_rec,
            "scenario_triggers": payload.get("scenario_triggers", []),
            "next_catalysts": payload.get("next_catalysts", []),
            "analysis_markdown": str(payload.get("analysis_markdown", "")).strip(),
        }

    return None


def _normalize_recommendation_payload_aliases(payload: dict) -> dict:
    recommendation = safe_mapping_dict(payload.get("recommendation"))
    if recommendation is None:
        return payload
    normalized = dict(recommendation)
    for key in ("建議", "recommendation"):
        if key in normalized:
            normalized[key] = normalize_recommendation_label(normalized[key])
    return {**payload, "recommendation": normalized}


def structured_output_to_report_text(agent_num: int, structured: dict, fallback_text: str = "") -> str:
    """Convert parsed JSON into the legacy report text expected by renderers."""
    structured = safe_mapping_dict(structured) or {}
    body = _report_body_text(structured.get("analysis_markdown"), fallback_text)

    if agent_num in {3, 12}:
        scores = safe_mapping_dict(structured.get("moat_scores")) or {}
        score_lines = "\n".join(
            _moat_score_line(key, value) for key, value in scores.items()
        )
        if not score_lines:
            score_lines = "護城河指標: N/A"
        reasoning_text = _moat_reasoning_steps_text(structured.get("reasoning_steps"))
        return f"[護城河評分]\n{score_lines}\n[/護城河評分]{reasoning_text}\n\n{body}".strip()

    if agent_num in {4, 14}:
        targets = safe_mapping_dict(structured.get("price_targets")) or {}
        order = ["熊市情境", "基本情境", "牛市情境"]
        price_lines = "\n".join(
            f"{key}: {_display_price_target(targets[key])}" for key in order if key in targets
        )
        if not price_lines:
            price_lines = "目標價: N/A"
        reasoning_text = _valuation_reasoning_text(structured.get("valuation_reasoning"))
        dcf_scenario_text = _dcf_scenarios_text(structured.get("dcf_scenarios"))
        summary = safe_mapping_dict(structured.get("valuation_summary")) or {}
        summary_text = ""
        if summary:
            summary_text = "\n\n## 結構化估值檢查\n" + "\n".join(
                _valuation_summary_line(key, value) for key, value in summary.items()
            )
        return f"[目標股價]\n{price_lines}\n[/目標股價]{reasoning_text}{dcf_scenario_text}\n\n{body}{summary_text}".strip()

    if agent_num == 20:
        tone = _display_line(structured.get("guidance_tone"), "資料不足")
        if tone not in _MANAGEMENT_GUIDANCE_TONES:
            tone = "資料不足"
        confidence = _coerce_number(structured.get("confidence"), 0, 1)
        confidence_text = f"信心分數：{confidence}\n" if confidence is not None else ""
        highlights = safe_dict_list(structured.get("highlights"))
        lines = [_management_highlight_line(item) for item in highlights]
        if not lines:
            lines = ["- **亮點**：資料不足"]
        body_text = "資料不足" if body and len(body) < 2 else body
        return f"## 管理層語氣：{tone}\n{confidence_text}" + "\n".join(lines) + f"\n\n{body_text}"

    if agent_num == 21:
        risks = safe_dict_list(structured.get("downside_risks"))
        lines = [_downside_risk_line(item) for item in risks]
        if not lines:
            lines = [_downside_risk_line({
                "title": "下行風險",
                "evidence": "資料不足",
                "severity": "warning",
                "confidence": 0.7,
            })]
        thesis_summary = _display_line(structured.get("thesis_summary"))
        if thesis_summary and len(thesis_summary) < 2:
            thesis_summary = "資料不足"
        summary_text = f"## 空方論點摘要\n{thesis_summary}\n\n" if thesis_summary else ""
        body_text = "資料不足" if body and len(body) < 2 else body
        return (
            summary_text
            + "## 最大下行風險 (Key Downside Risks) / 空頭觀點\n"
            + "\n".join(lines)
            + f"\n\n{body_text}"
        )

    if agent_num == 24:
        body_content = "資料不足" if body and len(body) < 2 else body
        body_text = f"\n\n{body_content}" if body_content else ""
        trade_direction = _display_line(structured.get("trade_direction"), "Neutral")
        if trade_direction not in _TRADE_DIRECTIONS:
            trade_direction = "Neutral"
        risk_level = _display_line(structured.get("risk_level"), "High")
        if risk_level not in _TRADE_RISK_LEVELS:
            risk_level = "High"
        return (
            "## 極短線交易計畫\n"
            f"- **交易方向：{trade_direction}**\n"
            f"- **進場區間：{_trade_plan_field(structured.get('entry_zone'))}**\n"
            f"- **1-2週目標價：{_trade_plan_field(structured.get('target_price'))}**\n"
            f"- **🛑 停損點：{_trade_plan_field(structured.get('stop_loss'))}**\n"
            f"- **核心催化劑：{_trade_plan_field(structured.get('core_catalyst'))}**\n"
            f"- **短期波動風險：{risk_level}**"
            f"{body_text}"
        )

    if agent_num in {7, 16, 19}:
        rec = safe_mapping_dict(structured.get("recommendation")) or {}

        basis = safe_mapping_dict(rec.get("confidence_basis")) or {}
        basis_text = ""
        if basis:
            basis_lines = []
            for ev in safe_text_list(basis.get("evidence_items")):
                line = _display_line(ev)
                if len(line) >= 2:
                    basis_lines.append(f"- **具體佐證**: {line}")
            for rsk in safe_text_list(basis.get("key_risks_acknowledged")):
                line = _display_line(rsk)
                if len(line) >= 2:
                    basis_lines.append(f"- **已納入考量的風險**: {line}")
            for gap in safe_text_list(basis.get("data_gaps")):
                line = _display_line(gap)
                if len(line) >= 2:
                    basis_lines.append(f"- **已知缺口**: {line}")
            if basis_lines:
                basis_text = "\n\n### 信心依據\n" + "\n".join(basis_lines) + "\n"

        triggers = safe_dict_list(structured.get("scenario_triggers"))
        trigger_text = ""
        if triggers:
            trigger_lines = []
            for t in triggers:
                condition = _display_line(t.get("trigger_condition"))
                if len(condition) < 2:
                    continue
                action = _display_line(t.get("action"), "重新檢查投資結論")
                if len(action) < 2:
                    action = "重新檢查投資結論"
                trigger_lines.append(f"- 若「{condition}」：建議 {action}")
            if trigger_lines:
                trigger_text = "\n\n### 情境觸發器\n" + "\n".join(trigger_lines) + "\n"

        catalyst_text = _next_catalyst_text(structured.get("next_catalysts"))
        reasoning_text = _reasoning_steps_text(structured.get("reasoning_steps"), "### 投資推論步驟")
        recommendation_block = format_recommendation_block(agent_num, rec)
        if agent_num == 19:
            body = ensure_agent19_required_sections(body, structured)
            return f"{body}{reasoning_text}{basis_text}{trigger_text}{catalyst_text}\n\n{recommendation_block}".strip()
        return f"{recommendation_block}{reasoning_text}\n\n{body}{basis_text}{trigger_text}{catalyst_text}".strip()

    return fallback_text


def price_targets_have_unit_error(targets: dict, current_price) -> bool:
    """Detect NT$5-style target prices when the stock trades in the hundreds/thousands."""
    if not isinstance(current_price, (int, float)) or current_price <= 100:
        return False
    prices = [value for value in targets.values() if isinstance(value, (int, float))]
    return bool(prices) and any(price < current_price * 0.05 for price in prices)


def warn_high_confidence_with_low_trust(agent_num: int, structured: dict, context: dict) -> None:
    if agent_num not in {7, 16, 19}:
        return
    trust = context.get("data", {}).get("data_trust", {}) if isinstance(context.get("data"), dict) else {}
    circuit_ever_opened = bool((context.get("circuit_breaker") or {}).get("_ever_opened", False))
    calibration = build_confidence_calibration(
        structured.get("recommendation", {}) or {},
        trust,
        circuit_ever_opened,
        has_unresolved_cross_source_conflict(context.get("data", {}) if isinstance(context.get("data"), dict) else {}),
    )
    context["confidence_calibration"] = calibration
    if calibration.get("status") != "needs_downgrade":
        return
    status = calibration.get("data_trust_status", "unknown")
    confidence = calibration.get("raw_confidence", "N/A")
    cap = calibration.get("max_recommended_confidence")
    context.setdefault("structured_quality_warnings", []).append(
        f"Agent {agent_num} 在 data_trust={status} 時給出高信心（{confidence}），建議信心上限 {cap}/10，需於報告中明確說明資料限制。"
    )


_confidence_score = confidence_score
_warn_high_confidence_with_low_trust = warn_high_confidence_with_low_trust
