"""Deterministic investment thesis discipline payloads."""

from __future__ import annotations

import re
from typing import Any

from pipeline_modes import normalize_pipeline_id


_DISCIPLINE_PROFILES = {
    "v1": {
        "heading": "長線投資論文與決策紀律",
        "health_label": "論文健康度",
        "mirror_heading": "鏡子測試五句話",
        "assumptions_heading": "核心假設",
        "red_lines_heading": "紅線",
    },
    "v2": {
        "heading": "部位決策與風控紀律",
        "health_label": "部位計畫健康度",
        "mirror_heading": "部位檢查五句話",
        "assumptions_heading": "持倉假設",
        "red_lines_heading": "風控紅線",
    },
    "v3": {
        "heading": "逆勢論文與風控紀律",
        "health_label": "逆勢論文健康度",
        "mirror_heading": "空方檢查五句話",
        "assumptions_heading": "逆勢假設",
        "red_lines_heading": "防軋空紅線",
    },
    "v4": {
        "heading": "交易計畫與風控紀律",
        "health_label": "交易計畫健康度",
        "mirror_heading": "交易檢查五句話",
        "assumptions_heading": "交易假設",
        "red_lines_heading": "停損紅線",
    },
}


def build_investment_thesis(context: dict[str, Any]) -> dict[str, Any]:
    """Build a decision-discipline payload from an analysis context."""
    data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
    parsed = context.get("parsed", {}) if isinstance(context.get("parsed"), dict) else {}
    recommendation = parsed.get("recommendation", {}) if isinstance(parsed.get("recommendation"), dict) else {}
    price_targets = parsed.get("price_targets", {}) if isinstance(parsed.get("price_targets"), dict) else {}
    moat_scores = parsed.get("moat_scores", {}) if isinstance(parsed.get("moat_scores"), dict) else {}
    audit = context.get("final_audit", {}) if isinstance(context.get("final_audit"), dict) else {}
    pipeline_id = normalize_pipeline_id(context.get("pipeline_id", "v1"))
    profile = _discipline_profile(pipeline_id)

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

    if pipeline_id == "v4":
        trade_setup = _trade_setup_from_context(context, parsed)
        rec_text = _trade_direction_label(trade_setup.get("trade_direction"))
        target_12m = trade_setup.get("target_price") or "N/A"
        confidence_text = trade_setup.get("risk_level") or "High"
        confidence = _trade_health_score(trade_setup, richness)
        health_score = confidence
        mirror_lines = _trade_mirror_lines(data, company_name, trade_setup)
        core_assumptions = _trade_core_assumptions(trade_setup)
        red_lines = _trade_red_lines(trade_setup)
        valuation_anchor = {
            "current_price": data.get("current_price_fmt") or data.get("current_price") or "N/A",
            "target_12m": "N/A",
            "bear_case": "N/A",
            "base_case": trade_setup.get("target_price") or "N/A",
            "bull_case": trade_setup.get("target_price") or "N/A",
        }
        next_review = {
            "trigger": "下一個交易日收盤或催化事件前後",
            "focus": "確認價格是否仍在進場區間、停損是否觸發、催化是否仍有效",
        }
    elif pipeline_id == "v3":
        crash_trigger = _analysis_section_excerpt(context, "做空觸發條件") or _trigger_from_structured(context, {"bearish_downgrade"})
        stop_condition = _analysis_section_excerpt(context, "防軋空停損點") or _trigger_from_structured(context, {"neutral_review", "bullish_upgrade"})
        mirror_lines = [
            f"我以 {data.get('current_price_fmt') or data.get('current_price') or 'N/A'} 評估 {company_name}，逆勢結論為 {rec_text}。",
            f"泡沫假設：{_first_analysis_sentence_for_agents(context, (17,)) or business_line}",
            f"硬證據：{_first_analysis_sentence_for_agents(context, (18,)) or downside_line}",
            f"做空觸發：{crash_trigger or '尚需等待可驗證催化，不能只因估值高就追空'}",
            f"防軋空/失效條件：{stop_condition or '若基本面改善或股價突破風控位，需回補或暫停空方假設'}",
        ]
        core_assumptions = _contrarian_core_assumptions(crash_trigger, stop_condition)
        red_lines = _contrarian_red_lines()
        valuation_anchor = {
            "current_price": data.get("current_price_fmt") or data.get("current_price") or "N/A",
            "target_12m": target_12m,
            "bear_case": _first_mapping_value(recommendation, "3個月") or "N/A",
            "base_case": _first_mapping_value(recommendation, "6個月") or "N/A",
            "bull_case": _first_mapping_value(recommendation, "12個月") or "N/A",
        }
        next_review = {
            "trigger": "下一次財報、法說會、籌碼轉折或做空觸發前後",
            "focus": _next_review_focus(data_gaps, rec_text),
        }
    elif pipeline_id == "v2":
        mirror_lines = [
            f"我以 {data.get('current_price_fmt') or data.get('current_price') or 'N/A'} 評估 {company_name}，部位判斷為 {rec_text}。",
            f"交易脈絡：{business_line}",
            f"籌碼與情緒：{_chip_line(data)}",
            f"風險報酬：12 個月參考目標 {target_12m}，{valuation_line}",
            f"若判斷錯誤，優先檢查：{downside_line}",
        ]
        core_assumptions = _position_core_assumptions(data, price_targets, recommendation)
        red_lines = _position_red_lines(data, rec_text)
        valuation_anchor = {
            "current_price": data.get("current_price_fmt") or data.get("current_price") or "N/A",
            "target_12m": target_12m,
            "bear_case": price_targets.get("熊市情境", "N/A"),
            "base_case": price_targets.get("基本情境", "N/A"),
            "bull_case": price_targets.get("牛市情境", "N/A"),
        }
        next_review = {
            "trigger": "下一次收盤、籌碼轉折、重大新聞或估值區間失效時",
            "focus": _next_review_focus(data_gaps, rec_text),
        }
    else:
        mirror_lines = [
            f"我以 {data.get('current_price_fmt') or data.get('current_price') or 'N/A'} 評估 {company_name}，目前結論為 {rec_text}。",
            f"這門生意的本質是：{business_line}",
            f"護城河判斷：{moat_line}",
            f"估值錨點：12 個月參考目標 {target_12m}，{valuation_line}",
            f"即使判斷錯誤，下行風險主要來自：{downside_line}",
        ]
        core_assumptions = _core_assumptions(data, moat_scores, price_targets, recommendation)
        red_lines = _red_lines(data, rec_text)
        valuation_anchor = {
            "current_price": data.get("current_price_fmt") or data.get("current_price") or "N/A",
            "target_12m": target_12m,
            "bear_case": price_targets.get("熊市情境", "N/A"),
            "base_case": price_targets.get("基本情境", "N/A"),
            "bull_case": price_targets.get("牛市情境", "N/A"),
        }
        next_review = {
            "trigger": "下一次季報或重大法說會後",
            "focus": _next_review_focus(data_gaps, rec_text),
        }

    mirror_status = "pass" if richness["grade"] != "C" and not _has_na(mirror_lines) else "gray_zone"
    if "避免" in rec_text or "放空" in rec_text:
        mirror_status = "pass"

    return {
        "schema_version": 1,
        "ticker": ticker,
        "company_name": company_name,
        "pipeline_id": pipeline_id,
        "discipline_heading": profile["heading"],
        "health_label": profile["health_label"],
        "mirror_heading": profile["mirror_heading"],
        "assumptions_heading": profile["assumptions_heading"],
        "red_lines_heading": profile["red_lines_heading"],
        "recommendation": rec_text,
        "confidence": confidence_text,
        "health_score": int(max(1, health_score)),
        "information_richness": richness,
        "mirror_test": {
            "status": mirror_status,
            "lines": mirror_lines,
        },
        "core_assumptions": core_assumptions,
        "red_lines": red_lines,
        "valuation_anchor": valuation_anchor,
        "data_gaps": data_gaps,
        "next_review": next_review,
    }


