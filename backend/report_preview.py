"""Mode-aware preview payloads for report history cards and side panels."""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any

from recommendation_labels import normalize_recommendation_label, recommendation_tone
from report_index_parsing import clean_report_text, extract_section


def _metric(label: str, value: Any, tone: str = "", *, not_applicable: str = "") -> dict:
    text = clean_report_text(value, limit=192) if value is not None else ""
    compound = re.fullmatch(r"(?:N/?A|--)[\s（(]+(.+?)[）)]?", text, re.I)
    if compound:
        reason_text = compound.group(1).rstrip("）)").strip()
        text = reason_text if re.match(r"不適用|來源異常|(?:尚)?未提供|(?:尚)?未確認|資料不足|未評估|未驗證|未估計", reason_text) else f"尚未確認（{reason_text}）"
    category = reason = ""
    for prefix, name in (("不適用", "not_applicable"), ("來源異常", "source_error"),
                         ("尚未提供", "not_provided"), ("未提供", "not_provided"),
                         ("尚未確認", "unconfirmed"), ("未確認", "unconfirmed"),
                         ("資料不足", "unconfirmed"), ("未評估", "unconfirmed"),
                         ("未驗證", "unconfirmed"), ("未估計", "unconfirmed")):
        if text.startswith(prefix):
            category = name
            reason = text[len(prefix):].strip(" （）()，：；。:;,")
            break
    absent = not text or text.upper() in {"N/A", "NA", "--", "NONE", "NULL", "NAN", "INF", "INFINITY"} or text in {
        "未提供", "尚未提供", "資料不足", "未評估", "尚未評估", "未驗證", "未估計", "未確認", "尚未確認"}
    if absent:
        category = "not_applicable" if not_applicable else (
            "unconfirmed" if re.search("股價|估值|情境|目標|壓力|停損|觸發|信心|風險|(?:3|6|12)個月", label) else "not_provided")
        reason = not_applicable or ("原報告未提供可核實的判斷或數值，不代填結論" if category == "unconfirmed"
                                    else "原報告未填此項，未記錄缺漏原因")
    result = {
        "label": label,
        "value": text,
        "tone": tone,
    }
    if category:
        reason = reason or "原報告未記錄更詳細原因，保留缺值，不代填數字"
        title = {"not_applicable": "不適用", "not_provided": "尚未提供",
                 "unconfirmed": "尚未確認", "source_error": "來源異常"}[category]
        result.update(value=f"{title}（{reason}）", missing_category=category, missing_reason=reason)
    return result


def _display_recommendation(value: Any) -> str:
    text = clean_report_text(value, limit=160)
    if re.match(r"^(?:觀望|中性|中立|偏多觀察|neutral\b|watch\b|wait\b)", text, re.I):
        return "觀望"
    return normalize_recommendation_label(value)


def _projected_recommendation(pipeline_id: str, recommendation: dict, markdown_text: str, snapshot: dict) -> str:
    current = _display_recommendation(recommendation.get("recommendation"))
    calibration = recommendation.get("recommendation_calibration")
    if current != "持有" or (isinstance(calibration, dict) and calibration.get("status") == "adjusted"):
        return current
    # The renderer also canonicalizes its Markdown; prefer the original
    # structured decision before falling back to saved decision text.
    for parent in (snapshot.get("rerun_context"), snapshot.get("data"), snapshot):
        parsed = parent.get("parsed") if isinstance(parent, dict) else None
        raw = parsed.get("recommendation") if isinstance(parsed, dict) else None
        if isinstance(raw, dict):
            raw = next((raw[key] for key in ("建議", "綜合建議", "recommendation") if raw.get(key)), None)
        if raw:
            return "觀望" if _display_recommendation(raw) == "觀望" else current
    from reporting.mode_templates import decision_markdown_heading, get_report_template_profile
    heading = decision_markdown_heading(get_report_template_profile(pipeline_id)).removeprefix("## ").strip()
    sections = [extract_section(markdown_text, heading), extract_section(markdown_text, "🎯 最終投資建議")]
    tagged = re.search(r"\[投資建議\](.*?)\[/投資建議\]", markdown_text, re.S)
    if tagged:
        sections.append(tagged.group(1))
    for section in sections:
        match = re.search(r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:綜合建議|建議|研究評級|最終建議|空方結論)(?:\*\*)?\s*[:：](?:\*\*)?\s*(.+?)\s*$", section, re.M)
        if match:
            return "觀望" if _display_recommendation(match.group(1)) == "觀望" else current
    return current


def _recommendation_tone(value: str) -> str:
    return "is-neutral" if _display_recommendation(value) == "觀望" else recommendation_tone(value)


