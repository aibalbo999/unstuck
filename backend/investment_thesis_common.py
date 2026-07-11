"""Shared helpers for deterministic investment thesis payloads."""

from __future__ import annotations

import re
from typing import Any

from output_sanitizer import sanitize_model_output


def first_mapping_value(mapping: dict[str, Any], needle: str) -> Any:
    for key, value in (mapping or {}).items():
        if needle in str(key):
            return value
    return None


def trade_setup_from_context(context: dict[str, Any], parsed: dict[str, Any]) -> dict[str, str]:
    candidates = []
    if isinstance(parsed.get("trade_setup"), dict):
        candidates.append(parsed.get("trade_setup"))
    structured_outputs = context.get("structured_outputs", {}) if isinstance(context.get("structured_outputs"), dict) else {}
    for key in (24, "24"):
        if isinstance(structured_outputs.get(key), dict):
            candidates.append(structured_outputs.get(key))
    for candidate in candidates:
        cleaned = {str(key): str(value).strip() for key, value in (candidate or {}).items() if value is not None}
        if cleaned:
            return cleaned
    return {}


def trade_direction_label(value: Any) -> str:
    direction = str(value or "Neutral").strip()
    labels = {
        "Long": "偏多 Long",
        "Short": "偏空 Short",
        "Neutral": "中性 Neutral",
    }
    return labels.get(direction, direction or "中性 Neutral")


def trade_health_score(trade_setup: dict[str, str], richness: dict[str, Any]) -> int:
    base = {"A": 7, "B": 6, "C": 4}.get(str(richness.get("grade") or "C"), 4)
    risk = str(trade_setup.get("risk_level") or "High")
    if risk == "Low":
        base += 1
    elif risk == "High":
        base -= 1
    if str(trade_setup.get("trade_direction") or "Neutral") == "Neutral":
        base = min(base, 6)
    missing = [
        key for key in ("trade_direction", "entry_zone", "target_price", "stop_loss", "core_catalyst")
        if not trade_setup.get(key)
    ]
    return max(1, min(10, base - len(missing)))


def trade_mirror_lines(data: dict[str, Any], company_name: str, trade_setup: dict[str, str]) -> list[str]:
    direction = trade_direction_label(trade_setup.get("trade_direction"))
    entry = trade_setup.get("entry_zone") or "尚未形成有效進場區間"
    target = trade_setup.get("target_price") or "N/A"
    stop = trade_setup.get("stop_loss") or "尚未定義停損"
    catalyst = trade_setup.get("core_catalyst") or "近期催化資料不足"
    risk = trade_setup.get("risk_level") or "High"
    return [
        f"我以 {data.get('current_price_fmt') or data.get('current_price') or 'N/A'} 評估 {company_name}，1-2 週交易方向為 {direction}。",
        f"交易計畫：進場區間 {entry}，1-2 週目標 {target}，嚴格停損 {stop}。",
        f"催化條件：{catalyst}",
        "風控邊界：若價格觸發停損、技術與籌碼互相衝突或催化失效，需取消交易或回到 Neutral。",
        f"短期波動風險為 {risk}，部位大小應先服從停損距離與資料新鮮度。",
    ]


def agent_text(context: dict[str, Any], agent_num: int) -> str:
    analyses = context.get("analyses", {}) if isinstance(context.get("analyses"), dict) else {}
    return str(analyses.get(agent_num) or analyses.get(str(agent_num)) or "")


def analysis_section_excerpt(context: dict[str, Any], heading_fragment: str) -> str:
    for agent_num in (19, 24, 18, 17):
        text = clean_analysis_text(agent_text(context, agent_num))
        if heading_fragment not in text:
            continue
        pattern = re.compile(
            rf"{re.escape(heading_fragment)}[^\n]*\n(?P<body>.*?)(?=\n## |\n### |\Z)",
            re.DOTALL,
        )
        match = pattern.search(text)
        body = match.group("body") if match else text.split(heading_fragment, 1)[-1]
        return first_sentence(body.replace("-", " "), limit=120)
    return ""


def trigger_from_structured(context: dict[str, Any], directions: set[str]) -> str:
    structured_outputs = context.get("structured_outputs", {}) if isinstance(context.get("structured_outputs"), dict) else {}
    for payload in structured_outputs.values():
        if not isinstance(payload, dict):
            continue
        for trigger in payload.get("scenario_triggers") or []:
            if not isinstance(trigger, dict) or trigger.get("direction") not in directions:
                continue
            condition = str(trigger.get("trigger_condition") or "").strip()
            action = str(trigger.get("action") or "").strip()
            if condition and action:
                return f"{condition}：{action}"
            if condition:
                return condition
    return ""


def confidence_number(value: Any) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return 5
    return int(round(max(1.0, min(10.0, float(match.group(1))))))