def investment_thesis_markdown(thesis: dict[str, Any]) -> str:
    """Render the thesis payload as a compact Markdown section."""
    if not thesis:
        return ""
    profile = _discipline_profile(thesis.get("pipeline_id", "v1"))
    lines = [f"## {thesis.get('discipline_heading') or profile['heading']}"]
    info = thesis.get("information_richness", {}) if isinstance(thesis.get("information_richness"), dict) else {}
    mirror = thesis.get("mirror_test", {}) if isinstance(thesis.get("mirror_test"), dict) else {}
    lines.append(f"- **{thesis.get('health_label') or profile['health_label']}:** {thesis.get('health_score', 'N/A')}/10")
    lines.append(f"- **資訊豐富度:** {info.get('grade', 'N/A')}（{info.get('summary', 'N/A')}）")
    lines.append(f"- **鏡子測試:** {mirror.get('status', 'N/A')}")
    lines.append("")
    lines.append(f"### {thesis.get('mirror_heading') or profile['mirror_heading']}")
    for item in mirror.get("lines", []) or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"### {thesis.get('assumptions_heading') or profile['assumptions_heading']}")
    for item in thesis.get("core_assumptions", []) or []:
        lines.append(f"- **{item.get('assumption', 'N/A')}**：{item.get('validation', 'N/A')}（{item.get('frequency', 'N/A')}）")
    lines.append("")
    lines.append(f"### {thesis.get('red_lines_heading') or profile['red_lines_heading']}")
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


