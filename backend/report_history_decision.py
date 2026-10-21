"""Mode-specific history categories, derived from the decision the card displays.

Keys are scoped to a mode: a short-term Short is not a long-term short rating,
and a position plan's wait is not an instruction to hold an existing position.
"""
from __future__ import annotations

_RATINGS = ("買入", "持有", "觀望", "避免", "放空")
_FILTERS = {
    "v1": ("研究評級", tuple((value, value) for value in _RATINGS)),
    "v2": ("部位動作", tuple((value, value) for value in ("進場", "續抱", "減碼", "等待"))),
    "v3": ("空方判斷", tuple((value, value) for value in _RATINGS)),
    "v4": ("交易方向", (("Long", "偏多 Long"), ("Short", "偏空 Short"), ("Neutral", "觀望 Neutral"))),
}


def history_filter_catalog() -> dict:
    return {mode: {
        "label": label,
        "options": [{"value": f"{mode}:{value}", "label": text} for value, text in options]
                   + [{"value": f"{mode}:unknown", "label": "尚未確認／未提供"}],
    } for mode, (label, options) in _FILTERS.items()}


HISTORY_FILTER_KEYS = frozenset(option["value"] for group in history_filter_catalog().values()
                                for option in group["options"])


def is_history_decision_filter(value: str) -> bool:
    return value in HISTORY_FILTER_KEYS or value in {"unknown", "觀望"}


def history_decision_from_preview(mode: str, preview: dict) -> dict:
    primary = preview.get("primary") if isinstance(preview.get("primary"), dict) else {}
    text = str(primary.get("value") or "").strip()
    value = "unknown"
    expected_kind = {"v1": "investment", "v2": "position_plan", "v3": "bubble_sniper", "v4": "swing_trade"}
    if preview.get("kind") == expected_kind.get(mode) and not primary.get("missing_category"):
        allowed = dict(_FILTERS.get(mode, ("", ()))[1])
        if mode == "v4":
            value = {"偏多 Long": "Long", "偏空 Short": "Short",
                     "觀望（暫不建立新交易）": "Neutral"}.get(text, "unknown")
        elif text in allowed:
            value = text
    # Publication/diagnostic notices replace the primary label and cannot be
    # mistaken for the original report's actionable decision.
    if primary.get("label") == "用途":
        value = "unknown"
    return {"schema_version": "report-history-decision.v1", "key": f"{mode}:{value}",
            "value": value, "label": _FILTERS.get(mode, ("報告判斷", ()))[0],
            "display_value": text}


def matches_history_decision(decision: dict, selected: str) -> bool:
    if selected == "unknown":
        return decision["value"] == "unknown"
    if selected == "觀望":
        return decision["value"] == "觀望"
    return decision["key"] == selected