def information_richness(data: dict[str, Any]) -> dict[str, Any]:
    data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    status = str(data_trust.get("status") or "unknown")
    audit_count = len(data.get("source_audit") or []) if isinstance(data.get("source_audit"), list) else 0
    history_count = sum(1 for key in ("revenue_history", "net_income_history", "fcf_history") if data.get(key))
    catalyst_count = len(data.get("recent_catalysts") or []) if isinstance(data.get("recent_catalysts"), list) else 0

    if status == "fresh" and audit_count >= 5 and history_count >= 2:
        grade = "A"
        summary = "資料充足，適合正常執行並加強反共識檢查"
    elif status in {"fresh", "partial"} and (audit_count >= 3 or history_count >= 1 or catalyst_count >= 2):
        grade = "B"
        summary = "資料中等，推算與信心需要標註限制"
    else:
        grade = "C"
        summary = "資料不足，應以灰色地帶與第一性原理問題為主"
    return {
        "grade": grade,
        "summary": summary,
        "data_trust_status": status,
        "source_audit_count": audit_count,
        "history_series_count": history_count,
        "catalyst_count": catalyst_count,
    }


def data_gaps(data: dict[str, Any], audit: dict[str, Any], richness: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if richness.get("grade") == "C":
        gaps.append("資料不足：無法把所有投資論文假設升級為高確定性結論。")
    data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    if data_trust.get("status") not in {"fresh", None}:
        gaps.append(f"資料可信度狀態為 {data_trust.get('status')}，需保留信心折讓。")
    for warning in list(audit.get("warnings") or [])[:3]:
        gaps.append(str(warning))
    return gaps


def first_analysis_sentence(context: dict[str, Any]) -> str:
    analyses = context.get("analyses", {}) if isinstance(context.get("analyses"), dict) else {}
    for key in (1, "1", 11, "11"):
        text = clean_analysis_text(analyses.get(key))
        if text:
            return first_sentence(text)
    for text in analyses.values():
        cleaned = clean_analysis_text(text)
        if cleaned:
            return first_sentence(cleaned)
    return ""


def first_analysis_sentence_for_agents(context: dict[str, Any], agent_nums: tuple[int, ...]) -> str:
    for agent_num in agent_nums:
        text = clean_analysis_text(agent_text(context, agent_num))
        if text:
            return first_sentence(text)
    return ""


def clean_analysis_text(value: Any) -> str:
    return sanitize_model_output(str(value or "")).strip()


def first_sentence(text: str, limit: int = 90) -> str:
    cleaned = " ".join(str(text or "").replace("#", " ").split())
    for sep in ("。", ".", "；", ";"):
        if sep in cleaned:
            cleaned = cleaned.split(sep, 1)[0]
            break
    return cleaned[:limit]


def moat_line(moat_scores: dict[str, Any]) -> str:
    overall = moat_scores.get("整體護城河")
    if overall is None:
        return "護城河資料不足，需以競爭格局與客戶黏著度補驗證"
    return f"整體護城河 {overall}/10，需追蹤分數是否由可驗證證據支撐"


def valuation_line(data: dict[str, Any], price_targets: dict[str, Any], target_12m: Any) -> str:
    current = data.get("current_price")
    base = price_targets.get("基本情境")
    if isinstance(current, (int, float)) and isinstance(base, (int, float)) and current:
        upside = (base / current - 1) * 100
        return f"基本情境隱含報酬約 {upside:.1f}%"
    return f"估值錨點為 {target_12m}"


def downside_line(audit: dict[str, Any], gaps: list[str]) -> str:
    critical = list(audit.get("critical") or []) if isinstance(audit, dict) else []
    if critical:
        return str(critical[0])
    if gaps:
        return gaps[0]
    return "財務品質、估值收斂或核心成長假設未達成"


def chip_line(data: dict[str, Any]) -> str:
    institutional = data.get("institutional_trading", {}) if isinstance(data.get("institutional_trading"), dict) else {}
    trend = institutional.get("trend")
    net = institutional.get("total_net_buy_thousand_shares")
    has_net = net is not None and net != ""
    if trend or has_net:
        return f"三大法人趨勢 {trend or 'N/A'}，累計買賣超約 {net if has_net else 'N/A'} 張"
    return "籌碼資料不足，需用法人買賣超、融資券或 TDCC 補驗證"


def next_review_focus(gaps: list[str], recommendation: str) -> str:
    if gaps:
        return "優先補齊資料缺口與來源差異"
    if "買" in recommendation:
        return "確認成長與估值安全邊際是否仍成立"
    if "避免" in recommendation or "放空" in recommendation:
        return "確認風險是否已被價格反映或基本面是否改善"
    return "確認持有論文是否轉強或轉弱"


def has_na(lines: list[str]) -> bool:
    return any("N/A" in line for line in lines)
