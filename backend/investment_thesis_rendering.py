"""Markdown rendering helpers for investment thesis discipline payloads."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list
from pipeline_modes import normalize_pipeline_id
from reporting.text_tokens import is_missing_text_token


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


def discipline_profile(pipeline_id: Any) -> dict[str, str]:
    return _DISCIPLINE_PROFILES.get(normalize_pipeline_id(pipeline_id), _DISCIPLINE_PROFILES["v1"])


def display_text(value: Any, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def investment_thesis_markdown(thesis: dict[str, Any]) -> str:
    """Render the thesis payload as a compact Markdown section."""
    thesis_payload = safe_mapping_dict(thesis) or {}
    if not thesis_payload:
        return ""
    profile = discipline_profile(thesis_payload.get("pipeline_id", "v1"))
    heading = display_text(thesis_payload.get("discipline_heading"), profile["heading"])
    health_label = display_text(thesis_payload.get("health_label"), profile["health_label"])
    health_score = display_text(thesis_payload.get("health_score"))
    mirror_heading = display_text(thesis_payload.get("mirror_heading"), profile["mirror_heading"])
    assumptions_heading = display_text(thesis_payload.get("assumptions_heading"), profile["assumptions_heading"])
    red_lines_heading = display_text(thesis_payload.get("red_lines_heading"), profile["red_lines_heading"])
    lines = [f"## {heading}"]
    info = safe_mapping_dict(thesis_payload.get("information_richness")) or {}
    mirror = safe_mapping_dict(thesis_payload.get("mirror_test")) or {}
    lines.append(f"- **{health_label}:** {health_score}/10")
    lines.append(f"- **資訊豐富度:** {display_text(info.get('grade'))}（{display_text(info.get('summary'))}）")
    lines.append(f"- **鏡子測試:** {display_text(mirror.get('status'))}")
    lines.append("")
    lines.append(f"### {mirror_heading}")
    for item in safe_text_list(mirror.get("lines")):
        lines.append(f"- {display_text(item)}")
    lines.append("")
    lines.append(f"### {assumptions_heading}")
    for item in safe_dict_list(thesis_payload.get("core_assumptions")):
        assumption = display_text(item.get("assumption"))
        validation = display_text(item.get("validation"))
        frequency = display_text(item.get("frequency"))
        lines.append(f"- **{assumption}**：{validation}（{frequency}）")
    lines.append("")
    lines.append(f"### {red_lines_heading}")
    for item in safe_dict_list(thesis_payload.get("red_lines")):
        severity = display_text(item.get("severity"))
        condition = display_text(item.get("condition"))
        action = display_text(item.get("action"))
        lines.append(f"- **{severity}**：{condition} -> {action}")
    gaps = safe_text_list(thesis_payload.get("data_gaps"))
    if gaps:
        lines.append("")
        lines.append("### 資料缺口")
        for gap in gaps[:5]:
            lines.append(f"- {display_text(gap)}")
    next_review = safe_mapping_dict(thesis_payload.get("next_review")) or {}
    lines.append("")
    lines.append(
        f"**下次檢查:** {display_text(next_review.get('trigger'))}；"
        f"重點：{display_text(next_review.get('focus'))}"
    )
    return "\n".join(lines).strip()