def _trade_direction_label(value: str) -> tuple[str, str]:
    direction = str(value or "").strip()
    labels = {
        "Long": ("偏多 Long", "is-long"),
        "Short": ("偏空 Short", "is-short"),
        "Neutral": ("觀望（暫不建立新交易）", "is-neutral"),
    }
    if _display_recommendation(direction) == "觀望":
        return labels["Neutral"]
    return labels.get(direction, ("尚未確認（原報告未提供可核實的交易方向）", "is-neutral"))


def _format_price(value: Any) -> str:
    if isinstance(value, bool):
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return clean_report_text(value or "N/A", limit=80)
    return f"NT${number:,.2f}" if math.isfinite(number) else "N/A"


def _read_snapshot(snapshot_path: str) -> dict:
    if not snapshot_path or not os.path.exists(snapshot_path):
        return {}
    try:
        with open(snapshot_path, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except (OSError, UnicodeDecodeError, TypeError, json.JSONDecodeError):
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


def extract_trade_setup(snapshot: dict, markdown_text: str = "") -> dict:
    """Return the mode-D trade setup from snapshot data, then Markdown fallback."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    return _snapshot_trade_setup(snapshot) or _markdown_trade_setup(markdown_text)


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


def _calibration_metric(recommendation: dict) -> dict | None:
    calibration = recommendation.get("recommendation_calibration")
    if not isinstance(calibration, dict):
        return None
    status = str(calibration.get("status") or "")
    if status == "adjusted":
        original = normalize_recommendation_label(calibration.get("original_recommendation"))
        calibrated = normalize_recommendation_label(calibration.get("calibrated_recommendation"))
        if original != "N/A" and calibrated != "N/A" and original != calibrated:
            return _metric("校準", f"{original} → {calibrated}", "is-neutral")
    if status == "watch":
        return _metric("校準", "需重審", "is-neutral")
    return None


def _investment_preview(ticker: str, recommendation: dict, markdown_text: str, snapshot: dict, pipeline_id: str) -> dict:
    rec = _projected_recommendation(pipeline_id, recommendation, markdown_text, snapshot)
    calibration_metric = _calibration_metric(recommendation)
    return {
        "kind": "investment",
        "title": f"{ticker} 投資建議",
        "primary": {"label": "建議", "value": rec, "tone": _recommendation_tone(rec)},
        "metrics": [
            _metric("當日股價", recommendation.get("current_price")),
            _metric("信心", recommendation.get("confidence")),
        ] + ([calibration_metric] if calibration_metric else []),
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


def _bubble_sniper_preview(ticker: str, recommendation: dict, markdown_text: str, snapshot: dict) -> dict:
    rec = _projected_recommendation("v3", recommendation, markdown_text, snapshot)
    crash = _extract_heading_body(markdown_text, "做空觸發條件")
    stop = _extract_heading_body(markdown_text, "防軋空停損點")
    return {
        "kind": "bubble_sniper",
        "title": f"{ticker} 泡沫狙擊預覽",
        "primary": {"label": "空方判斷", "value": rec, "tone": _recommendation_tone(rec)},
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
    setup = extract_trade_setup(snapshot, markdown_text)
    direction_label, direction_tone = _trade_direction_label(setup.get("trade_direction"))
    price_reason = "觀望中，暫不設定交易價位" if direction_label == "觀望（暫不建立新交易）" else ""
    return {
        "kind": "swing_trade",
        "title": f"{ticker} 極短線交易預覽",
        "primary": {"label": "交易方向", "value": direction_label, "tone": direction_tone},
        "metrics": [
            _metric("當日股價", _snapshot_current_price(snapshot, recommendation.get("current_price"))),
            _metric("風險", setup.get("risk_level", "High")),
        ],
        "targets": [
            _metric("進場區間", setup.get("entry_zone"), not_applicable=price_reason),
            _metric("1-2週目標", setup.get("target_price"), not_applicable=price_reason),
            _metric("停損", setup.get("stop_loss"), not_applicable=price_reason),
        ],
        "summary": clean_report_text(setup.get("core_catalyst"), limit=420) or _base_summary(recommendation, markdown_text),
        "list_metrics": [
            _metric("目標", setup.get("target_price"), not_applicable=price_reason),
            _metric("停損", setup.get("stop_loss"), not_applicable=price_reason),
        ],
    }


def build_report_preview(
    pipeline_id: str,
    ticker: str,
    recommendation: dict,
    *,
    markdown_text: str = "",
    snapshot_path: str = "",
    snapshot: dict | None = None,
) -> dict:
    """Return a compact preview model that matches the report mode semantics."""
    recommendation = recommendation if isinstance(recommendation, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else _read_snapshot(snapshot_path)
    if pipeline_id == "v4":
        return _swing_trade_preview(ticker, recommendation, markdown_text, snapshot)
    if pipeline_id == "v3":
        return _bubble_sniper_preview(ticker, recommendation, markdown_text, snapshot)
    return _investment_preview(ticker, recommendation, markdown_text, snapshot, pipeline_id)
