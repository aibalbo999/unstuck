"""Chart template context assembly for generated HTML reports."""

from __future__ import annotations

from mapping_fields import safe_mapping_dict, safe_text

from .chart_payload import chart_number, chart_number_series, chart_pe_river, chart_price_history, chart_text_series
from .chart_values import normalize_moat_scores
from .html_context import price_target_number
from .html_sanitizer import sanitize_report_plain_text
from .summary_cards import build_metric_cards_html, build_price_target_cards_html
from .text_tokens import is_missing_text_token


def build_html_chart_context(data: dict, parsed: dict) -> dict:
    """Build chart-related template fields from sanitized report data."""
    data = safe_mapping_dict(data) or {}
    parsed = safe_mapping_dict(parsed) or {}

    moat_scores = normalize_moat_scores(safe_mapping_dict(parsed.get("moat_scores", {})) or {})
    moat_labels = list(moat_scores.keys())
    moat_values = list(moat_scores.values())
    raw_price_targets = safe_mapping_dict(parsed.get("price_targets", {})) or {}
    price_targets = _price_target_payload(raw_price_targets)
    current_price = chart_number(data.get("current_price", 0))
    pe_river = chart_pe_river(data.get("pe_river_chart", {}))
    pe_river_source = safe_text(pe_river.get("source", "")).strip()
    pe_river_title = (
        "P/E 河流圖（EPS × 預設本益比通道）"
        if "default" in pe_river_source.lower()
        else "P/E 河流圖（EPS × 歷史本益比通道）"
    )

    chart_data = {
        "years": chart_text_series(data.get("years", [])),
        "moneyUnit": "hundred_million_twd",
        "sourceMoneyUnit": "billion_twd",
        "revenue": chart_number_series(data.get("revenue_history", []), scale=10),
        "netIncome": chart_number_series(data.get("net_income_history", []), scale=10),
        "fcf": chart_number_series(data.get("fcf_history", []), scale=10),
        "grossMargin": chart_number_series(data.get("gross_margin_history", [])),
        "opMargin": chart_number_series(data.get("op_margin_history", [])),
        "netMargin": chart_number_series(data.get("net_margin_history", [])),
        "roe": chart_number_series(data.get("roe_history", [])),
        "priceHistory": chart_price_history(data.get("price_history", {})),
        "moatLabels": chart_text_series(moat_labels),
        "moatValues": chart_number_series(moat_values),
        "priceTargets": price_targets,
        "currentPrice": current_price,
        "peRiver": pe_river,
    }
    return {
        "moat_scores": moat_scores,
        "moat_labels": moat_labels,
        "moat_values": moat_values,
        "overall_moat": moat_scores.get("整體護城河", 0),
        "price_targets": price_targets,
        "pe_river": pe_river,
        "pe_river_title": pe_river_title,
        "chart_data": chart_data,
        "current_price_numeric": current_price or 0,
        "metrics_html": build_metric_cards_html(data),
        "price_targets_html": build_price_target_cards_html(price_targets, data.get("current_price", 0)),
    }


def _price_target_payload(raw_price_targets: dict) -> dict:
    price_targets = {}
    for key, value in raw_price_targets.items():
        label = _price_target_label(key)
        label = _unique_display_label(price_targets, label)
        price_targets[label] = price_target_number(value)
    return price_targets


def _price_target_label(value) -> str:
    label = sanitize_report_plain_text(safe_text(value)).strip()
    if not label or is_missing_text_token(label):
        return "情境"
    return label


def _unique_display_label(existing: dict, label: str) -> str:
    candidate = label
    suffix = 2
    while candidate in existing:
        candidate = f"{label} {suffix}"
        suffix += 1
    return candidate
