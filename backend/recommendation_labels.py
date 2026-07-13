"""Canonical investment recommendation labels and aliases."""

from __future__ import annotations

from mapping_fields import safe_text


CANONICAL_RECOMMENDATIONS = ("買入", "持有", "避免", "放空")
UNKNOWN_RECOMMENDATION = "N/A"


def normalize_recommendation_label(value: object) -> str:
    """Collapse recommendation aliases into the product-wide label set."""
    text = safe_text(value).strip()
    if not text:
        return UNKNOWN_RECOMMENDATION
    lower = text.lower()

    if any(token in text for token in ("強烈放空", "放空", "做空", "空方")) or lower in {"short", "strong short"}:
        return "放空"
    if any(token in text for token in ("買入", "買進", "強烈買入", "加碼", "增持")) or lower in {"buy", "strong buy"}:
        return "買入"
    if any(token in text for token in ("避免", "賣出", "減碼", "避險觀察")) or lower in {"avoid", "sell", "reduce"}:
        return "避免"
    if any(token in text for token in ("持有", "觀望", "中立", "中性", "偏多觀察")) or lower in {"hold", "neutral"}:
        return "持有"
    return text


def recommendation_tone(value: object) -> str:
    label = normalize_recommendation_label(value)
    if label == "買入":
        return "is-buy"
    if label == "放空":
        return "is-short"
    if label == "避免":
        return "is-avoid"
    return "is-hold"
