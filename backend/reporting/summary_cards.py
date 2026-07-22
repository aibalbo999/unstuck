"""Summary-card HTML helpers for report overview sections."""

from __future__ import annotations

import math
from html import escape

from mapping_fields import safe_mapping_dict, safe_text
from numeric_safety import is_non_finite_number

from .chart_payload import chart_number
from .html_context import display_text, price_target_number
from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def build_metric_cards_html(data: dict) -> str:
    data = safe_mapping_dict(data) or {}
    rows = [
        ("股價", data.get("current_price_fmt", "N/A")),
        ("市值", data.get("market_cap_fmt", "N/A")),
        ("P/E", data.get("pe_ratio", "N/A")),
        ("P/B", data.get("pb_ratio", "N/A")),
        ("毛利率", data.get("gross_margin", "N/A")),
        ("ROE", data.get("roe", "N/A")),
        ("殖利率", data.get("dividend_yield", "N/A")),
        ("Beta", data.get("beta", "N/A")),
    ]
    cards = []
    for label, value in rows:
        cards.append(
            f"""
            <div class="metric-card">
                <div class="metric-label">{escape(label)}</div>
                <div class="metric-value">{escape(_plain_display(value))}</div>
            </div>"""
        )
    return "".join(cards)


def build_price_target_cards_html(price_targets: dict, current_price) -> str:
    targets = safe_mapping_dict(price_targets) or {}
    current = chart_number(current_price) or 0
    cards = []
    seen_scenarios = set()
    for scenario, price in targets.items():
        scenario_text = _scenario_label(scenario)
        scenario_text = _unique_display_label(seen_scenarios, scenario_text)
        color, icon = _scenario_style(scenario_text)
        price_num = price_target_number(price)
        pct_str = _target_delta_text(price_num, current)
        price_display = f"NT${price_num:.0f}" if price_num is not None else "N/A"
        cards.append(
            f"""
            <div class="price-target-card" style="border-color: {color};">
                <div class="pt-scenario">{escape(scenario_text)}</div>
                <div class="pt-price" style="color: {color};">{icon} {price_display}</div>
                <div class="pt-pct" style="color: {color};">{escape(pct_str)}</div>
            </div>"""
        )
    return "".join(cards)


def _plain_display(value) -> str:
    if is_non_finite_number(value):
        return "N/A"
    return sanitize_report_plain_text(display_text(value))


def _scenario_label(value) -> str:
    text = sanitize_report_plain_text(safe_text(value)).strip()
    if not text or is_missing_text_token(text):
        return "情境"
    return text


def _scenario_style(scenario: str) -> tuple[str, str]:
    if "熊" in scenario:
        return "#ef4444", "↓"
    if "牛" in scenario:
        return "#10b981", "↑"
    return "#3b82f6", "→"


def _unique_display_label(seen: set[str], label: str) -> str:
    candidate = label
    suffix = 2
    while candidate in seen:
        candidate = f"{label} {suffix}"
        suffix += 1
    seen.add(candidate)
    return candidate


def _target_delta_text(price_num: float | None, current: float) -> str:
    if not isinstance(current, (int, float)) or current <= 0 or price_num is None:
        return ""
    pct = ((price_num - current) / current) * 100
    return f"({'+' if pct > 0 else ''}{pct:.1f}%)"
