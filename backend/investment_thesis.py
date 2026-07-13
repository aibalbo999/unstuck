"""Deterministic investment thesis discipline payloads."""

from __future__ import annotations

from typing import Any

from investment_thesis_assumptions import (
    contrarian_core_assumptions as _contrarian_core_assumptions,
    contrarian_red_lines as _contrarian_red_lines,
    core_assumptions as _core_assumptions,
    position_core_assumptions as _position_core_assumptions,
    position_red_lines as _position_red_lines,
    red_lines as _red_lines,
    trade_core_assumptions as _trade_core_assumptions,
    trade_red_lines as _trade_red_lines,
)
from investment_thesis_common import (
    analysis_section_excerpt as _analysis_section_excerpt,
    chip_line as _chip_line,
    confidence_number as _confidence_number,
    data_gaps as _data_gaps,
    downside_line as _downside_line,
    first_analysis_sentence as _first_analysis_sentence,
    first_analysis_sentence_for_agents as _first_analysis_sentence_for_agents,
    first_mapping_value as _first_mapping_value,
    has_na as _has_na,
    information_richness as _information_richness,
    moat_line as _moat_line,
    next_review_focus as _next_review_focus,
    trade_direction_label as _trade_direction_label,
    trade_health_score as _trade_health_score,
    trade_mirror_lines as _trade_mirror_lines,
    trade_setup_from_context as _trade_setup_from_context,
    trigger_from_structured as _trigger_from_structured,
    valuation_line as _valuation_line,
)
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list
from pipeline_modes import normalize_pipeline_id


_DISCIPLINE_PROFILES = {
    "v1": {
        "heading": "長線投資論文與決策紀律",
        "health_label": "論文健康度",
        "mirror_heading": "鏡子測試五句話",
        "assumptions_heading": "核心假設",
        "red_lines_heading": "紅線",
    },
    "v2": {
        "heading": "部位決策與風控紀律",
        "health_label": "部位計畫健康度",
        "mirror_heading": "部位檢查五句話",
        "assumptions_heading": "持倉假設",
        "red_lines_heading": "風控紅線",
    },
    "v3": {
        "heading": "逆勢論文與風控紀律",
        "health_label": "逆勢論文健康度",
        "mirror_heading": "空方檢查五句話",
        "assumptions_heading": "逆勢假設",
        "red_lines_heading": "防軋空紅線",
    },
    "v4": {
        "heading": "交易計畫與風控紀律",
        "health_label": "交易計畫健康度",
        "mirror_heading": "交易檢查五句話",
        "assumptions_heading": "交易假設",
        "red_lines_heading": "停損紅線",
    },
}


def _discipline_profile(pipeline_id: Any) -> dict[str, str]:
    return _DISCIPLINE_PROFILES.get(normalize_pipeline_id(pipeline_id), _DISCIPLINE_PROFILES["v1"])


