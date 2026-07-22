"""Text rendering helpers for structured output normalization."""

from __future__ import annotations

import math
from numbers import Real
from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text
from structured_output_normalizer_basic import (
    _analysis_markdown_text,
    _coerce_number,
    _display_line,
    _display_price_target,
    _display_text,
    _pick_mapping_value,
    _report_body_text,
    _string_field_line,
    _string_field_text,
)


def _coerce_text(value: Any) -> str:
    if not isinstance(value, str):
        if isinstance(value, bool) or not isinstance(value, Real):
            return ""
        if not math.isfinite(float(value)):
            return ""
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
    lines = []
    for label, value in rows:
        text = _display_line(value)
        if len(text) >= 2:
            lines.append(f"- {label}: {text}")
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
    if not isinstance(value, (list, tuple)):
        return ""
    lines = []
    for step in safe_sequence_items(value):
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
    score = _display_line(value, "N/A")
    if len(score) < 2 and not score.isdigit():
        score = "N/A"
    return f"{label}: {score}"


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
