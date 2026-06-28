"""Deterministic investment thesis discipline payloads."""

from __future__ import annotations

import re
from typing import Any


def build_investment_thesis(context: dict[str, Any]) -> dict[str, Any]:
    """Build a decision-discipline payload from an analysis context."""
    data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
    parsed = context.get("parsed", {}) if isinstance(context.get("parsed"), dict) else {}
    recommendation = parsed.get("recommendation", {}) if isinstance(parsed.get("recommendation"), dict) else {}
    price_targets = parsed.get("price_targets", {}) if isinstance(parsed.get("price_targets"), dict) else {}
    moat_scores = parsed.get("moat_scores", {}) if isinstance(parsed.get("moat_scores"), dict) else {}
    audit = context.get("final_audit", {}) if isinstance(context.get("final_audit"), dict) else {}

    ticker = str(context.get("ticker") or data.get("ticker") or "")
    company_name = str(context.get("company_name") or data.get("company_name") or ticker or "本標的")
    rec_text = _first_mapping_value(recommendation, "建議") or "持有"
    target_12m = _first_mapping_value(recommendation, "12個月") or price_targets.get("基本情境") or "N/A"
    confidence_text = _first_mapping_value(recommendation, "信心") or "5/10"
    confidence = _confidence_number(confidence_text)
    richness = _information_richness(data)
    data_gaps = _data_gaps(data, audit, richness)
    health_score = min(confidence, {"A": 10, "B": 7, "C": 5}.get(richness["grade"], 5))

    business_line = _first_analysis_sentence(context) or f"{company_name} 的商業模式仍需由本次報告各章節交叉確認"
    moat_line = _moat_line(moat_scores)
    valuation_line = _valuation_line(data, price_targets, target_12m)
    downside_line = _downside_line(audit, data_gaps)

    mirror_lines = [
        f"我以 {data.get('current_price_fmt') or data.get('current_price') or 'N/A'} 評估 {company_name}，目前結論為 {rec_text}。",
        f"這門生意的本質是：{business_line}",
        f"護城河判斷：{moat_line}",
        f"估值錨點：12 個月參考目標 {target_12m}，{valuation_line}",
        f"即使判斷錯誤，下行風險主要來自：{downside_line}",
    ]
    mirror_status = "pass" if richness["grade"] != "C" and not _has_na(mirror_lines) else "gray_zone"
    if "避免" in rec_text or "放空" in rec_text:
        mirror_status = "pass"

    return {
        "schema_version": 1,
        "ticker": ticker,
        "company_name": company_name,
        "pipeline_id": context.get("pipeline_id", "v1"),
        "recommendation": rec_text,
        "confidence": confidence_text,
        "health_score": int(max(1, health_score)),
        "information_richness": richness,
        "mirror_test": {
            "status": mirror_status,
            "lines": mirror_lines,
        },
        "core_assumptions": _core_assumptions(data, moat_scores, price_targets, recommendation),
        "red_lines": _red_lines(data, rec_text),
        "valuation_anchor": {
            "current_price": data.get("current_price_fmt") or data.get("current_price") or "N/A",
            "target_12m": target_12m,
            "bear_case": price_targets.get("熊市情境", "N/A"),
            "base_case": price_targets.get("基本情境", "N/A"),
            "bull_case": price_targets.get("牛市情境", "N/A"),
        },
        "data_gaps": data_gaps,
        "next_review": {
            "trigger": "下一次季報或重大法說會後",
            "focus": _next_review_focus(data_gaps, rec_text),
        },
    }


def investment_thesis_markdown(thesis: dict[str, Any]) -> str:
    """Render the thesis payload as a compact Markdown section."""
    if not thesis:
        return ""
    lines = ["## 投資論文與決策紀律"]
    info = thesis.get("information_richness", {}) if isinstance(thesis.get("information_richness"), dict) else {}
    mirror = thesis.get("mirror_test", {}) if isinstance(thesis.get("mirror_test"), dict) else {}
    lines.append(f"- **論文健康度:** {thesis.get('health_score', 'N/A')}/10")
    lines.append(f"- **資訊豐富度:** {info.get('grade', 'N/A')}（{info.get('summary', 'N/A')}）")
    lines.append(f"- **鏡子測試:** {mirror.get('status', 'N/A')}")
    lines.append("")
    lines.append("### 鏡子測試五句話")
    for item in mirror.get("lines", []) or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 核心假設")
    for item in thesis.get("core_assumptions", []) or []:
        lines.append(f"- **{item.get('assumption', 'N/A')}**：{item.get('validation', 'N/A')}（{item.get('frequency', 'N/A')}）")
    lines.append("")
    lines.append("### 紅線")
    for item in thesis.get("red_lines", []) or []:
        lines.append(f"- **{item.get('severity', 'N/A')}**：{item.get('condition', 'N/A')} -> {item.get('action', 'N/A')}")
    gaps = thesis.get("data_gaps", []) or []
    if gaps:
        lines.append("")
        lines.append("### 資料缺口")
        for gap in gaps[:5]:
            lines.append(f"- {gap}")
    next_review = thesis.get("next_review", {}) if isinstance(thesis.get("next_review"), dict) else {}
    lines.append("")
    lines.append(f"**下次檢查:** {next_review.get('trigger', 'N/A')}；重點：{next_review.get('focus', 'N/A')}")
    return "\n".join(lines).strip()


def _first_mapping_value(mapping: dict[str, Any], needle: str) -> Any:
    for key, value in (mapping or {}).items():
        if needle in str(key):
            return value
    return None


def _confidence_number(value: Any) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return 5
    return int(round(max(1.0, min(10.0, float(match.group(1))))))


def _information_richness(data: dict[str, Any]) -> dict[str, Any]:
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