def build_investment_thesis(context: dict[str, Any]) -> dict[str, Any]:
    """Build a decision-discipline payload from an analysis context."""
    data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
    parsed = context.get("parsed", {}) if isinstance(context.get("parsed"), dict) else {}
    recommendation = parsed.get("recommendation", {}) if isinstance(parsed.get("recommendation"), dict) else {}
    price_targets = parsed.get("price_targets", {}) if isinstance(parsed.get("price_targets"), dict) else {}
    moat_scores = parsed.get("moat_scores", {}) if isinstance(parsed.get("moat_scores"), dict) else {}
    audit = context.get("final_audit", {}) if isinstance(context.get("final_audit"), dict) else {}
    pipeline_id = normalize_pipeline_id(context.get("pipeline_id", "v1"))
    profile = _discipline_profile(pipeline_id)

    ticker = _display_text(context.get("ticker"), "") or _display_text(data.get("ticker"), "")
    company_name = (
        _display_text(context.get("company_name"), "")
        or _display_text(data.get("company_name"), "")
        or ticker
        or "本標的"
    )
    rec_text = _first_mapping_value(recommendation, "建議") or "持有"
    target_12m = _first_mapping_value(recommendation, "12個月") or _display_text(price_targets.get("基本情境"), "")
    target_12m = target_12m or "N/A"
    confidence_text = _first_mapping_value(recommendation, "信心") or "5/10"
    confidence = _confidence_number(confidence_text)
    richness = _information_richness(data)
    data_gaps = _data_gaps(data, audit, richness)
    health_score = min(confidence, {"A": 10, "B": 7, "C": 5}.get(richness["grade"], 5))

    business_line = _first_analysis_sentence(context) or f"{company_name} 的商業模式仍需由本次報告各章節交叉確認"
    moat_line = _moat_line(moat_scores)
    valuation_line = _valuation_line(data, price_targets, target_12m)
    downside_line = _downside_line(audit, data_gaps)

    if pipeline_id == "v4":
        trade_setup = _trade_setup_from_context(context, parsed)
        rec_text = _trade_direction_label(trade_setup.get("trade_direction"))
        target_12m = trade_setup.get("target_price") or "N/A"
        confidence_text = trade_setup.get("risk_level") or "High"
        confidence = _trade_health_score(trade_setup, richness)
        health_score = confidence
        mirror_lines = _trade_mirror_lines(data, company_name, trade_setup)
        core_assumptions = _trade_core_assumptions(trade_setup)
        red_lines = _trade_red_lines(trade_setup)
        valuation_anchor = {
            "current_price": _current_price_text(data),
            "target_12m": "N/A",
            "bear_case": "N/A",
            "base_case": _display_text(trade_setup.get("target_price")),
            "bull_case": _display_text(trade_setup.get("target_price")),
        }
        next_review = {
            "trigger": "下一個交易日收盤或催化事件前後",
            "focus": "確認價格是否仍在進場區間、停損是否觸發、催化是否仍有效",
        }
    elif pipeline_id == "v3":
        crash_trigger = _analysis_section_excerpt(context, "做空觸發條件") or _trigger_from_structured(context, {"bearish_downgrade"})
        stop_condition = _analysis_section_excerpt(context, "防軋空停損點") or _trigger_from_structured(context, {"neutral_review", "bullish_upgrade"})
        mirror_lines = [
            f"我以 {_current_price_text(data)} 評估 {company_name}，逆勢結論為 {rec_text}。",
            f"泡沫假設：{_first_analysis_sentence_for_agents(context, (17,)) or business_line}",
            f"硬證據：{_first_analysis_sentence_for_agents(context, (18,)) or downside_line}",
            f"做空觸發：{crash_trigger or '尚需等待可驗證催化，不能只因估值高就追空'}",
            f"防軋空/失效條件：{stop_condition or '若基本面改善或股價突破風控位，需回補或暫停空方假設'}",
        ]
        core_assumptions = _contrarian_core_assumptions(crash_trigger, stop_condition)
        red_lines = _contrarian_red_lines()
        valuation_anchor = {
            "current_price": _current_price_text(data),
            "target_12m": target_12m,
            "bear_case": _first_mapping_value(recommendation, "3個月") or "N/A",
            "base_case": _first_mapping_value(recommendation, "6個月") or "N/A",
            "bull_case": _first_mapping_value(recommendation, "12個月") or "N/A",
        }
        next_review = {
            "trigger": "下一次財報、法說會、籌碼轉折或做空觸發前後",
            "focus": _next_review_focus(data_gaps, rec_text),
        }
    elif pipeline_id == "v2":
        mirror_lines = [
            f"我以 {_current_price_text(data)} 評估 {company_name}，部位判斷為 {rec_text}。",
            f"交易脈絡：{business_line}",
            f"籌碼與情緒：{_chip_line(data)}",
            f"風險報酬：12 個月參考目標 {target_12m}，{valuation_line}",
            f"若判斷錯誤，優先檢查：{downside_line}",
        ]
        core_assumptions = _position_core_assumptions(data, price_targets, recommendation)
        red_lines = _position_red_lines(data, rec_text)
        valuation_anchor = {
            "current_price": _current_price_text(data),
            "target_12m": target_12m,
            "bear_case": _display_text(price_targets.get("熊市情境")),
            "base_case": _display_text(price_targets.get("基本情境")),
            "bull_case": _display_text(price_targets.get("牛市情境")),
        }
        next_review = {
            "trigger": "下一次收盤、籌碼轉折、重大新聞或估值區間失效時",
            "focus": _next_review_focus(data_gaps, rec_text),
        }
    else:
        mirror_lines = [
            f"我以 {_current_price_text(data)} 評估 {company_name}，目前結論為 {rec_text}。",
            f"這門生意的本質是：{business_line}",
            f"護城河判斷：{moat_line}",
            f"估值錨點：12 個月參考目標 {target_12m}，{valuation_line}",
            f"即使判斷錯誤，下行風險主要來自：{downside_line}",
        ]
        core_assumptions = _core_assumptions(data, moat_scores, price_targets, recommendation)
        red_lines = _red_lines(data, rec_text)
        valuation_anchor = {
            "current_price": _current_price_text(data),
            "target_12m": target_12m,
            "bear_case": _display_text(price_targets.get("熊市情境")),
            "base_case": _display_text(price_targets.get("基本情境")),
            "bull_case": _display_text(price_targets.get("牛市情境")),
        }
        next_review = {
            "trigger": "下一次季報或重大法說會後",
            "focus": _next_review_focus(data_gaps, rec_text),
        }

    mirror_status = "pass" if richness["grade"] != "C" and not _has_na(mirror_lines) else "gray_zone"
    if "避免" in rec_text or "放空" in rec_text:
        mirror_status = "pass"

    return {
        "schema_version": 1,
        "ticker": ticker,
        "company_name": company_name,
        "pipeline_id": pipeline_id,
        "discipline_heading": profile["heading"],
        "health_label": profile["health_label"],
        "mirror_heading": profile["mirror_heading"],
        "assumptions_heading": profile["assumptions_heading"],
        "red_lines_heading": profile["red_lines_heading"],
        "recommendation": rec_text,
        "confidence": confidence_text,
        "health_score": int(max(1, health_score)),
        "information_richness": richness,
        "mirror_test": {
            "status": mirror_status,
            "lines": mirror_lines,
        },
        "core_assumptions": core_assumptions,
        "red_lines": red_lines,
        "valuation_anchor": valuation_anchor,
        "data_gaps": data_gaps,
        "next_review": next_review,
    }