def _discipline_profile(pipeline_id: Any) -> dict[str, str]:
    return _DISCIPLINE_PROFILES.get(normalize_pipeline_id(pipeline_id), _DISCIPLINE_PROFILES["v1"])


def _trade_setup_from_context(context: dict[str, Any], parsed: dict[str, Any]) -> dict[str, str]:
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


def _trade_direction_label(value: Any) -> str:
    direction = str(value or "Neutral").strip()
    labels = {
        "Long": "偏多 Long",
        "Short": "偏空 Short",
        "Neutral": "中性 Neutral",
    }
    return labels.get(direction, direction or "中性 Neutral")


def _trade_health_score(trade_setup: dict[str, str], richness: dict[str, Any]) -> int:
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


def _trade_mirror_lines(data: dict[str, Any], company_name: str, trade_setup: dict[str, str]) -> list[str]:
    direction = _trade_direction_label(trade_setup.get("trade_direction"))
    entry = trade_setup.get("entry_zone") or "尚未形成有效進場區間"
    target = trade_setup.get("target_price") or "N/A"
    stop = trade_setup.get("stop_loss") or "尚未定義停損"
    catalyst = trade_setup.get("core_catalyst") or "近期催化資料不足"
    risk = trade_setup.get("risk_level") or "High"
    return [
        f"我以 {data.get('current_price_fmt') or data.get('current_price') or 'N/A'} 評估 {company_name}，1-2 週交易方向為 {direction}。",
        f"交易計畫：進場區間 {entry}，1-2 週目標 {target}，嚴格停損 {stop}。",
        f"催化條件：{catalyst}",
        f"風控邊界：若價格觸發停損、技術與籌碼互相衝突或催化失效，需取消交易或回到 Neutral。",
        f"短期波動風險為 {risk}，部位大小應先服從停損距離與資料新鮮度。",
    ]


