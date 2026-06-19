"""Rendering helpers for structured agent report text."""

from __future__ import annotations

import re


def normalize_escaped_newlines(text: str) -> str:
    """Convert model-emitted literal newline escapes inside markdown bodies."""
    if "\\n" not in text:
        return text
    if "analysis_markdown" in text or "\\n##" in text or "\\n###" in text or re.search(r"^#{1,4}\s+.+\\n", text, re.MULTILINE):
        return text.replace("\\n", "\n")
    return text


def _coerce_text(value) -> str:
    return str(value).strip() if value is not None else ""


def _trigger_lines(triggers: list, directions: set[str]) -> list[str]:
    lines = []
    for trigger in triggers or []:
        if not isinstance(trigger, dict):
            continue
        if trigger.get("direction") not in directions:
            continue
        condition = _coerce_text(trigger.get("trigger_condition"))
        action = _coerce_text(trigger.get("action"))
        if not condition:
            continue
        lines.append(f"- {condition}：{action}" if action else f"- {condition}")
    return lines


def ensure_agent19_required_sections(body: str, structured: dict) -> str:
    body = normalize_escaped_newlines(body or "").strip()
    blocks = [body] if body else []
    triggers = structured.get("scenario_triggers", []) or []

    if "做空觸發條件（Catalyst for crash）" not in body:
        crash_lines = _trigger_lines(triggers, {"bearish_downgrade"})
        if not crash_lines:
            crash_lines = ["- 模型未提供足夠可量化崩盤催化；應等待財測下修、毛利率壓縮、法人派發擴大或估值均值回歸等可驗證事件。"]
        blocks.append("## 做空觸發條件（Catalyst for crash）\n" + "\n".join(crash_lines))

    if "防軋空停損點（Stop-loss level）" not in body:
        stop_lines = _trigger_lines(triggers, {"neutral_review", "bullish_upgrade"})
        if not stop_lines:
            stop_lines = ["- 模型未提供足夠可量化停損價位；若股價放量突破前高、基本面證據改善或估值重新獲得財務支撐，應回補或暫停空方假設。"]
        blocks.append("## 防軋空停損點（Stop-loss level）\n" + "\n".join(stop_lines))

    return "\n\n".join(block for block in blocks if block).strip()


def format_recommendation_block(agent_num: int, rec: dict) -> str:
    separator = "：" if agent_num == 19 else ": "
    if agent_num == 19:
        ordered_keys = [
            "建議",
            "短期目標（3個月）",
            "中期目標（6個月）",
            "長期目標（12個月）",
            "長期潛力（5年）",
            "信心指數",
        ]
        lines = [f"{key}{separator}{rec.get(key, 'N/A')}" for key in ordered_keys]
    else:
        display_rec = {k: v for k, v in rec.items() if not isinstance(v, dict)}
        lines = [f"{key}{separator}{value}" for key, value in display_rec.items()]
    return "[投資建議]\n" + "\n".join(lines) + "\n[/投資建議]"