def _display_text(value: Any, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    if not text:
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _current_price_text(data: dict[str, Any]) -> str:
    text = _display_text(data.get("current_price_fmt"), "")
    if text:
        return text
    return _display_text(data.get("current_price"))


def investment_thesis_markdown(thesis: dict[str, Any]) -> str:
    """Render the thesis payload as a compact Markdown section."""
    thesis_payload = safe_mapping_dict(thesis) or {}
    if not thesis_payload:
        return ""
    profile = _discipline_profile(thesis_payload.get("pipeline_id", "v1"))
    heading = _display_text(thesis_payload.get("discipline_heading"), profile["heading"])
    health_label = _display_text(thesis_payload.get("health_label"), profile["health_label"])
    health_score = _display_text(thesis_payload.get("health_score"))
    mirror_heading = _display_text(thesis_payload.get("mirror_heading"), profile["mirror_heading"])
    assumptions_heading = _display_text(thesis_payload.get("assumptions_heading"), profile["assumptions_heading"])
    red_lines_heading = _display_text(thesis_payload.get("red_lines_heading"), profile["red_lines_heading"])
    lines = [f"## {heading}"]
    info = safe_mapping_dict(thesis_payload.get("information_richness")) or {}
    mirror = safe_mapping_dict(thesis_payload.get("mirror_test")) or {}
    lines.append(f"- **{health_label}:** {health_score}/10")
    lines.append(f"- **資訊豐富度:** {_display_text(info.get('grade'))}（{_display_text(info.get('summary'))}）")
    lines.append(f"- **鏡子測試:** {_display_text(mirror.get('status'))}")
    lines.append("")
    lines.append(f"### {mirror_heading}")
    for item in safe_text_list(mirror.get("lines")):
        lines.append(f"- {_display_text(item)}")
    lines.append("")
    lines.append(f"### {assumptions_heading}")
    for item in safe_dict_list(thesis_payload.get("core_assumptions")):
        assumption = _display_text(item.get("assumption"))
        validation = _display_text(item.get("validation"))
        frequency = _display_text(item.get("frequency"))
        lines.append(f"- **{assumption}**：{validation}（{frequency}）")
    lines.append("")
    lines.append(f"### {red_lines_heading}")
    for item in safe_dict_list(thesis_payload.get("red_lines")):
        severity = _display_text(item.get("severity"))
        condition = _display_text(item.get("condition"))
        action = _display_text(item.get("action"))
        lines.append(f"- **{severity}**：{condition} -> {action}")
    gaps = safe_text_list(thesis_payload.get("data_gaps"))
    if gaps:
        lines.append("")
        lines.append("### 資料缺口")
        for gap in gaps[:5]:
            lines.append(f"- {_display_text(gap)}")
    next_review = safe_mapping_dict(thesis_payload.get("next_review")) or {}
    lines.append("")
    lines.append(
        f"**下次檢查:** {_display_text(next_review.get('trigger'))}；"
        f"重點：{_display_text(next_review.get('focus'))}"
    )
    return "\n".join(lines).strip()
