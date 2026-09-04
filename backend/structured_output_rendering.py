"""Rendering helpers for structured agent report text."""

from __future__ import annotations

import re
import math
from numbers import Real

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text
from recommendation_labels import normalize_recommendation_label


def normalize_escaped_newlines(text: str) -> str:
    """Convert model-emitted literal newline escapes inside markdown bodies."""
    if "\\n" not in text:
        return text
    if "analysis_markdown" in text or "\\n##" in text or "\\n###" in text or re.search(r"^#{1,4}\s+.+\\n", text, re.MULTILINE):
        return text.replace("\\n", "\n")
    return text


def _coerce_text(value) -> str:
    if not isinstance(value, str):
        if isinstance(value, bool) or not isinstance(value, Real):
            return ""
        if not math.isfinite(float(value)):
            return ""
    return safe_text(value).strip()


def _display_line(value, default: str = "") -> str:
    text = _coerce_text(value)
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _display_value(value, default: str = "N/A") -> str:
    return _display_line(value, default)


def _execution_line(value) -> str:
    text = _display_line(value)
    if not text or text.upper() in {"N/A", "NA"} or "資料不足" in text:
        return ""
    return text


def _ordered_recommendation_value(value, default: str = "N/A") -> str:
    text = _display_value(value, default)
    if len(text) < 2 and not text.isdigit():
        return default
    return text


def _trigger_lines(triggers, directions: set[str], fallback_action: str = "") -> list[str]:
    lines = []
    for trigger in safe_dict_list(triggers):
        if _coerce_text(trigger.get("direction")) not in directions:
            continue
        condition = _display_line(trigger.get("trigger_condition"))
        action = _display_line(trigger.get("action"), fallback_action)
        if len(condition) < 2:
            continue
        if fallback_action and len(action) < 2:
            action = fallback_action
        lines.append(f"- {condition}：{action}" if action else f"- {condition}")
    return lines


def ensure_agent19_required_sections(body: str, structured: dict) -> str:
    body = normalize_escaped_newlines(body or "").strip()
    blocks = [body] if body else []
    structured = safe_mapping_dict(structured) or {}
    triggers = structured.get("scenario_triggers")
    short_setup = safe_mapping_dict(structured.get("short_setup")) or {}

    if "做空觸發條件（Catalyst for crash）" not in body:
        entry_trigger = _execution_line(short_setup.get("entry_trigger"))
        downside_target = _execution_line(short_setup.get("downside_target"))
        crash_lines = [f"- {entry_trigger}"] if entry_trigger else []
        if downside_target:
            crash_lines.append(f"- 下行目標：{downside_target}")
        if not crash_lines:
            crash_lines = _trigger_lines(triggers, {"bearish_downgrade"}, "重新檢查空方假設")
        if not crash_lines:
            crash_lines = ["- 模型未提供足夠可量化崩盤催化；應等待財測下修、毛利率壓縮、法人派發擴大或估值均值回歸等可驗證事件。"]
        blocks.append("## 做空觸發條件（Catalyst for crash）\n" + "\n".join(crash_lines))

    if "防軋空停損點（Stop-loss level）" not in body:
        cover_stop = _execution_line(short_setup.get("cover_stop"))
        squeeze_risk = _execution_line(short_setup.get("squeeze_risk"))
        invalidation = _execution_line(short_setup.get("thesis_invalidation"))
        stop_lines = [f"- {cover_stop}"] if cover_stop else []
        if squeeze_risk:
            stop_lines.append(f"- 軋空風險：{squeeze_risk}")
        if invalidation:
            stop_lines.append(f"- 論文失效：{invalidation}")
        if not stop_lines:
            stop_lines = _trigger_lines(triggers, {"neutral_review", "bullish_upgrade"}, "回補或暫停空方假設")
        if not stop_lines:
            stop_lines = ["- 模型未提供足夠可量化停損價位；若股價放量突破前高、基本面證據改善或估值重新獲得財務支撐，應回補或暫停空方假設。"]
        blocks.append("## 防軋空停損點（Stop-loss level）\n" + "\n".join(stop_lines))

    return "\n\n".join(block for block in blocks if block).strip()


def format_recommendation_block(agent_num: int, rec: dict) -> str:
    separator = "：" if agent_num == 19 else ": "
    rec = safe_mapping_dict(rec) or {}
    if "建議" in rec:
        rec["建議"] = normalize_recommendation_label(rec.get("建議"))
    if agent_num == 19:
        ordered_keys = [
            "建議",
            "短期目標（3個月）",
            "中期目標（6個月）",
            "長期目標（12個月）",
            "長期潛力（5年）",
            "信心指數",
        ]
        lines = [f"{key}{separator}{_ordered_recommendation_value(rec.get(key))}" for key in ordered_keys]
    else:
        display_rec = {
            _display_line(key): _display_value(value)
            for key, value in rec.items()
            if safe_mapping_dict(value) is None and len(_display_line(key)) >= 2
        }
        lines = [f"{key}{separator}{value}" for key, value in display_rec.items() if value]
        if not lines:
            lines = [f"建議{separator}N/A"]
    return "[投資建議]\n" + "\n".join(lines) + "\n[/投資建議]"