def _trade_core_assumptions(trade_setup: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "assumption": "交易方向仍由技術、籌碼與事件共同支持",
            "validation": f"目前方向為 {_trade_direction_label(trade_setup.get('trade_direction'))}；若三者分歧，回到 Neutral",
            "frequency": "每日收盤後",
            "status": "active",
        },
        {
            "assumption": "進場區間仍有效",
            "validation": f"只在 {trade_setup.get('entry_zone') or '有效進場區間'} 附近等待觸發，不追價",
            "frequency": "盤中/收盤",
            "status": "active",
        },
        {
            "assumption": "停損優先於目標價",
            "validation": f"停損條件：{trade_setup.get('stop_loss') or '尚未定義，需補齊後才可使用'}",
            "frequency": "即時",
            "status": "active",
        },
        {
            "assumption": "催化事件仍在 1-2 週窗口內可驗證",
            "validation": trade_setup.get("core_catalyst") or "近期催化資料不足，應降低交易信心",
            "frequency": "事件前後",
            "status": "active",
        },
    ]


def _trade_red_lines(trade_setup: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "condition": f"價格觸發停損：{trade_setup.get('stop_loss') or '停損未定義'}",
            "severity": "致命",
            "action": "取消交易、出場或重新生成 Mode D 報告",
        },
        {
            "condition": "交易方向不是 Neutral，但技術、籌碼或事件任一核心證據失效",
            "severity": "嚴重",
            "action": "降為 Neutral，不可延用原進場區間",
        },
        {
            "condition": "核心催化劑過期、被否定或無法在 1-2 週內驗證",
            "severity": "嚴重",
            "action": "移出短線任務，改列 watchlist 觀察",
        },
        {
            "condition": "資料信心降級或缺少足以判斷短線波動的價格/籌碼資料",
            "severity": "警告",
            "action": "縮小部位或等待下一次資料刷新",
        },
    ]


def _agent_text(context: dict[str, Any], agent_num: int) -> str:
    analyses = context.get("analyses", {}) if isinstance(context.get("analyses"), dict) else {}
    return str(analyses.get(agent_num) or analyses.get(str(agent_num)) or "")


def _analysis_section_excerpt(context: dict[str, Any], heading_fragment: str) -> str:
    for agent_num in (19, 24, 18, 17):
        text = _agent_text(context, agent_num)
        if heading_fragment not in text:
            continue
        pattern = re.compile(
            rf"{re.escape(heading_fragment)}[^\n]*\n(?P<body>.*?)(?=\n## |\n### |\Z)",
            re.DOTALL,
        )
        match = pattern.search(text)
        body = match.group("body") if match else text.split(heading_fragment, 1)[-1]
        return _first_sentence(body.replace("-", " "), limit=120)
    return ""


def _trigger_from_structured(context: dict[str, Any], directions: set[str]) -> str:
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


def _first_analysis_sentence_for_agents(context: dict[str, Any], agent_nums: tuple[int, ...]) -> str:
    for agent_num in agent_nums:
        text = _agent_text(context, agent_num).strip()
        if text:
            return _first_sentence(text)
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


def _position_core_assumptions(
    data: dict[str, Any],
    price_targets: dict[str, Any],
    recommendation: dict[str, Any],
) -> list[dict[str, str]]:
    target_3m = _first_mapping_value(recommendation, "3個月") or "N/A"
    target_12m = _first_mapping_value(recommendation, "12個月") or price_targets.get("基本情境", "N/A")
    return [
        {
            "assumption": "短中期風險報酬仍可接受",
            "validation": f"3 個月參考 {target_3m}，12 個月參考 {target_12m}；若報酬不足需降級或等待",
            "frequency": "每次重跑報告",
            "status": "active",
        },
        {
            "assumption": "籌碼與情緒沒有明確轉弱",
            "validation": _chip_line(data),
            "frequency": "每日或每週",
            "status": "active",
        },
        {
            "assumption": "估值區間仍能約束部位大小",
            "validation": f"熊/基/牛情境：{price_targets.get('熊市情境', 'N/A')} / {price_targets.get('基本情境', 'N/A')} / {price_targets.get('牛市情境', 'N/A')}",
            "frequency": "每次重大價格變動後",
            "status": "active",
        },
        {
            "assumption": "結論沒有和資料可信度或 final audit 警示脫鉤",
            "validation": "若出現資料降級、建議/報酬矛盾或來源衝突，先降低信心",
            "frequency": "每次資料刷新",
            "status": "active",
        },
    ]


