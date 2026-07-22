"""Convert normalized structured output to legacy report text."""

from __future__ import annotations

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items
from structured_output_normalizer_basic import (
    _legacy_body_text,
    _MANAGEMENT_GUIDANCE_TONES,
    _TRADE_DIRECTIONS,
    _TRADE_RISK_LEVELS,
)
from structured_output_normalizer_text import (
    _coerce_number,
    _dcf_scenarios_text,
    _display_line,
    _display_price_target,
    _downside_risk_line,
    _management_highlight_line,
    _moat_reasoning_steps_text,
    _moat_score_line,
    _next_catalyst_text,
    _reasoning_steps_text,
    _report_body_text,
    _trade_plan_field,
    _valuation_reasoning_text,
    _valuation_summary_line,
)
from structured_output_rendering import ensure_agent19_required_sections, format_recommendation_block


def structured_output_to_report_text(agent_num: int, structured: dict, fallback_text: str = "") -> str:
    """Convert parsed JSON into the legacy report text expected by renderers."""
    structured = safe_mapping_dict(structured) or {}
    body = _report_body_text(structured.get("analysis_markdown"), fallback_text)

    if agent_num in {3, 12}:
        body = _legacy_body_text(body)
        scores = safe_mapping_dict(structured.get("moat_scores")) or {}
        score_lines = "\n".join(
            _moat_score_line(key, value) for key, value in scores.items()
        )
        if not score_lines:
            score_lines = "護城河指標: N/A"
        reasoning_text = _moat_reasoning_steps_text(structured.get("reasoning_steps"))
        return f"[護城河評分]\n{score_lines}\n[/護城河評分]{reasoning_text}\n\n{body}".strip()

    if agent_num in {4, 14}:
        body = _legacy_body_text(body)
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
        body = _legacy_body_text(body)
        rec = safe_mapping_dict(structured.get("recommendation")) or {}

        basis = safe_mapping_dict(rec.get("confidence_basis")) or {}
        basis_text = ""
        if basis:
            basis_lines = []
            for ev in safe_sequence_items(basis.get("evidence_items")):
                line = _display_line(ev)
                if len(line) >= 2:
                    basis_lines.append(f"- **具體佐證**: {line}")
            for rsk in safe_sequence_items(basis.get("key_risks_acknowledged")):
                line = _display_line(rsk)
                if len(line) >= 2:
                    basis_lines.append(f"- **已納入考量的風險**: {line}")
            for gap in safe_sequence_items(basis.get("data_gaps")):
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