def _data_gaps(data: dict[str, Any], audit: dict[str, Any], richness: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if richness.get("grade") == "C":
        gaps.append("資料不足：無法把所有投資論文假設升級為高確定性結論。")
    data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    if data_trust.get("status") not in {"fresh", None}:
        gaps.append(f"資料可信度狀態為 {data_trust.get('status')}，需保留信心折讓。")
    for warning in list(audit.get("warnings") or [])[:3]:
        gaps.append(str(warning))
    return gaps


def _first_analysis_sentence(context: dict[str, Any]) -> str:
    analyses = context.get("analyses", {}) if isinstance(context.get("analyses"), dict) else {}
    for key in (1, "1", 11, "11"):
        text = str(analyses.get(key) or "").strip()
        if text:
            return _first_sentence(text)
    for text in analyses.values():
        if str(text).strip():
            return _first_sentence(str(text))
    return ""


def _first_sentence(text: str, limit: int = 90) -> str:
    cleaned = " ".join(str(text or "").replace("#", " ").split())
    for sep in ("。", ".", "；", ";"):
        if sep in cleaned:
            cleaned = cleaned.split(sep, 1)[0]
            break
    return cleaned[:limit]


def _moat_line(moat_scores: dict[str, Any]) -> str:
    overall = moat_scores.get("整體護城河")
    if overall is None:
        return "護城河資料不足，需以競爭格局與客戶黏著度補驗證"
    return f"整體護城河 {overall}/10，需追蹤分數是否由可驗證證據支撐"


def _valuation_line(data: dict[str, Any], price_targets: dict[str, Any], target_12m: Any) -> str:
    current = data.get("current_price")
    base = price_targets.get("基本情境")
    if isinstance(current, (int, float)) and isinstance(base, (int, float)) and current:
        upside = (base / current - 1) * 100
        return f"基本情境隱含報酬約 {upside:.1f}%"
    return f"估值錨點為 {target_12m}"


def _downside_line(audit: dict[str, Any], data_gaps: list[str]) -> str:
    critical = list(audit.get("critical") or []) if isinstance(audit, dict) else []
    if critical:
        return str(critical[0])
    if data_gaps:
        return data_gaps[0]
    return "財務品質、估值收斂或核心成長假設未達成"


def _core_assumptions(
    data: dict[str, Any],
    moat_scores: dict[str, Any],
    price_targets: dict[str, Any],
    recommendation: dict[str, Any],
) -> list[dict[str, str]]:
    assumptions = [
        {
            "assumption": "核心營收與獲利不惡化",
            "validation": "追蹤季營收、TTM 淨利與自由現金流是否延續報告假設",
            "frequency": "每季",
            "status": "active",
        },
        {
            "assumption": "護城河沒有被同業明確突破",
            "validation": f"追蹤整體護城河分數 {moat_scores.get('整體護城河', 'N/A')} 與競爭證據",
            "frequency": "每半年",
            "status": "active",
        },
        {
            "assumption": "估值仍落在三情境可解釋區間",
            "validation": f"熊/基/牛情境：{price_targets.get('熊市情境', 'N/A')} / {price_targets.get('基本情境', 'N/A')} / {price_targets.get('牛市情境', 'N/A')}",
            "frequency": "每次重跑報告",
            "status": "active",
        },
    ]
    if data.get("recent_catalysts"):
        assumptions.append({
            "assumption": "近期催化劑能轉化為可驗證營運數據",
            "validation": "追蹤催化事件後的月營收、訂單或毛利率變化",
            "frequency": "事件後",
            "status": "active",
        })
    if _first_mapping_value(recommendation, "建議"):
        assumptions.append({
            "assumption": "最終建議與目標價沒有和後續資料脫鉤",
            "validation": "由 decision tracking 檢查 3/6/12 個月 ROI 與命中率",
            "frequency": "3/6/12 個月",
            "status": "active",
        })
    return assumptions


def _red_lines(data: dict[str, Any], recommendation: str) -> list[dict[str, str]]:
    lines = [
        {
            "condition": "核心資料可信度降為 error 或關鍵財務欄位熔斷未解除",
            "severity": "致命",
            "action": "停止使用目標價，先重跑資料校驗",
        },
        {
            "condition": "連續兩季營收或自由現金流明確低於投資論文假設",
            "severity": "嚴重",
            "action": "將論文狀態降級並重跑完整報告",
        },
        {
            "condition": "護城河證據被競爭者、技術替代或客戶流失明確推翻",
            "severity": "嚴重",
            "action": "重新評估持有理由與安全邊際",
        },
        {
            "condition": "管理層誠信、重大關係人交易或財報品質出現重大疑慮",
            "severity": "致命",
            "action": "人工審查前不得升級建議",
        },
    ]
    if "買" in recommendation:
        lines.append({
            "condition": "股價超過牛市情境且基本面沒有同步上修",
            "severity": "警告",
            "action": "停止加碼並檢查安全邊際",
        })
    if data.get("data_trust", {}).get("status") == "partial":
        lines.append({
            "condition": "partial data trust 持續且無法取得官方資料補驗證",
            "severity": "警告",
            "action": "維持灰色地帶，不提高信心分數",
        })
    return lines


def _next_review_focus(data_gaps: list[str], recommendation: str) -> str:
    if data_gaps:
        return "優先補齊資料缺口與來源差異"
    if "買" in recommendation:
        return "確認成長與估值安全邊際是否仍成立"
    if "避免" in recommendation or "放空" in recommendation:
        return "確認風險是否已被價格反映或基本面是否改善"
    return "確認持有論文是否轉強或轉弱"


def _has_na(lines: list[str]) -> bool:
    return any("N/A" in line for line in lines)
