"""Shared decision context helpers for generated reports."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict, safe_text
from recommendation_labels import normalize_recommendation_label

from .html_context import display_text
from .html_sanitizer import sanitize_report_plain_text
from .utils import get_recommendation_color, get_recommendation_icon


_TRADE_SETUP_KEYS = (
    "trade_direction",
    "entry_zone",
    "target_price",
    "stop_loss",
    "core_catalyst",
    "risk_level",
)
_TRADE_DIRECTION_LABELS = {
    "Long": "偏多 Long",
    "Short": "偏空 Short",
    "Neutral": "中性 Neutral",
}
_TRADE_DIRECTION_ICONS = {"Long": "↑", "Short": "↓", "Neutral": "→"}
_TRADE_DIRECTION_COLORS = {"Long": "#16a34a", "Short": "#dc2626", "Neutral": "#d97706"}
_RISK_LEVEL_LABELS = {"High": "高", "Medium": "中", "Low": "低"}


def _recommendation_value(recommendation: dict[str, Any], target_sub: str, default: str = "N/A") -> Any:
    for key, value in recommendation.items():
        if target_sub in safe_text(key):
            return value
    return default


def _clean_display_value(value: Any, default: str = "N/A") -> str:
    text = sanitize_report_plain_text(display_text(value, default))
    return text or default


def _clean_optional_text(value: Any) -> str:
    return sanitize_report_plain_text(display_text(value, ""))


def _build_trade_setup(parsed: dict[str, Any]) -> dict[str, str]:
    raw_trade_setup = safe_mapping_dict(parsed.get("trade_setup", {})) or {}
    trade_setup = {
        key: _clean_optional_text(raw_trade_setup.get(key, ""))
        for key in _TRADE_SETUP_KEYS
    }
    return {key: value for key, value in trade_setup.items() if value}


def build_decision_context(parsed: dict[str, Any], *, pipeline_id: str) -> dict[str, Any]:
    """Build sanitized recommendation and trade context shared by report renderers."""
    parsed_map = safe_mapping_dict(parsed) or {}
    recommendation = safe_mapping_dict(parsed_map.get("recommendation", {})) or {}
    rec_text = normalize_recommendation_label(
        _clean_display_value(_recommendation_value(recommendation, "建議", "持有"), "持有")
    )
    rec_color = get_recommendation_color(rec_text)
    rec_icon = get_recommendation_icon(rec_text)
    trade_setup = _build_trade_setup(parsed_map)
    trade_direction = trade_setup.get("trade_direction", "Neutral")

    if pipeline_id == "v4" and trade_setup:
        rec_color = _TRADE_DIRECTION_COLORS.get(trade_direction, "#d97706")

    return {
        "recommendation": recommendation,
        "rec_text": rec_text,
        "rec_color": rec_color,
        "rec_icon": rec_icon,
        "target_3m": _clean_display_value(_recommendation_value(recommendation, "3個月", "N/A")),
        "target_6m": _clean_display_value(_recommendation_value(recommendation, "6個月", "N/A")),
        "target_12m": _clean_display_value(_recommendation_value(recommendation, "12個月", "N/A")),
        "confidence": _clean_display_value(_recommendation_value(recommendation, "信心", "N/A")),
        "trade_setup": trade_setup,
        "trade_direction": trade_direction,
        "trade_direction_label": _TRADE_DIRECTION_LABELS.get(trade_direction, "中性 Neutral"),
        "trade_direction_icon": _TRADE_DIRECTION_ICONS.get(trade_direction, "→"),
        "swing_entry_zone": trade_setup.get("entry_zone", "N/A"),
        "swing_target_price": trade_setup.get("target_price", "N/A"),
        "swing_stop_loss": trade_setup.get("stop_loss", "N/A"),
        "swing_risk_level": _RISK_LEVEL_LABELS.get(trade_setup.get("risk_level", "High"), "高"),
    }


__all__ = ["build_decision_context"]