def _position_red_lines(data: dict[str, Any], recommendation: str) -> list[dict[str, str]]:
    lines = [
        {
            "condition": "目標價隱含報酬低於該建議所需風險報酬",
            "severity": "致命",
            "action": "降級建議、降低部位或等待更佳價格",
        },
        {
            "condition": "法人籌碼由支撐轉為連續派發，且價格跌破關鍵支撐",
            "severity": "嚴重",
            "action": "停止加碼並重跑 Mode B",
        },
        {
            "condition": "估值、籌碼與總經三者互相矛盾",
            "severity": "嚴重",
            "action": "改為觀望，不把單一訊號當成交易依據",
        },
    ]
    if data.get("data_trust", {}).get("status") == "partial":
        lines.append({
            "condition": "資料可信度為 partial 且缺少官方資料補驗證",
            "severity": "警告",
            "action": "降低部位與信心，不升級建議",
        })
    if "買" in recommendation:
        lines.append({
            "condition": "股價短期急漲至牛市情境上方但基本面未同步上修",
            "severity": "警告",
            "action": "停止追價，等待回測或重新估值",
        })
    return lines


def _contrarian_core_assumptions(crash_trigger: str, stop_condition: str) -> list[dict[str, str]]:
    return [
        {
            "assumption": "泡沫敘事仍未被基本面證實",
            "validation": "追蹤營收、毛利率、Forward EPS 與估值分位是否能支撐市場期待",
            "frequency": "每次財報或月營收後",
            "status": "active",
        },
        {
            "assumption": "財務與籌碼反證仍成立",
            "validation": "追蹤 FCF 品質、法人派發、借券/融券與同業相對指標",
            "frequency": "每週",
            "status": "active",
        },
        {
            "assumption": "做空或避險必須等待可驗證觸發",
            "validation": crash_trigger or "尚未形成具體觸發，不能只因估值高就追空",
            "frequency": "事件前後",
            "status": "active",
        },
        {
            "assumption": "防軋空與 thesis invalidation 條件未被觸發",
            "validation": stop_condition or "若基本面改善、股價突破風控位或籌碼轉強，需回補或暫停空方假設",
            "frequency": "每日收盤後",
            "status": "active",
        },
    ]


def _contrarian_red_lines() -> list[dict[str, str]]:
    return [
        {
            "condition": "股價放量突破防軋空停損位或關鍵壓力",
            "severity": "致命",
            "action": "回補、停止追空並重新檢查 thesis invalidation",
        },
        {
            "condition": "財測、訂單、毛利率或現金流證實多頭敘事",
            "severity": "致命",
            "action": "撤銷泡沫假設，改跑 Mode A 或 Mode B 重新定價",
        },
        {
            "condition": "做空觸發條件遲遲未出現但股價持續創高",
            "severity": "嚴重",
            "action": "只保留觀察，不建立新的反向部位",
        },
        {
            "condition": "借券、空單成本或籌碼資料不足以支持戰術做空",
            "severity": "警告",
            "action": "降低信心，改用避開或等待觸發",
        },
    ]


def _chip_line(data: dict[str, Any]) -> str:
    institutional = data.get("institutional_trading", {}) if isinstance(data.get("institutional_trading"), dict) else {}
    trend = institutional.get("trend")
    net = institutional.get("total_net_buy_thousand_shares")
    has_net = net is not None and net != ""
    if trend or has_net:
        return f"三大法人趨勢 {trend or 'N/A'}，累計買賣超約 {net if has_net else 'N/A'} 張"
    return "籌碼資料不足，需用法人買賣超、融資券或 TDCC 補驗證"


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
