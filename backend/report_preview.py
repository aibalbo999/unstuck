"""Mode-aware preview payloads for report history cards and side panels."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from report_index_parsing import clean_report_text


def _metric(label: str, value: Any, tone: str = "") -> dict:
    display_value = "N/A" if value is None or value == "" else value
    return {
        "label": label,
        "value": clean_report_text(display_value, limit=96),
        "tone": tone,
    }


def _recommendation_tone(value: str) -> str:
    text = str(value or "")
    if "強烈放空" in text or "避免" in text or "賣出" in text:
        return "is-avoid"
    if "買入" in text or "買進" in text:
        return "is-buy"
    return "is-hold"


def _trade_direction_label(value: str) -> tuple[str, str]:
    direction = str(value or "Neutral").strip()
    labels = {
        "Long": ("偏多 Long", "is-long"),
        "Short": ("偏空 Short", "is-short"),
        "Neutral": ("中性 Neutral", "is-neutral"),
    }
    return labels.get(direction, ("中性 Neutral", "is-neutral"))


def _format_price(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return clean_report_text(value or "N/A", limit=80)
    return f"NT${number:,.2f}"


def _read_snapshot(snapshot_path: str) -> dict:
    if not snapshot_path or not os.path.exists(snapshot_path):
        return {}
    try:
        with open(snapshot_path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, TypeError, json.JSONDecodeError):
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


def _snapshot_trade_setup(snapshot: dict) -> dict:
    candidates = [
        ((snapshot.get("rerun_context") or {}).get("parsed") or {}).get("trade_setup"),
        ((snapshot.get("data") or {}).get("parsed") or {}).get("trade_setup"),
    ]
    structured = (snapshot.get("rerun_context") or {}).get("structured_outputs") or {}
    for key in ("24", 24):
        if isinstance(structured, dict):
            candidates.append(structured.get(key))
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return {str(key): str(value).strip() for key, value in candidate.items() if value is not None}
    return {}


def _markdown_trade_setup(markdown_text: str) -> dict:
    match = re.search(
        r"^##[^\n]*極短線交易計畫[^\n]*\n(?P<body>.*?)(?=^##\s+|\Z)",
        markdown_text or "",
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return {}
    body = match.group("body")
    fields = {
        "交易方向": "trade_direction",
        "進場區間": "entry_zone",
        "1-2週目標": "target_price",
        "1-2週目標價": "target_price",
        "嚴格停損": "stop_loss",
        "停損點": "stop_loss",
        "核心催化劑": "core_catalyst",
        "短期波動風險": "risk_level",
    }
    setup: dict[str, str] = {}
    for line in body.splitlines():
        match = re.match(r"^\s*[-*]\s*\*\*(?P<label>[^:*：]+)\s*[:：]\*\*\s*(?P<value>.+?)\s*$", line)
        if not match:
            match = re.match(r"^\s*[-*]\s*\*\*(?P<label>[^*：:]+)\*\*\s*[:：]\s*(?P<value>.+?)\s*$", line)
        if not match:
            continue
        label = re.sub(r"^[^\w\u4e00-\u9fff]+", "", match.group("label").strip())
        key = fields.get(label)
        if key:
            setup[key] = clean_report_text(match.group("value"), limit=160)
    return setup


def _snapshot_current_price(snapshot: dict, fallback: str = "N/A") -> str:
    data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
    for source in (data, snapshot):
        if not isinstance(source, dict):
            continue
        if source.get("current_price") not in {None, ""}:
            return _format_price(source.get("current_price"))
        if source.get("current_price_fmt"):
            return clean_report_text(source.get("current_price_fmt"), limit=80)
    return clean_report_text(fallback or "N/A", limit=80)


def _extract_heading_body(markdown_text: str, heading_fragment: str) -> str:
    pattern = re.compile(
        rf"^##[^\n]*{re.escape(heading_fragment)}[^\n]*\n(?P<body>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(markdown_text or "")
    return clean_report_text(match.group("body"), limit=96) if match else "N/A"


def _base_summary(recommendation: dict, markdown_text: str) -> str:
    summary = clean_report_text(recommendation.get("summary", ""), limit=420)
    if summary:
        return summary
    title = re.search(r"^#\s+(.+)$", markdown_text or "", re.MULTILINE)
    return clean_report_text(title.group(1), limit=420) if title else "這份報告沒有可讀的一頁式摘要，可直接查看完整報告。"


def _investment_preview(ticker: str, recommendation: dict, markdown_text: str) -> dict:
    rec = recommendation.get("recommendation", "N/A")
    return {
        "kind": "investment",
        "title": f"{ticker} 投資建議",
        "primary": {"label": "建議", "value": rec, "tone": _recommendation_tone(rec)},
        "metrics": [
            _metric("當日股價", recommendation.get("current_price")),
            _metric("信心", recommendation.get("confidence")),
        ],
        "targets": [
            _metric("3個月", recommendation.get("target_3m")),
            _metric("6個月", recommendation.get("target_6m")),
            _metric("12個月", recommendation.get("target_12m")),
        ],
        "summary": _base_summary(recommendation, markdown_text),
        "list_metrics": [
            _metric("12個月", recommendation.get("target_12m")),
            _metric("信心", recommendation.get("confidence")),
        ],
    }


def _bubble_sniper_preview(ticker: str, recommendation: dict, markdown_text: str) -> dict:
    rec = recommendation.get("recommendation", "N/A")
    crash = _extract_heading_body(markdown_text, "做空觸發條件")
    stop = _extract_heading_body(markdown_text, "防軋空停損點")
    return {
        "kind": "bubble_sniper",
        "title": f"{ticker} 泡沫狙擊預覽",
        "primary": {"label": "空方判斷", "value": rec, "tone": "is-short" if "強烈放空" in rec else _recommendation_tone(rec)},
        "metrics": [
            _metric("當日股價", recommendation.get("current_price")),
            _metric("信心", recommendation.get("confidence")),
        ],
        "targets": [
            _metric("做空觸發", crash),
            _metric("防軋空停損", stop),
            _metric("3個月壓力", recommendation.get("target_3m")),
        ],
        "summary": _base_summary(recommendation, markdown_text),
        "list_metrics": [
            _metric("3個月壓力", recommendation.get("target_3m")),
            _metric("信心", recommendation.get("confidence")),
        ],
    }


def _swing_trade_preview(ticker: str, recommendation: dict, markdown_text: str, snapshot: dict) -> dict:
    setup = _snapshot_trade_setup(snapshot) or _markdown_trade_setup(markdown_text)
    direction_label, direction_tone = _trade_direction_label(setup.get("trade_direction"))
    return {
        "kind": "swing_trade",
        "title": f"{ticker} 極短線交易預覽",
        "primary": {"label": "交易方向", "value": direction_label, "tone": direction_tone},
        "metrics": [
            _metric("當日股價", _snapshot_current_price(snapshot, recommendation.get("current_price"))),
            _metric("風險", setup.get("risk_level", "High")),
        ],
        "targets": [
            _metric("進場區間", setup.get("entry_zone")),
            _metric("1-2週目標", setup.get("target_price")),
            _metric("停損", setup.get("stop_loss")),
        ],
        "summary": clean_report_text(setup.get("core_catalyst"), limit=420) or _base_summary(recommendation, markdown_text),
        "list_metrics": [
            _metric("目標", setup.get("target_price")),
            _metric("停損", setup.get("stop_loss")),
        ],
    }


def build_report_preview(
    pipeline_id: str,
    ticker: str,
    recommendation: dict,
    *,
    markdown_text: str = "",
    snapshot_path: str = "",
) -> dict:
    """Return a compact preview model that matches the report mode semantics."""
    recommendation = recommendation if isinstance(recommendation, dict) else {}
    snapshot = _read_snapshot(snapshot_path)
    if pipeline_id == "v4":
        return _swing_trade_preview(ticker, recommendation, markdown_text, snapshot)
    if pipeline_id == "v3":
        return _bubble_sniper_preview(ticker, recommendation, markdown_text)
    return _investment_preview(ticker, recommendation, markdown_text)
